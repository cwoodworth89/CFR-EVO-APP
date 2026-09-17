import os
import json
import re
import math
import logging
import urllib.request
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from backend.api.models import RoadClosureModel, RoadClosureSyncStatusModel
except ModuleNotFoundError:
    from api.models import RoadClosureModel, RoadClosureSyncStatusModel

logger = logging.getLogger(__name__)

# Spatial resolution is handled by PostGIS against the authoritative municipal layers
# (public.zones, public.city_boundary). The previous implementation loaded zones.json
# off disk and ran a hand-rolled ray-casting point_in_polygon; it predated the
# transportation-layer import. See backend/api/closure_spatial.py.
try:
    from backend.api.closure_spatial import (
        build_geojson_geometry, closure_city_bbox, is_within_city, resolve_zones_and_hall,
    )
except ModuleNotFoundError:
    from api.closure_spatial import (
        build_geojson_geometry, closure_city_bbox, is_within_city, resolve_zones_and_hall,
    )

import urllib.parse
from concurrent.futures import ThreadPoolExecutor

# DriveBC Open511 events endpoint. `bbox` and `status` are GET /events query parameters in BC's
# OpenAPI spec for the feed (bcgov/api-specs open511_OAS3.json, read 2026-09-16; standards
# index, "Road closure vocabulary"). Measured 2026-09-16 23:41 UTC with the buffered city box:
# 3 events, 5 KB, 0.22 s, including the in-city RIDE-100086 -- where the previous
# `limit=100` request brought 100 province-wide events (233 KB) and missed it (#92).
DRIVEBC_EVENTS_URL = "https://api.open511.gov.bc.ca/events"

# Municipal 511 publishers whose records the sync keeps, by the issue's `Source` field -- the
# value stored in road_closures.source. The data files hold every Transnomis client (about
# 6,500 issues, Florida included); filtering by publisher before any spatial query leaves the
# City's own ~83. Measured on the 2026-09-16 pull: City of Coquitlam and BC MOTI Gateway were
# the only publishers with any geometry within 100 m of the city boundary.
#
# BC MOTI Gateway is deliberately excluded. Its issues sit in the feed's division named
# "DriveBC" and copy the DriveBC stream: 272 of its 303 issues had a description identical
# to an active DriveBC event (pulls 2 h 30 min apart, 2026-09-16), including the Mary Hill
# Bypass record, verbatim RIDE-100086. DriveBC is now asked for the city's area directly and
# carries road state and direction, so keeping the copy would draw each highway event twice.
# Operator ruling 2026-09-16, gis-spatial-engineer's chat ("Drop MOTI copies"), accepting that
# a MOTI record absent from DriveBC would be lost (31 of 303 unmatched across the two pulls).
MUNICIPAL511_PUBLISHERS = ("City of Coquitlam",)

# Most Municipal 511 data files fetched at once. Measured 2026-09-16 on the kiosk: the Coquitlam
# page listed 13 files, fetched one after another in ~6.7 s of an 8.8 s sync, 181-byte files
# included at ~0.25 s each. Operator 2026-09-16 (#92): "We can parallel if it's easy"; all 13 at
# once, lead's bound. The requests, URLs and 5 s timeout are unchanged -- only their overlap is.
MUNICIPAL511_FETCH_WORKERS = 13

# Municipal 511 RoadClosureType (highest bit) -> (emergency_access, closure_type).
# Values and labels: the vendor's own switch in bc.municipal511.ca Framework.min.js, read
# 2026-09-16 (standards index, "Road closure vocabulary"). Tiers: operator ruling 2026-09-17,
# punch list #91 -- "Mapping is right, Detour is Warning, hide Unspecified by default".
# INFO is a stated tier ("this record is information"), not an unknown; 0 Unknown and any value
# outside these twenty stay null (N/A).
MUNICIPAL511_TIERS = {
    262144: ("NO_ACCESS", "FULL_CLOSURE"),        # Road Closed - No Emergency Access
    # Local Traffic Only and Detour are served as full closures -- a ruling the operator expects
    # to revisit ("for now"), 2026-09-17: "Yes, Local Traffic and Detour -> Full Closure for now."
    # His reason: "I often find local access only the road is no access at a certain point and
    # it can be misleading. Same with detours."
    16384: ("NO_ACCESS", "FULL_CLOSURE"),         # Road Closed - Local Traffic Only
    1: ("NO_ACCESS", "FULL_CLOSURE"),             # Detour
    65536: ("ACCESS_ONLY", "LANE_RESTRICTION"),   # Road Closed - Emergency Access Only
    32768: ("ACCESS_ONLY", "LANE_RESTRICTION"),   # Road Closed - Emergency Access Unspecified
    32: ("CAUTION", "LANE_RESTRICTION"),          # Lane(s) Closed
    2048: ("CAUTION", "LANE_RESTRICTION"),        # Alternating Traffic
    8192: ("CAUTION", "LANE_RESTRICTION"),        # Road Closed - One Direction
    131072: ("CAUTION", "LANE_RESTRICTION"),      # Intermittently Blocked
    4096: ("CAUTION", "LANE_RESTRICTION"),        # Opposite Side Lane Open
    2: ("INFO", None),                            # No / Minimal Traffic Impact
    4: ("INFO", None),                            # Shoulder Closure
    8: ("INFO", None),                            # Sidewalk Closure
    16: ("INFO", None),                           # Bike Lane Closure
    64: ("INFO", None),                           # Bus Lane Closure
    128: ("INFO", None),                          # HOV Lane Closure
    256: ("INFO", None),                          # Left Turn Closure
    512: ("INFO", None),                          # Right Turn Closure
    1024: ("INFO", None),                         # Buffer Lane Closure
}
# 0 is the vendor's "Unknown": stated as unknown, so null without an ERROR line.
MUNICIPAL511_UNKNOWN_TYPE = 0


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


# --- SYNC OUTCOME (punch list #89) -------------------------------------------
#
# Three states, persisted in public.road_closure_sync_status. The operator's ruling of
# 2026-09-16 is that the kiosk flags *the previous attempt having failed*, and clears the
# flag on the next success -- not the age of the data. Age was measured and ruled out:
# updated_at is stamped only on rows a sync touches, so a healthy sync that returns zero
# closures leaves it untouched and an age-based indicator would warn on a quiet day.

SYNC_NOT_ATTEMPTED = "NOT_ATTEMPTED"
SYNC_SUCCEEDED = "SUCCEEDED"
SYNC_FAILED = "FAILED"

# Returned by check_and_sync_if_stale. It used to return a bool, which collapsed
# "no sync was needed" and "the sync failed" into the same False.
SYNC_RESULT_NOT_NEEDED = "NOT_NEEDED"
SYNC_RESULT_SYNCED = "SYNCED"
SYNC_RESULT_FAILED = "FAILED"


def record_sync_outcome(db: Session, outcome: str, sources=None, error: str = None):
    """Writes the outcome of the attempt that just finished to the single status row.

    Called on every exit path of sync_road_closures_to_db, including the one where both
    feeds were unreachable and nothing raised.

    Rolls back first: the caller may arrive here from a failed commit, and the status row
    must be written even when the closure transaction could not be.
    """
    try:
        db.rollback()
        row = db.query(RoadClosureSyncStatusModel).filter(
            RoadClosureSyncStatusModel.id == 1
        ).first()
        if row is None:
            row = RoadClosureSyncStatusModel(id=1)
            db.add(row)
        row.last_outcome = outcome
        row.last_attempt_at = datetime.now(timezone.utc)
        row.last_error = error
        row.sources = sources or None
        db.commit()
    except Exception as e:
        # Never let bookkeeping take down the sync itself, but do not hide it either.
        logger.error(f"Could not record road closure sync outcome ({outcome}): {e}")
        try:
            db.rollback()
        except Exception:
            pass


def read_sync_status(db: Session) -> dict:
    """The last attempt's outcome, for GET /api/road-closures.

    An absent row means this database has never been synced by a build that records the
    outcome -- reported as NOT_ATTEMPTED, which is not a failure and must not render as
    one (CLAUDE.md 6.1: an unknown reported as unknown is a correct answer).
    """
    row = db.query(RoadClosureSyncStatusModel).filter(
        RoadClosureSyncStatusModel.id == 1
    ).first()
    if row is None:
        return {
            "outcome": SYNC_NOT_ATTEMPTED,
            "lastAttemptAt": None,
            "error": None,
            "sources": None,
            "skipped": None,
        }
    attempted = row.last_attempt_at
    if attempted is not None and attempted.tzinfo is None:
        attempted = attempted.replace(tzinfo=timezone.utc)
    return {
        "outcome": row.last_outcome or SYNC_NOT_ATTEMPTED,
        "lastAttemptAt": attempted.isoformat() if attempted else None,
        "error": row.last_error,
        "sources": row.sources,
        "skipped": _skipped_summary(row.sources),
    }


def _skipped_summary(sources):
    """{count, bySource} of records the last attempt dropped for having no feed id (#91).

    None when the attempt predates the count (no source carries skippedNoId), so an old
    status row does not read as "zero skipped".
    """
    if not sources:
        return None
    by_source = {name: r["skippedNoId"] for name, r in sources.items()
                 if isinstance(r, dict) and "skippedNoId" in r}
    if not by_source:
        return None
    return {"count": sum(by_source.values()), "bySource": by_source}


# --- FIELDS THE FEED DID NOT SEND (punch list #91) ----------------------------
#
# Operator rulings 2026-09-16:
# * An unknown severity is not a tier. It is stored and served as null; the kiosk shows N/A.
# * A text field the feed did not send is null; the kiosk shows "--". Nothing is made up.
# * A record with no feed id is skipped: not stored, not served, logged at ERROR with the
#   raw record, and counted per source in the sync status so an admin can see it. It is
#   never given an id from its position in the list (the old db_<n> / muni_None_<n>).

def _feed_id(value):
    """The feed's own id as a string, or None when the feed sent none.

    Missing, None and blank all count as none, and all are skipped. str(None) used to turn a
    present-but-null id into the id "None", which every such record would share.
    """
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


# Open511 v1.0 Events specification, documentation/1.0/event.html (github.com/open511/open511API),
# read 2026-09-16 and HELD in docs/standards/README.md, "Road closure vocabulary".
OPEN511_ROAD_STATES = ("CLOSED", "SOME_LANES_CLOSED", "SINGLE_LANE_ALTERNATING", "ALL_LANES_OPEN")
OPEN511_DIRECTIONS = ("N", "NW", "W", "SW", "S", "SE", "E", "NE", "NONE", "BOTH")
# Open511 v1.0 `severity`. Carried through as the feed's word only; never a tier (#91 ruling 5).
OPEN511_SEVERITIES = ("MINOR", "MODERATE", "MAJOR", "UNKNOWN")


def _open511_road_access(state, direction):
    """(emergency_access, closure_type) for one Open511 road, per the operator 2026-09-16.

    * CLOSED, direction BOTH / NONE / absent -> NO_ACCESS ("Closed -> No access").
    * CLOSED in one direction -> CAUTION ("Closed per direction -> Caution - Restrictions,
      and state the road closure direction. We often can go counterflow with the help of
      flaggers.") The direction is carried separately so the kiosk can state it.
    * SOME_LANES_CLOSED, SINGLE_LANE_ALTERNATING -> CAUTION ("Some_lanes/alternating").
    * ALL_LANES_OPEN -> INFO ("All_lanes_open -> Info"). Served as emergencyAccess "INFO"
      since 2026-09-17 (#91), the same tier Municipal 511's information-only types get, so one
      field carries the tier for both feeds. roadState still says ALL_LANES_OPEN.
    * absent -> None (N/A).
    """
    if state == "CLOSED":
        if direction in (None, "BOTH", "NONE"):
            return "NO_ACCESS", "FULL_CLOSURE"
        return "CAUTION", "LANE_RESTRICTION"
    if state in ("SOME_LANES_CLOSED", "SINGLE_LANE_ALTERNATING"):
        return "CAUTION", "LANE_RESTRICTION"
    if state == "ALL_LANES_OPEN":
        return "INFO", None
    return None, None


# Which road wins when an event lists several. Most restrictive first, so a closure on any
# listed road is never hidden behind an open one; a stated ALL_LANES_OPEN outranks a road
# whose state is unknown.
_ACCESS_RANK = {"NO_ACCESS": 4, "ACCESS_ONLY": 3, "CAUTION": 2, "INFO": 1}


def _drivebc_access(evt, closure_id=None):
    """Access fields for a DriveBC event, read from roads[].state and roads[].direction.

    Returns a dict: emergency_access, closure_type, road_state, road_direction,
    feed_severity. `severity` is never read as a tier: Open511 defines it as traffic
    impact, and on 2026-09-16 18 MAJOR events had every lane open and 5 MINOR were CLOSED.
    """
    raw_sev = _feed_text(evt.get('severity'))
    feed_severity = raw_sev.upper() if raw_sev else None
    if feed_severity and feed_severity not in OPEN511_SEVERITIES:
        logger.error(f"DriveBC event {closure_id}: severity {raw_sev!r} is not an Open511 "
                     f"v1.0 value; carried as sent.")

    candidates = []
    roads = evt.get('roads') if isinstance(evt.get('roads'), list) else []
    for road in roads:
        if not isinstance(road, dict):
            continue
        raw_state = _feed_text(road.get('state'))
        state = raw_state.upper() if raw_state else None
        if state and state not in OPEN511_ROAD_STATES:
            logger.error(f"DriveBC event {closure_id}: roads[].state {raw_state!r} is not an "
                         f"Open511 v1.0 value; treated as unknown.")
            state = None
        raw_dir = _feed_text(road.get('direction'))
        direction = raw_dir.upper() if raw_dir else None
        if direction and direction not in OPEN511_DIRECTIONS:
            logger.error(f"DriveBC event {closure_id}: roads[].direction {raw_dir!r} is not an "
                         f"Open511 v1.0 value; treated as absent.")
            direction = None
        access, closure_type = _open511_road_access(state, direction)
        rank = _ACCESS_RANK.get(access, 0)
        candidates.append((rank, state, direction, access, closure_type,
                           _feed_text(road.get('name'))))

    if not candidates:
        return {"emergency_access": None, "closure_type": None, "road_state": None,
                "road_direction": None, "feed_severity": feed_severity, "road_name": None}

    if len({(c[1], c[2]) for c in candidates}) > 1:
        logger.warning(
            f"DriveBC event {closure_id}: its roads disagree "
            f"{[(c[1], c[2]) for c in candidates]}; serving the most restrictive."
        )
    # max() keeps the first of equal rank, i.e. the feed's own order.
    rank, state, direction, access, closure_type, road_name = max(candidates, key=lambda c: c[0])
    # road_name is the name of the road the tier was taken from, as the feed sent it.
    return {"emergency_access": access, "closure_type": closure_type, "road_state": state,
            "road_direction": direction, "feed_severity": feed_severity, "road_name": road_name}


def _feed_text(value):
    """A text field as the feed sent it, stripped, or None when it sent nothing usable."""
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _skip_id_less_record(source, record, skipped):
    """Log and count a feed record that has no id. It is not stored or served (#91)."""
    skipped[source] = skipped.get(source, 0) + 1
    logger.error(
        f"Road closure record from {source} has no id in the feed; skipped, not stored or "
        f"shown (punch list #91). Raw record: {json.dumps(record, default=str)[:2000]}"
    )


# --- LIVE INGESTION & POSTGRESQL SYNC PIPELINE ---

def sync_road_closures_to_db(db: Session):
    """
    Fetches DriveBC and Municipal 511 feeds server-side,
    applies spatial Ray-Casting PIP to verify Emergency Zone containment,
    enriches with zone_id and affected_zones array, and upserts into PostgreSQL road_closures table.

    Records the attempt's outcome in public.road_closure_sync_status on every exit path,
    so the daemon and the manual POST /api/road-closures/sync both leave a trace.

    A source that could not be ingested in full makes the whole attempt FAILED. That is
    conservative on purpose: a partial list looks exactly like a complete one on the
    kiosk, so "we reached one of the two feeds" is not an all-clear. Per-source detail
    goes in the `sources` column so the operator can see which one.
    """
    source_results = {}
    # Records dropped for having no feed id, by source (#91). Folded into `sources` so the
    # count is recorded per attempt without another column.
    skipped = {}
    try:
        count = _ingest_road_closures(db, source_results, skipped)
    except Exception as e:
        _merge_skipped(source_results, skipped)
        record_sync_outcome(db, SYNC_FAILED, sources=source_results, error=str(e))
        raise
    _merge_skipped(source_results, skipped)

    unreachable = [name for name, r in source_results.items() if not r.get("reached")]
    record_sync_outcome(
        db,
        SYNC_FAILED if unreachable else SYNC_SUCCEEDED,
        sources=source_results,
        error=(f"Source(s) not ingested: {', '.join(unreachable)}" if unreachable else None),
    )
    return count


def _merge_skipped(source_results, skipped):
    for name, result in source_results.items():
        result["skippedNoId"] = skipped.get(name, 0)


def _ingest_road_closures(db: Session, source_results: dict, skipped: dict):
    """The ingestion itself. `source_results` is filled in per feed by reference.

    Note for anyone changing the error handling here: neither feed's failure propagates
    out of this function. Each is caught, logged and swallowed, and an unreachable network
    simply yields an empty `raw_notices` -- the same shape as a genuinely quiet day. That
    is why reachability is recorded per source at the point the block completes, and not
    inferred from whether this function raised.
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    now_utc = datetime.now(timezone.utc)
    raw_notices = []

    # 1. Fetch DriveBC Open511
    source_results["DriveBC Open511"] = {"reached": False, "error": "not attempted"}
    try:
        # Ask for the city's area, not the province (operator 2026-09-16, #92: "why not ask
        # DriveBC what do you have in Coquitlam?"). No box, no request: an unfiltered pull
        # would bring back the silent cap this replaces.
        bbox = closure_city_bbox(db)
        if bbox is None:
            raise RuntimeError("could not compute the city bounding box; DriveBC not asked")
        next_url = DRIVEBC_EVENTS_URL + "?" + urllib.parse.urlencode({
            "format": "json", "status": "ACTIVE", "bbox": ",".join(f"{v:.5f}" for v in bbox),
        })
        events, seen_urls = [], set()
        # Follow the feed's own pagination.next_url until it stops offering one.
        while next_url and next_url not in seen_urls:
            seen_urls.add(next_url)
            req = urllib.request.Request(next_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                db_data = json.loads(resp.read().decode('utf-8'))
            events.extend(db_data.get('events', []))
            next_url = (db_data.get('pagination') or {}).get('next_url')

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

            # Build geometry from the feed. No default coordinate: a closure whose
            # geometry cannot be parsed is dropped, never pinned to a placeholder
            # location, which would file it under an arbitrary zone and hall
            # (CLAUDE.md §6.1).
            if t == 'Point':
                all_pts = [[coords[1], coords[0]]]
            else:
                all_pts = [[pt[1], pt[0]] for pt in coords]

            geo = build_geojson_geometry(all_pts)
            if not geo:
                continue

            # Municipal boundary containment via PostGIS, replacing the Fraser River
            # latitude threshold and the neighbouring-city description blocklist.
            if not is_within_city(db, geo):
                continue

            # Kept even with no zone within reach (#92): it is inside the buffered city, so
            # it is Coquitlam's; zone_id null and the kiosk groups it as OTHER.
            affected_zones, primary_zone, hall_id = resolve_zones_and_hall(db, geo)

            mid = len(all_pts) // 2
            lat, lng = all_pts[mid][0], all_pts[mid][1]


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

            # Skipped here, after the city and zone filters, so the count is of records
            # that would have been shown in Coquitlam -- not the province-wide feed's.
            closure_id = _feed_id(evt.get('id'))
            if closure_id is None:
                _skip_id_less_record("DriveBC Open511", evt, skipped)
                continue
            access = _drivebc_access(evt, closure_id)

            raw_notices.append({
                "closure_id": closure_id,
                # Parsed values, not the raw roads[]: an out-of-spec state already has its
                # own ERROR line naming it, and one line per problem is the rule (#91).
                "raw_severity": f"roads[].state={access['road_state']!r}",
                # roads[].name of the road the tier came from (#92). Open511 has no top-level
                # road_name: reading one discarded every DriveBC road name (0 of 286 events
                # carried it, 286 of 286 carried roads[].name, 2026-09-16). Absent -> null.
                "street_name": access["road_name"],
                "source": "DriveBC Open511",
                "closure_type": access["closure_type"],
                "emergency_access": access["emergency_access"],
                "road_state": access["road_state"],
                "road_direction": access["road_direction"],
                "feed_severity": access["feed_severity"],
                "headline": _feed_text(evt.get('headline')),
                "description": _feed_text(evt.get('description')),
                "geometry": geo,
                "coordinates": [lat, lng],
                "zone_id": primary_zone,
                "affected_zones": affected_zones,
                "hall_id": hall_id,
                "start_time": start_dt,
                "end_time": end_dt
            })
        # Reached only once the whole block has run: a mid-list parse failure leaves a
        # partial contribution from this feed, which is not a successful ingestion.
        source_results["DriveBC Open511"] = {"reached": True}
    except Exception as e:
        logger.warning(f"DriveBC ingestion warning: {e}")
        source_results["DriveBC Open511"] = {"reached": False, "error": str(e)}

    # 2. Fetch Municipal 511
    source_results["Municipal 511"] = {"reached": False, "error": "not attempted"}
    muni_chunk_errors = []
    try:
        req_page = urllib.request.Request("https://bc.municipal511.ca/?municipality=coquitlam", headers=headers)
        with urllib.request.urlopen(req_page, timeout=5) as resp:
            html = resp.read().decode('utf-8')

        matches = re.findall(r'"(jsonData\d*\.txt)"\s*:\s*"([^"]+)"', html)
        if not matches:
            matches = [("jsonData0.txt", "jsonData0.txt")]

        def _fetch_file(filename):
            # The body, or the exception, so one failed file is reported below exactly as the
            # sequential loop reported it: a chunk error, and Municipal 511 not reached.
            try:
                req_data = urllib.request.Request(f"https://bc.municipal511.ca/Dynamic/{filename}", headers=headers)
                with urllib.request.urlopen(req_data, timeout=5) as resp:
                    return resp.read()
            except Exception as fetch_err:
                return fetch_err

        # Fetched concurrently, processed in the page's order. Each file carries its own
        # CoordsEncoded stream and gets its own decoder, so the order files are *processed* in
        # is what keeps geometry aligned, and that order is unchanged (map preserves it).
        filenames = [filename for _, filename in matches]
        with ThreadPoolExecutor(max_workers=max(1, min(MUNICIPAL511_FETCH_WORKERS, len(filenames)))) as pool:
            bodies = list(pool.map(_fetch_file, filenames))

        for filename, body in zip(filenames, bodies):
            try:
                if isinstance(body, Exception):
                    raise body
                muni_data = json.loads(body.decode('utf-8'))

                issues = muni_data.get('Issues', [])
                decoder = PythonGeometryDecoder(muni_data.get('CoordsEncoded', ''))

                for issue in issues:
                    geoms = issue.get('Geometry', [])
                    # Another client's issue: skipped before any spatial query (#92). Its
                    # points are still read, because the decoder is one stream per file and
                    # every later issue's geometry depends on this one's being consumed.
                    other_publisher = issue.get('Source') not in MUNICIPAL511_PUBLISHERS
                    for geom_idx, geom in enumerate(geoms):
                        num_points = geom.get('NumPoints', 0)
                        path_pts = decoder.get_n_points(num_points)
                        if other_publisher:
                            continue

                        # No default coordinate: an unparseable geometry is dropped
                        # rather than pinned to a placeholder (CLAUDE.md §6.1).
                        geo = build_geojson_geometry(path_pts)
                        if not geo:
                            continue

                        if not is_within_city(db, geo):
                            continue

                        # Kept even with no zone within reach (#92); grouped as OTHER.
                        affected_zones, primary_zone, hall_id = resolve_zones_and_hall(db, geo)

                        mid = len(path_pts) // 2
                        lat, lng = path_pts[mid][0], path_pts[mid][1]
                        rct = geom.get('MarkerInfo', {}).get('RoadClosureType', 0)
                        highest_bit = 0
                        if rct > 0:
                            highest_bit = 1 << int(math.log2(rct))

                        desc = issue.get('Description', {})
                        desc_lower = (desc.get('BaseDescription') or "").lower()
                        headline_lower = (desc.get('Headline') or "").lower()
                        is_closed = "road closed" in desc_lower or "full closure" in desc_lower or "road closed" in headline_lower or "full closure" in headline_lower

                        # The tier is the stated type's (MUNICIPAL511_TIERS, operator 2026-09-17).
                        emergency_access, closure_type = MUNICIPAL511_TIERS.get(highest_bit, (None, None))
                        if highest_bit != MUNICIPAL511_UNKNOWN_TYPE and highest_bit not in MUNICIPAL511_TIERS:
                            logger.error(
                                f"Municipal 511 issue {issue.get('IssueId')}: RoadClosureType {rct!r} "
                                f"is not one of the vendor's twenty values; tier null.")
                        # "road closed" / "full closure" in the text raises the record to
                        # ACCESS_ONLY whatever its stated type -- CAUTION, INFO or none -- and never
                        # lowers one: a stated NO_ACCESS stays NO_ACCESS. Operator ruling 2026-09-17
                        # (#91): "Added text should elevate as necessary." Measured on the
                        # 2026-09-16 pull, it raises one stated record: Alternating Traffic (CAUTION)
                        # noting "full closure dec 5".
                        if is_closed and _ACCESS_RANK.get(emergency_access, 0) < _ACCESS_RANK["ACCESS_ONLY"]:
                            emergency_access, closure_type = "ACCESS_ONLY", "LANE_RESTRICTION"

                        start_dt = None
                        end_dt = None
                        if desc.get('ProposedStartTimeUtcEpochMillis'):
                            start_dt = datetime.fromtimestamp(desc['ProposedStartTimeUtcEpochMillis'] / 1000, tz=timezone.utc)
                        if desc.get('ProposedEndTimeUtcEpochMillis'):
                            end_dt = datetime.fromtimestamp(desc['ProposedEndTimeUtcEpochMillis'] / 1000, tz=timezone.utc)

                        # Every fallback here is another field of the same record; none is
                        # made up. Nothing sent -> None -> "--" on the kiosk (#91).
                        loc_name = (_feed_text(geom.get('MarkerInfo', {}).get('LocationName'))
                                    or _feed_text(issue.get('TableViewInfo', {}).get('Location'))
                                    or _feed_text(desc.get('BaseLocationDescription')))
                        headline_text = _feed_text(desc.get('Headline')) or loc_name
                        desc_text = _feed_text(desc.get('BaseDescription'))

                        # geom_idx separates the geometries of one issue; it is not a
                        # substitute for the issue's own id. No IssueId -> skipped (#91).
                        issue_id = _feed_id(issue.get('IssueId'))
                        if issue_id is None:
                            _skip_id_less_record("Municipal 511", {**issue, "Geometry": [geom]}, skipped)
                            continue

                        raw_notices.append({
                            "closure_id": f"muni_{issue_id}_{geom_idx}",
                            "raw_severity": rct,
                            "street_name": loc_name,
                            "source": issue.get('Source') or "City of Coquitlam",
                            "closure_type": closure_type,
                            "emergency_access": emergency_access,
                            "headline": headline_text,
                            "description": desc_text,
                            "geometry": geo,
                            "coordinates": [lat, lng],
                            "zone_id": primary_zone,
                            "affected_zones": affected_zones,
                            "hall_id": hall_id,
                            "start_time": start_dt,
                            "end_time": end_dt
                        })
            except Exception as chunk_err:
                logger.warning(f"Municipal 511 chunk parse warning: {chunk_err}")
                muni_chunk_errors.append(f"{filename}: {chunk_err}")

        if muni_chunk_errors:
            # Some chunks came back and some did not, so this feed's contribution is
            # incomplete. Not an all-clear.
            source_results["Municipal 511"] = {
                "reached": False,
                "error": "; ".join(muni_chunk_errors),
            }
        else:
            source_results["Municipal 511"] = {"reached": True}
    except Exception as e:
        logger.warning(f"Municipal 511 ingestion warning: {e}")
        source_results["Municipal 511"] = {"reached": False, "error": str(e)}

    # Upsert notices into PostgreSQL differentials
    if not raw_notices:
        # Zero notices is ambiguous on its own -- an unreachable feed and a genuinely
        # quiet day produce the identical empty list. The caller tells them apart from
        # source_results, not from this count (punch list #89).
        logger.warning("No road closure notices were scraped from remote feeds. Retaining local database cache for offline survival.")
        return 0

    active_closure_ids = set()
    # Records stored with no stated severity, per feed, for one summary line per sync.
    no_severity = {"Municipal 511": 0, "DriveBC Open511": 0}

    for item in raw_notices:
        cid = item["closure_id"]
        active_closure_ids.add(cid)

        # Stored as null, never defaulted (#91). Counted, not logged per record: one line
        # per sync, below. INFO is a stated tier, not a gap; only a null tier is counted.
        if item["emergency_access"] is None:
            # DriveBC rows carry source "DriveBC Open511"; Municipal 511 rows carry the
            # issuing organisation ("City of Coquitlam", "BC MOTI Gateway").
            feed = "DriveBC Open511" if item["source"] == "DriveBC Open511" else "Municipal 511"
            no_severity[feed] += 1

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
            existing.hall_id = item.get("hall_id")
            existing.road_state = item.get("road_state")
            existing.road_direction = item.get("road_direction")
            existing.feed_severity = item.get("feed_severity")
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
                hall_id=item.get("hall_id"),
                road_state=item.get("road_state"),
                road_direction=item.get("road_direction"),
                feed_severity=item.get("feed_severity"),
                start_time=item["start_time"],
                end_time=end_time,
                active=is_active
            )
            db.add(new_record)

    # One line per sync, not one per record (operator 2026-09-16, #91). WARNING: on these
    # feeds an unstated severity is expected, not a defect. The per-record ERROR lines an
    # admin needs -- a record skipped for having no id -- are logged above and stay per record.
    stored_without = sum(no_severity.values())
    if stored_without:
        logger.warning(
            f"{stored_without} of {len(raw_notices)} records stored with no stated severity "
            f"(Municipal 511: {no_severity['Municipal 511']}, "
            f"DriveBC Open511: {no_severity['DriveBC Open511']})"
        )

    # Early completion deactivation: If a closure is missing from a successful scrape (where raw_notices > 0)
    # and its start_time is in the past, mark active = False (assuming construction completed early).
    if active_closure_ids:
        db.query(RoadClosureModel).filter(
            RoadClosureModel.active == True,
            RoadClosureModel.start_time != None,
            RoadClosureModel.start_time <= now_utc,
            ~RoadClosureModel.closure_id.in_(active_closure_ids)
        ).update({RoadClosureModel.active: False}, synchronize_session=False)

    # Scheduled expiration deactivation: Deactivate records whose scheduled end_time has passed
    db.query(RoadClosureModel).filter(
        RoadClosureModel.active == True,
        RoadClosureModel.end_time != None,
        RoadClosureModel.end_time < now_utc
    ).update({RoadClosureModel.active: False}, synchronize_session=False)

    # 30-Day Retention Purge: Hard-delete records that have been soft-deactivated (active = False) for > 30 days
    purge_cutoff = now_utc - timedelta(days=30)
    deleted_count = db.query(RoadClosureModel).filter(
        RoadClosureModel.active == False,
        RoadClosureModel.updated_at < purge_cutoff
    ).delete(synchronize_session=False)

    db.flush()

    # Mirror the jsonb geometry into the PostGIS geom column so spatial queries have a
    # real, GiST-indexed geometry to work against.
    db.execute(text("""
        UPDATE public.road_closures
           SET geom = ST_SetSRID(ST_GeomFromGeoJSON(geometry::text), 4326)
         WHERE geometry IS NOT NULL
           AND (geom IS NULL OR updated_at >= :since)
    """), {"since": now_utc - timedelta(minutes=5)})

    db.commit()
    logger.info(f"Successfully differentials-synced {len(active_closure_ids)} road closures. Purged {deleted_count} stale records older than 30 days.")
    return len(active_closure_ids)


def check_and_sync_if_stale(db: Session, max_age_seconds: int = 86400) -> str:
    """
    Checks the last update timestamp of local road closures in PostgreSQL.
    If the database is empty OR the last update is older than max_age_seconds (default 24h),
    triggers a differential sync.

    Returns one of SYNC_RESULT_NOT_NEEDED / SYNC_RESULT_SYNCED / SYNC_RESULT_FAILED.

    It used to return a bool, and returned False both for "no sync was needed" and for
    "the sync failed" -- so the caller could not tell an idle hour from an outage
    (punch list #89). Do not collapse these back to a truthiness test: all three values
    are non-empty strings and all three are truthy.
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
        except Exception as e:
            # sync_road_closures_to_db has already recorded SYNC_FAILED before re-raising.
            logger.error(f"Failed to run scheduled road closure sync: {e}")
            return SYNC_RESULT_FAILED

        # The sync returning normally does not make it a success: an unreachable feed is
        # caught and swallowed inside the ingestion, so the outcome it recorded is the
        # only honest answer here.
        if read_sync_status(db).get("outcome") == SYNC_FAILED:
            return SYNC_RESULT_FAILED
        return SYNC_RESULT_SYNCED

    return SYNC_RESULT_NOT_NEEDED

