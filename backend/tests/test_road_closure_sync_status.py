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


if __name__ == "__main__":
    unittest.main()
