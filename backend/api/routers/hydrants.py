"""
Hydrant Endpoints for CFR EVO API Gateway.

Serves the municipal hydrant inventory from public.hydrants, which replaced the
browser-fetched frontend/public/data/hydrants.json cache.

flow_class is nullable and is returned as null when the City of Coquitlam records no
NFPA 291 rating (typical for private hydrants). It is never defaulted -- a previous sync
substituted "AA", the highest class, which presented unrated hydrants to crews as the
best available supply. Clients must render null as an explicit UNRATED warning
(CLAUDE.md §6.1).
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from backend.api.database import get_db
except ModuleNotFoundError:
    from api.database import get_db

router = APIRouter(prefix="/api/hydrants", tags=["hydrants"])

# 60s in-memory cache: the inventory changes only on a sync run, and the kiosk map
# re-queries on pan/zoom.
_cache = {"data": None, "ts": 0.0}
_CACHE_TTL_SECONDS = 60.0


def invalidate_hydrants_cache():
    _cache["data"] = None
    _cache["ts"] = 0.0
    logging.info("Hydrants in-memory cache invalidated.")


@router.get("")
def get_hydrants(
    db: Session = Depends(get_db),
    bbox: Optional[str] = Query(
        None,
        description="Optional viewport filter as 'min_lng,min_lat,max_lng,max_lat'.",
    ),
):
    """Returns hydrants. Unrated hydrants carry flowClass: null -- render as UNRATED."""
    import time

    if bbox:
        try:
            min_lng, min_lat, max_lng, max_lat = (float(v) for v in bbox.split(","))
        except (ValueError, TypeError):
            logging.warning(f"Ignoring malformed hydrant bbox: {bbox!r}")
            bbox = None

    if not bbox and _cache["data"] is not None and (time.time() - _cache["ts"]) < _CACHE_TTL_SECONDS:
        return _cache["data"]

    sql = """
        SELECT object_id, gis_id, status, flow_class, lat, lng, zone_id
        FROM public.hydrants
    """
    params = {}
    if bbox:
        sql += """
        WHERE geom && ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326)
        """
        params = {"min_lng": min_lng, "min_lat": min_lat,
                  "max_lng": max_lng, "max_lat": max_lat}

    rows = db.execute(text(sql), params).mappings().all()

    payload = [
        {
            "id": r["object_id"],
            "gisId": r["gis_id"],
            "status": r["status"],
            # null when unrated at source. Do not coerce to a class or empty string.
            "flowClass": r["flow_class"],
            "lat": r["lat"],
            "lng": r["lng"],
            "zoneId": r["zone_id"],
        }
        for r in rows
    ]

    if not bbox:
        _cache["data"] = payload
        _cache["ts"] = time.time()

    return payload


@router.get("/stats")
def get_hydrant_stats(db: Session = Depends(get_db)):
    """Rated vs unrated counts by status. Useful for spotting a sync that fabricated values."""
    rows = db.execute(text("""
        SELECT status,
               count(*) AS total,
               count(flow_class) AS rated,
               count(*) - count(flow_class) AS unrated
        FROM public.hydrants
        GROUP BY status ORDER BY total DESC
    """)).mappings().all()
    return {
        "by_status": [dict(r) for r in rows],
        "total": sum(r["total"] for r in rows),
        "unrated": sum(r["unrated"] for r in rows),
    }
