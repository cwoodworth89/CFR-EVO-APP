#!/usr/bin/env python3
"""
Empirical Challenge Test Harness for Challenger 2 (Milestone 1: Backend & Data Sync)
"""
import sys
import os
import unittest
import logging

# Ensure root and backend are in path
workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
backend_dir = os.path.join(workspace_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base
from api.models import ParcelModel, StreetViewOverrideModel
from api.server import (
    _clean_streetview_address,
    lookup_parcel,
    save_parcel_streetview,
    get_streetview_override,
    save_streetview_override,
    get_all_streetview_overrides,
    ParcelCameraOverrideSchema,
    StreetViewOverrideSchema
)
from scripts.migrate_streetview_to_parcels import migrate_overrides

class TestMilestone1EmpiricalChallenge(unittest.TestCase):

    def setUp(self):
        # Use a temporary SQLite database for isolated test execution
        self.db_path = os.path.join(os.path.dirname(__file__), "test_temp.db")
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        for table in Base.metadata.tables.values():
            try:
                table.create(bind=self.engine, checkfirst=True)
            except Exception:
                pass
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=self.engine)
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # TEST SUITE 1: Legacy streetview_overrides Fallback
    # -------------------------------------------------------------------------
    def test_fallback_lookup_parcel_when_parcels_empty(self):
        """Verify lookup_parcel falls back to streetview_overrides when parcels has no record."""
        # Insert legacy override record only
        legacy = StreetViewOverrideModel(
            clean_address="123 FALLBACK ST",
            front_lat=49.2811,
            front_lng=-122.7911,
            heading=120.0,
            pitch=15.0,
            fov=75.0
        )
        self.db.add(legacy)
        self.db.commit()

        # Query via lookup_parcel using different case / whitespace
        res = lookup_parcel(query=" 123 fallback st ", db=self.db)
        self.assertTrue(res["found"])
        self.assertIsNotNone(res["parcel"])
        self.assertIsNone(res["parcel"]["id"])
        self.assertIsNone(res["parcel"]["gis_id"])
        self.assertEqual(res["parcel"]["clean_address"], "123 FALLBACK ST")
        self.assertEqual(res["parcel"]["front_lat"], 49.2811)
        self.assertEqual(res["parcel"]["front_lng"], -122.7911)
        self.assertEqual(res["parcel"]["streetview_heading"], 120.0)
        self.assertEqual(res["parcel"]["streetview_pitch"], 15.0)
        self.assertEqual(res["parcel"]["streetview_fov"], 75.0)
        self.assertEqual(res["parcel"]["lat"], 49.2811)
        self.assertEqual(res["parcel"]["lng"], -122.7911)
        self.assertEqual(res["parcel"]["heading"], 120.0)

    def test_fallback_get_streetview_override_when_parcels_empty(self):
        """Verify get_streetview_override falls back to streetview_overrides when parcels has no record."""
        legacy = StreetViewOverrideModel(
            clean_address="456 FALLBACK AVE",
            front_lat=49.2900,
            front_lng=-122.7800,
            heading=270.0,
            pitch=0.0,
            fov=90.0
        )
        self.db.add(legacy)
        self.db.commit()

        res = get_streetview_override(address="456 Fallback Ave, Coquitlam", db=self.db)
        self.assertEqual(res["clean_address"], "456 FALLBACK AVE")
        self.assertEqual(res["front_lat"], 49.2900)
        self.assertEqual(res["front_lng"], -122.7800)
        self.assertEqual(res["heading"], 270.0)
        self.assertEqual(res["pitch"], 0.0)
        self.assertEqual(res["fov"], 90.0)
        self.assertEqual(res["lat"], 49.2900)
        self.assertEqual(res["lng"], -122.7800)

    def test_parcel_takes_precedence_over_legacy_override(self):
        """Verify parcels record takes precedence over legacy override if both exist."""
        legacy = StreetViewOverrideModel(
            clean_address="789 DUAL WAY",
            front_lat=49.1000,
            front_lng=-122.1000,
            heading=10.0,
            pitch=10.0,
            fov=80.0
        )
        parcel = ParcelModel(
            gis_id="GIS-789",
            clean_address="789 DUAL WAY",
            front_lat=49.2000,
            front_lng=-122.2000,
            streetview_heading=200.0,
            streetview_pitch=5.0,
            streetview_fov=60.0
        )
        self.db.add(legacy)
        self.db.add(parcel)
        self.db.commit()

        # lookup_parcel check
        res = lookup_parcel(query="789 DUAL WAY", db=self.db)
        self.assertTrue(res["found"])
        self.assertEqual(res["parcel"]["gis_id"], "GIS-789")
        self.assertEqual(res["parcel"]["streetview_heading"], 200.0)
        self.assertEqual(res["parcel"]["lat"], 49.2000)

        # get_streetview_override check
        ov = get_streetview_override(address="789 DUAL WAY", db=self.db)
        self.assertEqual(ov["heading"], 200.0)
        self.assertEqual(ov["front_lat"], 49.2000)

    def test_lookup_and_override_when_neither_exists(self):
        """Verify behavior when address exists in neither table."""
        res = lookup_parcel(query="NONEXISTENT ADDRESS 999", db=self.db)
        self.assertFalse(res["found"])
        self.assertIsNone(res["parcel"])

        with self.assertRaises(HTTPException) as ctx:
            get_streetview_override(address="NONEXISTENT ADDRESS 999", db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    # -------------------------------------------------------------------------
    # TEST SUITE 2: Migration Script Stress Testing
    # -------------------------------------------------------------------------
    def test_migration_zero_rows(self):
        """Test migration script with zero rows in streetview_overrides."""
        migrated, created = migrate_overrides(db_session=self.db)
        self.assertEqual(migrated, 0)
        self.assertEqual(created, 0)
        self.assertEqual(self.db.query(ParcelModel).count(), 0)

    def test_migration_single_row_no_existing_parcel(self):
        """Test migration script with 1 legacy row and no existing parcel."""
        legacy = StreetViewOverrideModel(
            clean_address="100 MIGRATION RD",
            front_lat=49.3000,
            front_lng=-122.7000,
            heading=45.0,
            pitch=12.0,
            fov=85.0
        )
        self.db.add(legacy)
        self.db.commit()

        migrated, created = migrate_overrides(db_session=self.db)
        self.assertEqual(migrated, 0)
        self.assertEqual(created, 1)

        parcel = self.db.query(ParcelModel).filter(ParcelModel.clean_address == "100 MIGRATION RD").first()
        self.assertIsNotNone(parcel)
        self.assertEqual(parcel.gis_id, "100 MIGRATION RD")
        self.assertEqual(parcel.front_lat, 49.3000)
        self.assertEqual(parcel.streetview_heading, 45.0)
        self.assertEqual(parcel.streetview_pitch, 12.0)
        self.assertEqual(parcel.streetview_fov, 85.0)

    def test_migration_single_row_existing_parcel(self):
        """Test migration script updating an existing parcel from legacy override."""
        parcel = ParcelModel(
            gis_id="GIS-EXISTING-1",
            clean_address="200 EXISTING ST",
            front_lat=None,
            front_lng=None,
            streetview_heading=0.0,
            streetview_pitch=5.0,
            streetview_fov=80.0
        )
        legacy = StreetViewOverrideModel(
            clean_address="200 EXISTING ST",
            front_lat=49.3100,
            front_lng=-122.7100,
            heading=180.0,
            pitch=8.0,
            fov=65.0
        )
        self.db.add(parcel)
        self.db.add(legacy)
        self.db.commit()

        migrated, created = migrate_overrides(db_session=self.db)
        self.assertEqual(migrated, 1)
        self.assertEqual(created, 0)

        updated_parcel = self.db.query(ParcelModel).filter(ParcelModel.clean_address == "200 EXISTING ST").first()
        self.assertEqual(updated_parcel.streetview_heading, 180.0)
        self.assertEqual(updated_parcel.streetview_pitch, 8.0)
        self.assertEqual(updated_parcel.streetview_fov, 65.0)
        self.assertEqual(updated_parcel.front_lat, 49.3100)
        self.assertEqual(updated_parcel.front_lng, -122.7100)

    def test_migration_duplicate_rows_different_raw_same_normalized(self):
        """
        STRESS TEST: Legacy table contains multiple records that normalize to the SAME clean address.
        e.g. '3030 GORDON AVE, COQUITLAM, BC' and 'UNIT 101 3030 GORDON AVE'
        Both normalize to '3030 GORDON AVE'.
        """
        legacy1 = StreetViewOverrideModel(
            clean_address="3030 GORDON AVE, COQUITLAM, BC",
            front_lat=49.2785,
            front_lng=-122.7932,
            heading=100.0,
            pitch=5.0,
            fov=80.0
        )
        legacy2 = StreetViewOverrideModel(
            clean_address="UNIT 101 3030 GORDON AVE",
            front_lat=49.2786,
            front_lng=-122.7933,
            heading=105.0,
            pitch=6.0,
            fov=82.0
        )
        self.db.add(legacy1)
        self.db.add(legacy2)
        self.db.commit()

        # Run migration - check if handles duplicates gracefully or throws IntegrityError
        try:
            migrated, created = migrate_overrides(db_session=self.db)
            print(f"[TEST INFO] Duplicate migration result: migrated={migrated}, created={created}")
            
            # Verify resulting parcels in DB
            parcels = self.db.query(ParcelModel).all()
            print(f"[TEST INFO] Total parcels created: {len(parcels)}")
            for p in parcels:
                print(f"  Parcel ID={p.id}, clean_address='{p.clean_address}', gis_id='{p.gis_id}', heading={p.streetview_heading}")

            # Check that clean_address='3030 GORDON AVE' exists without crashing
            p_clean = self.db.query(ParcelModel).filter(ParcelModel.clean_address == "3030 GORDON AVE").first()
            self.assertIsNotNone(p_clean)

        except Exception as e:
            print(f"[BUG FOUND] Migration failed on duplicate legacy records: {e}")
            raise e

    def test_migration_duplicate_rows_with_preexisting_parcel(self):
        """
        STRESS TEST: Parcel already exists, and 2 legacy override rows normalize to it.
        """
        parcel = ParcelModel(
            gis_id="GIS-DUP-1",
            clean_address="500 LOUGHEED HIGHWAY",
            front_lat=49.2500,
            front_lng=-122.8000,
            streetview_heading=0.0
        )
        legacy1 = StreetViewOverrideModel(
            clean_address="500 LOUGHEED HWY",
            front_lat=49.2501,
            front_lng=-122.8001,
            heading=110.0,
            pitch=5.0,
            fov=80.0
        )
        legacy2 = StreetViewOverrideModel(
            clean_address="500 LOUGHEED HIGHWAY, COQUITLAM",
            front_lat=49.2502,
            front_lng=-122.8002,
            heading=115.0,
            pitch=6.0,
            fov=85.0
        )
        self.db.add(parcel)
        self.db.add(legacy1)
        self.db.add(legacy2)
        self.db.commit()

        migrated, created = migrate_overrides(db_session=self.db)
        self.assertEqual(created, 0)
        self.assertEqual(migrated, 2)

        updated_p = self.db.query(ParcelModel).filter(ParcelModel.clean_address == "500 LOUGHEED HIGHWAY").first()
        self.assertIsNotNone(updated_p)
        self.assertIn(updated_p.streetview_heading, [110.0, 115.0])

    # -------------------------------------------------------------------------
    # TEST SUITE 3: Return Formats and API Specification Conformance
    # -------------------------------------------------------------------------
    def test_save_parcel_streetview_return_format(self):
        """Verify POST /api/parcels/streetview return dictionary schema."""
        payload = ParcelCameraOverrideSchema(
            clean_address="1000 SPEC TEST RD",
            front_lat=49.3500,
            front_lng=-122.6500,
            heading=330.0,
            pitch=14.0,
            fov=75.0
        )
        res = save_parcel_streetview(payload=payload, db=self.db)

        # Check top-level keys
        self.assertIn("status", res)
        self.assertIn("parcel", res)
        self.assertEqual(res["status"], "success")

        # Check nested parcel dict required keys per API spec
        p = res["parcel"]
        required_keys = [
            "id", "gis_id", "clean_address", "full_address", "street_number",
            "street_name", "municipality", "zone_id", "parcel_lat", "parcel_lng",
            "front_lat", "front_lng", "streetview_heading", "streetview_pitch",
            "streetview_fov", "lock_box_notes", "hazard_notes", "pre_plan_pdf_url",
            "created_at", "updated_at", "lat", "lng", "heading", "pitch", "fov"
        ]
        for k in required_keys:
            self.assertIn(k, p, f"Missing key '{k}' in parcel dictionary")

        self.assertEqual(p["clean_address"], "1000 SPEC TEST RD")
        self.assertEqual(p["streetview_heading"], 330.0)
        self.assertEqual(p["heading"], 330.0)
        self.assertEqual(p["pitch"], 14.0)
        self.assertEqual(p["fov"], 75.0)

    def test_save_streetview_override_legacy_endpoint_return_format(self):
        """Verify POST /api/streetview-overrides return dictionary schema."""
        payload = StreetViewOverrideSchema(
            clean_address="2000 LEGACY SPEC ST",
            front_lat=49.3600,
            front_lng=-122.6400,
            heading=45.0,
            pitch=5.0,
            fov=80.0
        )
        res = save_streetview_override(payload=payload, db=self.db)

        required_top_keys = [
            "status", "clean_address", "front_lat", "front_lng",
            "heading", "pitch", "fov", "parcel"
        ]
        for k in required_top_keys:
            self.assertIn(k, res, f"Missing top-level key '{k}' in legacy override response")

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["clean_address"], "2000 LEGACY SPEC ST")
        self.assertEqual(res["heading"], 45.0)
        self.assertIsNotNone(res["parcel"])

    def test_get_all_streetview_overrides_return_format(self):
        """Verify GET /api/streetview-overrides returns dict keyed by upper address."""
        legacy = StreetViewOverrideModel(
            clean_address="3000 ALL TEST BLVD",
            front_lat=49.3700,
            front_lng=-122.6300,
            heading=90.0,
            pitch=0.0,
            fov=80.0
        )
        self.db.add(legacy)
        self.db.commit()

        res = get_all_streetview_overrides(db=self.db)
        self.assertIn("3000 ALL TEST BLVD", res)
        item = res["3000 ALL TEST BLVD"]
        self.assertEqual(item["lat"], 49.3700)
        self.assertEqual(item["lng"], -122.6300)
        self.assertEqual(item["heading"], 90.0)
        self.assertEqual(item["pitch"], 0.0)
        self.assertEqual(item["fov"], 80.0)

    def test_sync_between_parcels_and_legacy_overrides(self):
        """Verify saving via save_parcel_streetview keeps legacy table synced."""
        payload = ParcelCameraOverrideSchema(
            clean_address="4000 SYNC WAY",
            front_lat=49.3800,
            front_lng=-122.6200,
            heading=150.0,
            pitch=7.0,
            fov=85.0
        )
        save_parcel_streetview(payload=payload, db=self.db)

        # Check legacy table
        legacy_rec = self.db.query(StreetViewOverrideModel).filter(
            StreetViewOverrideModel.clean_address == "4000 SYNC WAY"
        ).first()
        self.assertIsNotNone(legacy_rec)
        self.assertEqual(legacy_rec.heading, 150.0)
        self.assertEqual(legacy_rec.front_lat, 49.3800)

        # Update parcel camera angle
        payload_update = ParcelCameraOverrideSchema(
            clean_address="4000 SYNC WAY",
            front_lat=49.3805,
            front_lng=-122.6205,
            heading=180.0,
            pitch=10.0,
            fov=70.0
        )
        save_parcel_streetview(payload=payload_update, db=self.db)

        # Re-check legacy table updated
        legacy_rec_updated = self.db.query(StreetViewOverrideModel).filter(
            StreetViewOverrideModel.clean_address == "4000 SYNC WAY"
        ).first()
        self.assertEqual(legacy_rec_updated.heading, 180.0)
        self.assertEqual(legacy_rec_updated.front_lat, 49.3805)

    def test_lookup_by_gis_id(self):
        """Verify lookup_parcel resolves by gis_id when clean_address doesn't match raw query."""
        parcel = ParcelModel(
            gis_id="P123456",
            clean_address="5000 UNIQUE ADDRESS WAY",
            front_lat=49.4000,
            front_lng=-122.6000,
            streetview_heading=210.0
        )
        self.db.add(parcel)
        self.db.commit()

        res = lookup_parcel(query="P123456", db=self.db)
        self.assertTrue(res["found"])
        self.assertEqual(res["parcel"]["clean_address"], "5000 UNIQUE ADDRESS WAY")
        self.assertEqual(res["parcel"]["gis_id"], "P123456")
        self.assertEqual(res["parcel"]["streetview_heading"], 210.0)

    def test_address_normalization_edge_cases(self):
        """Verify complex address strings clean deterministically."""
        self.assertEqual(_clean_streetview_address("APT 204 1234 MARINER WAY"), "1234 MARINER WAY")
        self.assertEqual(_clean_streetview_address("SUITE 5 3030 GORDON AVE, COQUITLAM, BC V3C 2K6"), "3030 GORDON AVE")
        self.assertEqual(_clean_streetview_address(" # 102 500 LOUGHEED HWY "), "500 LOUGHEED HIGHWAY")
        self.assertEqual(_clean_streetview_address("100 DEWDNEY TRUNK RD"), "100 DEWDNEY TRUNK RD")
        # Empirical finding check: APT 204 - 1234 MARINER WAY currently leaves leading dash
        cleaned_dash = _clean_streetview_address("APT 204 - 1234 MARINER WAY")
        self.assertEqual(cleaned_dash, "- 1234 MARINER WAY")

    def test_partial_camera_update_preserves_lat_lng(self):
        """Verify updating camera angles without lat/lng preserves existing parcel lat/lng."""
        parcel = ParcelModel(
            gis_id="GIS-PARTIAL-1",
            clean_address="6000 PARTIAL AVE",
            front_lat=49.4111,
            front_lng=-122.5111,
            streetview_heading=10.0,
            streetview_pitch=5.0,
            streetview_fov=80.0
        )
        self.db.add(parcel)
        self.db.commit()

        # Save camera angles only (front_lat & front_lng omitted / None)
        payload = ParcelCameraOverrideSchema(
            clean_address="6000 PARTIAL AVE",
            heading=245.0,
            pitch=18.0,
            fov=60.0
        )
        res = save_parcel_streetview(payload=payload, db=self.db)

        self.assertEqual(res["parcel"]["front_lat"], 49.4111)
        self.assertEqual(res["parcel"]["front_lng"], -122.5111)
        self.assertEqual(res["parcel"]["streetview_heading"], 245.0)
        self.assertEqual(res["parcel"]["streetview_pitch"], 18.0)
        self.assertEqual(res["parcel"]["streetview_fov"], 60.0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
