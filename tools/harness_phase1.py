#!/usr/bin/env python3
"""Phase-1 simulator: what the completion trigger would have published, and when, chunk by chunk.

Why
---
Phase 1 (`backend/cfr_dispatch/pipeline/phase1.py`) transcribes the capture in growing chunks,
the first at 10 s and then every 3 s (`sound_capture.py`, `MIN_PHASE_1_DURATION_S`,
`PHASE_1_CHECK_INTERVAL_S`), and publishes a preliminary payload the moment
`is_round_1_complete_check` passes. On 2026-09-05 (DISP-2026-33D8C2, punch list #72) it passed at
23 s on a chunk the model had finished for itself -- "structure fire 166 coquitlam map grid 68" --
and the kiosk showed a house number, a grid, a pin and six ETAs that were not in the broadcast.
The operator's rule: unknown beats a guess. This tool measures how often that happens across the
corpus, and what two candidate rules would have done instead.

What it does
------------
For every verified call with a recording it replays the listener's schedule on the WAV: the
tone-filtered first 10 s, then 13 s, 16 s, ... through the real STT and the real parser, and asks
the real completion check. At the first chunk that passes (the baseline, what production does) it
builds the payload production would have published and scores it against the verified fields:

  grid     EXACT / WRONG / NONE against verified_map_grid
  address  classify() against verified_address, and which resolver step answered

Two rules are scored on the same chunks, without changing production:

  A  location gate: the location and grid are published only when the resolver answered at the
     parcel or intersection tier (1-exact, 1b-overlong-house, 2-intersection); otherwise phase 1
     publishes units and incident with the location unknown (the Tier 1 card).
  B  stability: the grid and the address string must be the same on two consecutive chunks; the
     payload is built on the second. Speech persists from chunk to chunk; completions change.
  C  anchor: the grid is published only when the same chunk parsed a talk group (the template
     puts "use talk group N ..." immediately before "coquitlam map grid N"); otherwise the grid
     is withheld and the rest of the payload goes out.

Measured on DISP-2026-3E1426 before the corpus run: at 19, 22 and 25 s the model completed the
chunk with "use talk group 10 combined response coquitlam map grid 68", the same wrong grid three
chunks running, with a talk group in front of it; the real "map grid 82" appeared at 28 s. So B
and C are expected to fail on completions of that shape; the corpus run says how common it is.

A call is "published" under a rule at the chunk where the rule first allows it; a call the rule
never allows within the recording is "left to phase 2", which runs on the full recording anyway.

Runs on the kiosk (the model, the recordings and the database live there). `--limit 2` first.
"""
import argparse
import csv
import os
import statistics
import sys
import wave
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness_common as hc  # noqa: E402
from harness_chain import RECORDINGS, training_ids, candidates_like_phase2  # noqa: E402
from trace_geocode_corpus import classify, install_tracer  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND)
import cfr_dispatch  # noqa: E402,F401  sibling services on sys.path
from cfr_dispatch.config import UNITS_VOCABULARY  # noqa: E402
from cfr_dispatch.config.dsp import (  # noqa: E402
    GOLDEN_FINGERPRINTS, MAX_DISPATCH_DURATION_S, MIN_PHASE_1_DURATION_S, PHASE_1_CHECK_INTERVAL_S)
from cfr_dispatch.config.hardware import AUDIO_SAMPLE_RATE  # noqa: E402
from cfr_dispatch.parser import sanitize_transcript  # noqa: E402
from cfr_dispatch.pipeline.phase1 import is_round_1_complete_check  # noqa: E402
from cfr_dispatch.pipeline.payload_builder import build_dispatch_payload  # noqa: E402
from gis_service import CoquitlamDataValidator  # noqa: E402

SOLID = {"1-exact", "1b-overlong-house", "2-intersection"}  # rule A: a parcel or a junction
EXTRA_CHUNKS_AFTER_PASS = 3  # rule B gets this many more chunks to agree; bounds the STT cost


def schedule(n_samples: int) -> list[float]:
    """The listener's phase-1 check times, in seconds of audio, for a recording this long."""
    total = n_samples / AUDIO_SAMPLE_RATE
    t, out = float(MIN_PHASE_1_DURATION_S), []
    while t <= min(total, MAX_DISPATCH_DURATION_S):
        out.append(t)
        t += PHASE_1_CHECK_INTERVAL_S
    return out


def read_wav(path: str) -> np.ndarray:
    with wave.open(path) as w:
        assert w.getframerate() == AUDIO_SAMPLE_RATE and w.getnchannels() == 1 and w.getsampwidth() == 2, \
            (path, w.getframerate(), w.getnchannels(), w.getsampwidth())
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def grid_verdict(got, truth) -> str:
    if not truth:
        return "n/a"
    if not got:
        return "NONE"
    return "EXACT" if str(got).lstrip("0") == str(truth).lstrip("0") else "WRONG"


def winning_step(trace_log, address: str) -> str:
    hits = [e for e in trace_log if e["hit"]]
    for e in reversed(hits):
        if (e.get("address") or "") == (address or ""):
            return e["step"]
    return hits[-1]["step"] if hits else "none"


def new_bucket():
    return {"n": 0, "published": 0, "t_pub": [], "grid": Counter(), "place": Counter(),
            "location_unknown": 0, "resolved_by": Counter()}


def score(bucket, t, payload, resolved_by, truth, location_shown=True, grid_shown=True):
    bucket["published"] += 1
    bucket["t_pub"].append(t)
    target = (payload or {}).get("target") or {}
    got_grid = target.get("map_grid")
    sys_addr = target.get("address") or (payload or {}).get("address") or ""
    if not location_shown:
        bucket["location_unknown"] += 1
        bucket["grid"]["withheld"] += 1
        return
    bucket["grid"][grid_verdict(got_grid, truth["map_grid"]) if grid_shown else "withheld"] += 1
    if truth["address"]:
        bucket["place"][classify(sys_addr, truth["address"]) or "unresolved"] += 1
    bucket["resolved_by"][resolved_by] += 1


def summarize(b):
    return {"n": b["n"], "published": b["published"],
            "t_pub_median": statistics.median(b["t_pub"]) if b["t_pub"] else None,
            "grid": dict(sorted(b["grid"].items())), "place": dict(sorted(b["place"].items())),
            "location_unknown": b["location_unknown"], "resolved_by": dict(sorted(b["resolved_by"].items()))}


def print_bucket(name, b):
    s = summarize(b)
    print(f"  {name:10s} published {s['published']}/{s['n']}  median at {s['t_pub_median']} s  "
          f"grid {s['grid']}  place {s['place']}  location unknown {s['location_unknown']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    hc.add_common_args(ap)
    ap.add_argument("--only-csv", metavar="PATH", help="replay only the calls this CSV lists")
    ap.add_argument("--csv", help="write per-call rows here")
    ap.add_argument("--dispatch-id", help="replay one call and print every chunk")
    args = ap.parse_args()

    db = hc.database_url()
    engine = create_engine(db)
    if args.dispatch_id:
        where, params = ["dispatch_id = :did"], {"did": args.dispatch_id}
    else:
        where = ["coalesce(btrim(verified_address), '') <> ''",
                 "position('[PA]' in coalesce(target->>'review_notes', '')) = 0"]
        dw, params = hc.date_where(args)
        where += dw
    sql = ("SELECT dispatch_id, timestamp, verified_address, verified_map_grid, target->>'tone_name' AS tone_name "
           "FROM public.dispatches WHERE " + " AND ".join(f"({w})" for w in where) + " ORDER BY timestamp")
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    engine.dispose()
    if args.only_csv:
        keep = training_ids(args.only_csv)
        rows = [r for r in rows if r["dispatch_id"] in keep]
    rows = [r for r in rows if os.path.exists(os.path.join(RECORDINGS, f"{r['dispatch_id']}.wav"))]
    if not rows:
        sys.exit("no verified dispatches with a recording in that range")
    print(f"{len(rows)} verified calls with a recording; chunks at {MIN_PHASE_1_DURATION_S:.0f} s then every "
          f"{PHASE_1_CHECK_INTERVAL_S:.0f} s, as the listener does")

    from cfr_dispatch.stt import transcribe_audio_local  # loads PortAudio; kiosk only
    from cfr_dispatch.config.runtime import WHISPER_MODEL
    from audio_service import filter_known_tones
    validator = CoquitlamDataValidator(database_url=db)
    trace_log = install_tracer()
    model_version = os.path.basename(WHISPER_MODEL.rstrip("/\\")) or WHISPER_MODEL

    buckets = {k: new_bucket() for k in ("baseline", "rule A", "rule B", "rule C")}
    per_month = defaultdict(lambda: {k: new_bucket() for k in buckets})
    out_rows = []

    def publish(chunk_raw: str):
        """What production would publish from this chunk: the payload and the step that placed it."""
        san, cands = candidates_like_phase2(chunk_raw)
        trace_log.clear()
        try:
            payload, _units = build_dispatch_payload("SIM", chunk_raw, san, cands, validator, UNITS_VOCABULARY)
        except Exception:
            payload = {}
        target = (payload or {}).get("target") or {}
        return payload, winning_step(trace_log, target.get("address") or "")

    for r in rows:
        did, month = r["dispatch_id"], hc.month_of(r["timestamp"])
        truth = {"address": r["verified_address"], "map_grid": r["verified_map_grid"]}
        audio = read_wav(os.path.join(RECORDINGS, f"{did}.wav"))
        for b in (buckets, per_month[month]):
            for k in b:
                b[k]["n"] += 1

        chunks = []          # (t, raw, passes, grid, address) per chunk
        base_t = None
        b_t = None
        for t in schedule(len(audio)):
            piece = audio[: int(t * AUDIO_SAMPLE_RATE)]
            if r["tone_name"]:
                piece = filter_known_tones(piece, r["tone_name"], AUDIO_SAMPLE_RATE, GOLDEN_FINGERPRINTS)
            raw = transcribe_audio_local(piece.astype(np.float32) / 32768.0, validator=validator) or ""
            san, cands = candidates_like_phase2(raw)
            passes = is_round_1_complete_check(cands, san)
            first = next((c for c in cands if c.address or c.intersection), None)
            grid = next((c.map_grid for c in cands if c.map_grid), None)
            addr = (first.address or first.intersection) if first else None
            talk = next((c.radio_channel for c in cands if c.radio_channel), None)
            chunks.append((t, raw, passes, grid, addr, talk))
            if args.dispatch_id:
                print(f"  {t:5.1f} s  pass={passes!s:5}  grid={grid!s:5}  talk={talk!r:22}  addr={addr!r:28}  {raw[:400]!r}")
            if passes and base_t is None:
                base_t = t
            if passes and b_t is None and len(chunks) >= 2:
                prev = chunks[-2]
                if prev[3] == grid and prev[4] == addr and (grid or addr):
                    b_t = t
            if base_t is not None and (b_t is not None or t - base_t >= EXTRA_CHUNKS_AFTER_PASS * PHASE_1_CHECK_INTERVAL_S):
                break

        row = {"dispatch_id": did, "month": month, "verified_address": truth["address"],
               "verified_map_grid": truth["map_grid"], "chunks": len(chunks)}
        if base_t is not None:
            raw_at = next(c[1] for c in chunks if c[0] == base_t)
            payload, step = publish(raw_at)
            target = (payload or {}).get("target") or {}
            talk_at = next(c[5] for c in chunks if c[0] == base_t)
            for b in (buckets, per_month[month]):
                score(b["baseline"], base_t, payload, step, truth)
                score(b["rule A"], base_t, payload, step, truth, location_shown=step in SOLID)
                score(b["rule C"], base_t, payload, step, truth, grid_shown=bool(talk_at))
            row.update({"t_base": base_t, "base_grid": target.get("map_grid"), "base_address": target.get("address"),
                        "base_resolved_by": step, "base_grid_verdict": grid_verdict(target.get("map_grid"), truth["map_grid"]),
                        "base_place": classify(target.get("address") or "", truth["address"]) if truth["address"] else "",
                        "rule_a_location": "shown" if step in SOLID else "unknown",
                        "rule_c_grid": "shown" if talk_at else "withheld", "base_transcript": raw_at})
        if b_t is not None:
            raw_b = next(c[1] for c in chunks if c[0] == b_t)
            payload_b, step_b = publish(raw_b)
            target_b = (payload_b or {}).get("target") or {}
            for b in (buckets, per_month[month]):
                score(b["rule B"], b_t, payload_b, step_b, truth)
            row.update({"t_b": b_t, "b_grid": target_b.get("map_grid"), "b_address": target_b.get("address"),
                        "b_grid_verdict": grid_verdict(target_b.get("map_grid"), truth["map_grid"]),
                        "b_place": classify(target_b.get("address") or "", truth["address"]) if truth["address"] else ""})
        out_rows.append(row)
        if args.dispatch_id:
            print(f"  baseline published at {base_t} s, rule B at {b_t} s; verified grid {truth['map_grid']!r}, address {truth['address']!r}")

    print()
    for month in sorted(per_month):
        print(f"{month}  (n={per_month[month]['baseline']['n']})")
        for k, b in per_month[month].items():
            print_bucket(k, b)
    print(f"POOLED  (n={buckets['baseline']['n']})")
    for k, b in buckets.items():
        print_bucket(k, b)

    if args.csv:
        keys = sorted({k for row in out_rows for k in row})
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(out_rows)
        print(f"\nper-call rows written to {args.csv}")

    summary = {"stage": "phase1", "model_version": model_version, "n": buckets["baseline"]["n"],
               "pooled": {k: summarize(b) for k, b in buckets.items()},
               "months": {m: {k: summarize(b) for k, b in per_month[m].items()} for m in sorted(per_month)}}
    b0, ba, bb, bc = (summarize(buckets[k]) for k in ("baseline", "rule A", "rule B", "rule C"))
    headline = (f"phase 1 published {b0['published']}/{b0['n']} (median {b0['t_pub_median']} s); "
                f"grid wrong {b0['grid'].get('WRONG', 0)}, wrong street {b0['place'].get('wrong-street', 0)}; "
                f"A withholds {ba['location_unknown']} locations; B publishes {bb['published']}, grid wrong "
                f"{bb['grid'].get('WRONG', 0)}; C withholds {bc['grid'].get('withheld', 0)} grids, wrong {bc['grid'].get('WRONG', 0)}")
    print("\n" + headline)
    if args.json:
        hc.save_summary(args.json, summary)
    if args.baseline:
        hc.diff_summaries(summary, hc.load_summary(args.baseline))
    if args.record:
        hc.record_run(stage="phase1", n=buckets["baseline"]["n"], args=args, metrics=summary,
                      model_version=model_version,
                      period=(min(r["timestamp"] for r in rows).date(), max(r["timestamp"] for r in rows).date()),
                      headline=headline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
