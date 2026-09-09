"""
Comprehensive Integration Tests for Decomposed FastAPI Routers in CFR EVO.
Tests auth, dispatches, parcels, streetview, routing, road closures, evaluations, audio, and tiles.
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt

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

try:
    from api.server import app, health_check
    from api.database import Base, engine, SessionLocal
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
except ModuleNotFoundError:
    from backend.api.server import app, health_check
    from backend.api.database import Base, engine, SessionLocal
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

# Ensure database schema exists
Base.metadata.create_all(bind=engine)


class TestAPIRouters(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

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
        # The row this test writes lands in the only Postgres there is -- the kiosk's live
        # parcels table -- and it was found there as a real-looking address with a saved
        # Street View (2026-09-06). Remove it when the test ends, pass or fail.
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
        closures = get_road_closures(db=self.db)
        self.assertTrue(isinstance(closures, list))

    def test_audio_and_tiles_routers(self):
        status = get_listener_status()
        self.assertIn("status", status)

        # "ortho" since 2026-08-31; the Esri "satellite" layer was retired.
        tile_resp = _serve_tile("ortho", 15, 5250, 11420, ext="jpg")
        self.assertEqual(tile_resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
