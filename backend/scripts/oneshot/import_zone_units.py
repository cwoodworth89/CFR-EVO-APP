"""Imports zone -> unit -> hall assignment into public.zones.

public.zones was created with geometry only (map_name, geom). The first-due apparatus
per zone lived exclusively in frontend/public/data/zones.json, which forced the kiosk to
fetch that file just to group road closures by hall.

This backfills unit_id, station and hall_id onto the existing rows. Geometry is not
touched -- that stays owned by import_gis_data.py.

Usage:
    python backend/scripts/import_zone_units.py
"""

import json
import logging
import os
import sys

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

# Q5 (Quint 5) is quartered at Hall 3 alongside E3; every other unit number matches its
# hall. Source: zones.json "station" field, City of Coquitlam response zone assignment.
UNIT_TO_HALL = {"E1": "1", "E2": "2", "E3": "3", "Q5": "3", "E4": "4"}


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set.")
    return url


def find_zones_json() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        os.path.join(root, "frontend", "public", "data", "zones.json"),
        os.path.join(root, "backend", "data", "zones.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise SystemExit(f"zones.json not found. Looked in: {candidates}")


def main() -> int:
    path = find_zones_json()
    with open(path, "r", encoding="utf-8") as f:
        zones = json.load(f)
    if isinstance(zones, dict):
        zones = zones.get("features", [])
    logging.info(f"Loaded {len(zones)} zone records from {path}")

    engine = create_engine(get_database_url())
    updated = skipped = 0
    unmapped_units = set()

    with engine.begin() as conn:
        for z in zones:
            zone_id = str(z.get("zone_id") or "").strip()
            unit_id = str(z.get("unit_id") or "").strip().upper()
            station = (z.get("station") or "").strip() or None

            if not zone_id or not unit_id:
                skipped += 1
                continue

            hall_id = UNIT_TO_HALL.get(unit_id)
            if hall_id is None:
                unmapped_units.add(unit_id)

            res = conn.execute(text("""
                UPDATE public.zones
                   SET unit_id = :unit_id,
                       station = :station,
                       hall_id = :hall_id
                 WHERE map_name = :zone_id
            """), {
                "unit_id": unit_id,
                "station": station,
                "hall_id": hall_id,
                "zone_id": zone_id,
            })
            if res.rowcount:
                updated += 1
            else:
                skipped += 1
                logging.warning(f"No public.zones row with map_name = {zone_id!r}")

        summary = conn.execute(text("""
            SELECT hall_id, count(*) AS zones
            FROM public.zones
            GROUP BY hall_id ORDER BY hall_id NULLS LAST
        """)).mappings().all()

    logging.info(f"Updated {updated} zones, skipped {skipped}.")
    if unmapped_units:
        logging.warning(
            f"Units with no hall mapping (hall_id left NULL): {sorted(unmapped_units)}. "
            "Add them to UNIT_TO_HALL."
        )
    for row in summary:
        logging.info(f"  hall {row['hall_id'] or '(unassigned)'}: {row['zones']} zones")

    return 0


if __name__ == "__main__":
    sys.exit(main())
