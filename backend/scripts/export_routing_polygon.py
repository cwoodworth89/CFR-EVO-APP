#!/usr/bin/env python3
"""Write the polygon the routing graph uses to tell a City street from a tour through another
city: public.city_boundary, buffered outward, as one GeoJSON Feature for
`osrm-extract --location-dependent-data`.

    backend/scripts/export_routing_polygon.py --buffer-m 100 --out backend/data/osrm/coquitlam_plus_100m.geojson

Operator, 2026-09-09: "use the city boundary + 100m. That way we cleanly get all the city
streets, but it wouldn't take a big tour through another city." OSRM decides which polygon a
way is in by the way's LAST node (the pinned source; the project wiki page "Using location
dependent data in profiles"), so a boundary road whose way ends within the buffer counts as
inside, and a road that runs out of the city counts as outside from the way where it leaves.
Measured on the 2,248 deployed corpus routes the same day: the raw boundary flags 369 routes,
the 100 m buffer 25, 23 of them by more than 500 m.

The polygon is derived from public.city_boundary and is regenerated at every graph build by
backend/scripts/build_osrm_graph.sh rather than stored in git, so it cannot drift from its
source (docs/standards/dependency-behaviour.md, "the same failure outside libraries"). The
Feature's properties record the source, the buffer and the time. The profile reads
`way:get_location_tag('cfr_city')` and treats anything but 'coquitlam' as outside.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        env_path = os.path.join(BACKEND, ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if not url.startswith("postgresql://"):
        sys.exit("DATABASE_URL is not set (environment or backend/.env). Refusing to guess a database.")
    return url


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--buffer-m", type=float, default=100.0, help="metres outward from public.city_boundary (operator ruling 2026-09-09: 100)")
    ap.add_argument("--out", required=True, help="GeoJSON path to write")
    ap.add_argument("--tag", default="coquitlam", help="value the profile tests way:get_location_tag('cfr_city') against")
    args = ap.parse_args()

    from sqlalchemy import create_engine, text  # imported here so --help works without the venv

    engine = create_engine(database_url())
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT ST_AsGeoJSON(ST_Buffer(ST_Union(geom)::geography, :m)::geometry, 6) AS gj,
                   count(*) AS parts,
                   round((ST_Area(ST_Union(geom)::geography) / 1e6)::numeric, 2) AS city_km2,
                   round((ST_Area(ST_Buffer(ST_Union(geom)::geography, :m)) / 1e6)::numeric, 2) AS polygon_km2
            FROM public.city_boundary
        """), {"m": args.buffer_m}).mappings().one()
    engine.dispose()
    if not row["gj"]:
        sys.exit("public.city_boundary is empty; nothing to export")

    geometry = json.loads(row["gj"])
    feature = {
        "type": "Feature",
        "properties": {
            "cfr_city": args.tag,
            "source": "public.city_boundary",
            "source_rows": int(row["parts"]),
            "buffer_m": args.buffer_m,
            "city_km2": float(row["city_km2"]),
            "polygon_km2": float(row["polygon_km2"]),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "geometry": geometry,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": [feature]}, fh)
    n = sum(len(ring) for poly in (geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]) for ring in poly)
    print(f"wrote {args.out}: {geometry['type']}, {n} vertices, city {row['city_km2']} km2, polygon {row['polygon_km2']} km2, buffer {args.buffer_m} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
