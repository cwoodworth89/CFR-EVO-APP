# backend/scripts/prepare_training_clips.py
"""Builds the Whisper fine-tuning dataset as round-1 clips paired with round-1 labels.

Design, provenance and rejected alternatives:
docs/briefings/whisper_training_round1_labelling.md

Replaces the whole-call labelling used by the 2026-07-17 run, which paired the first 30
seconds of audio (WhisperFeatureExtractor truncates there, silently) with a label covering
the entire ~48-second double-round broadcast. See docs/standards/dependency-behaviour.md.

Writes clips to backend/data/training/round1_clips/ and metadata_round1.csv -- deliberately
NOT the audio/ + metadata.csv that extract_training_data.py writes, so a whole-call dataset
and a round-1 dataset can never be confused for one another by the trainer.
"""
import os
import re
import csv
import sys
import time
import difflib
import logging
import argparse

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import cfr_dispatch                      # _load_env() on import is what sets DATABASE_URL
from cfr_dispatch.parser import split_rounds
from cfr_dispatch.config import UNITS_VOCABULARY
from extract_training_data import normalize_transcript_raw

# --- Geometry constants. Every one carries its source (CLAUDE.md s6.3). ---

# The capture loop ends a recording after 3 seconds of silence (department operational
# policy, operator 2026-08-31). Independently measured across 15 kiosk recordings the same
# day: trailing silence 3.14-3.39 s. Subtracted so the midpoint splits speech, not padding.
TRAILING_SILENCE_S = 3.0

# Whisper's encoder consumes a fixed 30.0 s window: chunk_length(30) * sampling_rate(16000)
# = 480,000 samples, verified against the installed transformers 5.14.1 on the kiosk
# 2026-08-31 (WhisperFeatureExtractor.n_samples). A round longer than this cannot be
# represented, so it is dropped rather than silently truncated.
WHISPER_WINDOW_S = 30.0

# Below this the geometry is implausible for a Coquitlam dispatch round -- it indicates a
# bad cut or a partial capture, not a genuinely short call. Shortest round measured across
# the 40-call sample was 12.2 s.
MIN_ROUND_S = 8.0

# The first spoken word of a dispatch is always "Coquitlam" (operator, 15-year SME,
# 2026-08-31; 40 of 40 flagged calls sampled). Fuzzy so STT variants pass -- "COQUITLUM"
# was observed and is the same word.
WAKE_WORD = "coquitlam"
WAKE_WORD_MIN_RATIO = 0.7

# "Contact dispatch via radio for location information" is spoken AFTER the second round,
# on calls with no addressable location (both instances found were Eagle Mountain Park).
# It is the only addendum dispatch appends (operator, 2026-09-01), and it breaks the
# geometry below: the cut halves total speech assuming exactly two rounds, so a ~5 s tail
# pushes the midpoint into round 2 and the clip ends up holding words its label does not.
# Operator ruling 2026-09-01: exclude these rather than special-case the formula.
# Matched against verified_transcript, which is operator-written and so free of STT noise --
# all 3 corpus instances carry the phrase verbatim. \s+ because the operator's punctuation
# varies (docs/standards/dependency-behaviour.md: a space-separated pattern undercounts).
ADDENDUM_PATTERN = r"contact\s+dispatch"

SAMPLE_RATE = 16000


def first_spoken_word(model, audio, sample_rate, look_ahead_s):
    """Returns (first_word, all_words) from the head of the recording."""
    segments, _ = model.transcribe(
        audio[:int(sample_rate * look_ahead_s)],
        beam_size=1, language="en",
        word_timestamps=True, condition_on_previous_text=False,
    )
    words = []
    for seg in segments:
        words.extend(seg.words or [])
    return (words[0] if words else None), words


def main():
    ap = argparse.ArgumentParser(description="Build round-1 Whisper training clips.")
    ap.add_argument("--limit", type=int, default=0, help="process at most N calls (0 = all)")
    ap.add_argument("--force", action="store_true", help="rewrite clips that already exist")
    ap.add_argument("--model", default="base", help="model used only to locate the onset")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    import librosa
    import soundfile as sf
    from sqlalchemy import create_engine, text
    from faster_whisper import WhisperModel

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL is not set. It lives in backend/.env on the kiosk and is "
                 "loaded by importing cfr_dispatch; see docs/agent_onboarding.md.")

    training_dir = os.path.join(backend_dir, "data", "training")
    clips_dir = os.path.join(training_dir, "round1_clips")
    recordings_dir = os.path.join(backend_dir, "audio_files", "recordings")
    os.makedirs(clips_dir, exist_ok=True)

    rows = create_engine(db_url).connect().execute(text(
        "SELECT dispatch_id, audio_duration, verified_transcript FROM public.dispatches "
        "WHERE feedback_submitted AND verified_transcript IS NOT NULL "
        "AND btrim(verified_transcript) <> :empty "
        "AND COALESCE((target->>:flag)::boolean, TRUE) "
        "ORDER BY dispatch_id"), {"empty": "", "flag": "include_in_training"}).fetchall()
    if args.limit:
        rows = rows[:args.limit]
    logging.info("%d calls flagged for training." % len(rows))

    logging.info("Loading '%s' to locate speech onset..." % args.model)
    model = WhisperModel(args.model, device="cpu", compute_type="int8", local_files_only=True)

    kept, dropped, ratios = [], {}, []

    def drop(reason, did, detail=""):
        dropped.setdefault(reason, []).append(("%s %s" % (did, detail)).strip())

    started = time.time()
    for i, (did, db_duration, verified) in enumerate(rows, 1):
        if i % 25 == 0:
            rate = (time.time() - started) / i
            logging.info("  %d/%d  kept=%d  ~%.1fs/call  eta %.0f min"
                         % (i, len(rows), len(kept), rate, (len(rows) - i) * rate / 60))

        wav = os.path.join(recordings_dir, "%s.wav" % did)
        out = os.path.join(clips_dir, "%s.wav" % did)
        if not os.path.exists(wav):
            drop("no audio file", did)
            continue

        if re.search(ADDENDUM_PATTERN, verified or "", re.IGNORECASE):
            drop("has a post-round addendum", did)
            continue

        # The label is round 1 of what the operator verified. split_rounds is text-only and
        # reliable; it is the onset that needed measuring, not the round boundary in text.
        rounds = split_rounds(verified, UNITS_VOCABULARY)
        label = normalize_transcript_raw(rounds[0])
        if not label:
            drop("empty label", did)
            continue

        audio, sr = librosa.load(wav, sr=SAMPLE_RATE)
        duration = len(audio) / sr

        # Look far enough ahead to cover onset plus a whole round, so the word list can also
        # serve the audio-vs-label word-count diagnostic below without a second pass.
        w0, words = first_spoken_word(model, audio, sr, min(duration, 40.0))
        if w0 is None:
            drop("no words transcribed", did, "%.1fs" % duration)
            continue

        first = w0.word.strip().lower().strip(".,!?")
        if difflib.SequenceMatcher(None, first, WAKE_WORD).ratio() < WAKE_WORD_MIN_RATIO:
            drop("does not open with Coquitlam", did, "heard %s" % w0.word.strip()[:20])
            continue

        onset = w0.start
        round_len = (duration - TRAILING_SILENCE_S - onset) / 2.0
        if round_len > WHISPER_WINDOW_S:
            drop("round exceeds the 30s window", did, "%.1fs" % round_len)
            continue
        if round_len < MIN_ROUND_S:
            drop("round implausibly short", did, "%.1fs" % round_len)
            continue

        if not (os.path.exists(out) and not args.force):
            clip = audio[int(onset * sr):int((onset + round_len) * sr)]
            sf.write(out, clip, sr, subtype="PCM_16")
        kept.append({"file_name": "%s.wav" % did, "verified_transcript": label})

        # Diagnostic only, never a drop rule: how many words the audio actually contains up
        # to the cut, against how many the label claims. A systematically bad cut shows here
        # as a skewed ratio. Content mismatch is NOT used -- dropping calls the base model
        # transcribes poorly would bias the set toward what it already gets right.
        heard = sum(1 for w in words if w.start < onset + round_len)
        claimed = len(label.split())
        if claimed:
            ratios.append(float(heard) / claimed)

    def write_csv(path, rows_out):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["file_name", "verified_transcript"])
            writer.writeheader()
            writer.writerows(rows_out)

    meta = os.path.join(training_dir, "metadata_round1.csv")
    write_csv(meta, kept)

    # A held-out split, so the resulting model can be scored on calls it never saw.
    # Without this the only available number is train-on-test, which is what makes the
    # 2026-07-17 "22.6% -> 3.5% WER" untrustworthy (CLAUDE.md s6.6: an unknown reported as
    # a number is a defect). Deterministic -- every 10th call by sorted dispatch_id -- so
    # a re-run scores against the same holdout and the comparison stays honest.
    holdout = kept[::10]
    train = [r for r in kept if r not in holdout]
    write_csv(os.path.join(training_dir, "metadata_round1_train.csv"), train)
    write_csv(os.path.join(training_dir, "metadata_round1_holdout.csv"), holdout)
    logging.info("split: %d train / %d holdout" % (len(train), len(holdout)))

    logging.info("=" * 70)
    logging.info("KEPT %d of %d flagged calls -> %s" % (len(kept), len(rows), meta))
    for reason, ids in sorted(dropped.items(), key=lambda kv: -len(kv[1])):
        logging.info("  dropped %3d  %s" % (len(ids), reason))
        for one in ids[:5]:
            logging.info("               %s" % one)
        if len(ids) > 5:
            logging.info("               ... and %d more" % (len(ids) - 5))
    if ratios:
        ratios.sort()
        mid = ratios[len(ratios) // 2]
        lo = sum(1 for r in ratios if r < 0.6)
        hi = sum(1 for r in ratios if r > 1.6)
        logging.info("  cut diagnostic: heard/claimed words median %.2f "
                     "(%d below 0.6, %d above 1.6, of %d)" % (mid, lo, hi, len(ratios)))


if __name__ == "__main__":
    main()
