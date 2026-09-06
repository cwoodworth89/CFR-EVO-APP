#!/usr/bin/env python3
"""Builds the round-2 Whisper training set: round-1 clips, the calls verified since, a second
holdout, and truncated pairs so the model learns that a transcript ends where the audio ends.

Why truncated pairs
-------------------
All 508 verified transcripts end in "... map grid N". A model fine-tuned on nothing else finishes
any cut chunk with that tail: on 448 recordings replayed in the listener's own chunks, the grid
in the chunk that trips phase 1's completion check was the model's completion on 314 (punch
list #72, 2026-09-05). The pipeline works around it (the parcel's zone as the grid). This is the
model-side fix: pairs whose audio stops at 10, 16 or 22 s into round 1, the times phase 1
transcribes at, labelled with the words spoken before the cut and nothing after.

The assumption, stated before it is built on: training on such pairs makes the model stop at
the end of the audio. The measurement that falsifies it: `tools/harness_phase1.py` on the new
model, counting chunks whose parsed grid was not yet spoken. If that number does not fall from
314 of 448, the augmentation did not take.

What it writes (backend/data/training/)
---------------------------------------
  round2_clips/                   round-1 train clips copied in, the new calls cut the same
                                  way, and the truncated clips as <id>_t10.wav, _t16, _t22
  metadata_round2_train.csv       full clips and truncated pairs (file_name, verified_transcript)
  metadata_round2_holdout.csv     50 full clips drawn at random (seed 2026) from everything
                                  round 1 did not hold out; never truncated, never trained on
The round-1 holdout (metadata_round1_holdout.csv) is left exactly as it is, never trained on,
so every number recorded against it today stays comparable.

Alignment
---------
The truncated label needs to know when each label word was spoken. The model in service
transcribes the clip with word timestamps, its words are matched to the verified label with a
sequence match on normalised text, and a cut is labelled with the label words up to the last
matched word that ENDS before the cut. A word the cut lands on is left out: phase 1's chunks
split words too, and the point is that the label claims nothing the audio does not carry. A
clip whose label matched under 80 % is used whole and gets no truncated pairs.

Runs on the kiosk: the recordings, the model and the database are there. `--limit 3` first.
"""
import argparse
import csv
import difflib
import logging
import os
import random
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _repo import BACKEND  # noqa: E402
sys.path.insert(0, str(BACKEND))
import cfr_dispatch  # noqa: E402,F401
from cfr_dispatch.config import UNITS_VOCABULARY  # noqa: E402
from cfr_dispatch.parser import split_rounds  # noqa: E402
from extract_training_data import normalize_transcript_raw  # noqa: E402  the label normaliser round 1 used
import prepare_training_clips as r1  # noqa: E402  the round-1 cut, reused not copied

CUT_TIMES_S = (10.0, 16.0, 22.0)   # phase 1's first check and two later ones (sound_capture.py)
HOLDOUT2_SIZE = 50
HOLDOUT2_SEED = 2026
MIN_ALIGNMENT = 0.80
MIN_TRUNCATED_WORDS = 4
WORD_END_MARGIN_S = 0.10           # a word must have ended this long before the cut to be claimed


def norm_word(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (w or "").lower())


def align(label_words, heard):
    """Map label word index -> (start, end) of the heard word it matched, on matched blocks only."""
    a = [norm_word(w) for w in label_words]
    b = [norm_word(w.word) for w in heard]
    times = {}
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = (heard[blk.b + k].start, heard[blk.b + k].end)
    return times


def read_csv(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file_name", "verified_transcript"])
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=0, help="truncate at most N train clips (0 = all); a smoke test")
    ap.add_argument("--model", default=os.path.join(str(BACKEND), "models", "whisper-base-cfr-ct2"),
                    help="model for word timestamps (the one in service: its words match the labels best)")
    ap.add_argument("--onset-model", default="base", help="model the round-1 builder used to cut new calls")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    import librosa
    import soundfile as sf
    from sqlalchemy import create_engine, text
    from faster_whisper import WhisperModel

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL is not set (backend/.env on the kiosk, loaded by importing cfr_dispatch).")
    training = os.path.join(str(BACKEND), "data", "training")
    r1_clips = os.path.join(training, "round1_clips")
    r2_clips = os.path.join(training, "round2_clips")
    os.makedirs(r2_clips, exist_ok=True)
    recordings = os.path.join(str(BACKEND), "audio_files", "recordings")

    r1_train = read_csv(os.path.join(training, "metadata_round1_train.csv"))
    r1_hold = read_csv(os.path.join(training, "metadata_round1_holdout.csv"))
    seen = {r["file_name"] for r in r1_train} | {r["file_name"] for r in r1_hold}
    logging.info("round 1: %d train, %d holdout (kept aside, unchanged)", len(r1_train), len(r1_hold))

    # ---- 1. the calls verified since round 1, cut exactly as round 1 cut its clips -----------
    engine = create_engine(db_url)
    rows = engine.connect().execute(text(
        "SELECT dispatch_id, verified_transcript FROM public.dispatches "
        "WHERE feedback_submitted AND verified_transcript IS NOT NULL AND btrim(verified_transcript) <> '' "
        "AND COALESCE((target->>'include_in_training')::boolean, TRUE) "
        "AND position('[PA]' in coalesce(target->>'review_notes', '')) = 0 ORDER BY dispatch_id")).fetchall()
    new_rows = [(d, v) for d, v in rows if f"{d}.wav" not in seen]
    logging.info("%d calls eligible now, %d not in round 1", len(rows), len(new_rows))
    onset_model = WhisperModel(args.onset_model, device="cpu", compute_type="int8", local_files_only=True)
    new_kept, dropped = [], {}
    for did, verified in new_rows:
        wav = os.path.join(recordings, f"{did}.wav")
        if not os.path.exists(wav):
            dropped.setdefault("no audio file", []).append(did); continue
        if re.search(r1.ADDENDUM_PATTERN, verified or "", re.IGNORECASE):
            dropped.setdefault("has a post-round addendum", []).append(did); continue
        rounds = split_rounds(verified, UNITS_VOCABULARY)
        label = normalize_transcript_raw(rounds[0]) if rounds else ""
        if not label:
            dropped.setdefault("empty label", []).append(did); continue
        audio, sr = librosa.load(wav, sr=r1.SAMPLE_RATE)
        duration = len(audio) / sr
        words = r1.timestamped_words(onset_model, audio, sr, min(duration, 45.0))
        if not words:
            dropped.setdefault("no words transcribed", []).append(did); continue
        first = words[0].word.strip().lower().strip(".,!?")
        if difflib.SequenceMatcher(None, first, r1.WAKE_WORD).ratio() < r1.WAKE_WORD_MIN_RATIO:
            dropped.setdefault("does not open with Coquitlam", []).append(did); continue
        onset = words[0].start
        boundary = r1.round_boundary_time(words, UNITS_VOCABULARY)
        if boundary is None:
            dropped.setdefault("rounds not separable in the audio", []).append(did); continue
        round_len = boundary - onset
        if round_len > r1.WHISPER_WINDOW_S:
            dropped.setdefault("round exceeds the 30s window", []).append(did); continue
        if round_len < r1.MIN_ROUND_S:
            dropped.setdefault("round implausibly short", []).append(did); continue
        sf.write(os.path.join(r2_clips, f"{did}.wav"), audio[int(onset * sr):int(boundary * sr)], sr, subtype="PCM_16")
        new_kept.append({"file_name": f"{did}.wav", "verified_transcript": label})
    logging.info("new calls: %d cut, %d dropped %s", len(new_kept), sum(len(v) for v in dropped.values()),
                 {k: len(v) for k, v in dropped.items()})

    # ---- 2. the pool, and the second holdout -------------------------------------------------
    for r in r1_train:
        src, dst = os.path.join(r1_clips, r["file_name"]), os.path.join(r2_clips, r["file_name"])
        if not os.path.exists(dst):
            shutil.copyfile(src, dst)
    pool = sorted(r1_train + new_kept, key=lambda r: r["file_name"])
    rng = random.Random(HOLDOUT2_SEED)
    hold2 = sorted(rng.sample(pool, min(HOLDOUT2_SIZE, len(pool))), key=lambda r: r["file_name"])
    hold2_names = {r["file_name"] for r in hold2}
    train_full = [r for r in pool if r["file_name"] not in hold2_names]
    logging.info("pool %d -> round-2 holdout %d, train (full clips) %d", len(pool), len(hold2), len(train_full))

    # ---- 3. truncated pairs -------------------------------------------------------------------
    model = WhisperModel(args.model, device="cpu", compute_type="int8", local_files_only=True)
    truncated, no_align, coverage = [], 0, []
    todo = train_full[: args.limit] if args.limit else train_full
    started = time.time()
    for i, r in enumerate(todo, 1):
        if i % 25 == 0:
            rate = (time.time() - started) / i
            logging.info("  truncating %d/%d  pairs=%d  eta %.0f min", i, len(todo), len(truncated), (len(todo) - i) * rate / 60)
        path = os.path.join(r2_clips, r["file_name"])
        audio, sr = librosa.load(path, sr=r1.SAMPLE_RATE)
        clip_len = len(audio) / sr
        label_words = r["verified_transcript"].split()
        segments, _ = model.transcribe(audio, beam_size=1, language="en", word_timestamps=True,
                                       condition_on_previous_text=False)
        heard = [w for seg in segments for w in (seg.words or [])]
        times = align(label_words, heard)
        cov = len(times) / max(1, len(label_words))
        coverage.append(cov)
        if cov < MIN_ALIGNMENT:
            no_align += 1
            continue
        stem = r["file_name"][:-4]
        for t in CUT_TIMES_S:
            if t >= clip_len - 2.0:
                continue
            last = max((k for k, (s, e) in times.items() if e <= t - WORD_END_MARGIN_S), default=-1)
            if last + 1 < MIN_TRUNCATED_WORDS:
                continue
            name = f"{stem}_t{int(t)}.wav"
            sf.write(os.path.join(r2_clips, name), audio[: int(t * sr)], sr, subtype="PCM_16")
            truncated.append({"file_name": name, "verified_transcript": " ".join(label_words[: last + 1])})
    logging.info("truncated pairs: %d from %d clips (%d clips below %.0f%% alignment, skipped); "
                 "alignment median %.2f", len(truncated), len(todo) - no_align, no_align,
                 MIN_ALIGNMENT * 100, sorted(coverage)[len(coverage) // 2] if coverage else 0)

    # ---- 4. write --------------------------------------------------------------------------------
    write_csv(os.path.join(training, "metadata_round2_train.csv"), train_full + truncated)
    write_csv(os.path.join(training, "metadata_round2_holdout.csv"), hold2)
    print(f"\nround 2: train {len(train_full)} full + {len(truncated)} truncated = {len(train_full) + len(truncated)} rows; "
          f"holdout-2 {len(hold2)}; round-1 holdout {len(r1_hold)} untouched")
    print(f"clips in {r2_clips}; metadata_round2_train.csv / metadata_round2_holdout.csv in {training}")
    if dropped:
        print("new calls dropped:", {k: v[:5] for k, v in dropped.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
