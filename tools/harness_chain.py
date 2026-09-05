#!/usr/bin/env python3
"""The whole chain, scored: recording -> transcript -> parsed fields -> point on the map.

    .venv/bin/python tools/harness_chain.py --since 2026-09-01                      # STT + parser + geocoder
    .venv/bin/python tools/harness_chain.py --skip-stt --since 2026-08-01           # stored transcript -> parser -> geocoder
    .venv/bin/python tools/harness_chain.py --since 2026-09-01 --json /tmp/before.json --record
        ... change something, rebuild, then ...
    .venv/bin/python tools/harness_chain.py --since 2026-09-01 --baseline /tmp/before.json --record --notes "what changed"
    .venv/bin/python tools/harness_chain.py --dispatch-id DISP-2026-55B7B6          # one call, every stage shown

Runs on the kiosk with the project virtualenv (STT needs the model and the recordings;
over SSH set XDG_RUNTIME_DIR=/run/user/1000). With --skip-stt it runs anywhere that can
reach the database.

Why this exists
---------------
The parser harness starts from the stored transcript and stops at the fields. The geocoder
harness starts from the stored parser output and stops at the address string. Each isolates
one stage, which is right for blame and wrong for the question the operator asked on
2026-09-04: did this change make the system better as a whole? This harness runs the chain
the way production builds a dispatch, from the recording (or, with --skip-stt, from the
transcript the live system produced at the time) to the geocoded point, and scores every
stage against the operator-verified columns in one pass.

What it replays, and how faithfully
-----------------------------------
* STT: `cfr_dispatch.stt.transcribe_audio_file_local` on backend/audio_files/recordings/<id>.wav
  with the validator production passes for hotword biasing, so the model the kiosk runs
  (WHISPER_MODEL from backend/.env) is scored on the task it actually performs.
* Parser fields: `backtest_parser_corpus.parse_like_production`, that harness's mirror of
  Phase 2's cross-round selection, scored with its `score_row`, so the field numbers here
  are directly comparable with the parser harness.
* The place: `cfr_dispatch.pipeline.payload_builder.build_dispatch_payload`, production's own
  constructor, fed the candidates Phase 2 would build and the real PostGIS geocoder. Its
  `target.address` is bucketed by `trace_geocode_corpus.classify`, the geocoder harness's
  rule, and its `target.lat/lng` is measured in metres against where the same geocoder puts
  the verified address.
* Not replayed: Phase 1. Production also builds a Phase 1 payload from the first seconds of
  audio and Phase 2 cross-checks against it (punch-list #44a). This harness runs the Phase 2
  constructor alone, which is the single-phase path and the code both branches share.

Reading the numbers
-------------------
Split by month before believing any rate (qa_harnesses.md §5). The STT figure is round 1
against round 1 of `verified_transcript`, because the reviewer verifies one round and the
audio holds two (§4's trap). The round-1 training clips are left out of the STT figure unless
--include-training is given: a fine-tuned model scoring its own training data is memorisation.
"Unknown" is a correct answer when the audio did not contain the value (CLAUDE.md 6.1); it
counts as WRONG here only where the operator verified a value.
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
from collections import Counter, defaultdict

from _repo import BACKEND  # noqa: F401  tools/_repo.py puts backend/ and services/*/src on sys.path
import harness_common as hc  # noqa: E402
from backtest_parser_corpus import FIELDS, parse_like_production, score_row  # noqa: E402
from trace_geocode_corpus import classify, install_tracer  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from cfr_dispatch.config import UNITS_VOCABULARY  # noqa: E402
from cfr_dispatch.parser import (  # noqa: E402
    parse_dispatch_announcement,
    sanitize_transcript,
    split_rounds,
)
from cfr_dispatch.pipeline.payload_builder import build_dispatch_payload  # noqa: E402
from gis_service.geocoder import CoquitlamDataValidator  # noqa: E402

PLACE_OK = ("exact", "cosmetic")          # the same place; every other bucket is a defect
PLACE_BUCKETS = ("exact", "cosmetic", "house-number", "wrong-street", "no-street", "unresolved")
RECORDINGS = os.path.join(str(BACKEND), "audio_files", "recordings")
TRAINING_CSV = os.path.join(str(BACKEND), "data", "training", "metadata_round1_train.csv")


def training_ids(path: str) -> set[str]:
    ids = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = row.get("file_name") or row.get("dispatch_id") or ""
                ids.add(os.path.splitext(os.path.basename(name))[0])
    return ids


def round1(text_: str) -> str:
    san = sanitize_transcript(text_ or "")
    rounds = split_rounds(san, UNITS_VOCABULARY)
    return rounds[0] if rounds else san


def candidates_like_phase2(transcript: str):
    """Exactly phase2.py's candidate build: sanitise, split rounds, parse each round with
    more than two words."""
    san = sanitize_transcript(transcript)
    cands = []
    for seg in split_rounds(san, UNITS_VOCABULARY):
        if len(seg.split()) > 2:
            cands.extend(parse_dispatch_announcement(seg, UNITS_VOCABULARY))
    return san, cands


def new_bucket():
    return {"n": 0, "fields": {f: Counter() for f in FIELDS}, "place": Counter(), "dist": [], "wer": [],
            "resolved_by": Counter()}


def summarise(b: dict) -> dict:
    place_total = sum(b["place"].values())
    place_ok = sum(b["place"][k] for k in PLACE_OK)
    return {
        "n": b["n"],
        "fields": {f: dict(b["fields"][f]) for f in FIELDS},
        "fields_wrong": {f: b["fields"][f].get("WRONG", 0) for f in FIELDS},
        "place": {k: b["place"].get(k, 0) for k in PLACE_BUCKETS},
        "place_ok_pct": hc.pct(place_ok, place_total),
        # Which resolver step answered (trace_geocode_corpus's wrapper). Steps 5 and 6 return
        # the same address string and differ only in the point, so this is the only view that
        # separates them (punch-list #62).
        "resolved_by": dict(sorted(b["resolved_by"].items())),
        "distance_m": {"n": len(b["dist"]),
                       "median": round(statistics.median(b["dist"]), 1) if b["dist"] else None,
                       "p90": round(hc.quantile(b["dist"], 0.9), 1) if b["dist"] else None},
        "wer": {"n": len(b["wer"]),
                "mean_pct": round(100 * statistics.fmean(b["wer"]), 2) if b["wer"] else None,
                "median_pct": round(100 * statistics.median(b["wer"]), 2) if b["wer"] else None},
    }


def print_block(title: str, b: dict) -> None:
    s = summarise(b)
    print(f"\n{title}  (n={s['n']})")
    print(f"  {'field':<11}{'EXACT':>7}{'COSMETIC':>10}{'WRONG':>7}   {'%wrong':>7}")
    for f in FIELDS:
        c = b["fields"][f]
        tot = sum(c.values())
        w = c.get("WRONG", 0)
        print(f"  {f:<11}{c.get('EXACT', 0):>7}{c.get('COSMETIC', 0):>10}{w:>7}   "
              f"{(hc.pct(w, tot) if tot else '-'):>7}")
    print("  place       " + "  ".join(f"{k} {s['place'][k]}" for k in PLACE_BUCKETS)
          + f"   ok {s['place_ok_pct']}%")
    d = s["distance_m"]
    print(f"  distance    n={d['n']} median={d['median']} m  p90={d['p90']} m   (target vs the geocoded verified address)")
    print("  resolved by " + "  ".join(f"{k} {v}" for k, v in s["resolved_by"].items()))
    w = s["wer"]
    if w["n"]:
        print(f"  stt wer     n={w['n']} mean={w['mean_pct']}%  median={w['median_pct']}%   (round 1 vs round 1 of verified_transcript)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    hc.add_common_args(ap)
    ap.add_argument("--skip-stt", action="store_true",
                    help="start from the stored raw_transcript instead of the recording")
    ap.add_argument("--include-training", action="store_true",
                    help="score STT on the round-1 training clips too (that is memorisation)")
    ap.add_argument("--training-csv", default=TRAINING_CSV,
                    help="clips left out of the STT figure (default: the round-1 train set)")
    ap.add_argument("--only-csv", metavar="PATH",
                    help="replay only the calls this CSV lists (file_name or dispatch_id column), "
                         "e.g. backend/data/training/metadata_round1_holdout.csv for the honest STT number")
    ap.add_argument("--csv", help="write per-call rows here")
    ap.add_argument("--dispatch-id", help="replay one call and print every stage")
    args = ap.parse_args()

    db = hc.database_url()
    engine = create_engine(db)
    if args.dispatch_id:
        where, params = ["dispatch_id = :did"], {"did": args.dispatch_id}
    else:
        where = ["(coalesce(btrim(verified_address), '') <> '' OR verified_incident IS NOT NULL "
                 "OR coalesce(btrim(verified_transcript), '') <> '')"]
        dw, params = hc.date_where(args)
        where += dw
    sql = ("SELECT dispatch_id, timestamp, raw_transcript, verified_transcript, verified_address, "
           "verified_incident, verified_units, verified_map_grid, verified_talkgroup "
           "FROM public.dispatches WHERE " + " AND ".join(f"({w})" for w in where) + " ORDER BY timestamp")
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    engine.dispose()
    if args.only_csv:
        keep = training_ids(args.only_csv)
        rows = [r for r in rows if r["dispatch_id"] in keep]
        print(f"restricted to the {len(keep)} calls listed in {args.only_csv}: {len(rows)} in range")
    if not rows:
        sys.exit("no verified dispatches in that range")

    validator = CoquitlamDataValidator(database_url=db)
    trace_log = install_tracer()  # which resolver answered each call; cleared before every payload build
    if args.skip_stt:
        model_version = "stored-transcript"
        excluded = set()
        transcribe = None
    else:
        from cfr_dispatch.stt import transcribe_audio_file_local  # loads PortAudio; kiosk only
        from cfr_dispatch.config.runtime import WHISPER_MODEL
        transcribe = transcribe_audio_file_local
        model_version = os.path.basename(WHISPER_MODEL.rstrip("/\\")) or WHISPER_MODEL
        excluded = set() if args.include_training else training_ids(args.training_csv)
        print(f"model {WHISPER_MODEL}; {len(excluded)} training clips left out of the STT figure"
              if excluded else f"model {WHISPER_MODEL}; training clips included in the STT figure")

    pooled = new_bucket()
    per_month = defaultdict(new_bucket)
    counts = Counter()
    verified_points: dict[str, tuple] = {}
    out_rows = []

    for r in rows:
        did, month = r["dispatch_id"], hc.month_of(r["timestamp"])
        truth = {"incident": r["verified_incident"], "units": r["verified_units"],
                 "address": r["verified_address"], "map_grid": r["verified_map_grid"],
                 "talkgroup": r["verified_talkgroup"]}

        # 1. the transcript
        stt_ran = False
        if transcribe is None:
            transcript = r["raw_transcript"] or ""
        else:
            wav = os.path.join(RECORDINGS, f"{did}.wav")
            if not os.path.exists(wav):
                counts["no_audio"] += 1
                continue
            try:
                hyp = transcribe(wav, validator=validator) or ""
            except Exception as exc:  # a crash is a finding, not a reason to stop the sweep
                counts["stt_failed"] += 1
                hyp = ""
                if args.dispatch_id:
                    print(f"  stt error   : {exc}")
            stt_ran = bool(hyp)
            transcript = hyp if hyp else "[Transcription Failed]"

        # 2. STT score, round 1 against round 1, holdout only
        w = None
        if stt_ran and (r["verified_transcript"] or "").strip():
            if did in excluded:
                counts["stt_excluded"] += 1
            else:
                w = hc.wer(round1(r["verified_transcript"]), round1(transcript))

        # 3. parser fields, the parser harness's way
        got = parse_like_production(transcript)
        verdict = score_row(got, truth)

        # 4. the place, production's way
        san, cands = candidates_like_phase2(transcript)
        trace_log.clear()
        try:
            payload, _units = build_dispatch_payload(did, transcript, san, cands, validator, UNITS_VOCABULARY)
        except Exception as exc:
            counts["payload_failed"] += 1
            payload = {}
            if args.dispatch_id:
                print(f"  payload err : {exc}")
        # Read before the verified address is geocoded below, which would overwrite the log.
        resolved_by = next((e["step"] for e in trace_log if e["hit"]), "none")
        target = payload.get("target") or {}
        sys_addr = target.get("address") or payload.get("address") or ""
        place = dist = None
        if truth["address"]:
            place = classify(sys_addr, truth["address"])
            if did not in verified_points:
                try:
                    res = validator.get_coordinates(truth["address"]) or {}
                except Exception:
                    res = {}
                verified_points[did] = (res.get("lat"), res.get("lng"))
            vlat, vlng = verified_points[did]
            if None not in (target.get("lat"), target.get("lng"), vlat, vlng):
                dist = hc.haversine_m(target["lat"], target["lng"], vlat, vlng)

        for b in (pooled, per_month[month]):
            b["n"] += 1
            for f in FIELDS:
                if verdict[f]:
                    b["fields"][f][verdict[f]] += 1
            if place:
                b["place"][place] += 1
            if dist is not None:
                b["dist"].append(dist)
            if w is not None:
                b["wer"].append(w)
            b["resolved_by"][resolved_by] += 1

        out_rows.append({"dispatch_id": did, "month": month, "stt_ran": stt_ran,
                         "wer": None if w is None else round(w, 4),
                         **{f: verdict[f] or "" for f in FIELDS},
                         "place": place or "", "resolved_by": resolved_by,
                         "distance_m": None if dist is None else round(dist, 1),
                         "system_address": sys_addr, "verified_address": truth["address"],
                         "lat": target.get("lat"), "lng": target.get("lng")})

        if args.dispatch_id:
            print(f"  dispatch    : {did}  ({r['timestamp']})")
            print(f"  transcript  : {transcript[:200]!r}" + ("  [stored]" if transcribe is None else "  [STT now]"))
            if r["verified_transcript"]:
                print(f"  verified r1 : {round1(r['verified_transcript'])[:200]!r}")
            if w is not None:
                print(f"  wer         : {100 * w:.1f}%")
            for f in FIELDS:
                print(f"  {f:<12}: got {got[f]!r:<40} truth {truth[f]!r:<30} {verdict[f] or ''}")
            print(f"  place       : {sys_addr!r} vs {truth['address']!r} -> {place}"
                  + (f", {dist:.0f} m apart" if dist is not None else "") + f"  (resolved by {resolved_by})")

    if args.dispatch_id:
        return 0

    print(f"\nreplayed {pooled['n']} verified dispatches through "
          f"{'STT -> ' if transcribe else 'the stored transcript -> '}parser -> geocoder"
          + (f"; skipped {counts['no_audio']} with no recording" if counts["no_audio"] else "")
          + (f"; {counts['stt_failed']} transcriptions failed" if counts["stt_failed"] else "")
          + (f"; {counts['payload_failed']} payload builds failed" if counts["payload_failed"] else "")
          + (f"; {counts['stt_excluded']} training clips left out of the WER" if counts["stt_excluded"] else ""))
    for m in sorted(per_month):
        print_block(m, per_month[m])
    print_block("POOLED (all dates; mixes fixed and live defects, prefer the months)", pooled)

    summary = {"stage": "chain" if transcribe else "chain-no-stt", "model_version": model_version,
               "n": pooled["n"], "counts": dict(counts), "pooled": summarise(pooled),
               "months": {m: summarise(b) for m, b in sorted(per_month.items())}}
    if args.csv and out_rows:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            wcsv = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
            wcsv.writeheader()
            wcsv.writerows(out_rows)
        print(f"\nper-call rows written to {args.csv}")
    if args.json:
        hc.save_summary(args.json, summary)
    if args.baseline:
        hc.diff_summaries(summary["pooled"], hc.load_summary(args.baseline).get("pooled", {}))
    if args.record:
        p = summary["pooled"]
        headline = (f"place ok {p['place_ok_pct']}% (n={sum(p['place'].values())}), "
                    f"median {p['distance_m']['median']} m; wrong "
                    + ", ".join(f"{f} {p['fields_wrong'][f]}" for f in FIELDS)
                    + (f"; wer {p['wer']['mean_pct']}% (n={p['wer']['n']})" if p["wer"]["n"] else ""))
        hc.record_run(stage=summary["stage"], n=pooled["n"], args=args, metrics=summary,
                      model_version=model_version,
                      period=(rows[0]["timestamp"].date(), rows[-1]["timestamp"].date()),
                      wer_pct=p["wer"]["mean_pct"], headline=headline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
