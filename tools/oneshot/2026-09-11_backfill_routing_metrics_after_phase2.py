"""Recompute per-unit ETAs for dispatches whose stored metrics never followed their coordinates.

WHY
    `routing_metrics` was computed once, in phase 1, and only when phase 1 itself geocoded
    a location. When phase 1 failed and phase 2 rescued the address -- the CORRECTION_AUDIT
    path, and the withheld-location path -- the coordinates moved and nothing recomputed
    what had been derived from them. Those calls show their units with '--:--' forever.
    A smaller set carries the opposite: ETAs routed to phase 1's WRONG destination, which
    is worse, because a wrong number reads exactly like a right one (CLAUDE.md 6.1, 6.6).

    The pipeline fix (payload_builder.refresh_routing_metrics, called from both phase 2
    paths) stops it happening again. This script repairs the records already written.

WHAT IT TOUCHES
    Only rows that have responding units, real coordinates, and either no metrics or
    metrics routed to somewhere other than the recorded destination. Street-section
    dispatches route each unit to the nearer end of the section by design and are left
    alone. Both copies of the value are written -- the `routing_metrics` column and
    `target->'routing_metrics'` -- because the API reads the column and falls back to the
    target, so they must not disagree.

RUN IT ON THE KIOSK
    It needs OSRM on :5000 and the `gis_service` package, and importing `cfr_dispatch`
    initialises PortAudio, so:

        ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && \\
          XDG_RUNTIME_DIR=/run/user/1000 .venv/bin/python backend/scripts/backfill_routing_metrics.py"

    Dry run by default -- it prints what it would change and writes nothing. Add --apply
    to commit. --limit N caps the number of rows considered, for a cautious first pass.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path

# backend/ on the path, so `cfr_dispatch` imports and injects the sibling service paths
# (CLAUDE.md 2 -- do not "fix" the gis_service import inside payload_builder).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cfr_dispatch.pipeline.payload_builder import (  # noqa: E402
    compute_routing_metrics, _routing_matches_destination)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

SELECT_SQL = """
    SELECT dispatch_id,
           responding_units,
           target,
           routing_metrics
    FROM public.dispatches
    WHERE COALESCE(array_length(responding_units, 1), 0) > 0
      AND target->>'lat' IS NOT NULL
      AND target->>'lng' IS NOT NULL
      AND (target->>'lat')::float <> 0
    ORDER BY timestamp DESC
"""

UPDATE_SQL = """
    UPDATE public.dispatches
       SET routing_metrics = CAST(:metrics AS jsonb),
           target = jsonb_set(target, '{routing_metrics}', CAST(:metrics AS jsonb), true)
     WHERE dispatch_id = :dispatch_id
"""


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write the recomputed metrics (default: dry run, writes nothing)")
    ap.add_argument("--limit", type=int, default=None,
                    help="consider at most N rows")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Deliberate exit, as the backtest scripts do. A fallback connection string here
        # would silently target whichever database happened to be local.
        sys.exit("DATABASE_URL is not set. Read backend/.env on the machine you are targeting.")

    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)

    repaired, skipped, unchanged = [], [], 0

    with engine.begin() as conn:
        rows = conn.execute(text(SELECT_SQL)).mappings().all()
        if args.limit:
            rows = rows[:args.limit]
        logging.info(f"{len(rows)} dispatches have units and coordinates; checking each.")

        for row in rows:
            target = row["target"] or {}
            existing = row["routing_metrics"]
            if not isinstance(existing, list):
                existing = target.get("routing_metrics") or []

            lat, lng = _as_float(target.get("lat")), _as_float(target.get("lng"))
            if lat is None or lng is None:
                continue

            # Already routed to this destination: nothing derived has gone stale.
            if existing and _routing_matches_destination(existing, lat, lng):
                unchanged += 1
                continue

            reason = "no metrics" if not existing else "destination moved"
            fresh = compute_routing_metrics(
                row["dispatch_id"], list(row["responding_units"] or []), lat, lng,
                response_type=target.get("response_type"),
                destination_options=target.get("endpoints"))

            if not fresh:
                # The router could not answer. Leave the record alone rather than writing
                # an empty array over whatever is there -- this script's job is to repair,
                # and a failed route is not a repair (CLAUDE.md 6.1).
                skipped.append((row["dispatch_id"], reason))
                continue

            etas = ", ".join(f"{m.get('unit')}={m.get('eta_minutes')}min/"
                             f"{m.get('road_distance_km')}km" for m in fresh)
            logging.info(f"  {row['dispatch_id']}: {reason} -> {etas}")
            repaired.append(row["dispatch_id"])

            if args.apply:
                conn.execute(text(UPDATE_SQL), {"dispatch_id": row["dispatch_id"],
                                                "metrics": json.dumps(fresh)})

    print()
    print(f"  already correct : {unchanged}")
    print(f"  repaired        : {len(repaired)}{'' if args.apply else '  (DRY RUN, nothing written)'}")
    print(f"  skipped         : {len(skipped)}")
    for dispatch_id, reason in skipped:
        print(f"      {dispatch_id} ({reason}) -- router returned nothing; left untouched")
    if repaired and not args.apply:
        print("\n  Re-run with --apply to write these.")


if __name__ == "__main__":
    main()
