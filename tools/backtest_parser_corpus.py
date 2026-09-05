# tools/backtest_parser_corpus.py
"""Replay verified dispatches through the CURRENT parser and score each field against
human ground truth.

The parser-side counterpart to `trace_geocode_corpus.py`. That one replays the geocoder and
asks "does an address round-trip"; this one replays the parser and asks "did we extract the
right values out of what the radio actually said".

    raw_transcript -> parser -> {incident, units, map_grid, talkgroup, address}
                                        |
                                        v  compared against
                      verified_incident / verified_units /
                      verified_map_grid / verified_talkgroup / verified_address

Read-only. Replays real historical records only -- never synthesises a dispatch
(CLAUDE.md §6.5).

WHY THIS EXISTS
---------------
Every accuracy figure quoted during the 2026-08-23 parser audit came from throwaway scripts,
and three of them were wrong in the same way: a rate pooled over the whole corpus mixes
already-fixed defects with live ones. The corpus spans a period of active fixes, so
**--by-month is the default reading**, not an extra. See `docs/qa_harnesses.md`.

Two other traps this encodes so they are not re-derived:

  * **Per-field denominators differ.** `verified_map_grid` exists on ~150 calls and
    `verified_incident` on ~305. Dividing every field by the same n understated the map-grid
    error rate as 9.4% when it was 12.7%.
  * **Cosmetic diffs are not errors.** "Ave"/"Avenue", trailing unit numbers and intersection
    leg order made the address error rate read 30.2% when the real figure was 16.8%. Address
    scoring here buckets EXACT / COSMETIC / WRONG.

USAGE
-----
    # headline numbers, split by month (the honest default)
    python tools/backtest_parser_corpus.py

    # everything pooled -- only for a corpus you know is homogeneous
    python tools/backtest_parser_corpus.py --pooled

    # one call, showing every field and both rounds
    python tools/backtest_parser_corpus.py --dispatch-id DISP-2026-A19179

    # per-call rows for spreadsheet triage
    python tools/backtest_parser_corpus.py --csv /tmp/parser_corpus.csv

    # before/after a change: run, stash the json, change code, run again, diff
    python tools/backtest_parser_corpus.py --json /tmp/before.json
    python tools/backtest_parser_corpus.py --baseline /tmp/before.json

Requires DATABASE_URL (see CLAUDE.md §3 -- without it the kiosk database is unreachable and
this refuses to run rather than silently scoring nothing).
"""
import argparse
import collections
import csv
import json
import os
import re
import sys

import psycopg2

from _repo import BACKEND  # tools/_repo.py locates the repo and puts backend/ on sys.path
import harness_common as hc  # noqa: E402
_BACKEND = str(BACKEND)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from cfr_dispatch.config import CALL_TYPES, UNITS_VOCABULARY  # noqa: E402
from cfr_dispatch.parser import (  # noqa: E402
    sanitize_transcript,
    split_rounds,
    parse_dispatch_announcement,
)
from cfr_dispatch.parser.call_types import match_incident_type  # noqa: E402

# Street suffix equivalences for cosmetic-diff detection. Reviewers expand suffixes the
# parser abbreviates; neither is wrong.
_SUFFIX = {
    "ave": "avenue", "st": "street", "rd": "road", "dr": "drive", "blvd": "boulevard",
    "cres": "crescent", "pl": "place", "crt": "court", "ct": "court", "ln": "lane",
    "hwy": "highway", "pkwy": "parkway", "way": "way", "grn": "green", "gr": "green",
    "sq": "square", "trl": "trail", "ter": "terrace",
}

FIELDS = ["incident", "units", "map_grid", "talkgroup", "address"]


# --------------------------------------------------------------------------- normalisation
def _words(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower())).strip()


def norm_incident(s):
    """Hyphen spacing between main and sub type is cosmetic; the terms are not."""
    return _words(re.sub(r"\s*-\s*", " ", str(s or "")))


def norm_units(u):
    """Ground truth and parser represent units in three different shapes.

    Ground truth is a list of abbreviations (``['E2', 'R2', 'Q5']``); the parser returns one
    space-separated string of spoken forms (``'coquitlam engine 2 rescue 2 quint 5'``);
    elsewhere they appear comma-separated. Compare on the set of (first letter, number) so
    only a genuinely different apparatus counts.

    Scanning the whole string for TYPE+NUMBER pairs rather than splitting on commas matters:
    an earlier version of this harness split on commas only and scored production units at
    76% when the true figure was 99%. A harness bug and a parser bug look identical in the
    output -- when a number moves sharply, check the harness against stored production output
    before believing it.
    """
    if not u:
        return frozenset()
    text = " , ".join(str(x) for x in u) if isinstance(u, (list, tuple)) else str(u)
    text = text.lower()
    words = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
             "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
    num = r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    out = set()
    # Spoken/expanded form: "engine 2", "quint 5", "car seven".
    for word, n in re.findall(r"\b([a-z]{2,})\s*" + num + r"\b", text):
        if word in ("group", "grid", "number", "unit", "suite", "block", "talk"):
            continue
        out.add((word[0], words.get(n, n)))
    # Abbreviated form: "E2", "R2", "C5".
    for letter, n in re.findall(r"\b([a-z])\s?(\d+)\b", text):
        out.add((letter, n))
    return frozenset(out)


def norm_grid(g):
    d = re.sub(r"\D", "", str(g or ""))
    return d or None


def norm_talkgroup(t):
    """'10 Combined Response' and 'Talk Group 10 Combined Response Coquitlam' are one channel."""
    s = str(t or "").lower()
    if not s:
        return None
    if "combined" in s:
        return "10-combined"
    d = re.sub(r"\D", "", s)
    return d or None


def norm_address_exact(a):
    return _words(a)


def norm_address_loose(a):
    """Collapse the differences that are presentation, not location.

    Suffix spelling, unit/apartment designators, and intersection leg order.

    `&` is expanded to " and " BEFORE `_words` strips punctuation. Reviewers write
    "Westwood St & Lincoln Ave" where the parser produces "Westwood Street And Lincoln Ave";
    stripping the ampersand first destroyed the separator, left one unsplittable run, and
    scored an identical intersection as WRONG.
    """
    s = _words(re.sub(r"\s*&\s*", " and ", str(a or "")))
    s = re.sub(r"\b(number|unit|suite|apt|apartment|basement|block)\b.*$", "", s).strip()
    parts = re.split(r"\s+and\s+|\s*&\s*", s)
    norm_parts = []
    for p in parts:
        w = [_SUFFIX.get(x, x) for x in p.split()]
        norm_parts.append(" ".join(w).strip())
    # Intersection leg order is not meaningful: "A and B" == "B and A".
    return " and ".join(sorted(x for x in norm_parts if x))


# ------------------------------------------------------------------------------- the parse
def parse_like_production(raw):
    """Reproduce how Phase 2 selects values across rounds.

    MIRRORS `pipeline/phase2.py` (candidate build at :113, address selection at :146,
    grid/channel at :164/:167). It is a mirror, not a call into the pipeline, because the
    real path needs a geocoder, a validator and DB writes -- none of which belong in a
    parser measurement.

    That mirroring is a maintenance hazard: if phase2's selection changes and this does not,
    the harness scores something the system no longer does. Keep them in step, and prefer
    changing both in one commit.

    Note `next(...)` for the address is the round-1-wins bias of punch-list #44 -- it is
    reproduced here deliberately, because the harness must measure what production does, not
    what it should do.
    """
    san = sanitize_transcript(raw)
    rounds = split_rounds(san, UNITS_VOCABULARY)

    all_candidates = []
    for seg in rounds:
        if len(seg.split()) > 2:
            all_candidates.extend(parse_dispatch_announcement(seg, UNITS_VOCABULARY))

    addr_c = next((d for d in all_candidates if d.address or d.intersection), None)
    return {
        "incident": match_incident_type(san, CALL_TYPES),
        "units": (addr_c.units if addr_c else None)
                 or next((d.units for d in all_candidates if d.units), None),
        "map_grid": next((d.map_grid for d in all_candidates if d.map_grid), None),
        "talkgroup": next((d.radio_channel for d in all_candidates if d.radio_channel), None),
        "address": (addr_c.address or addr_c.intersection) if addr_c else None,
        "_rounds": rounds,
        "_candidates": all_candidates,
    }


def score_row(got, truth):
    """Return {field: 'EXACT'|'COSMETIC'|'WRONG'|None}. None means no ground truth to score."""
    out = {}

    out["incident"] = None if not truth["incident"] else (
        "EXACT" if norm_incident(got["incident"]) == norm_incident(truth["incident"]) else "WRONG"
    )

    gt_units = norm_units(truth["units"])
    out["units"] = None if not gt_units else (
        "EXACT" if norm_units(got["units"]) == gt_units else "WRONG"
    )

    out["map_grid"] = None if not truth["map_grid"] else (
        "EXACT" if norm_grid(got["map_grid"]) == norm_grid(truth["map_grid"]) else "WRONG"
    )

    out["talkgroup"] = None if not truth["talkgroup"] else (
        "EXACT" if norm_talkgroup(got["talkgroup"]) == norm_talkgroup(truth["talkgroup"])
        else "WRONG"
    )

    if not truth["address"]:
        out["address"] = None
    elif norm_address_exact(got["address"]) == norm_address_exact(truth["address"]):
        out["address"] = "EXACT"
    elif got["address"] and norm_address_loose(got["address"]) == norm_address_loose(truth["address"]):
        out["address"] = "COSMETIC"
    else:
        out["address"] = "WRONG"

    return out


# ----------------------------------------------------------------------------- reporting
def fetch(conn, args):
    where = ["raw_transcript IS NOT NULL", "raw_transcript <> '[Transcription Failed]'"]
    params = []
    if args.dispatch_id:
        where.append("dispatch_id = %s")
        params.append(args.dispatch_id)
    else:
        where.append("verified_incident IS NOT NULL")
        # PA pages tagged "[PA]" by the operator are not dispatches (punch-list #14).
        where.append("position('[PA]' in coalesce(target->>'review_notes', '')) = 0")
        if args.since:
            where.append("timestamp >= %s")
            params.append(args.since)
        if args.until:
            where.append("timestamp < %s")
            params.append(args.until)
    cur = conn.cursor()
    cur.execute(
        f"""SELECT dispatch_id, timestamp, raw_transcript,
                   verified_incident, verified_units, verified_address,
                   verified_map_grid, verified_talkgroup
              FROM dispatches WHERE {' AND '.join(where)} ORDER BY timestamp""",
        params,
    )
    return cur.fetchall()


def print_table(buckets, label):
    print(f"\n{label}")
    header = f"  {'field':<11}{'n':>6}{'exact':>8}{'cosmetic':>10}{'wrong':>7}{'accuracy':>11}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for f in FIELDS:
        b = buckets[f]
        n = b["EXACT"] + b["COSMETIC"] + b["WRONG"]
        if not n:
            continue
        ok = b["EXACT"] + b["COSMETIC"]
        print(f"  {f:<11}{n:>6}{b['EXACT']:>8}{b['COSMETIC']:>10}{b['WRONG']:>7}"
              f"{ok / n * 100:>10.1f}%")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dispatch-id", help="trace a single call in detail")
    ap.add_argument("--pooled", action="store_true",
                    help="one combined table instead of per-month (see the note above)")
    ap.add_argument("--since", help="ISO date lower bound, e.g. 2026-08-01")
    ap.add_argument("--until", help="ISO date upper bound (exclusive)")
    ap.add_argument("--csv", help="write per-call rows here")
    ap.add_argument("--json", help="write the summary here, for use as a --baseline later")
    ap.add_argument("--baseline", help="compare against a summary written by --json")
    ap.add_argument("--record", action="store_true",
                    help="write one row to public.evaluation_history (tools/harness_common.py)")
    ap.add_argument("--notes", help="free text stored with --record")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL is not set. Refusing to run: without it this scores nothing "
                 "and reads as a pass (CLAUDE.md §3, parser_audit_handoff.md §9).")

    conn = psycopg2.connect(db_url)
    rows = fetch(conn, args)
    if not rows:
        sys.exit("No matching dispatches.")

    if args.dispatch_id:
        did, ts, raw, v_inc, v_units, v_addr, v_grid, v_tg = rows[0]
        got = parse_like_production(raw)
        truth = {"incident": v_inc, "units": v_units, "address": v_addr,
                 "map_grid": v_grid, "talkgroup": v_tg}
        verdict = score_row(got, truth)
        print(f"{did}   {ts}\n")
        for i, seg in enumerate(got["_rounds"], 1):
            print(f"  round {i}: {seg}")
        print()
        for f in FIELDS:
            mark = {"EXACT": "ok  ", "COSMETIC": "cos ", "WRONG": "WRONG", None: "--  "}[verdict[f]]
            print(f"  {mark} {f:<10} got={got[f]!r}")
            print(f"       {'':<10} truth={truth[f]!r}")
        return

    per_month = collections.defaultdict(
        lambda: {f: collections.Counter() for f in FIELDS})
    pooled = {f: collections.Counter() for f in FIELDS}
    csv_rows = []

    for did, ts, raw, v_inc, v_units, v_addr, v_grid, v_tg in rows:
        got = parse_like_production(raw)
        truth = {"incident": v_inc, "units": v_units, "address": v_addr,
                 "map_grid": v_grid, "talkgroup": v_tg}
        verdict = score_row(got, truth)
        month = ts.strftime("%Y-%m")
        for f in FIELDS:
            if verdict[f]:
                per_month[month][f][verdict[f]] += 1
                pooled[f][verdict[f]] += 1
        if args.csv:
            row = {"dispatch_id": did, "month": month}
            for f in FIELDS:
                row[f] = verdict[f] or ""
                row[f + "_got"] = got[f]
                row[f + "_truth"] = truth[f]
            csv_rows.append(row)

    print(f"replayed {len(rows)} verified dispatches through the current parser")

    if args.pooled:
        print_table(pooled, "POOLED (all dates)")
        print("\n  NOTE: pooled rates mix already-fixed defects with live ones. This corpus"
              "\n  spans a period of active fixes -- prefer the per-month view.")
    else:
        for month in sorted(per_month):
            print_table(per_month[month], month)

    summary = {f: dict(pooled[f]) for f in FIELDS}
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(f"\nsummary written to {args.json}")

    if args.baseline:
        with open(args.baseline, encoding="utf-8") as fh:
            base = json.load(fh)
        print("\nCHANGE VS BASELINE (wrong count; negative is an improvement)")
        for f in FIELDS:
            b = base.get(f, {}).get("WRONG", 0)
            n = summary[f].get("WRONG", 0)
            if b or n:
                print(f"  {f:<11}{b:>5} -> {n:<5} {n - b:+d}")

    if args.record:
        ts_all = [row[1] for row in rows]
        hc.record_run(stage="parser", n=len(rows), args=args,
                      metrics={"stage": "parser", "n": len(rows), "pooled": summary,
                               "months": {m: {f: dict(c) for f, c in per_month[m].items()} for m in sorted(per_month)}},
                      model_version="stored-transcript",
                      period=(min(ts_all).date(), max(ts_all).date()),
                      headline="wrong: " + ", ".join(f"{f} {summary[f].get('WRONG', 0)}" for f in FIELDS))
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(csv_rows[0].keys()))
            w.writeheader()
            w.writerows(csv_rows)
        print(f"\nper-call rows written to {args.csv}")

    conn.close()


if __name__ == "__main__":
    main()
