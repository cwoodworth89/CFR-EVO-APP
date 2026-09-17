"""
Live Road Closures API Pipeline & In-Memory TTL Cache for CFR EVO API Gateway.
Provides active road closure data, manual differential sync triggers, and background staleness daemon.
"""
import math
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
    from backend.api.road_closure_service import (
        sync_road_closures_to_db, check_and_sync_if_stale, read_sync_status,
        SYNC_RESULT_NOT_NEEDED, SYNC_SUCCEEDED,
    )
except ModuleNotFoundError:
    from api.database import get_db, SessionLocal
    from api.models import RoadClosureModel
    from api.road_closure_service import (
        sync_road_closures_to_db, check_and_sync_if_stale, read_sync_status,
        SYNC_RESULT_NOT_NEEDED, SYNC_SUCCEEDED,
    )

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


DRIVEBC_FEED = "DriveBC Open511"
MUNICIPAL_FEED = "Municipal 511"


def _feed_of(source):
    """The feed a closure came from. DriveBC rows carry source "DriveBC Open511"; Municipal
    511 rows carry the issuing organisation instead ("City of Coquitlam", "BC MOTI Gateway"),
    so anything else is Municipal 511 -- the only other feed road_closure_service ingests."""
    return DRIVEBC_FEED if source == DRIVEBC_FEED else MUNICIPAL_FEED


def _parse_closure_point(raw):
    """A closure's stored [lat, lng] as floats, or None when it is not a usable point.

    Unusable means missing, not exactly two values, not numeric, NaN/infinite, or 0 --
    CLAUDE.md §5 treats null, NaN and 0 alike as an unresolved location.
    """
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return None
    try:
        lat, lng = float(raw[0]), float(raw[1])
    except (ValueError, TypeError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lng)) or lat == 0 or lng == 0:
        return None
    return [lat, lng]


@router.get("")
def get_road_closures(db: Session = Depends(get_db)):
    """Active road closures, and the outcome of the last attempt to sync them.

    Per closure, since #91: `id` is always the feed's id (records without one are skipped at
    ingestion and counted in `sync.skipped`); `rowId` is the database row, for keys and
    selection only; `severity` and `emergencyAccess` are null when the feed stated none;
    `street`, `headline` and `description` are null when the feed sent nothing.
    DriveBC closures also carry `roadState`, `roadDirection` and `feedSeverity` (Open511 v1.0
    values or null); emergencyAccess is derived from roadState/roadDirection, never severity.

    Shape (changed 2026-09-16, punch list #89 -- this used to be the bare array):

        {
          "closures": [ ...unchanged closure objects... ],
          "sync": {
            "outcome": "NOT_ATTEMPTED" | "SUCCEEDED" | "FAILED",
            "lastAttemptAt": ISO-8601 string | null,
            "error": string | null,
            "sources": {"<feed name>": {"reached": bool, "error": string,
                                        "skippedNoId": int}} | null,
            "skipped": {"count": int, "bySource": {"<feed name>": int}} | null
          }
        }

    `sync.outcome == "FAILED"` is what raises the kiosk's warning flag, and it is what
    makes an empty list readable: no flag and no closures means the source was reached and
    the City has none; a flag and no closures means we could not reach it.

    Both parts are cached together for 60s so the flag can never be served from a
    different attempt than the list beside it.
    """
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
        # Closures served with no stated severity, per feed, for one summary line (below).
        no_severity = {DRIVEBC_FEED: 0, MUNICIPAL_FEED: 0}
        for r in records:
            geom = r.geometry or {}
            # No default coordinate (CLAUDE.md §5, §6.1; punch list #90). This used to fall
            # back to a hardcoded [49.28, -122.80] with no source, so a record with missing
            # or malformed coordinates was drawn as an ordinary closure near Coquitlam
            # Centre. It now goes out as null, and the failure is logged at ERROR with the
            # closure id so it cannot pass unnoticed. The kiosk still lists the closure;
            # RoadClosureMarker draws it from its own polyline or not at all.
            parsed_coords = _parse_closure_point(r.coordinates)
            if parsed_coords is None:
                logging.error(
                    "Road closure %s has no usable coordinates (stored value %r); "
                    "returned with coordinates=null, not drawn at a default point.",
                    r.closure_id, r.coordinates,
                )

            polyline = []
            if geom.get("type") == "LineString":
                raw_poly = geom.get("coordinates", [])
                polyline = [[float(pt[0]), float(pt[1])] for pt in raw_poly if isinstance(pt, (list, tuple)) and len(pt) >= 2]

            # Unknown severity is served as null in both fields, never defaulted: the
            # old `or "FULL_CLOSURE"` drew an unknown as the most severe tier (punch list
            # #91). The kiosk shows N/A in the access box. Counted, not logged per record:
            # see the summary line after the loop. A stated ALL_LANES_OPEN is not a gap.
            if r.emergency_access is None:
                no_severity[_feed_of(r.source)] += 1

            results.append({
                # rowId is this database's row, for React keys and selection only; never
                # display it as the feed's id.
                "id": r.closure_id,
                "rowId": r.id,
                "headline": r.headline or r.street_name,
                "street": r.street_name,
                "severity": r.closure_type,
                "emergencyAccess": r.emergency_access,
                # emergencyAccess: "NO_ACCESS" | "ACCESS_ONLY" | "CAUTION" | "INFO" | null
                # (null = N/A, the feed stated nothing usable). INFO since 2026-09-17 (#91).
                # DriveBC only; null for Municipal 511. roadState is the stated restriction
                # (ALL_LANES_OPEN is served with emergencyAccess "INFO"); null means unknown.
                "roadState": r.road_state,
                "roadDirection": r.road_direction,
                "feedSeverity": r.feed_severity,
                # No placeholder text: null when the feed sent none (#91); kiosk shows "--".
                "description": r.description,
                "coordinates": parsed_coords,
                "polyline": polyline,
                "source": r.source,
                "zoneId": r.zone_id,
                "affectedZones": r.affected_zones or ([r.zone_id] if r.zone_id else []),
                "startDate": r.start_time.isoformat() if r.start_time else None,
                "endDate": r.end_time.isoformat() if r.end_time else None
            })

        # One line per uncached serve, not one per closure (operator ruling 2026-09-16, #91:
        # 141 ERROR lines in three minutes buried the per-record lines an admin needs -- the
        # id-less skip and #90's unusable coordinate, which stay ERROR per record).
        # WARNING, not ERROR: on this feed an unstated severity is expected and known
        # (Municipal 511 states a type on almost none of its records), so it is a condition
        # to watch, not a defect to act on. Logged only when the count is non-zero.
        missing = sum(no_severity.values())
        if missing:
            logging.warning(
                "%d of %d closures served with no stated severity (%s: %d, %s: %d)",
                missing, len(results),
                MUNICIPAL_FEED, no_severity[MUNICIPAL_FEED],
                DRIVEBC_FEED, no_severity[DRIVEBC_FEED],
            )

        payload = {
            "closures": results,
            "sync": read_sync_status(db),
        }

        _ROAD_CLOSURES_CACHE["data"] = payload
        _ROAD_CLOSURES_CACHE["expires_at"] = time.time() + 60.0
        return payload


@router.post("/sync")
def trigger_road_closure_sync(db: Session = Depends(get_db)):
    """Manual admin endpoint to trigger immediate differential road closure sync."""
    try:
        count = sync_road_closures_to_db(db)
        invalidate_road_closures_cache()
        # The call returning normally is not the same as the feeds being reachable: an
        # unreachable feed is caught and swallowed inside the ingestion and yields a count
        # of 0 with no exception. Report what the attempt recorded, not the fact that
        # nothing raised -- "success" with the link down is exactly the plausible wrong
        # answer CLAUDE.md 6.1 is about.
        status = read_sync_status(db)
        return {
            "status": "success" if status["outcome"] == SYNC_SUCCEEDED else "failed",
            "syncedCount": count,
            "sync": status,
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
                result = check_and_sync_if_stale(db, max_age_seconds=86400)
                # Three values now, and all three are truthy strings -- test the value,
                # never the truthiness (punch list #89). A failed attempt invalidates the
                # cache too: the flag it just raised has to reach the kiosk on the next
                # poll, not up to 60s after someone else happens to clear the cache.
                if result != SYNC_RESULT_NOT_NEEDED:
                    invalidate_road_closures_cache()
            finally:
                db.close()
        except Exception as e:
            logging.error(f"Error in periodic road closure sync daemon: {e}")
        # Sleep for 1 hour between staleness checks
        time.sleep(3600)
