#!/usr/bin/env python3
"""The harness runs recorded in public.evaluation_history, oldest first: is the system
improving over time?

    .venv/bin/python tools/harness_history.py
    .venv/bin/python tools/harness_history.py --stage chain --last 10

Each row is one `--record` run of a harness (see tools/harness_common.py): the stage it
measured, the code it ran (git hash), the model, the slice of the corpus, and the harness's
one-line headline. Rows from before 2026-09-05 are backtest_regression.py runs and carry only
a WER. Compare like with like: the same stage, the same --since/--until, the same --skip-stt.
"""
from __future__ import annotations

import argparse
import sys

from _repo import BACKEND  # noqa: F401
import harness_common as hc  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stage", help="only this stage: stt, parser, geocoder, chain, chain-no-stt")
    ap.add_argument("--last", type=int, help="only the most recent N rows")
    args = ap.parse_args()

    where, params = [], {}
    if args.stage:
        where.append("stage = :stage")
        params["stage"] = args.stage
    sql = ("SELECT created_at, stage, git_hash, model_version, total_samples, wer, "
           "period_start, period_end, metrics->>'headline' AS headline, notes "
           "FROM public.evaluation_history"
           + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY created_at")
    engine = create_engine(hc.database_url())
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    engine.dispose()
    if args.last:
        rows = rows[-args.last:]
    if not rows:
        print("no runs recorded")
        return 0

    print(f"{'when':<17}{'stage':<13}{'git':<9}{'model':<24}{'n':>5}  {'period':<23} result")
    for r in rows:
        when = r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else "?"
        period = (f"{r['period_start']}..{r['period_end']}" if r["period_start"] else "")
        result = r["headline"] or (f"wer {r['wer']}%" if r["wer"] is not None else "")
        print(f"{when:<17}{(r['stage'] or ''):<13}{(r['git_hash'] or ''):<9}"
              f"{(r['model_version'] or '')[:23]:<24}{r['total_samples']:>5}  {period:<23} {result}")
        if r["notes"]:
            print(f"{'':<17}note: {r['notes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
