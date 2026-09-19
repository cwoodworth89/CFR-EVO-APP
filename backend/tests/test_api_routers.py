"""
Comprehensive Integration Tests for Decomposed FastAPI Routers in CFR EVO.
Tests auth, dispatches, parcels, streetview, routing, road closures, evaluations, audio, and tiles.

**This suite runs against a throwaway SQLite file and never touches the kiosk.** Until
2026-09-19 it did: `api.database`'s engine is bound to `DATABASE_URL`, which points at the
kiosk's PostgreSQL -- the only database this system has -- so the suite ran `create_all`
there and then created, updated and deleted `TEST-ROUTER-DISPATCH-999` and a
`5000 TESTING WAY` parcel in production. The parcel row was found there on 2026-09-06 with a
saved Street View, reading as a real address (backlog #35a).
"""
import atexit
import logging
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Add project root and backend dir to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
ROOT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# The token signing key is read from the environment per call (auth.py); unset, login answers
# 503. A test key, not a secret: it signs nothing outside this process.
os.environ.setdefault("JWT_SECRET", "unit-test-signing-key")

# --- the throwaway database ---------------------------------------------------------------
# `api.database` cannot be pointed at a test database: it refuses any non-PostgreSQL URL and
# exits the process when Postgres is unreachable, both deliberately (punch-list #61 -- the
# SQLite fallback it replaced let a whole agent's work land in a file nobody read). So it is
# replaced with a stub bound to a temp-file SQLite engine *before* anything imports it, which
# is the pattern already used by test_road_closure_sync_status.py:24-59.
#
# Both spellings are stubbed. `backend/` and `backend/api/` have no __init__.py, so `api.X`
# and `backend.api.X` are two namespace-package routes to the same source file and would
# otherwise import as two separate module objects with two separate engines -- this file
# imports `api.server`, while `api/server.py` internally prefers `backend.api.database`.
# One stub object under both names keeps the whole graph on one engine and one MetaData.
#
# The real entries are put back afterwards: other files in this directory (for instance
# test_parcels_and_streetview_api.py) import the same modules and do want the kiosk.
_DB_FD, _DB_PATH = tempfile.mkstemp(prefix="cfr_test_api_routers_", suffix=".sqlite")
os.close(_DB_FD)
TEST_DATABASE_URL = "sqlite:///" + _DB_PATH.replace("\\", "/")


@atexit.register
def _drop_test_database():
    # dispose() first: the engine's pool can still hold an open handle on the file, and
    # Windows refuses to unlink a file that is open, so an unlink without it left a stray
    # .sqlite in %TEMP% on every run. Reported rather than swallowed -- a cleanup that
    # cannot say it failed is how the litter went unnoticed.
    test_engine.dispose()
    try:
        os.unlink(_DB_PATH)
    except OSError as exc:
        logging.warning("could not remove the router suite's temp database %s: %s", _DB_PATH, exc)


def _api_module_names():
    """Every `api.*` / `backend.api.*` entry currently in sys.modules."""
    return [n for n in list(sys.modules)
            if n in ("api", "backend.api") or n.startswith(("api.", "backend.api."))]


# Saved, not merely noted: the restore below has to put back *exactly* this set. An earlier
# version re-installed only the names that already existed, which left every module first
# imported under the stub -- server, models, schemas, every router -- in sys.modules still
# bound to the SQLite engine and the stub Base. Which database a later test file reached then
# depended on collection order. The sibling pattern is test_road_closure_sync_status.py:53-57.
_SAVED = {n: sys.modules.pop(n) for n in _api_module_names()}

test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

_db_stub = types.ModuleType("api.database")
_db_stub.DATABASE_URL = TEST_DATABASE_URL
_db_stub.Base = declarative_base()
_db_stub.engine = test_engine
_db_stub.SessionLocal = TestSessionLocal


def _test_get_db():
    """The stub's `get_db`. Every router captured *this* object at import (`Depends(get_db)`),
    so it is also the key `app.dependency_overrides` has to be keyed on."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


_db_stub.get_db = _test_get_db
sys.modules["api.database"] = _db_stub
sys.modules["backend.api.database"] = _db_stub

# `backend.api.*` first, and this order is load-bearing: every module under backend/api/
# prefers that spelling internally (server.py:27, parcels.py:16, streetview.py:10,
# evaluations.py:12, road_closures.py:17). Importing `api.*` here instead produced a SECOND
# module object per source file, so every model class was declared twice on one MetaData --
# and because `extend_existing=True` re-appends each `index=True` column's Index, create_all
# then emitted `CREATE UNIQUE INDEX ix_dispatches_dispatch_id` twice and failed. Against
# Postgres that stayed invisible, because create_all skips tables that already exist there.
try:
    from backend.api.server import app, health_check
    from backend.api.database import Base, engine, SessionLocal, get_db
    from backend.api.models import LiveCallModel, ParcelModel
    from backend.api.schemas import (
        LoginRequest,
        DispatchCreateSchema,
        DispatchUpdateSchema,
        FeedbackSchema,
        ParcelCameraOverrideSchema,
        StreetViewOverrideSchema
    )
    from backend.api.routers.auth import login, get_session, get_me, logout
    from backend.api.routers.dispatches import (
        get_dispatches,
        create_or_upsert_dispatch,
        get_dispatch_by_id,
        update_dispatch,
        submit_dispatch_feedback,
        get_dispatch_stats,
        get_unverified_dispatches,
        delete_dispatch,
        serialize_call
    )
    from backend.api.routers.parcels import (
        lookup_parcel,
        search_parcels,
        save_parcel_streetview,
        get_parcels_in_bbox,
        _clean_streetview_address
    )
    from backend.api.routers.streetview import (
        get_all_streetview_overrides,
        get_streetview_override,
        save_streetview_override
    )
    from backend.api.routers.evaluations import get_evaluations, get_metrics_summary
    from backend.api.routers.audio import get_listener_status
    from backend.api.routers.road_closures import get_road_closures, invalidate_road_closures_cache
    from backend.api.routers.tiles import _serve_tile
except ModuleNotFoundError:
    from api.server import app, health_check
    from api.database import Base, engine, SessionLocal, get_db
    from api.models import LiveCallModel, ParcelModel
    from api.schemas import (
        LoginRequest,
        DispatchCreateSchema,
        DispatchUpdateSchema,
        FeedbackSchema,
        ParcelCameraOverrideSchema,
        StreetViewOverrideSchema
    )
    from api.routers.auth import login, get_session, get_me, logout
    from api.routers.dispatches import (
        get_dispatches,
        create_or_upsert_dispatch,
        get_dispatch_by_id,
        update_dispatch,
        submit_dispatch_feedback,
        get_dispatch_stats,
        get_unverified_dispatches,
        delete_dispatch,
        serialize_call
    )
    from api.routers.parcels import (
        lookup_parcel,
        search_parcels,
        save_parcel_streetview,
        get_parcels_in_bbox,
        _clean_streetview_address
    )
    from api.routers.streetview import (
        get_all_streetview_overrides,
        get_streetview_override,
        save_streetview_override
    )
    from api.routers.evaluations import get_evaluations, get_metrics_summary
    from api.routers.audio import get_listener_status
    from api.routers.road_closures import get_road_closures, invalidate_road_closures_cache
    from api.routers.tiles import _serve_tile

# Restore sys.modules to exactly what it was before the swap, for the other test files in
# this directory that import the same names and do want the kiosk. Drop everything the block
# above imported under the stub first -- otherwise those modules stay behind, bound to the
# SQLite engine. The objects imported above keep referring to the stub, which is the point.
for _name in _api_module_names():
    del sys.modules[_name]
sys.modules.update(_SAVED)

# Build the schema in the temp file. Every model is now registered on the stub's Base, so
# this is the whole schema; on PostgreSQL the DDL is unchanged (models.py declares JSON/ARRAY
# /UUID as `.with_variant(...)` types that still render JSONB, ARRAY and UUID there).
Base.metadata.create_all(bind=engine)

# FastAPI resolves `Depends(get_db)` by the function object the router captured at import.
# The stub supplied that object, so the app is already on the temp database; the override is
# the explicit statement of it, and setUpModule asserts no route escaped.
app.dependency_overrides[get_db] = _test_get_db


def setUpModule():
    """Fail loudly rather than run against Postgres.

    The whole point of this file is that it cannot reach the kiosk. That claim is checkable
    in two ways and both are checked here, because the failure mode being guarded against --
    the suite quietly finding the real engine again -- looks exactly like a passing run.
    """
    assert engine.url.get_backend_name() == "sqlite", f"router suite bound to {engine.url!r}"
    assert str(engine.url) == TEST_DATABASE_URL, f"router suite bound to {engine.url!r}"

    escaped = []

    def _walk(dependant, path):
        # Recursive: require_admin and friends carry their own sub-dependants, so a get_db
        # one level down would be invisible to a single-level check.
        for dep in getattr(dependant, "dependencies", None) or []:
            call = getattr(dep, "call", None)
            if getattr(call, "__name__", "") == "get_db" and call not in app.dependency_overrides:
                escaped.append(f"{path} -> {call!r}")
            _walk(dep, path)

    for route in app.routes:
        _walk(getattr(route, "dependant", None), getattr(route, "path", route))
    assert not escaped, "routes reach an un-overridden get_db: " + "; ".join(escaped)


def tearDownModule():
    app.dependency_overrides.pop(get_db, None)


class TestAPIRouters(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_suite_database_is_disposable(self):
        """The guard for backlog #35a: this file must never be able to write to the kiosk."""
        self.assertEqual(self.db.get_bind().url.get_backend_name(), "sqlite")
        self.assertEqual(str(self.db.get_bind().url), TEST_DATABASE_URL)
        self.assertTrue(os.path.isfile(_DB_PATH))

    def test_health_check(self):
        res = health_check()
        self.assertEqual(res["status"], "online")
        self.assertEqual(res["version"], "1.0.0")

    def test_auth_router(self):
        mock_req = MagicMock()
        mock_req.headers = {}
        mock_req.client.host = "127.0.0.1"

        # 1. Login success. The password comes from the environment, never a literal in the
        # tree (punch list #65); auth.py reads ADMIN_PASSWORD, so any value set here is accepted.
        admin_password = os.environ.get("ADMIN_PASSWORD")
        if not admin_password:
            self.skipTest("ADMIN_PASSWORD is not set; the login test never carries a password literal")
        login_res = login(LoginRequest(username="cfradmin", password=admin_password), mock_req)
        self.assertIn("access_token", login_res)
        token = login_res["access_token"]

        # 1b. The three literals the old code accepted beside the configured one are refused,
        # and the 401 no longer names a default (#65).
        from fastapi import HTTPException as _HTTPExc
        for stale in ("cfr2026", "admin", admin_password + "x"):
            with self.assertRaises(_HTTPExc) as ctx:
                login(LoginRequest(username="cfradmin", password=stale), mock_req)
            self.assertEqual(ctx.exception.status_code, 401)
            self.assertNotIn("rescue", ctx.exception.detail)

        # 2. Session verification
        session_res = get_session(mock_req, authorization=f"Bearer {token}")
        self.assertIsNotNone(session_res.get("session"))
        self.assertEqual(session_res["session"]["user"]["username"], "cfradmin")

        # 3. Me alias
        me_res = get_me(mock_req, authorization=f"Bearer {token}")
        self.assertEqual(me_res, session_res)

        # 4. Logout
        logout_res = logout()
        self.assertEqual(logout_res["status"], "success")

    def test_dispatches_router(self):
        dispatch_id = "TEST-ROUTER-DISPATCH-999"
        payload = DispatchCreateSchema(
            dispatch_id=dispatch_id,
            incident_type="Apparatus Routing Test",
            responding_units=["E1", "MEDIC1"],
            raw_transcript="Engine 1 responding to testing street",
            confidence_score=97.0
        )

        # 1. Create or upsert
        created = create_or_upsert_dispatch(payload, db=self.db)
        self.assertEqual(created["dispatch_id"], dispatch_id)
        self.assertEqual(created["incident_type"], "Apparatus Routing Test")

        # 2. Get list
        dispatches = get_dispatches(limit=10, offset=0, db=self.db)
        self.assertTrue(any(d["dispatch_id"] == dispatch_id for d in dispatches))

        # 3. Get single
        single = get_dispatch_by_id(dispatch_id, db=self.db)
        self.assertEqual(single["dispatch_id"], dispatch_id)

        # 4. Update
        updated = update_dispatch(
            dispatch_id,
            DispatchUpdateSchema(incident_type="Structure Fire Confirmed"),
            db=self.db
        )
        self.assertEqual(updated["incident_type"], "Structure Fire Confirmed")

        # 5. Feedback
        feedback_res = submit_dispatch_feedback(
            dispatch_id,
            FeedbackSchema(verified_incident="Structure Fire Level 2", quality_rating="5_STAR"),
            db=self.db
        )
        self.assertTrue(feedback_res["feedback_submitted"])

        # 6. Stats & unverified
        stats = get_dispatch_stats(db=self.db)
        self.assertIn("total_dispatches", stats)

        unverified = get_unverified_dispatches(limit=50, db=self.db)
        self.assertTrue(isinstance(unverified, list))

        # 7. Delete
        del_res = delete_dispatch(dispatch_id, db=self.db)
        self.assertEqual(del_res["status"], "success")

    def test_parcels_and_streetview_router(self):
        # This row used to land in the only Postgres there is -- the kiosk's live parcels
        # table -- where it was found on 2026-09-06 as a real-looking address with a saved
        # Street View (#35a). It now goes to the temp SQLite file built at the top of this
        # module. The cleanup stays so the tests do not depend on each other's order.
        def _remove_test_parcel():
            self.db.query(ParcelModel).filter(ParcelModel.address == "5000 TESTING WAY").delete(synchronize_session=False)
            self.db.commit()
        self.addCleanup(_remove_test_parcel)

        # 1. Save parcel streetview
        save_res = save_parcel_streetview(
            ParcelCameraOverrideSchema(
                address="5000 TESTING WAY, COQUITLAM",
                front_lat=49.285,
                front_lng=-122.805,
                heading=270.0,
                pitch=5.0,
                fov=80.0
            ),
            db=self.db
        )
        self.assertEqual(save_res["status"], "success")

        # 2. Lookup parcel
        lookup_res = lookup_parcel(query="5000 TESTING WAY", db=self.db)
        self.assertTrue(lookup_res["found"])
        self.assertEqual(lookup_res["parcel"]["streetview_heading"], 270.0)

        # 3. Search parcels
        search_res = search_parcels(q="TESTING", limit=5, db=self.db)
        self.assertGreaterEqual(search_res["count"], 1)

        # 4. Streetview overrides
        overrides = get_all_streetview_overrides(db=self.db)
        self.assertIn("5000 TESTING WAY", overrides)

        # 5. Single streetview override
        single_override = get_streetview_override("5000 TESTING WAY", db=self.db)
        self.assertEqual(single_override["heading"], 270.0)

        # 6. Save via streetview router
        sv_save_res = save_streetview_override(
            StreetViewOverrideSchema(
                address="5000 TESTING WAY",
                front_lat=49.285,
                front_lng=-122.805,
                heading=280.0
            ),
            db=self.db
        )
        self.assertEqual(sv_save_res["status"], "success")

        # 7. Bounding box
        bbox_res = get_parcels_in_bbox(
            min_lat=49.0, min_lng=-123.0, max_lat=50.0, max_lng=-122.0, limit=10, db=self.db
        )
        self.assertIn("parcels", bbox_res)

    def test_admin_gate_on_operator_saves(self):
        """The arrival point and the Street View saves answer 401 without an admin token, on
        every route that reaches them; reads stay open; a valid token passes the gate and a
        forged one does not (operator, 2026-09-08: the two saves are admin-only)."""
        from fastapi.testclient import TestClient
        client = TestClient(app)   # no `with`: the lifespan (listener, watchdog) is not started
        sv = {"address": "5000 TESTING WAY", "front_lat": 49.285, "front_lng": -122.805, "heading": 1.0}
        for path, body in [
            ("/api/parcels/entrance", {"address": "5000 TESTING WAY", "set_by": "test"}),
            ("/api/parcels/streetview", sv),
            ("/api/streetview-overrides", sv),
            ("/api/streetview/override", sv),
        ]:
            res = client.post(path, json=body)
            self.assertEqual(res.status_code, 401, f"{path} answered {res.status_code} with no token")
        self.assertEqual(client.get("/api/parcels/lookup", params={"query": "5000 TESTING WAY"}).status_code, 200)

        forged = jwt.encode({"sub": "cfradmin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                            "not-the-configured-key", algorithm="HS256")
        res = client.post("/api/parcels/entrance", json={"address": "5000 TESTING WAY", "set_by": "test"},
                          headers={"Authorization": f"Bearer {forged}"})
        self.assertEqual(res.status_code, 401)

        admin_password = os.environ.get("ADMIN_PASSWORD")
        if not admin_password:
            self.skipTest("ADMIN_PASSWORD is not set; the unlocked half needs a real login")
        login = client.post("/api/auth/login", json={"username": "cfradmin", "password": admin_password})
        self.assertEqual(login.status_code, 200)
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        # Through the gate: a parcel that does not exist answers 404 from the handler, not 401
        # from the gate, and nothing is written.
        res = client.post("/api/parcels/entrance", json={"address": "NO SUCH PARCEL 0", "set_by": "test"}, headers=headers)
        self.assertEqual(res.status_code, 404)

    def test_evaluations_router(self):
        evals = get_evaluations(db=self.db)
        self.assertTrue(isinstance(evals, list))

        metrics = get_metrics_summary(db=self.db)
        self.assertEqual(metrics["status"], "online")
        self.assertIn("telemetry", metrics)
        self.assertIn("containers", metrics)

    def test_road_closures_router(self):
        invalidate_road_closures_cache()
        payload = get_road_closures(db=self.db)
        # Shape changed 2026-09-16 (punch list #89): the outcome of the last sync now
        # travels beside the list, so an empty list can be read.
        self.assertTrue(isinstance(payload, dict))
        self.assertTrue(isinstance(payload["closures"], list))
        self.assertIn(
            payload["sync"]["outcome"], ("NOT_ATTEMPTED", "SUCCEEDED", "FAILED")
        )

    def test_audio_and_tiles_routers(self):
        status = get_listener_status()
        self.assertIn("status", status)

        # "ortho" since 2026-08-31; the Esri "satellite" layer was retired.
        tile_resp = _serve_tile("ortho", 15, 5250, 11420, ext="jpg")
        self.assertEqual(tile_resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
