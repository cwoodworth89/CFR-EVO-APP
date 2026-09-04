#!/usr/bin/env python3
"""Score cross-round disagreement as a warning signal, against the rated corpus.

Why this exists
---------------
The confidence score is being removed (punch-list #54, operator ruling 2026-08-30) and
warnings move to the amber banner / flag model. Before any flag is shown to crews, it has
to be shown to be worth showing: a flag that fires on most calls is noise, and a flag that
fires on the wrong calls is worse than none.

`public.dispatches` already holds the answer. Every row has `raw_transcript`, and the rated
rows carry the operator's own `quality_rating` and `verified_address`. Replaying the stored
transcript through the current parser and comparator scores the signal against real
outcomes rather than against an assumption.

This is read-only. Nothing is INSERTed, UPDATEd, or published, and no dispatch is
synthesised (CLAUDE.md §6.5) -- every row replayed is a real historical record.

What it can and cannot measure
------------------------------
It compares **Phase 2 round 1 against Phase 2 round 2**, because those are the two
observations recoverable from a stored transcript. Phase 1's own parse lives in ephemeral
session state and is not in the database, so the P1-vs-P2 pairing cannot be backtested
here -- which matters little, since that pairing is the same audio through the same model
and agrees largely by construction (see `round_comparison` module docstring).

Two caveats on reading the output:

* **The rated subset is not a random sample.** The operator reviews what the operator
  reviews. Rates are comparable *between the flagged and unflagged buckets* within this
  corpus; they are not an estimate of a citywide rate.
* **Replay uses today's parser**, not the parser that ran at the time. That is the point --
  it scores the signal as it would behave now -- but it means the numbers do not describe
  what the operator actually saw historically.

Usage
-----
    python tools/backtest_round_comparison.py
    python tools/backtest_round_comparison.py --csv /tmp/rounds.csv
    python tools/backtest_round_comparison.py --show-disagreements 20
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import defaultdict

import _repo  # noqa: F401  tools/_repo.py puts backend/ and services/*/src on sys.path

from sqlalchemy import create_engine, text  # noqa: E402

from cfr_dispatch.parser import sanitize_transcript, split_rounds, parse_dispatch_announcement  # noqa: E402
from cfr_dispatch.config.vocab import UNITS_VOCABULARY  # noqa: E402
from cfr_dispatch.pipeline.round_comparison import (  # noqa: E402
    AGREE, DISAGREE, SINGLE, ABSENT,
    compare_observations, observations_from_rounds, normalize_location_text,
)

RATED = ("PERFECT", "OPERATIONAL", "FAILED")


def load_rows(engine):
    with engine.connect() as conn:
        return conn.execute(text("""
            SELECT dispatch_id, timestamp, raw_transcript, quality_rating,
                   verified_address, target->>'address' AS system_address
            FROM public.dispatches
            WHERE raw_transcript IS NOT NULL AND length(raw_transcript) > 40
            ORDER BY timestamp
        """)).mappings().all()


def replay(row):
    """Re-derive the per-round observations for one stored dispatch."""
    try:
        rounds = split_rounds(sanitize_transcript(row["raw_transcript"]), UNITS_VOCABULARY)
    except Exception:
        return None, 0
    per_round = []
    for chunk in rounds:
        if len(chunk.split()) <= 2:
            per_round.append([])
            continue
        try:
            per_round.append(parse_dispatch_announcement(chunk, UNITS_VOCABULARY))
        except Exception:
            per_round.append([])
    # Phase 1's observation is not recoverable from the database -- see the module
    # docstring. Passing None keeps the source list honest rather than inventing one.
    return compare_observations(observations_from_rounds(None, per_round)), len(rounds)


def pct(n, d):
    return (100.0 * n / d) if d else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="write per-dispatch results here")
    ap.add_argument("--show-disagreements", type=int, default=10,
                    help="print this many address disagreements verbatim")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL is not set. Without it this scores nothing and exits, "
                 "rather than reporting an empty corpus as a clean result.")

    rows = load_rows(create_engine(db_url))

    # per field -> verdict -> {n, rated, failed, verified, corrected}
    tally = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    single_round = 0
    examples = []
    csv_rows = []

    for row in rows:
        comparison, n_rounds = replay(row)
        if comparison is None:
            continue
        if n_rounds < 2:
            single_round += 1

        rating = row["quality_rating"]
        is_rated = rating in RATED
        has_verified = bool(row["verified_address"])
        corrected = has_verified and (
            normalize_location_text(row["verified_address"])
            != normalize_location_text(row["system_address"]))

        for name, fc in comparison.fields.items():
            b = tally[name][fc.verdict]
            b["n"] += 1
            b["rated"] += 1 if is_rated else 0
            b["failed"] += 1 if rating == "FAILED" else 0
            b["verified"] += 1 if has_verified else 0
            b["corrected"] += 1 if corrected else 0

        addr = comparison.fields["address"]
        if addr.verdict == DISAGREE and len(examples) < args.show_disagreements:
            vals = list(addr.values.items())
            examples.append((row["dispatch_id"], vals, rating,
                             row["verified_address"] or ""))

        if args.csv:
            csv_rows.append({
                "dispatch_id": row["dispatch_id"],
                "rounds": n_rounds,
                "quality_rating": rating or "",
                "corrected": corrected,
                **{f"{k}_verdict": v.verdict for k, v in comparison.fields.items()},
            })

    print(f"corpus: {len(rows)} dispatches with a stored transcript "
          f"({single_round} produced only one round, so cannot be cross-checked)\n")

    header = (f"{'field':<15}{'verdict':<10}{'n':>6}{'rated':>7}{'FAILED':>8}"
              f"{'FAILED%':>9}{'verified':>10}{'corr%':>8}")
    print(header)
    print("-" * len(header))
    for name in tally:
        for verdict in (DISAGREE, AGREE, SINGLE, ABSENT):
            b = tally[name].get(verdict)
            if not b or not b["n"]:
                continue
            print(f"{name:<15}{verdict:<10}{b['n']:>6}{b['rated']:>7}{b['failed']:>8}"
                  f"{pct(b['failed'], b['rated']):>8.1f}%{b['verified']:>10}"
                  f"{pct(b['corrected'], b['verified']):>7.1f}%")
        print()

    if examples:
        print("Address disagreements, verbatim (the module reports both; it picks neither):")
        for did, vals, rating, verified in examples:
            shown = "  |  ".join(f"{s}={v}" for s, v in vals)
            print(f"  {did}  {shown}")
            print(f"{'':>21}rating={rating or '-'}  operator={verified or '-'}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            if csv_rows:
                w = csv.DictWriter(fh, fieldnames=list(csv_rows[0].keys()))
                w.writeheader()
                w.writerows(csv_rows)
        print(f"\nwrote {len(csv_rows)} rows to {args.csv}")


if __name__ == "__main__":
    main()
