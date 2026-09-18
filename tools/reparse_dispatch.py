# tools/reparse_dispatch.py
"""Re-run one stored dispatch through the phase-2 parse and target resolution, and re-record
the result on the SAME row.

    python tools/reparse_dispatch.py DISP-2026-A018E9 --dry-run   # print what it would write
    python tools/reparse_dispatch.py DISP-2026-A018E9             # write it

Built 2026-09-18 for DISP-2026-A018E9 (punch-list #95): the parser fix f91bdedd landed after
the call, and the operator asked for the call to be run through the pipeline and re-recorded
rather than re-dispatched. It runs on the kiosk, in the agent's venv, from backend/, with the
environment the cfr-agent unit uses (XDG_RUNTIME_DIR=/run/user/1000; DATABASE_URL comes from
backend/.env the way cfr_dispatch loads it on import).

What runs is the worker's own path, not a copy of it: sanitize_transcript -> split_rounds ->
parse_dispatch_announcement -> build_dispatch_payload with the worker's shared validator,
exactly as pipeline/phase2.py takes a call whose phase 1 was skipped (phase2.py:197). The
geocoder, the near-road resolution, the routing metrics (OSRM on the kiosk) and the review
flags are therefore the pipeline's answers for this transcript.

What it writes -- four columns, one UPDATE, and nothing else:

    sanitized_transcript, incident_type, responding_units, target

The old target, and the old values of the other three, are kept under
target.reparsed_from with the run time and the commit of the code that ran, so the change
is auditable and reversible by hand. raw_transcript, timestamp, audio_url, audio_duration,
verify_location, routing_metrics (the column; the API falls back to target.routing_metrics
when it is empty), origins, every verified_* column, feedback_submitted, quality_rating,
review_notes and model_updated are not touched.

What it never does: publish to MQTT or ntfy (the API's PATCH does, so this does not go
through the API), create a row, or overwrite a placed location with an unplaced one -- if
the re-parse yields no coordinates it prints the result and refuses (CLAUDE.md 6.1: a null
over a null teaches nothing, and a null over a point would be a regression).
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys

import psycopg2
from psycopg2.extras import Json

from _repo import BACKEND  # noqa: F401  -- puts backend/ and services/*/src on sys.path
import harness_common as hc

from cfr_dispatch.config import UNITS_VOCABULARY  # noqa: E402
from cfr_dispatch.parser import (  # noqa: E402
    sanitize_transcript,
    split_rounds,
    parse_dispatch_announcement,
)
from cfr_dispatch.pipeline.payload_builder import build_dispatch_payload  # noqa: E402
from cfr_dispatch.worker import get_shared_validator  # noqa: E402

TOUCHED = ("sanitized_transcript", "incident_type", "responding_units", "target")

# Keys whose values are too long to read in a diff; shown as a size instead.
_BULKY = {"routing_metrics", "rings", "segment", "endpoints", "reparsed_from"}


def _short(value) -> str:
    text = json.dumps(value, default=str)
    return text if len(text) <= 160 else f"{text[:157]}... ({len(text)} chars)"


def _print_target_diff(before: dict, after: dict) -> None:
    keys = sorted(set(before) | set(after))
    for k in keys:
        b, a = before.get(k), after.get(k)
        if b == a:
            continue
        if k in _BULKY:
            bs = f"<{len(b) if isinstance(b, (list, dict)) else 0} items>" if b is not None else "None"
            as_ = f"<{len(a) if isinstance(a, (list, dict)) else 0} items>" if a is not None else "None"
            print(f"    target.{k:<20} {bs}  ->  {as_}")
        else:
            print(f"    target.{k:<20} {_short(b)}  ->  {_short(a)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dispatch_id")
    ap.add_argument("--dry-run", action="store_true", help="print what would be written; write nothing")
    args = ap.parse_args()

    conn = psycopg2.connect(hc.database_url())
    cur = conn.cursor()
    cur.execute(
        """SELECT id, timestamp, raw_transcript, sanitized_transcript, incident_type,
                  responding_units, target, audio_url, audio_duration
             FROM public.dispatches WHERE dispatch_id = %s""",
        (args.dispatch_id,),
    )
    row = cur.fetchone()
    if not row:
        print(f"{args.dispatch_id}: no such dispatch. Nothing written.")
        return 2
    row_id, ts, raw, old_san, old_inc, old_units, old_target, audio_url, audio_duration = row
    old_target = old_target or {}
    if not raw or raw == "[Transcription Failed]":
        print(f"{args.dispatch_id}: raw_transcript is {raw!r}; there is nothing to re-parse. Nothing written.")
        return 2

    print(f"{args.dispatch_id}  id={row_id}  timestamp={ts}  commit={hc.GIT_HASH_AT_START}"
          + ("  (working tree dirty)" if hc.git_dirty() else ""))
    print(f"raw_transcript: {raw}")

    # ---- the worker's path, phase 2 with phase 1 skipped (pipeline/phase2.py:171-200)
    transcript = sanitize_transcript(raw)
    all_candidates = []
    for text in split_rounds(transcript, UNITS_VOCABULARY):
        if len(text.split()) > 2:
            all_candidates.extend(parse_dispatch_announcement(text, UNITS_VOCABULARY))

    validator = get_shared_validator()
    if validator is None:
        print("The worker's validator could not be built (see the log above). Nothing written.")
        return 2

    # The captured tone is the listener's, not the transcript's; carry it as the live call did.
    tone_name = old_target.get("captured_tones") or old_target.get("tone_name")
    db_payload, _units = build_dispatch_payload(
        args.dispatch_id, raw, transcript, all_candidates, validator, UNITS_VOCABULARY,
        audio_url=audio_url, audio_duration=float(audio_duration) if audio_duration is not None else None,
        tone_name=tone_name,
    )
    new_target = dict(db_payload.get("target") or {})
    new_san = db_payload.get("sanitized_transcript")
    new_inc = db_payload.get("incident_type")
    new_units = list(db_payload.get("responding_units") or [])

    print(f"\nparsed {len(all_candidates)} candidate(s) from {len(split_rounds(transcript, UNITS_VOCABULARY))} round(s)")
    print("\nBEFORE -> AFTER")
    print(f"  sanitized_transcript:\n    {old_san!r}\n    -> {new_san!r}")
    print(f"  incident_type:      {old_inc!r} -> {new_inc!r}")
    print(f"  responding_units:   {old_units!r} -> {new_units!r}")
    print("  target (keys that change):")
    _print_target_diff(old_target, new_target)

    if new_target.get("lat") is None or new_target.get("lng") is None:
        print(f"\nREFUSED: the re-parse placed no location (address={new_target.get('address')!r}, "
              f"flags={new_target.get('review_flags')}). Nothing written.")
        return 3

    new_target["reparsed_from"] = {
        "run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "commit": hc.GIT_HASH_AT_START,
        "tool": "tools/reparse_dispatch.py",
        "target": old_target,
        "sanitized_transcript": old_san,
        "incident_type": old_inc,
        "responding_units": old_units,
    }

    if args.dry_run:
        print("\nDRY RUN: would UPDATE public.dispatches SET " + ", ".join(TOUCHED)
              + f" WHERE dispatch_id = {args.dispatch_id!r} (one row). Nothing written.")
        conn.rollback()
        return 0

    cur.execute(
        """UPDATE public.dispatches
              SET sanitized_transcript = %s, incident_type = %s, responding_units = %s, target = %s
            WHERE dispatch_id = %s
        RETURNING id""",
        (new_san, new_inc, new_units, Json(new_target), args.dispatch_id),
    )
    if cur.rowcount != 1:
        conn.rollback()
        print(f"\nUPDATE matched {cur.rowcount} rows, not 1. Rolled back; nothing written.")
        return 2
    conn.commit()
    print(f"\nWROTE id={cur.fetchone()[0]}: {', '.join(TOUCHED)}. Old values kept under target.reparsed_from. "
          "No MQTT, no ntfy, no new row.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
