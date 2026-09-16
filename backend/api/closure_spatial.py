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

# Metres outward from public.city_boundary within which a closure is kept, and within which the
# nearest response zone is borrowed when no zone polygon touches it (punch list #92).
# REUSED, not newly ruled: the operator's figure for the routing polygon, 2026-09-09 ("use the
# city boundary + 100m", backend/scripts/export_routing_polygon.py). Measured 2026-09-16 on the
# Municipal 511 pull: the City-published closures the unbuffered tests dropped lay 0.1-7.8 m
# from the boundary line and 1.5-27.3 m from the nearest zone, because boundary roads (North
# Rd, Westwood St, Victoria Dr, the Mary Hill Bypass) run on the boundary line itself and the
# zone layer's outer edge does not follow the boundary. The buffer admitted those seven and no
# other record in that pull.
CLOSURE_BOUNDARY_BUFFER_M = 100


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
    """True when the geometry comes within CLOSURE_BOUNDARY_BUFFER_M of the municipal boundary.

    Replaces the previous `pt[0] < 49.231` Fraser River latitude test and the
    ["surrey", "delta", "langley", ...] description blocklist, neither of which
    described the actual boundary.

    Buffered since #92: a closure on a boundary road (North Rd is the Burnaby line) falls a
    few metres either side of the line by construction, and the plain intersection dropped
    City-published closures on those roads. Closures only -- the kiosk's out-of-city card
    uses SpatialQueryEngine.is_within_city (ST_Covers, unbuffered) and is not affected.
    """
    if not geojson:
        return False
    try:
        row = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM public.city_boundary cb
                WHERE ST_DWithin(cb.geom::geography,
                                 ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)::geography, :m)
            ) AS inside
        """), {"gj": _dumps(geojson), "m": CLOSURE_BOUNDARY_BUFFER_M}).mappings().fetchone()
        return bool(row and row["inside"])
    except Exception as e:
        logger.warning(f"City boundary check failed: {e}")
        return False


def resolve_zones_and_hall(db: Session, geojson: dict) -> Tuple[List[str], Optional[str], Optional[str]]:
    """Resolves (affected_zones, primary_zone, hall_id) for a closure geometry.

    Every zone the geometry touches is returned, ordered numerically. The primary zone
    and hall come from the zone containing the geometry's centroid, which is stable for
    a linear closure spanning several zones.

    When no zone polygon touches the geometry, the nearest zone within
    CLOSURE_BOUNDARY_BUFFER_M is used instead (#92: the zone layer's outer edge stops short of
    the city boundary along boundary roads). Returns ([], None, None) when no zone is within
    that distance either; the caller keeps the closure, and the kiosk groups it as OTHER.
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
            nearest = db.execute(text("""
                SELECT z.map_name AS zone_id, z.hall_id
                FROM public.zones z
                WHERE ST_DWithin(z.geom::geography,
                                 ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)::geography, :m)
                ORDER BY ST_Distance(z.geom::geography,
                                     ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)::geography)
                LIMIT 1
            """), {"gj": gj, "m": CLOSURE_BOUNDARY_BUFFER_M}).mappings().fetchone()
            if not nearest or nearest["zone_id"] is None:
                return [], None, None
            return [str(nearest["zone_id"])], str(nearest["zone_id"]), nearest["hall_id"]

        # public.zone_for_point is the canonical containment definition. This used
        # ST_Contains directly, so a closure whose centroid fell on a road -- which is
        # most of them, being road closures -- missed the primary lookup and fell through
        # to the fallback below.
        primary = db.execute(text("""
            SELECT z.map_name AS zone_id, z.hall_id
            FROM public.zones z
            WHERE z.map_name = public.zone_for_point(
                ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)))
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
