import os
import json
import re
import math
import logging
import urllib.request
from datetime import datetime, timezone
from sqlalchemy.orm import Session

try:
    from backend.api.models import RoadClosureModel
except ModuleNotFoundError:
    from api.models import RoadClosureModel

logger = logging.getLogger(__name__)

# --- RAY-CASTING POINT-IN-POLYGON & EMERGENCY ZONE MATCHING ---

_ZONES_CACHE = []

def _load_emergency_zones():
    global _ZONES_CACHE
    if _ZONES_CACHE:
        return _ZONES_CACHE

    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "frontend", "public", "data", "zones.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "zones.json"),
        "frontend/public/data/zones.json"
    ]

    for p in possible_paths:
        abs_p = os.path.abspath(p)
        if os.path.exists(abs_p):
            try:
                with open(abs_p, "r", encoding="utf-8") as f:
                    _ZONES_CACHE = json.load(f)
                logger.info(f"Loaded {len(_ZONES_CACHE)} Emergency Zone polygons for spatial matching.")
                return _ZONES_CACHE
            except Exception as e:
                logger.warning(f"Failed to load zones from {abs_p}: {e}")

    logger.error("Could not locate zones.json for spatial enrichment.")
    return []

def point_in_polygon(lng: float, lat: float, polygon_coords: list) -> bool:
    """Ray-casting algorithm to test if (lng, lat) lies inside polygon_coords."""
    inside = False
    n = len(polygon_coords)
    if n < 3:
        return False
    p1x, p1y = polygon_coords[0]
    for i in range(n + 1):
        p2x, p2y = polygon_coords[i % n]
        if lat > min(p1y, p2y):
            if lat <= max(p1y, p2y):
                if lng <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or lng <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def resolve_affected_zones(pts: list) -> list:
    """
    Given a list of points (each [lat, lng] or [lng, lat]) for a point or polyline hazard,
    returns a sorted list of unique zone_id strings touched by the hazard geometry.
    """
    zones = _load_emergency_zones()
    affected = set()
    for pt in pts:
        val1, val2 = pt[0], pt[1]
        # If val1 is latitude (~49) and val2 is longitude (~-122)
        if 40 <= val1 <= 60 and -130 <= val2 <= -110:
            lat, lng = val1, val2
        else:
            lng, lat = val1, val2

        for z in zones:
            coords = z.get("geometry", {}).get("coordinates", [])
            if coords and point_in_polygon(lng, lat, coords[0]):
                affected.add(str(z.get("zone_id")))

    return sorted(list(affected), key=lambda x: int(x) if x.isdigit() else x)

class PythonGeometryDecoder:
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


# --- LIVE INGESTION & POSTGRESQL SYNC PIPELINE ---

def sync_road_closures_to_db(db: Session):
    """
    Fetches DriveBC and Municipal 511 feeds server-side,
    applies spatial Ray-Casting PIP to verify Emergency Zone containment,
    enriches with zone_id and affected_zones array, and upserts into PostgreSQL road_closures table.
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    now_utc = datetime.now(timezone.utc)
    raw_notices = []

    # 1. Fetch DriveBC Open511
    try:
        req = urllib.request.Request("https://api.open511.gov.bc.ca/events?format=json&limit=100", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            db_data = json.loads(resp.read().decode('utf-8'))

        events = db_data.get('events', [])
        for evt in events:
            geog = evt.get('geography', {})
            coords = geog.get('coordinates', [])
            t = geog.get('type')
            if t == 'Point':
                pts = [coords]
            elif t == 'LineString':
                pts = coords
            else:
                continue

            lat, lng = 49.28, -122.80
            polyline = []
            if t == 'Point':
                lng, lat = coords[0], coords[1]
            elif t == 'LineString':
                polyline = [[pt[1], pt[0]] for pt in coords]
                mid = len(coords) // 2
                lng, lat = coords[mid][0], coords[mid][1]

            # Strict geographic checks: Exclude events south of Fraser River (lat < 49.231) or referencing neighboring cities
            all_pts = polyline if polyline else [[lat, lng]]
            if any(pt[0] < 49.231 for pt in all_pts):
                continue

            text_content = f"{evt.get('headline', '')} {evt.get('description', '')} {evt.get('road_name', '')}".lower()
            if any(city in text_content for city in ["surrey", "delta", "langley", "richmond", "pattullo"]):
                continue

            # Perform PIP check across all vertices
            affected_zones = resolve_affected_zones(all_pts)
            if not affected_zones:
                continue  # Skip items outside Coquitlam emergency zones!

            primary_zone = affected_zones[0]

            sev = (evt.get('severity') or 'MINOR').upper()
            emergency_access = 'NO_ACCESS' if sev == 'MAJOR' else 'CAUTION'

            start_dt = None
            end_dt = None
            sched = evt.get('schedule', {})
            if sched and isinstance(sched.get('intervals'), list) and len(sched['intervals']) > 0:
                parts = sched['intervals'][0].split('/')
                if len(parts) == 2:
                    try:
                        start_dt = datetime.fromisoformat(parts[0].replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(parts[1].replace('Z', '+00:00'))
                    except Exception:
                        pass
            elif sched and isinstance(sched.get('recurring_schedules'), list) and len(sched['recurring_schedules']) > 0:
                rs = sched['recurring_schedules'][0]
                if rs.get('start_date'):
                    try:
                        start_dt = datetime.fromisoformat(f"{rs['start_date']}T{rs.get('daily_start_time', '00:00')}:00+00:00")
                    except Exception:
                        pass
                if rs.get('end_date'):
                    try:
                        end_dt = datetime.fromisoformat(f"{rs['end_date']}T{rs.get('daily_end_time', '23:59')}:59+00:00")
                    except Exception:
                        pass

            if not start_dt and evt.get('created'):
                try:
                    start_dt = datetime.fromisoformat(evt['created'].replace('Z', '+00:00'))
                except Exception:
                    pass

            raw_notices.append({
                "closure_id": str(evt.get('id', f"db_{len(raw_notices)}")),
                "street_name": (evt.get('road_name') or "Regional Corridor").strip(),
                "source": "DriveBC Open511",
                "closure_type": "FULL_CLOSURE" if sev == "MAJOR" else "LANE_RESTRICTION",
                "emergency_access": emergency_access,
                "headline": (evt.get('headline') or "TRAFFIC ALERT").strip(),
                "description": (evt.get('description') or "Active traffic event.").strip(),
                "geometry": geog,
                "coordinates": [lat, lng],
                "zone_id": primary_zone,
                "affected_zones": affected_zones,
                "start_time": start_dt,
                "end_time": end_dt
            })
    except Exception as e:
        logger.warning(f"DriveBC ingestion warning: {e}")

    # 2. Fetch Municipal 511
    try:
        req_page = urllib.request.Request("https://bc.municipal511.ca/?municipality=coquitlam", headers=headers)
        with urllib.request.urlopen(req_page, timeout=5) as resp:
            html = resp.read().decode('utf-8')

        matches = re.findall(r'"(jsonData\d*\.txt)"\s*:\s*"([^"]+)"', html)
        if not matches:
            matches = [("jsonData0.txt", "jsonData0.txt")]

        for _, filename in matches:
            try:
                req_data = urllib.request.Request(f"https://bc.municipal511.ca/Dynamic/{filename}", headers=headers)
                with urllib.request.urlopen(req_data, timeout=5) as resp:
                    muni_data = json.loads(resp.read().decode('utf-8'))

                issues = muni_data.get('Issues', [])
                decoder = PythonGeometryDecoder(muni_data.get('CoordsEncoded', ''))

                for issue in issues:
                    geoms = issue.get('Geometry', [])
                    for geom_idx, geom in enumerate(geoms):
                        num_points = geom.get('NumPoints', 0)
                        path_pts = decoder.get_n_points(num_points)

                        lat, lng = 49.28, -122.80
                        polyline = []
                        if len(path_pts) == 1:
                            lat, lng = path_pts[0][0], path_pts[0][1]
                        elif len(path_pts) > 1:
                            polyline = path_pts
                            mid = len(path_pts) // 2
                            lat, lng = path_pts[mid][0], path_pts[mid][1]
                        else:
                            continue

                        # Perform PIP check across all vertices
                        all_pts = polyline if polyline else [[lat, lng]]
                        affected_zones = resolve_affected_zones(all_pts)
                        if not affected_zones:
                            continue  # Skip items outside Coquitlam emergency zones!

                        primary_zone = affected_zones[0]
                        rct = geom.get('MarkerInfo', {}).get('RoadClosureType', 0)
                        highest_bit = 0
                        if rct > 0:
                            highest_bit = 1 << int(math.log2(rct))

                        desc = issue.get('Description', {})
                        desc_lower = (desc.get('BaseDescription') or "").lower()
                        headline_lower = (desc.get('Headline') or "").lower()
                        is_closed = "road closed" in desc_lower or "full closure" in desc_lower or "road closed" in headline_lower or "full closure" in headline_lower

                        emergency_access = "CAUTION"
                        sev = "MINOR"
                        if highest_bit == 262144:
                            emergency_access = "NO_ACCESS"
                            sev = "MAJOR"
                        elif highest_bit in (65536, 32768, 16384) or is_closed:
                            emergency_access = "ACCESS_ONLY"
                            sev = "MODERATE"

                        start_dt = None
                        end_dt = None
                        if desc.get('ProposedStartTimeUtcEpochMillis'):
                            start_dt = datetime.fromtimestamp(desc['ProposedStartTimeUtcEpochMillis'] / 1000, tz=timezone.utc)
                        if desc.get('ProposedEndTimeUtcEpochMillis'):
                            end_dt = datetime.fromtimestamp(desc['ProposedEndTimeUtcEpochMillis'] / 1000, tz=timezone.utc)

                        loc_name = geom.get('MarkerInfo', {}).get('LocationName') or issue.get('TableViewInfo', {}).get('Location') or desc.get('BaseLocationDescription') or "Local Road"
                        headline_text = desc.get('Headline') or loc_name
                        desc_text = (desc.get('BaseDescription') or "").strip() or "Local road construction or restriction."

                        geom_json = {
                            "type": "LineString" if len(polyline) > 1 else "Point",
                            "coordinates": polyline if len(polyline) > 1 else [lng, lat]
                        }

                        raw_notices.append({
                            "closure_id": f"muni_{issue.get('IssueId')}_{geom_idx}",
                            "street_name": loc_name.strip(),
                            "source": issue.get('Source') or "City of Coquitlam",
                            "closure_type": "FULL_CLOSURE" if emergency_access == "NO_ACCESS" else "LANE_RESTRICTION",
                            "emergency_access": emergency_access,
                            "headline": headline_text.strip(),
                            "description": desc_text.strip(),
                            "geometry": geom_json,
                            "coordinates": [lat, lng],
                            "zone_id": primary_zone,
                            "affected_zones": affected_zones,
                            "start_time": start_dt,
                            "end_time": end_dt
                        })
            except Exception as chunk_err:
                logger.warning(f"Municipal 511 chunk parse warning: {chunk_err}")
    except Exception as e:
        logger.warning(f"Municipal 511 ingestion warning: {e}")

    # Upsert notices into PostgreSQL differentials
    if not raw_notices:
        logger.warning("No road closure notices were scraped from remote feeds. Retaining local database cache for offline survival.")
        return 0

    active_closure_ids = set()

    for item in raw_notices:
        cid = item["closure_id"]
        active_closure_ids.add(cid)

        # Check for expired
        end_time = item["end_time"]
        if end_time and end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        
        is_expired = end_time and now_utc > end_time
        is_active = not is_expired

        existing = db.query(RoadClosureModel).filter(RoadClosureModel.closure_id == cid).first()
        if existing:
            existing.street_name = item["street_name"]
            existing.source = item["source"]
            existing.closure_type = item["closure_type"]
            existing.emergency_access = item["emergency_access"]
            existing.headline = item["headline"]
            existing.description = item["description"]
            existing.geometry = item["geometry"]
            existing.coordinates = item["coordinates"]
            existing.zone_id = item["zone_id"]
            existing.affected_zones = item["affected_zones"]
            existing.start_time = item["start_time"]
            existing.end_time = end_time
            existing.active = is_active
            existing.updated_at = now_utc
        else:
            new_record = RoadClosureModel(
                closure_id=cid,
                street_name=item["street_name"],
                source=item["source"],
                closure_type=item["closure_type"],
                emergency_access=item["emergency_access"],
                headline=item["headline"],
                description=item["description"],
                geometry=item["geometry"],
                coordinates=item["coordinates"],
                zone_id=item["zone_id"],
                affected_zones=item["affected_zones"],
                start_time=item["start_time"],
                end_time=end_time,
                active=is_active
            )
            db.add(new_record)

    # Differential cleanup: ONLY deactivate active records if they are no longer in active_closure_ids
    if active_closure_ids:
        db.query(RoadClosureModel).filter(
            RoadClosureModel.active == True,
            ~RoadClosureModel.closure_id.in_(active_closure_ids)
        ).update({RoadClosureModel.active: False}, synchronize_session=False)

    # Also automatically deactivate any records whose end_time has passed
    db.query(RoadClosureModel).filter(
        RoadClosureModel.active == True,
        RoadClosureModel.end_time != None,
        RoadClosureModel.end_time < now_utc
    ).update({RoadClosureModel.active: False}, synchronize_session=False)

    db.commit()
    logger.info(f"Successfully differentials-synced {len(active_closure_ids)} active road closures to database.")
    return len(active_closure_ids)


def check_and_sync_if_stale(db: Session, max_age_seconds: int = 86400) -> bool:
    """
    Checks the last update timestamp of local road closures in PostgreSQL.
    If the database is empty OR the last update is older than max_age_seconds (default 24h),
    triggers a differential sync.
    """
    from sqlalchemy import func
    latest_update = db.query(func.max(RoadClosureModel.updated_at)).scalar()
    active_count = db.query(RoadClosureModel).filter(RoadClosureModel.active == True).count()

    now_utc = datetime.now(timezone.utc)
    
    should_sync = False
    if active_count == 0 or latest_update is None:
        logger.info("Local database contains 0 active road closures. Triggering immediate sync...")
        should_sync = True
    else:
        if latest_update.tzinfo is None:
            latest_update = latest_update.replace(tzinfo=timezone.utc)
        age_seconds = (now_utc - latest_update).total_seconds()
        logger.info(f"Local road closure database last updated {age_seconds:.0f}s ago (threshold: {max_age_seconds}s).")
        if age_seconds > max_age_seconds:
            should_sync = True

    if should_sync:
        try:
            sync_road_closures_to_db(db)
            return True
        except Exception as e:
            logger.error(f"Failed to run scheduled road closure sync: {e}")
            return False
    return False

