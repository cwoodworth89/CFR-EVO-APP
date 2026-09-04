# tools/eval_round1_holdout.py
"""Scores one or more Whisper models on the held-out round-1 clips.

The holdout is written by prepare_training_clips.py and is never trained on, so the WER
here is a real generalisation number rather than train-on-test. Reports stock `base` and
the fine-tuned model side by side; a fine-tune that does not beat base on this set has not
earned deployment.

Usage:
    python tools/eval_round1_holdout.py
    python tools/eval_round1_holdout.py --models base ../models/whisper-base-cfr-ct2
"""
import os
import csv
import sys
import logging
import argparse

from _repo import BACKEND  # tools/_repo.py locates the repo and puts backend/ and services/*/src on sys.path
backend_dir = str(BACKEND)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import cfr_dispatch  # noqa: F401  -- _load_env() on import


def levenshtein(a, b):
    """Edit distance between two token lists."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, tok_a in enumerate(a, 1):
        current = [i]
        for j, tok_b in enumerate(b, 1):
            current.append(min(previous[j] + 1,          # deletion
                               current[j - 1] + 1,       # insertion
                               previous[j - 1] + (tok_a != tok_b)))
        previous = current
    return previous[-1]


def normalise(text):
    """Same shape as the training labels: lowercase, no punctuation, single spaces."""
    text = text.lower()
    for ch in [".", ",", ";", ":", "?", "!", '"', "'", "-"]:
        text = text.replace(ch, " ")
    return " ".join(text.split())


def main():
    ap = argparse.ArgumentParser(description="Score models on the held-out round-1 clips.")
    ap.add_argument("--models", nargs="+",
                    default=["base", os.path.join(backend_dir, "models", "whisper-base-cfr-ct2")])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    from faster_whisper import WhisperModel

    training_dir = os.path.join(backend_dir, "data", "training")
    clips_dir = os.path.join(training_dir, "round1_clips")
    holdout_csv = os.path.join(training_dir, "metadata_round1_holdout.csv")
    if not os.path.exists(holdout_csv):
        sys.exit("No holdout found at %s. Run prepare_training_clips.py first." % holdout_csv)

    with open(holdout_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[:args.limit]
    logging.info("Scoring %d held-out clips." % len(rows))

    results = {}
    for spec in args.models:
        if not (spec in ("tiny", "base", "small") or os.path.isdir(spec)):
            logging.warning("Skipping '%s': not a known size and not a directory." % spec)
            continue
        logging.info("Loading %s ..." % spec)
        try:
            model = WhisperModel(spec, device="cpu", compute_type="int8", local_files_only=True)
        except Exception as e:
            logging.error("Could not load %s: %s" % (spec, e))
            continue

        errors = total = 0
        exact = 0
        for row in rows:
            path = os.path.join(clips_dir, row["file_name"])
            if not os.path.exists(path):
                continue
            segments, _ = model.transcribe(path, beam_size=2, language="en",
                                           condition_on_previous_text=False)
            hyp = normalise(" ".join(s.text for s in segments)).split()
            ref = normalise(row["verified_transcript"]).split()
            if not ref:
                continue
            errors += levenshtein(ref, hyp)
            total += len(ref)
            exact += (ref == hyp)
        wer = 100.0 * errors / total if total else float("nan")
        results[spec] = (wer, exact, len(rows))
        logging.info("  %-45s WER %6.2f%%   exact %d/%d" % (spec, wer, exact, len(rows)))

    print("")
    print("=" * 74)
    print("%-46s %10s %14s" % ("model", "WER", "exact match"))
    print("-" * 74)
    for spec, (wer, exact, n) in results.items():
        print("%-46s %9.2f%% %10d/%-3d" % (os.path.basename(spec.rstrip("/")) or spec, wer, exact, n))
    print("=" * 74)
    if len(results) == 2:
        (_, (a, _, _)), (_, (b, _, _)) = list(results.items())
        delta = a - b
        verdict = "IMPROVED" if delta > 0 else "REGRESSED"
        print("%s by %.2f WER points on calls the model never saw." % (verdict, abs(delta)))


if __name__ == "__main__":
    main()
