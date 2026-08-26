#!/usr/bin/env python3
"""
export_tile_coverage.py
=======================
Regenerates `backend/data/gis/coquitlam_tile_coverage.geojson` from
`public.city_boundary` — the polygon that decides which map tiles get crawled.

Run this if the municipal boundary changes. **Do not hand-edit the GeoJSON.**
Hand-picked map bounds are exactly what caused punch-list #40: a constant named
`COQUITLAM_MIN_LON = -122.865` that was 0.028 deg short in the west and left
18,713 parcels with no basemap above zoom 16.

Why a polygon rather than a bounding box: Coquitlam is an L wrapped around Port
Moody and Port Coquitlam. Its bbox is 289.3 km2 against a real area of 129.7 km2,
so a box crawl spends 55% of its requests on Belcarra, Anmore, Pitt Meadows and
the northern watershed. Measured over z12-20: 778,515 box tiles vs 430,845 that
touch the city.

Usage:
    python backend/scripts/export_tile_coverage.py
    python backend/scripts/export_tile_coverage.py --buffer-m 1500
"""
import os
import json
import argparse
import logging

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("export_tile_coverage")

DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "gis", "coquitlam_tile_coverage.geojson"
)

# 1 km beyond the municipal line, for border and mutual-aid response.
DEFAULT_BUFFER_M = 1000

# ~60 m. Well under one z20 tile (~30 m at this latitude) after the buffer has
# already pushed the edge out by 1 km. This polygon SELECTS TILES; it is never
# used for a spatial decision about a call, so edge precision costs nothing
# operational. Keeping it small (55 points) keeps the per-tile test cheap.
DEFAULT_SIMPLIFY_DEG = 0.0008


def main() -> int:
    ap = argparse.ArgumentParser(description="Export the tile-coverage polygon from public.city_boundary")
    ap.add_argument("--database-url", default=os.environ.get("DATABASE_URL"),
                    help="PostGIS connection string (default: $DATABASE_URL)")
    ap.add_argument("--buffer-m", type=float, default=DEFAULT_BUFFER_M)
    ap.add_argument("--simplify-deg", type=float, default=DEFAULT_SIMPLIFY_DEG)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    if not args.database_url:
        logger.error("No DATABASE_URL. Pass --database-url or set the environment variable.")
        return 2

    engine = create_engine(args.database_url)
    sql = text("""
        SELECT ST_AsGeoJSON(g, 6) AS gj,
               ST_NPoints(g) AS pts,
               ST_Area(g::geography) / 1e6 AS area_km2,
               ST_Area(ST_Envelope(g)::geography) / 1e6 AS bbox_km2
        FROM (
            SELECT ST_Simplify(
                       ST_Buffer(geom::geography, :buf)::geometry,
                       :simp
                   ) AS g
            FROM public.city_boundary
        ) q;
    """)

    with engine.connect() as conn:
        row = conn.execute(sql, {"buf": args.buffer_m, "simp": args.simplify_deg}).fetchone()

    if row is None:
        logger.error("public.city_boundary returned no rows. Nothing exported.")
        return 1

    geometry = json.loads(row.gj)
    doc = {
        "type": "FeatureCollection",
        "name": "coquitlam_tile_coverage",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "metadata": {
            "source": "public.city_boundary (City of Coquitlam Open Data)",
            "generated_by": "backend/scripts/export_tile_coverage.py",
            "derivation": f"ST_Simplify(ST_Buffer(geom::geography, {args.buffer_m})::geometry, {args.simplify_deg})",
            "buffer_m": args.buffer_m,
            "buffer_rationale": "border and mutual-aid response outside the municipal line",
            "simplify_deg": args.simplify_deg,
            "simplify_rationale": "selects tiles only; never used for a spatial decision about a call",
            "points": int(row.pts),
            "area_km2": round(float(row.area_km2), 1),
            "bbox_area_km2": round(float(row.bbox_km2), 1),
            "note": "Generated file. Do not hand-edit - re-run the script instead.",
        },
        "features": [{
            "type": "Feature",
            "properties": {"name": f"Coquitlam + {int(args.buffer_m)}m"},
            "geometry": geometry,
        }],
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)

    pct = 100.0 * float(row.area_km2) / float(row.bbox_km2)
    logger.info(f"Wrote {args.out}")
    logger.info(f"  {int(row.pts)} points, {float(row.area_km2):.1f} km2 "
                f"({pct:.1f}% of its {float(row.bbox_km2):.1f} km2 bounding box)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
