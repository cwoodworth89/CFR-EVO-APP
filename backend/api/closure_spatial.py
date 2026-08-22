"""PostGIS spatial resolution for road closures.

Replaces the hand-rolled geometry that predated the transportation-layer import:
a ray-casting `point_in_polygon`, zone polygons loaded from `zones.json` off disk, a
latitude threshold standing in for the Fraser River, and a city-name blocklist.

All of it is now answered by the authoritative municipal layers already in PostGIS
(`public.zones`, `public.city_boundary`), per CLAUDE.md §6.2.
"""

import logging
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def build_geojson_geometry(points: List[List[float]]) -> Optional[dict]:
    """Builds a GeoJSON geometry from [lat, lng] points.

    Returns None when there is nothing usable. Callers must drop the closure rather
    than substituting a placeholder location (CLAUDE.md §6.1) -- a closure pinned to a
    default coordinate lands in whichever zone that point falls in and is then filed
    under the wrong hall.
    """
    usable = [
        p for p in (points or [])
        if p and len(p) >= 2 and p[0] is not None and p[1] is not None
    ]
    if not usable:
        return None

    if len(usable) == 1:
        lat, lng = usable[0][0], usable[0][1]
        return {"type": "Point", "coordinates": [lng, lat]}

    return {"type": "LineString", "coordinates": [[p[1], p[0]] for p in usable]}


def is_within_city(db: Session, geojson: dict) -> bool:
    """True when the geometry intersects the Coquitlam municipal boundary.

    Replaces the previous `pt[0] < 49.231` Fraser River latitude test and the
    ["surrey", "delta", "langley", ...] description blocklist, neither of which
    described the actual boundary.
    """
    if not geojson:
        return False
    try:
        row = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM public.city_boundary cb
                WHERE ST_Intersects(cb.geom, ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326))
            ) AS inside
        """), {"gj": _dumps(geojson)}).mappings().fetchone()
        return bool(row and row["inside"])
    except Exception as e:
        logger.warning(f"City boundary check failed: {e}")
        return False


def resolve_zones_and_hall(db: Session, geojson: dict) -> Tuple[List[str], Optional[str], Optional[str]]:
    """Resolves (affected_zones, primary_zone, hall_id) for a closure geometry.

    Every zone the geometry touches is returned, ordered numerically. The primary zone
    and hall come from the zone containing the geometry's centroid, which is stable for
    a linear closure spanning several zones.

    Returns ([], None, None) when the geometry touches no zone -- the caller drops it.
    """
    if not geojson:
        return [], None, None

    gj = _dumps(geojson)
    try:
        rows = db.execute(text("""
            SELECT z.map_name AS zone_id, z.hall_id
            FROM public.zones z
            WHERE ST_Intersects(z.geom, ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326))
        """), {"gj": gj}).mappings().all()

        affected = sorted(
            {str(r["zone_id"]) for r in rows if r["zone_id"] is not None},
            key=lambda x: int(x) if x.isdigit() else 10**9,
        )
        if not affected:
            return [], None, None

        primary = db.execute(text("""
            SELECT z.map_name AS zone_id, z.hall_id
            FROM public.zones z
            WHERE ST_Contains(
                z.geom,
                ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326))
            )
            LIMIT 1
        """), {"gj": gj}).mappings().fetchone()

        if primary:
            return affected, str(primary["zone_id"]), primary["hall_id"]

        # Centroid fell outside every zone (possible on a concave boundary):
        # fall back to the lowest-numbered zone actually touched.
        fallback = next((r for r in rows if str(r["zone_id"]) == affected[0]), None)
        return affected, affected[0], (fallback["hall_id"] if fallback else None)

    except Exception as e:
        logger.warning(f"Zone resolution failed: {e}")
        return [], None, None


def _dumps(geojson: dict) -> str:
    import json
    return json.dumps(geojson)
