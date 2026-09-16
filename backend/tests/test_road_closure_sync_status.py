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

    def tearDown(self):
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
        "CoordsEncoded": "".join(_encode_polyline(p) for p in muni_paths),
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

    # --- ruling 1: unknown severity ------------------------------------------

    def test_missing_severity_is_stored_null_and_logged_not_minor(self):
        for sev in (_ABSENT, None, "", "  ", "UNKNOWN", "unknown"):
            with self.subTest(severity=sev):
                self.db.query(RoadClosureModel).delete()
                self.db.commit()
                with self.assertLogs(svc.logger, level="ERROR") as logs:
                    self._sync([_event(severity=sev)])
                (row,) = self._rows()
                self.assertIsNone(row.closure_type)
                self.assertIsNone(row.emergency_access)
                self.assertTrue(any("DBC-1" in m and "severity" in m for m in logs.output))

    def test_present_severity_keeps_its_existing_mapping(self):
        self._sync([_event(id="a", severity="MAJOR"), _event(id="b", severity="minor")])
        rows = {r.closure_id: r for r in self._rows()}
        self.assertEqual((rows["a"].closure_type, rows["a"].emergency_access),
                         ("FULL_CLOSURE", "NO_ACCESS"))
        self.assertEqual((rows["b"].closure_type, rows["b"].emergency_access),
                         ("LANE_RESTRICTION", "CAUTION"))

    # --- ruling 2: missing feed id -------------------------------------------

    def test_missing_id_is_kept_null_and_never_positional(self):
        for missing in (_ABSENT, None, ""):
            with self.subTest(id=missing):
                self.db.query(RoadClosureModel).delete()
                self.db.commit()
                with self.assertLogs(svc.logger, level="ERROR") as logs:
                    self._sync([_event(id="has-id", road_name="A St"),
                                _event(id=missing, road_name="B St")])
                ids = sorted((r.closure_id or "<null>") for r in self._rows())
                self.assertEqual(ids, ["<null>", "has-id"])
                for r in self._rows():
                    self.assertFalse((r.closure_id or "").startswith("db_"))
                    self.assertNotEqual(r.closure_id, "None")
                self.assertTrue(any("no id in the feed record" in m for m in logs.output))

    def test_id_less_record_is_matched_across_syncs_not_duplicated(self):
        evt = _event(id=_ABSENT)
        self._sync([evt])
        (first,) = self._rows()
        self.assertIsNone(first.closure_id)
        self.assertTrue(first.feed_record_key.startswith("sha256:"))
        row_id = first.id

        # Hourly sync, then one where the feed edited the headline and severity in place.
        self._sync([evt])
        self._sync([dict(evt, headline="EDITED", severity="MINOR")])
        (row,) = self._rows()
        self.assertEqual(row.id, row_id)
        self.assertEqual(row.headline, "EDITED")
        self.assertEqual(row.emergency_access, "CAUTION")

    def test_two_different_id_less_records_stay_two_rows(self):
        self._sync([_event(id=_ABSENT, road_name="A St"), _event(id=_ABSENT, road_name="B St")])
        self.assertEqual(len(self._rows()), 2)

    def test_identical_id_less_records_in_one_batch_collapse_loudly(self):
        evt = _event(id=_ABSENT)
        with self.assertLogs(svc.logger, level="ERROR") as logs:
            self._sync([evt, dict(evt)])
        self.assertEqual(len(self._rows()), 1)
        self.assertTrue(any("share content key" in m for m in logs.output))

    def test_id_less_record_is_deactivated_when_it_leaves_the_feed(self):
        gone = _event(id=_ABSENT, road_name="Gone St")
        self._sync([gone, _event(id="stays")])
        self._sync([_event(id="stays")])
        rows = {r.street_name: r for r in self._rows()}
        self.assertFalse(rows["Gone St"].active)
        self.assertTrue(rows["Lougheed Hwy"].active)

    def test_municipal_issue_without_issue_id_is_null_not_muni_none(self):
        issue = {
            "IssueId": None,
            "Source": "City of Coquitlam",
            "Geometry": [{"NumPoints": 2, "MarkerInfo": {"RoadClosureType": 0,
                                                         "LocationName": "Como Lake Ave"}}],
            "Description": {"Headline": "Paving", "BaseDescription": "Lane closed."},
        }
        path = [(49.28, -122.80), (49.281, -122.801)]
        self._sync([], muni_issues=[issue], muni_paths=[path])
        self._sync([], muni_issues=[issue], muni_paths=[path])
        (row,) = self._rows()
        self.assertIsNone(row.closure_id)
        self.assertIsNotNone(row.feed_record_key)


if __name__ == "__main__":
    unittest.main()
