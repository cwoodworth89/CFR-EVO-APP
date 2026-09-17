"""Punch list #89 -- a failed road closure sync must be distinguishable from a quiet day.

These run against an in-memory SQLite database with `api.database` stubbed out, so they
need neither the kiosk's Postgres nor the network. What they cannot check is the live
behaviour on the kiosk; that needs the api rebuild and the operator's falsifier (pull the
link for one hourly tick). See the #89 item.

The case that matters most here is `test_unreachable_feeds_record_failed_without_raising`:
neither feed's failure propagates out of the ingestion -- each is caught, logged and
swallowed -- so an outage produces an empty list and a clean return. Any implementation
that inferred failure from an exception would report SUCCEEDED with the link down, and the
operator's falsifier would fail.
"""
import json
import sys
import types
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# --- import the service against a stubbed api.database ------------------------
# The real api.database connects to the kiosk's Postgres at import and sys.exit()s when it
# cannot (punch-list #61). These are standalone unit checks, so they supply their own Base
# and no engine.
#
# The swap is undone immediately afterwards. Other test files in the same pytest session
# import api.server, which runs Base.metadata.create_all(bind=engine) at import and would
# fail against an engine of None -- and if any of them ran first, their real modules are
# already in sys.modules and would be handed back here instead of the stubbed ones. So the
# real entries are saved, replaced, and put back, in both orders. The two model sets end up
# on separate MetaData objects, which is harmless because nothing is shared between them.
_MODULES = ("api", "api.database", "api.models", "api.road_closure_service")
_saved = {name: sys.modules.pop(name, None) for name in _MODULES}

_Base = declarative_base()
_stub = types.ModuleType("api.database")
_stub.Base = _Base
_stub.engine = None
_stub.SessionLocal = None
_stub.get_db = lambda: None
_stub.DATABASE_URL = "postgresql://stub/stub"

_api_pkg = types.ModuleType("api")
_api_pkg.__path__ = [__file__.rsplit("tests", 1)[0] + "api"]
sys.modules["api"] = _api_pkg
sys.modules["api.database"] = _stub

from api.models import RoadClosureModel, RoadClosureSyncStatusModel  # noqa: E402
from api import road_closure_service as svc  # noqa: E402

for _name in reversed(_MODULES):
    if _saved[_name] is not None:
        sys.modules[_name] = _saved[_name]
    else:
        sys.modules.pop(_name, None)


class _Resp:
    """Minimal stand-in for the object urllib.request.urlopen yields."""

    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _reachable_but_empty(req, timeout=None):
    """Both feeds answer, and neither has anything inside Coquitlam. A quiet day."""
    url = req.full_url if hasattr(req, "full_url") else str(req)
    if "open511" in url:
        return _Resp(json.dumps({"events": []}).encode())
    if url.endswith("municipality=coquitlam"):
        return _Resp(b'{"jsonData0.txt":"jsonData0.txt"}')
    return _Resp(json.dumps({"Issues": [], "CoordsEncoded": ""}).encode())


def _unreachable(req, timeout=None):
    raise OSError("[Errno -3] Temporary failure in name resolution")


def _closure(closure_id, street, age_days):
    return RoadClosureModel(
        closure_id=closure_id,
        street_name=street,
        source="test",
        emergency_access="CAUTION",
        geometry={"type": "Point", "coordinates": [0, 0]},
        coordinates=["49.28", "-122.80"],
        active=True,
        updated_at=datetime.now(timezone.utc) - timedelta(days=age_days),
    )


class RoadClosureSyncStatusTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        # Only the two tables under test: other models in api.models declare raw JSONB,
        # which SQLite cannot render, and none of them are involved here.
        _Base.metadata.create_all(
            bind=self.engine,
            tables=[RoadClosureModel.__table__, RoadClosureSyncStatusModel.__table__],
        )
        self.db = sessionmaker(bind=self.engine)()
        # closure_city_bbox is PostGIS; a box measured from the kiosk's table stands in.
        self._bbox = patch.object(svc, "closure_city_bbox", lambda db: (-122.89492, 49.2184, -122.6197, 49.35263))
        self._bbox.start()

    def tearDown(self):
        self._bbox.stop()
        self.db.close()

    # --- the status row itself ------------------------------------------------

    def test_absent_row_reads_as_not_attempted_not_as_failure(self):
        status = svc.read_sync_status(self.db)
        self.assertEqual(status["outcome"], svc.SYNC_NOT_ATTEMPTED)
        self.assertIsNone(status["lastAttemptAt"])

    def test_outcome_round_trips_and_stays_a_single_row(self):
        svc.record_sync_outcome(
            self.db,
            svc.SYNC_FAILED,
            sources={"DriveBC Open511": {"reached": False, "error": "boom"}},
            error="boom",
        )
        status = svc.read_sync_status(self.db)
        self.assertEqual(status["outcome"], svc.SYNC_FAILED)
        self.assertIsNotNone(status["lastAttemptAt"])
        self.assertFalse(status["sources"]["DriveBC Open511"]["reached"])

        svc.record_sync_outcome(
            self.db, svc.SYNC_SUCCEEDED, sources={"DriveBC Open511": {"reached": True}}
        )
        status = svc.read_sync_status(self.db)
        self.assertEqual(status["outcome"], svc.SYNC_SUCCEEDED)
        self.assertIsNone(status["error"])
        self.assertEqual(self.db.query(RoadClosureSyncStatusModel).count(), 1)

    # --- the case the flag exists for -----------------------------------------

    def test_unreachable_feeds_record_failed_without_raising(self):
        with patch("urllib.request.urlopen", _unreachable):
            count = svc.sync_road_closures_to_db(self.db)

        # It does not raise, and it reports zero closures -- identical, from the outside,
        # to a day with no closures in the City.
        self.assertEqual(count, 0)

        status = svc.read_sync_status(self.db)
        self.assertEqual(status["outcome"], svc.SYNC_FAILED)
        self.assertFalse(status["sources"]["DriveBC Open511"]["reached"])
        self.assertFalse(status["sources"]["Municipal 511"]["reached"])

    def test_quiet_day_records_succeeded_so_the_flag_clears(self):
        svc.record_sync_outcome(self.db, svc.SYNC_FAILED, error="earlier outage")

        with patch("urllib.request.urlopen", _reachable_but_empty):
            count = svc.sync_road_closures_to_db(self.db)

        self.assertEqual(count, 0)
        # Zero closures and the flag cleared: the source was reached and the City has none.
        self.assertEqual(svc.read_sync_status(self.db)["outcome"], svc.SYNC_SUCCEEDED)

    # --- check_and_sync_if_stale is no longer two-valued ----------------------

    def test_not_needed_is_distinct_from_failed(self):
        self.db.add(_closure("fresh-1", "Pinetree Way", age_days=0))
        self.db.commit()

        self.assertEqual(
            svc.check_and_sync_if_stale(self.db, max_age_seconds=86400),
            svc.SYNC_RESULT_NOT_NEEDED,
        )
        # Nothing was attempted, so nothing was recorded.
        self.assertEqual(svc.read_sync_status(self.db)["outcome"], svc.SYNC_NOT_ATTEMPTED)

    def test_stale_data_and_a_dead_link_returns_failed(self):
        self.db.add(_closure("stale-1", "Como Lake Ave", age_days=3))
        self.db.commit()

        with patch("urllib.request.urlopen", _unreachable):
            result = svc.check_and_sync_if_stale(self.db, max_age_seconds=86400)

        self.assertEqual(result, svc.SYNC_RESULT_FAILED)
        self.assertEqual(svc.read_sync_status(self.db)["outcome"], svc.SYNC_FAILED)

    def test_stale_data_and_a_live_link_returns_synced(self):
        self.db.add(_closure("stale-2", "Austin Ave", age_days=3))
        self.db.commit()

        with patch("urllib.request.urlopen", _reachable_but_empty):
            result = svc.check_and_sync_if_stale(self.db, max_age_seconds=86400)

        self.assertEqual(result, svc.SYNC_RESULT_SYNCED)
        self.assertEqual(svc.read_sync_status(self.db)["outcome"], svc.SYNC_SUCCEEDED)

    def test_the_three_results_are_all_truthy(self):
        """The old bool return is why #89 existed. A truthiness test must not come back."""
        results = (svc.SYNC_RESULT_NOT_NEEDED, svc.SYNC_RESULT_SYNCED, svc.SYNC_RESULT_FAILED)
        for value in results:
            self.assertTrue(value)
        self.assertEqual(len(set(results)), 3)


# --- punch list #91: fields the feed did not send --------------------------------------
#
# The ingestion runs for real against SQLite. The three things that need PostGIS are
# replaced: the city/zone lookups (answer "inside zone 1") and the geom mirror UPDATE
# (ST_GeomFromGeoJSON), which becomes a no-op statement.

def _encode_polyline(points):
    """Google polyline encoding at 1e5, the inverse of PythonGeometryDecoder."""
    out, prev_lat, prev_lng = [], 0, 0
    for lat, lng in points:
        for value, prev in ((round(lat * 1e5), prev_lat), (round(lng * 1e5), prev_lng)):
            delta = value - prev
            delta = ~(delta << 1) if delta < 0 else (delta << 1)
            while delta >= 0x20:
                out.append(chr((0x20 | (delta & 0x1f)) + 63))
                delta >>= 5
            out.append(chr(delta + 63))
        prev_lat, prev_lng = round(lat * 1e5), round(lng * 1e5)
    return "".join(out)


def _feeds(drivebc_events, muni_issues=(), muni_paths=()):
    """An urlopen stand-in serving the given DriveBC events and Municipal 511 issues."""
    muni = {
        "Issues": list(muni_issues),
        # One continuous encoding: the decoder carries its running deltas across issues.
        "CoordsEncoded": _encode_polyline([pt for path in muni_paths for pt in path]),
    }

    def _urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "open511" in url:
            return _Resp(json.dumps({"events": list(drivebc_events)}).encode())
        if url.endswith("municipality=coquitlam"):
            return _Resp(b'{"jsonData0.txt":"jsonData0.txt"}')
        return _Resp(json.dumps(muni).encode())

    return _urlopen


def _event(**overrides):
    evt = {
        "id": "drivebc.ca/DBC-1",
        "severity": "MAJOR",
        "road_name": "Lougheed Hwy",
        "headline": "CONSTRUCTION",
        "description": "Lane closed.",
        "geography": {"type": "Point", "coordinates": [-122.80, 49.28]},
        "schedule": {"intervals": ["2026-09-01T00:00Z/2099-01-01T00:00Z"]},
    }
    evt.update(overrides)
    return {k: v for k, v in evt.items() if v is not _ABSENT}


_ABSENT = object()


class FeedGapTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import text as sa_text
        self.engine = create_engine("sqlite://")
        _Base.metadata.create_all(
            bind=self.engine,
            tables=[RoadClosureModel.__table__, RoadClosureSyncStatusModel.__table__],
        )
        self.db = sessionmaker(bind=self.engine)()
        self.patches = [
            patch.object(svc, "is_within_city", lambda db, geo: True),
            patch.object(svc, "resolve_zones_and_hall", lambda db, geo: (["1"], "1", "1")),
            patch.object(svc, "text", lambda sql: sa_text("SELECT 1")),
            patch.object(svc, "closure_city_bbox", lambda db: (-122.89492, 49.2184, -122.6197, 49.35263)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.db.close()

    def _sync(self, *args, **kwargs):
        with patch("urllib.request.urlopen", _feeds(*args, **kwargs)):
            return svc.sync_road_closures_to_db(self.db)

    def _rows(self):
        return self.db.query(RoadClosureModel).order_by(RoadClosureModel.id).all()

    # --- ruling 5: DriveBC access from roads[].state, never severity ----------

    def _one(self, **event):
        self.db.query(RoadClosureModel).delete()
        self.db.commit()
        self._sync([_event(**event)])
        (row,) = self._rows()
        return row

    def _access(self, row):
        return (row.emergency_access, row.closure_type, row.road_state, row.road_direction)

    def test_measured_major_with_all_lanes_open_is_informational_not_no_access(self):
        # 2026-09-16: 18 MAJOR events had every lane open.
        row = self._one(severity="MAJOR", roads=[_road("ALL_LANES_OPEN", "BOTH")])
        # INFO since 2026-09-17 (#91): one field carries the tier for both feeds.
        self.assertEqual(self._access(row), ("INFO", None, "ALL_LANES_OPEN", "BOTH"))
        self.assertEqual(row.feed_severity, "MAJOR")

    def test_measured_minor_closed_both_ways_is_no_access(self):
        # 2026-09-16: 5 MINOR events were CLOSED.
        for direction in ("BOTH", "NONE", _ABSENT):
            with self.subTest(direction=direction):
                row = self._one(severity="MINOR", roads=[_road("CLOSED", direction)])
                self.assertEqual(row.emergency_access, "NO_ACCESS")
                self.assertEqual(row.closure_type, "FULL_CLOSURE")
                self.assertEqual(row.feed_severity, "MINOR")

    def test_closed_in_one_direction_is_caution_and_carries_the_direction(self):
        for direction in ("N", "NW", "W", "SW", "S", "SE", "E", "NE", "ne"):
            with self.subTest(direction=direction):
                row = self._one(roads=[_road("CLOSED", direction)])
                self.assertEqual(self._access(row),
                                 ("CAUTION", "LANE_RESTRICTION", "CLOSED", direction.upper()))

    def test_unused_spec_states_are_caution_not_unknown(self):
        for state in ("SOME_LANES_CLOSED", "SINGLE_LANE_ALTERNATING"):
            with self.subTest(state=state):
                row = self._one(roads=[_road(state, "BOTH")])
                self.assertEqual(row.emergency_access, "CAUTION")
                self.assertEqual(row.road_state, state)

    def test_absent_state_is_null_and_logged(self):
        # Measured: 52 of 306 events carried no state.
        for roads in (_ABSENT, [], [_road(_ABSENT, "BOTH")]):
            with self.subTest(roads=roads):
                self.db.query(RoadClosureModel).delete()
                self.db.commit()
                with self.assertLogs(svc.logger, level="WARNING") as logs:
                    self._sync([_event(roads=roads)])
                (row,) = self._rows()
                self.assertEqual(self._access(row)[:3], (None, None, None))
                self.assertIn(
                    "WARNING:" + svc.logger.name + ":1 of 1 records stored with no stated "
                    "severity (Municipal 511: 0, DriveBC Open511: 1)", logs.output)

    # --- #92: ask the feeds for Coquitlam, not the province ----------------------

    def test_drivebc_is_asked_for_the_city_box_active_only_with_no_cap(self):
        seen = []
        inner = _feeds([_event()])

        def spy(req, timeout=None):
            seen.append(req.full_url)
            return inner(req, timeout)

        with patch("urllib.request.urlopen", spy):
            svc.sync_road_closures_to_db(self.db)
        (drivebc,) = [u for u in seen if "open511" in u]
        self.assertTrue(drivebc.startswith("https://api.open511.gov.bc.ca/events?"))
        self.assertIn("status=ACTIVE", drivebc)
        self.assertIn("bbox=-122.89492%2C49.21840%2C-122.61970%2C49.35263", drivebc)
        self.assertNotIn("limit=", drivebc)

    def test_drivebc_follows_the_feeds_pagination(self):
        pages = {
            "first": {"events": [_event(id="p1", road_name="A St")],
                      "pagination": {"offset": "0", "next_url": "https://api.open511.gov.bc.ca/events?page=2"}},
            "second": {"events": [_event(id="p2", road_name="B St")], "pagination": {"offset": "1"}},
        }
        inner = _feeds([])

        def urlopen(req, timeout=None):
            url = req.full_url
            if url.endswith("page=2"):
                return _Resp(json.dumps(pages["second"]).encode())
            if "open511" in url:
                return _Resp(json.dumps(pages["first"]).encode())
            return inner(req, timeout)

        with patch("urllib.request.urlopen", urlopen):
            svc.sync_road_closures_to_db(self.db)
        self.assertEqual(sorted(r.closure_id for r in self._rows()), ["p1", "p2"])

    def test_no_city_box_means_drivebc_is_not_asked_and_the_sync_fails(self):
        seen = []
        inner = _feeds([_event()])

        def spy(req, timeout=None):
            seen.append(req.full_url)
            return inner(req, timeout)

        with patch.object(svc, "closure_city_bbox", lambda db: None), \
                patch("urllib.request.urlopen", spy):
            svc.sync_road_closures_to_db(self.db)
        self.assertFalse(any("open511" in u for u in seen))
        status = svc.read_sync_status(self.db)
        self.assertEqual(status["outcome"], svc.SYNC_FAILED)
        self.assertFalse(status["sources"]["DriveBC Open511"]["reached"])

    def test_municipal_keeps_only_the_citys_own_issues_and_stays_aligned(self):
        # Another client's issue and a MOTI copy come first in the file: they are skipped,
        # but their points are consumed, so the City's issue still gets its own geometry.
        florida = dict(_muni_issue(issue_id=11, rct=262144, location="Pine Terrace"),
                       Source="Transnomis Solutions")
        moti = dict(_muni_issue(issue_id=12, rct=262144, location="Mary Hill Bypass"),
                    Source="BC MOTI Gateway")
        city = _muni_issue(issue_id=13, rct=262144, location="Como Lake Ave")
        calls = []
        real = svc.is_within_city

        def within(db, geo):
            calls.append(geo)
            return True

        with patch.object(svc, "is_within_city", within):
            self._sync([], muni_issues=[florida, moti, city], muni_paths=[_PATH, _PATH2, _PATH3])
        (row,) = self._rows()
        self.assertEqual((row.closure_id, row.source), ("muni_13_0", "City of Coquitlam"))
        # Only the City's geometry reached a spatial test, and it is the third path, not the first.
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["coordinates"][0], [_PATH3[0][1], _PATH3[0][0]])

    # --- #92: Municipal 511 data files fetched concurrently ---------------------

    def _muni_files(self, files, fail=(), barrier=None):
        """urlopen for a page listing `files` (name -> (issues, paths)); names in `fail` raise."""
        page = json.dumps({f"{n}.txt": n for n in files}).encode()

        def urlopen(req, timeout=None):
            url = req.full_url
            if "open511" in url:
                return _Resp(json.dumps({"events": []}).encode())
            if url.endswith("municipality=coquitlam"):
                return _Resp(page)
            name = url.rsplit("/", 1)[-1]
            if barrier is not None:
                barrier.wait()  # every file request must be in flight at once to pass
            if name in fail:
                raise OSError(f"timed out: {name}")
            issues, paths = files[name]
            return _Resp(json.dumps({"Issues": issues, "CoordsEncoded":
                                     _encode_polyline([pt for path in paths for pt in path])}).encode())
        return urlopen

    def test_municipal_files_are_fetched_at_the_same_time(self):
        import threading
        files = {f"jsonData{i}": ([], []) for i in range(3)}
        barrier = threading.Barrier(3, timeout=5)
        with patch("urllib.request.urlopen", self._muni_files(files, barrier=barrier)):
            svc.sync_road_closures_to_db(self.db)
        # A sequential fetch would break the barrier and mark the feed not reached.
        self.assertTrue(svc.read_sync_status(self.db)["sources"]["Municipal 511"]["reached"])

    def test_each_file_keeps_its_own_geometry_when_fetched_concurrently(self):
        files = {
            "jsonData0": ([_muni_issue(issue_id=1, rct=262144, location="A St"),
                           _muni_issue(issue_id=2, rct=262144, location="B St")], [_PATH, _PATH2]),
            "jsonData1": ([_muni_issue(issue_id=3, rct=262144, location="C St")], [_PATH3]),
        }
        with patch("urllib.request.urlopen", self._muni_files(files)):
            svc.sync_road_closures_to_db(self.db)
        got = {r.closure_id: r.coordinates for r in self._rows()}
        mid = lambda path: [path[len(path) // 2][0], path[len(path) // 2][1]]
        self.assertEqual(got, {"muni_1_0": mid(_PATH), "muni_2_0": mid(_PATH2), "muni_3_0": mid(_PATH3)})

    def test_one_failed_file_still_marks_municipal_511_not_reached(self):
        files = {"jsonData0": ([_muni_issue(issue_id=1, rct=262144)], [_PATH]),
                 "jsonData1": ([], [])}
        with patch("urllib.request.urlopen", self._muni_files(files, fail={"jsonData1"})):
            svc.sync_road_closures_to_db(self.db)
        status = svc.read_sync_status(self.db)
        self.assertFalse(status["sources"]["Municipal 511"]["reached"])
        self.assertIn("jsonData1: timed out", status["sources"]["Municipal 511"]["error"])
        self.assertEqual(status["outcome"], svc.SYNC_FAILED)
        # The file that did arrive is still ingested, as it was when fetched in sequence.
        self.assertEqual([r.closure_id for r in self._rows()], ["muni_1_0"])

    def test_severity_is_one_summary_line_per_sync_not_one_per_record(self):
        # #91: ~70 per-record ERROR lines a sync buried the id-less skip lines.
        drivebc = [_event(id="gap", road_name="A St"),
                   _event(id="info", road_name="B St", roads=[_road("ALL_LANES_OPEN", "BOTH")]),
                   _event(id="closed", road_name="C St", roads=[_road("CLOSED", "BOTH")]),
                   _event(id=_ABSENT, road_name="Skipped St")]
        muni = [_muni_issue(issue_id=1, rct=0), _muni_issue(issue_id=2, rct=32),
                _muni_issue(issue_id=3, rct=262144)]
        with self.assertLogs(svc.logger, level="DEBUG") as logs:
            self._sync(drivebc, muni_issues=muni, muni_paths=[_PATH, _PATH2, _PATH3])
        summaries = [m for m in logs.output if "no stated severity" in m]
        self.assertEqual(summaries, [
            "WARNING:" + svc.logger.name + ":2 of 6 records stored with no stated severity "
            "(Municipal 511: 1, DriveBC Open511: 1)"])
        errors = [m for m in logs.output if m.startswith("ERROR:")]
        # The only ERROR left is the id-less skip, per record.
        self.assertEqual(len(errors), 1)
        self.assertIn("no id in the feed", errors[0])

    def test_no_summary_line_when_every_severity_is_stated(self):
        with self.assertLogs(svc.logger, level="DEBUG") as logs:
            self._sync([_event(roads=[_road("CLOSED", "BOTH")])])
        self.assertFalse(any("no stated severity" in m for m in logs.output))

    def test_state_outside_the_spec_is_null_and_named_in_one_error(self):
        with self.assertLogs(svc.logger, level="ERROR") as logs:
            row = self._one(roads=[_road("PARTLY_OPEN", "BOTH")])
        self.assertIsNone(row.emergency_access)
        self.assertIsNone(row.road_state)
        self.assertEqual(sum("PARTLY_OPEN" in m for m in logs.output), 1)

    def test_all_lanes_open_is_not_logged_as_a_gap(self):
        with self.assertLogs(svc.logger, level="INFO") as logs:
            self._one(roads=[_road("ALL_LANES_OPEN", "BOTH")])
        self.assertFalse(any("ERROR" in m for m in logs.output))

    def test_severity_is_carried_as_the_feeds_word_and_never_sets_the_tier(self):
        for sev in ("MINOR", "MODERATE", "MAJOR", "UNKNOWN"):
            with self.subTest(severity=sev):
                row = self._one(severity=sev, roads=[_road("SOME_LANES_CLOSED", "BOTH")])
                self.assertEqual(row.feed_severity, sev)
                self.assertEqual(row.emergency_access, "CAUTION")
        row = self._one(severity=_ABSENT, roads=[_road("CLOSED", "BOTH")])
        self.assertIsNone(row.feed_severity)
        self.assertEqual(row.emergency_access, "NO_ACCESS")

    def test_several_roads_serve_the_most_restrictive_and_log_the_disagreement(self):
        with self.assertLogs(svc.logger, level="WARNING") as logs:
            row = self._one(roads=[_road("ALL_LANES_OPEN", "BOTH"), _road("CLOSED", "E"),
                                   _road("CLOSED", "BOTH")])
        self.assertEqual(self._access(row), ("NO_ACCESS", "FULL_CLOSURE", "CLOSED", "BOTH"))
        self.assertTrue(any("disagree" in m for m in logs.output))

        row = self._one(roads=[_road(_ABSENT, "BOTH"), _road("ALL_LANES_OPEN", "BOTH")])
        self.assertEqual(row.road_state, "ALL_LANES_OPEN")

    def test_drivebc_street_is_the_name_of_the_road_the_tier_came_from(self):
        # Measured shape: no top-level road_name, the name in roads[] (#92, RIDE-100086).
        row = self._one(road_name=_ABSENT, roads=[dict(_road("ALL_LANES_OPEN", "BOTH"), name="Highway 7B")])
        self.assertEqual(row.street_name, "Highway 7B")
        row = self._one(road_name=_ABSENT, roads=[dict(_road("ALL_LANES_OPEN", "BOTH"), name="Highway 1"),
                                                  dict(_road("CLOSED", "BOTH"), name="Highway 7")])
        self.assertEqual((row.street_name, row.emergency_access), ("Highway 7", "NO_ACCESS"))
        row = self._one(road_name=_ABSENT, roads=[{k: v for k, v in _road("CLOSED", "BOTH").items() if k != "name"}])
        self.assertIsNone(row.street_name)

    def test_municipal_rows_carry_no_open511_fields(self):
        self._sync([], muni_issues=[_muni_issue(issue_id=9, rct=262144)], muni_paths=[_PATH])
        (row,) = self._rows()
        self.assertEqual((row.road_state, row.road_direction, row.feed_severity),
                         (None, None, None))

    # --- #91 ruled 2026-09-17: Municipal 511 type -> tier ------------------------

    def test_every_vendor_type_gets_the_ruled_tier(self):
        ruled = {
            # 16384 Local Traffic Only and 1 Detour: full closure "for now", operator 2026-09-17.
            262144: "NO_ACCESS", 16384: "NO_ACCESS", 1: "NO_ACCESS",
            65536: "ACCESS_ONLY", 32768: "ACCESS_ONLY",
            32: "CAUTION", 2048: "CAUTION", 8192: "CAUTION", 131072: "CAUTION", 4096: "CAUTION",
            2: "INFO", 4: "INFO", 8: "INFO", 16: "INFO", 64: "INFO", 128: "INFO", 256: "INFO",
            512: "INFO", 1024: "INFO",
            0: None,
        }
        self.assertEqual(len(ruled), 20)  # the vendor's twenty values, 0 Unknown included
        for rct, tier in ruled.items():
            with self.subTest(rct=rct):
                self.db.query(RoadClosureModel).delete()
                self.db.commit()
                self._sync([], muni_issues=[_muni_issue(issue_id=rct, rct=rct, base="Lane closed.")],
                           muni_paths=[_PATH])
                (row,) = self._rows()
                self.assertEqual(row.emergency_access, tier)

    def test_a_value_outside_the_twenty_is_null_with_one_error_and_unknown_has_none(self):
        with self.assertLogs(svc.logger, level="ERROR") as logs:
            self._sync([], muni_issues=[_muni_issue(issue_id=5, rct=524288, base="Lane closed.")],
                       muni_paths=[_PATH])
        (row,) = self._rows()
        self.assertIsNone(row.emergency_access)
        self.assertEqual(sum("524288" in m for m in logs.output), 1)

        self.db.query(RoadClosureModel).delete()
        self.db.commit()
        with self.assertLogs(svc.logger, level="DEBUG") as logs:
            self._sync([], muni_issues=[_muni_issue(issue_id=6, rct=0, base="Lane closed.")],
                       muni_paths=[_PATH])
        self.assertFalse(any(m.startswith("ERROR:") for m in logs.output))

    def test_road_closed_text_raises_any_lower_tier_and_never_lowers_one(self):
        # Operator 2026-09-17: "Added text should elevate as necessary." The measured case is
        # Alternating Traffic noting "full closure dec 5".
        self._sync([], muni_issues=[
            _muni_issue(issue_id=1, rct=2048, base="5515441 - full closure dec 5"),
            _muni_issue(issue_id=2, rct=8, base="Road closed to pedestrians"),
            _muni_issue(issue_id=3, rct=0, base="Road closed for paving."),
            _muni_issue(issue_id=4, rct=262144, base="Road closed, full closure"),
            _muni_issue(issue_id=5, rct=32, base="Lane closed."),
        ], muni_paths=[_PATH, _PATH2, _PATH3, _PATH, _PATH2])
        tiers = {r.closure_id: r.emergency_access for r in self._rows()}
        self.assertEqual(tiers, {"muni_1_0": "ACCESS_ONLY", "muni_2_0": "ACCESS_ONLY",
                                 "muni_3_0": "ACCESS_ONLY", "muni_4_0": "NO_ACCESS",
                                 "muni_5_0": "CAUTION"})

    def test_info_ranks_below_caution_and_above_unknown_across_roads(self):
        row = self._one(roads=[_road("ALL_LANES_OPEN", "BOTH"), _road("SOME_LANES_CLOSED", "BOTH")])
        self.assertEqual((row.emergency_access, row.road_state), ("CAUTION", "SOME_LANES_CLOSED"))
        row = self._one(roads=[_road(_ABSENT, "BOTH"), _road("ALL_LANES_OPEN", "BOTH")])
        self.assertEqual((row.emergency_access, row.road_state), ("INFO", "ALL_LANES_OPEN"))

    def test_municipal_record_with_no_stated_type_is_null_not_caution(self):
        issue = _muni_issue(issue_id=7, rct=0, headline="Community event", base="Street fair.")
        self._sync([], muni_issues=[issue], muni_paths=[_PATH])
        (row,) = self._rows()
        self.assertIsNone(row.closure_type)
        self.assertIsNone(row.emergency_access)

    def test_municipal_stated_type_still_raises_it(self):
        self._sync([], muni_issues=[
            _muni_issue(issue_id=1, rct=262144),
            _muni_issue(issue_id=2, rct=0, base="Road closed for paving."),
        ], muni_paths=[_PATH, _PATH2])
        rows = {r.closure_id: r for r in self._rows()}
        self.assertEqual(rows["muni_1_0"].emergency_access, "NO_ACCESS")
        self.assertEqual(rows["muni_2_0"].emergency_access, "ACCESS_ONLY")

    # --- ruling: text the feed did not send ----------------------------------

    def test_missing_text_is_null_not_a_placeholder(self):
        self._sync([_event(road_name=_ABSENT, headline=None, description="   ")])
        (row,) = self._rows()
        self.assertIsNone(row.street_name)
        self.assertIsNone(row.headline)
        self.assertIsNone(row.description)

    def test_municipal_missing_text_is_null_not_a_placeholder(self):
        issue = _muni_issue(issue_id=3, rct=262144, location=None, headline=None, base=None)
        self._sync([], muni_issues=[issue], muni_paths=[_PATH])
        (row,) = self._rows()
        self.assertIsNone(row.street_name)
        self.assertIsNone(row.headline)
        self.assertIsNone(row.description)

    # --- ruling (reversed): a record with no feed id is skipped ---------------

    def test_id_less_drivebc_record_is_skipped_logged_and_counted(self):
        for missing in (_ABSENT, None, "", "  "):
            with self.subTest(id=missing):
                self.db.query(RoadClosureModel).delete()
                self.db.commit()
                with self.assertLogs(svc.logger, level="ERROR") as logs:
                    self._sync([_event(id="has-id", road_name="A St"),
                                _event(id=missing, road_name="Skipped St")])
                ids = [r.closure_id for r in self._rows()]
                self.assertEqual(ids, ["has-id"])
                self.assertTrue(any("no id in the feed" in m and "Skipped St" in m
                                    for m in logs.output))
                status = svc.read_sync_status(self.db)
                self.assertEqual(status["skipped"],
                                 {"count": 1, "bySource": {"DriveBC Open511": 1,
                                                           "Municipal 511": 0}})
                self.assertEqual(status["outcome"], svc.SYNC_SUCCEEDED)

    def test_id_less_municipal_record_is_skipped_not_muni_none(self):
        with self.assertLogs(svc.logger, level="ERROR") as logs:
            self._sync([], muni_issues=[_muni_issue(issue_id=None, rct=262144,
                                                    location="Como Lake Ave")],
                       muni_paths=[_PATH])
        self.assertEqual(self._rows(), [])
        self.assertTrue(any("Municipal 511" in m and "Como Lake Ave" in m for m in logs.output))
        self.assertEqual(svc.read_sync_status(self.db)["skipped"]["bySource"]["Municipal 511"], 1)

    def test_skipped_count_resets_on_the_next_attempt(self):
        self._sync([_event(id=_ABSENT)])
        self.assertEqual(svc.read_sync_status(self.db)["skipped"]["count"], 1)
        self._sync([_event(id="ok")])
        self.assertEqual(svc.read_sync_status(self.db)["skipped"]["count"], 0)

    def test_a_status_row_without_counts_reads_skipped_null_not_zero(self):
        svc.record_sync_outcome(self.db, svc.SYNC_SUCCEEDED,
                                sources={"DriveBC Open511": {"reached": True}})
        self.assertIsNone(svc.read_sync_status(self.db)["skipped"])


def _road(state, direction):
    """One Open511 roads[] entry with the fields DriveBC supports."""
    road = {"name": "Lougheed Hwy", "from": "A", "to": "B", "state": state,
            "direction": direction}
    return {k: v for k, v in road.items() if v is not _ABSENT}


_PATH = [(49.28, -122.80), (49.281, -122.801)]
_PATH2 = [(49.29, -122.81), (49.291, -122.811)]
_PATH3 = [(49.27, -122.79), (49.271, -122.791)]


def _muni_issue(issue_id, rct, location="Como Lake Ave", headline="Paving", base="Lane closed."):
    return {
        "IssueId": issue_id,
        "Source": "City of Coquitlam",
        "Geometry": [{"NumPoints": 2, "MarkerInfo": {"RoadClosureType": rct,
                                                     "LocationName": location}}],
        "Description": {"Headline": headline, "BaseDescription": base},
    }

if __name__ == "__main__":
    unittest.main()
