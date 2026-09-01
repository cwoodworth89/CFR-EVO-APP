"""
Comprehensive Integration Tests for Decomposed FastAPI Routers in CFR EVO.
Tests auth, dispatches, parcels, streetview, routing, road closures, evaluations, audio, and tiles.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock

# Add project root and backend dir to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
ROOT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

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

        # 1. Login success
        login_res = login(LoginRequest(username="cfradmin", password="rescue"), mock_req)
        self.assertIn("access_token", login_res)
        token = login_res["access_token"]

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
