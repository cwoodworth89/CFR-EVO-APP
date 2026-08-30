#!/usr/bin/env python3
"""
backfill_tone_spectra.py
========================
Reconstructs tone peak data from ARCHIVED dispatch recordings.

Why this exists (punch-list #14): `tone_spectral_history.jsonl` is written by the
live listener at detection time, so it only grows when new calls arrive. On
2026-08-29 it held 55 Engine and 41 Rescue events but only **3** Chief -- far too
thin to judge the Chief fingerprint against. Tagging historical records in the
review panel does not help: the tagging lives in the database, the spectra do not.

But the audio is archived. Re-running the SAME analyzer the listener uses over the
stored recordings reconstructs the peak data that would have been logged, turning
3 Chief samples into as many as 20 without waiting for more calls.

READ-ONLY. Touches no live path, writes only its own output file.

## One deliberate difference from the live path

The listener analyses a fixed 3.5 s window starting when the trigger fires. A saved
recording includes the pre-trigger history buffer, so the tone is NOT at t=0 and a
fixed window would often miss it.

This script therefore SLIDES a 3.5 s window across the opening of the file and keeps
the window that best matches any known fingerprint. That is a different selection
rule, so a backfilled spectrum is not bit-identical to a live one -- it is the best
tone-bearing window rather than the first. Recorded here rather than glossed over,
because it means backfilled and live rows are not quite the same measurement.

## Usage

    python backend/scripts/backfill_tone_spectra.py                  # all recordings
    python backend/scripts/backfill_tone_spectra.py --tone chief     # only chief-tagged
    python backend/scripts/backfill_tone_spectra.py --limit 20

Output: backend/data/tone_spectra_backfill.jsonl (does NOT touch the live history).
"""
import os
import sys
import json
import wave
import glob
import argparse
import logging

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "services", "audio_analysis", "src"))
sys.path.insert(0, BACKEND_DIR)

from audio_service.dsp_tone_spotter import (  # noqa: E402
    analyze_live_audio, get_all_matches, has_pa_marker, is_mains_hum,
)
from cfr_dispatch.config.dsp import (  # noqa: E402
    GOLDEN_FINGERPRINTS, FREQUENCY_TOLERANCE_HZ, MATCH_THRESHOLD_PERCENT,
    NUM_PEAKS_TO_FIND, TONE_ZSCORE_THRESHOLD, TONE_ANALYSIS_DURATION_SECONDS,
    PA_DISCRIMINATOR_HZ, MAINS_HUM_FUNDAMENTAL_HZ, MAINS_HUM_TOLERANCE_HZ,
    MAINS_HUM_MIN_PEAKS,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill")

RECORDINGS_DIR = os.path.join(BACKEND_DIR, "audio_files", "recordings")
OUT_PATH = os.path.join(BACKEND_DIR, "data", "tone_spectra_backfill.jsonl")

# How far into the recording to look for the tone. Tones open a dispatch; scanning
# the whole file would waste time and risk matching mid-call audio.
SEARCH_SECONDS = 20.0
HOP_SECONDS = 0.25


def read_wav_mono16(path):
    """Return (samples int16, sample_rate) or (None, None) if unreadable."""
    try:
        with wave.open(path, "rb") as w:
            rate = w.getframerate()
            n_ch = w.getnchannels()
            width = w.getsampwidth()
            frames = w.readframes(w.getnframes())
        if width != 2:
            return None, None
        data = np.frombuffer(frames, dtype=np.int16)
        if n_ch > 1:
            data = data[::n_ch]
        return data, rate
    except Exception:
        return None, None


def best_tone_window(samples, rate):
    """Slide a tone-analysis window and return the best-matching one.

    'Best' = highest total fingerprint match score. Ties keep the earliest window,
    which is the one the live listener would have seen.
    """
    win = int(TONE_ANALYSIS_DURATION_SECONDS * rate)
    hop = max(1, int(HOP_SECONDS * rate))
    limit = min(len(samples), int(SEARCH_SECONDS * rate))
    if len(samples) < win:
        return None

    best = None
    for start in range(0, max(1, limit - win + 1), hop):
        chunk = samples[start:start + win]
        if len(chunk) < win:
            break
        freqs = analyze_live_audio(chunk.tobytes(), rate,
                                   NUM_PEAKS_TO_FIND, TONE_ZSCORE_THRESHOLD)
        if not freqs:
            continue
        matches = get_all_matches(freqs, GOLDEN_FINGERPRINTS,
                                  FREQUENCY_TOLERANCE_HZ, MATCH_THRESHOLD_PERCENT)
        score = sum(m[1] for m in matches)
        if best is None or score > best["score"]:
            best = {
                "score": score,
                "offset_s": round(start / rate, 2),
                "frequencies": sorted(freqs),
                "matched_tones": [m[0] for m in matches],
            }
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tone", default=None,
                    help="Only recordings whose stored tone_name contains this "
                         "(e.g. 'chief'). Requires --meta.")
    ap.add_argument("--meta", default=None,
                    help="JSON file of [{dispatch_id, tone_name, review_notes}] "
                         "to filter and annotate by.")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    meta = {}
    if args.meta:
        with open(args.meta, "r", encoding="utf-8") as fh:
            for row in json.load(fh):
                meta[row["dispatch_id"]] = row

    files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "*.wav")))
    if args.tone:
        if not meta:
            logger.error("--tone requires --meta")
            return 2
        files = [f for f in files
                 if args.tone.lower() in
                 (meta.get(os.path.basename(f)[:-4], {}).get("tone_name") or "").lower()]
    if args.limit:
        files = files[:args.limit]

    logger.info(f"Analyzing {len(files)} recordings "
                f"(window {TONE_ANALYSIS_DURATION_SECONDS}s, hop {HOP_SECONDS}s, "
                f"first {SEARCH_SECONDS}s)")

    written = skipped = 0
    with open(args.out, "w", encoding="utf-8") as out:
        for i, path in enumerate(files, 1):
            did = os.path.basename(path)[:-4]
            samples, rate = read_wav_mono16(path)
            if samples is None:
                skipped += 1
                logger.warning(f"  [{i}/{len(files)}] {did}: unreadable, skipped")
                continue
            best = best_tone_window(samples, rate)
            if best is None:
                skipped += 1
                logger.warning(f"  [{i}/{len(files)}] {did}: no analyzable window")
                continue
            m = meta.get(did, {})
            rec = {
                "dispatch_id": did,
                "source": "backfill",
                "sample_rate": rate,
                "window_offset_s": best["offset_s"],
                "matched_tones": best["matched_tones"],
                "all_detected_frequencies_hz": best["frequencies"],
                "stored_tone_name": m.get("tone_name"),
                "review_notes": m.get("review_notes"),
                "has_pa_marker": has_pa_marker(best["frequencies"],
                                               PA_DISCRIMINATOR_HZ,
                                               FREQUENCY_TOLERANCE_HZ),
                "is_mains_hum": is_mains_hum(best["frequencies"],
                                             MAINS_HUM_FUNDAMENTAL_HZ,
                                             MAINS_HUM_TOLERANCE_HZ,
                                             MAINS_HUM_MIN_PEAKS),
            }
            out.write(json.dumps(rec) + "\n")
            written += 1
            if i % 25 == 0:
                logger.info(f"  ... {i}/{len(files)}")

    logger.info(f"Wrote {written} rows to {args.out} ({skipped} skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
