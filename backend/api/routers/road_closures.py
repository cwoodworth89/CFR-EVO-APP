"""
Live Road Closures API Pipeline & In-Memory TTL Cache for CFR EVO API Gateway.
Provides active road closure data, manual differential sync triggers, and background staleness daemon.
"""
import time
import threading
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

try:
    from backend.api.database import get_db, SessionLocal
    from backend.api.models import RoadClosureModel
    from backend.api.road_closure_service import sync_road_closures_to_db, check_and_sync_if_stale
except ModuleNotFoundError:
    from api.database import get_db, SessionLocal
    from api.models import RoadClosureModel
    from api.road_closure_service import sync_road_closures_to_db, check_and_sync_if_stale

router = APIRouter(prefix="/api/road-closures", tags=["road-closures"])

# High-performance in-memory TTL cache (<5ms response time)
_ROAD_CLOSURES_CACHE = {
    "data": None,
    "expires_at": 0.0,
    "lock": threading.Lock()
}


def invalidate_road_closures_cache():
    """Invalidates the in-memory road closures cache."""
    with _ROAD_CLOSURES_CACHE["lock"]:
        _ROAD_CLOSURES_CACHE["expires_at"] = 0.0
        _ROAD_CLOSURES_CACHE["data"] = None
    logging.info("Road closures in-memory cache invalidated.")


class PythonGeometryDecoder:
    """Decodes polyline-encoded geometry strings into latitude/longitude point lists."""
    def __init__(self, encoded: str):
        self.points = []
        self.index = 0
        if not encoded:
            return
        u = 0
        c = len(encoded)
        f = 0
        e = 0
        while u < c:
            r = 0
            t = 0
            while True:
                i = ord(encoded[u]) - 63
                u += 1
                t |= (i & 31) << r
                r += 5
                if i < 32:
                    break
            o = ~(t >> 1) if (t & 1) != 0 else (t >> 1)
            f += o

            r = 0
            t = 0
            while True:
                i = ord(encoded[u]) - 63
                u += 1
                t |= (i & 31) << r
                r += 5
                if i < 32:
                    break
            s = ~(t >> 1) if (t & 1) != 0 else (t >> 1)
            e += s

            self.points.append([f / 1e5, e / 1e5])

    def get_n_points(self, n: int):
        pts = self.points[self.index : self.index + n]
        self.index += n
        return pts


@router.get("")
def get_road_closures(db: Session = Depends(get_db)):
    """Returns active road closures with a high-performance 60-second in-memory TTL cache (<5ms response time)."""
    now = time.time()
    # Fast lock-free read path
    cached_data = _ROAD_CLOSURES_CACHE["data"]
    if cached_data is not None and now < _ROAD_CLOSURES_CACHE["expires_at"]:
        return cached_data

    with _ROAD_CLOSURES_CACHE["lock"]:
        # Re-check under lock
        now = time.time()
        if _ROAD_CLOSURES_CACHE["data"] is not None and now < _ROAD_CLOSURES_CACHE["expires_at"]:
            return _ROAD_CLOSURES_CACHE["data"]

        records = db.query(RoadClosureModel).filter(
            RoadClosureModel.active == True
        ).order_by(desc(RoadClosureModel.updated_at)).all()

        results = []
        for r in records:
            geom = r.geometry or {}
            raw_coords = r.coordinates or [49.28, -122.80]
            try:
                parsed_coords = [float(c) for c in raw_coords]
            except (ValueError, TypeError):
                parsed_coords = [49.28, -122.80]

            polyline = []
            if geom.get("type") == "LineString":
                raw_poly = geom.get("coordinates", [])
                polyline = [[float(pt[0]), float(pt[1])] for pt in raw_poly if isinstance(pt, (list, tuple)) and len(pt) >= 2]

            results.append({
                "id": r.closure_id,
                "headline": r.headline or r.street_name,
                "street": r.street_name,
                "severity": r.closure_type or "FULL_CLOSURE",
                "emergencyAccess": r.emergency_access,
                "description": r.description or "Active traffic event.",
                "coordinates": parsed_coords,
                "polyline": polyline,
                "source": r.source,
                "zoneId": r.zone_id,
                "affectedZones": r.affected_zones or ([r.zone_id] if r.zone_id else []),
                "startDate": r.start_time.isoformat() if r.start_time else None,
                "endDate": r.end_time.isoformat() if r.end_time else None
            })

        _ROAD_CLOSURES_CACHE["data"] = results
        _ROAD_CLOSURES_CACHE["expires_at"] = time.time() + 60.0
        return results


@router.post("/sync")
def trigger_road_closure_sync(db: Session = Depends(get_db)):
    """Manual admin endpoint to trigger immediate differential road closure sync."""
    try:
        count = sync_road_closures_to_db(db)
        invalidate_road_closures_cache()
        return {
            "status": "success",
            "syncedCount": count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logging.error(f"Manual road closure sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def run_periodic_road_closure_sync():
    """Background daemon worker: checks database staleness and performs daily differential road closure sync."""
    while True:
        try:
            db = SessionLocal()
            try:
                synced = check_and_sync_if_stale(db, max_age_seconds=86400)
                if synced:
                    invalidate_road_closures_cache()
            finally:
                db.close()
        except Exception as e:
            logging.error(f"Error in periodic road closure sync daemon: {e}")
        # Sleep for 1 hour between staleness checks
        time.sleep(3600)
