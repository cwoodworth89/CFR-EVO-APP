import os
import json
import hashlib
import re
import math
import logging
import urllib.request
from datetime import datetime, timezone, timedelta
from sqlalchemy import text, or_, and_
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
        build_geojson_geometry, is_within_city, resolve_zones_and_hall,
    )
except ModuleNotFoundError:
    from api.closure_spatial import (
        build_geojson_geometry, is_within_city, resolve_zones_and_hall,
    )


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
        }
    attempted = row.last_attempt_at
    if attempted is not None and attempted.tzinfo is None:
        attempted = attempted.replace(tzinfo=timezone.utc)
    return {
        "outcome": row.last_outcome or SYNC_NOT_ATTEMPTED,
        "lastAttemptAt": attempted.isoformat() if attempted else None,
        "error": row.last_error,
        "sources": row.sources,
    }


# --- FIELDS THE FEED DID NOT SEND (punch list #91) ----------------------------
#
# Operator rulings 2026-09-16. An unknown severity is not a tier: it is stored and served as
# null, and the kiosk shows N/A in the access box. A feed record with no id keeps a null id
# and says so; it is never given one from its position in the list.

def _feed_id(value):
    """The feed's own id as a string, or None when the feed sent none.

    Missing, None and blank all count as none. str(None) would otherwise become the id
    "None", which every id-less record would share.
    """
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _drivebc_severity(evt):
    """(closure_type, emergency_access) for a DriveBC event, or (None, None) when unknown.

    Unknown means the feed sent no severity, a blank one, or the literal "UNKNOWN". It used
    to default to MINOR and so to CAUTION. Present values keep the mapping they already had
    (MAJOR -> FULL_CLOSURE / NO_ACCESS, anything else -> LANE_RESTRICTION / CAUTION); that
    mapping predates #91 and is not ruled on here.
    """
    raw = evt.get('severity')
    sev = raw.strip().upper() if isinstance(raw, str) else None
    if not sev or sev == 'UNKNOWN':
        return None, None
    if sev == 'MAJOR':
        return 'FULL_CLOSURE', 'NO_ACCESS'
    return 'LANE_RESTRICTION', 'CAUTION'


def _content_record_key(source, fields):
    """A match key for a feed record that has no id, derived only from what the feed sent.

    It is not an id and is never served as one: GET /api/road-closures returns id = null and
    idMissing = true for these rows. It exists so the upsert can find the same record on the
    next sync instead of inserting it again. Built from raw feed fields only (never the text
    placeholders), and it deliberately leaves out the fields a feed edits in place --
    headline, description, severity, end time -- so an edit to those updates the row rather
    than forking it.
    """
    blob = json.dumps({"source": source, **fields}, sort_keys=True,
                      separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


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
    try:
        count = _ingest_road_closures(db, source_results)
    except Exception as e:
        record_sync_outcome(db, SYNC_FAILED, sources=source_results, error=str(e))
        raise

    unreachable = [name for name, r in source_results.items() if not r.get("reached")]
    record_sync_outcome(
        db,
        SYNC_FAILED if unreachable else SYNC_SUCCEEDED,
        sources=source_results,
        error=(f"Source(s) not ingested: {', '.join(unreachable)}" if unreachable else None),
    )
    return count


def _ingest_road_closures(db: Session, source_results: dict):
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

            affected_zones, primary_zone, hall_id = resolve_zones_and_hall(db, geo)
            if not affected_zones:
                continue  # Outside every Coquitlam emergency response zone.

            mid = len(all_pts) // 2
            lat, lng = all_pts[mid][0], all_pts[mid][1]

            closure_type, emergency_access = _drivebc_severity(evt)

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

            closure_id = _feed_id(evt.get('id'))
            raw_notices.append({
                "closure_id": closure_id,
                "feed_record_key": None if closure_id else _content_record_key(
                    "DriveBC Open511",
                    {
                        "road_name": evt.get('road_name'),
                        "geography": geog,
                        "schedule": evt.get('schedule'),
                        "created": evt.get('created'),
                    },
                ),
                "raw_severity": evt.get('severity'),
                "street_name": (evt.get('road_name') or "Regional Corridor").strip(),
                "source": "DriveBC Open511",
                "closure_type": closure_type,
                "emergency_access": emergency_access,
                "headline": (evt.get('headline') or "TRAFFIC ALERT").strip(),
                "description": (evt.get('description') or "Active traffic event.").strip(),
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

                        # No default coordinate: an unparseable geometry is dropped
                        # rather than pinned to a placeholder (CLAUDE.md §6.1).
                        geo = build_geojson_geometry(path_pts)
                        if not geo:
                            continue

                        if not is_within_city(db, geo):
                            continue

                        affected_zones, primary_zone, hall_id = resolve_zones_and_hall(db, geo)
                        if not affected_zones:
                            continue  # Outside every Coquitlam emergency response zone.

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

                        # geom_idx separates the geometries of one issue; it is not a
                        # substitute for the issue's own id. No IssueId -> no closure_id.
                        issue_id = _feed_id(issue.get('IssueId'))
                        raw_notices.append({
                            "closure_id": f"muni_{issue_id}_{geom_idx}" if issue_id else None,
                            "feed_record_key": None if issue_id else _content_record_key(
                                issue.get('Source') or "City of Coquitlam",
                                {
                                    "location": geom.get('MarkerInfo', {}).get('LocationName'),
                                    "path": path_pts,
                                    "start_ms": desc.get('ProposedStartTimeUtcEpochMillis'),
                                },
                            ),
                            "raw_severity": rct,
                            "street_name": loc_name.strip(),
                            "source": issue.get('Source') or "City of Coquitlam",
                            "closure_type": "FULL_CLOSURE" if emergency_access == "NO_ACCESS" else "LANE_RESTRICTION",
                            "emergency_access": emergency_access,
                            "headline": headline_text.strip(),
                            "description": desc_text.strip(),
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
    # Content match keys for records the feed sent without an id (punch list #91).
    active_record_keys = set()

    for item in raw_notices:
        cid = item["closure_id"]
        record_key = item.get("feed_record_key")
        label = cid or record_key

        if item["closure_type"] is None or item["emergency_access"] is None:
            logger.error(
                f"Road closure {label} from {item['source']}: the feed sent no usable "
                f"severity ({item.get('raw_severity')!r}); stored with closure_type and "
                f"emergency_access null, not defaulted (punch list #91)."
            )

        if cid is None:
            logger.error(
                f"Road closure from {item['source']} has no id in the feed record; kept with "
                f"closure_id null and matched on content key {record_key} (punch list #91)."
            )
            if record_key in active_record_keys:
                # Two id-less records identical in every key field in one batch. They cannot
                # be told apart without inventing something, so the first is kept.
                logger.error(
                    f"Two id-less road closure records from {item['source']} share content "
                    f"key {record_key} in one sync; kept the first, dropped the second."
                )
                continue
            active_record_keys.add(record_key)
        else:
            active_closure_ids.add(cid)

        # Check for expired
        end_time = item["end_time"]
        if end_time and end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        
        is_expired = end_time and now_utc > end_time
        is_active = not is_expired

        if cid is not None:
            existing = db.query(RoadClosureModel).filter(RoadClosureModel.closure_id == cid).first()
        else:
            existing = db.query(RoadClosureModel).filter(
                RoadClosureModel.closure_id == None,
                RoadClosureModel.feed_record_key == record_key,
            ).first()
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
            existing.start_time = item["start_time"]
            existing.end_time = end_time
            existing.active = is_active
            existing.feed_record_key = record_key
            existing.updated_at = now_utc
        else:
            new_record = RoadClosureModel(
                closure_id=cid,
                feed_record_key=record_key,
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
                start_time=item["start_time"],
                end_time=end_time,
                active=is_active
            )
            db.add(new_record)

    # Early completion deactivation: If a closure is missing from a successful scrape (where raw_notices > 0)
    # and its start_time is in the past, mark active = False (assuming construction completed early).
    # An id-less row has closure_id NULL, and NOT IN over a NULL is never true -- without the
    # second branch those rows would never be deactivated once they leave the feed.
    if active_closure_ids or active_record_keys:
        db.query(RoadClosureModel).filter(
            RoadClosureModel.active == True,
            RoadClosureModel.start_time != None,
            RoadClosureModel.start_time <= now_utc,
            or_(
                and_(RoadClosureModel.closure_id != None,
                     ~RoadClosureModel.closure_id.in_(list(active_closure_ids))),
                and_(RoadClosureModel.closure_id == None,
                     ~RoadClosureModel.feed_record_key.in_(list(active_record_keys))),
            )
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
    synced_count = len(active_closure_ids) + len(active_record_keys)
    logger.info(f"Successfully differentials-synced {synced_count} road closures. Purged {deleted_count} stale records older than 30 days.")
    return synced_count


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

