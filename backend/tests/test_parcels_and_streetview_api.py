#!/usr/bin/env python3
"""
Unit and Integration Tests for Milestone 1: Parcels Schema & Street View REST API Overhaul.
"""
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
root_dir = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from api.database import SessionLocal, engine, Base
    from api.models import ParcelModel, StreetViewOverrideModel
    from api.server import (
        _clean_streetview_address,
        lookup_parcel,
        save_parcel_streetview,
        get_streetview_override,
        save_streetview_override,
        ParcelCameraOverrideSchema,
        StreetViewOverrideSchema
    )
    from scripts.migrate_streetview_to_parcels import migrate_overrides
except ModuleNotFoundError:
    from backend.api.database import SessionLocal, engine, Base
    from backend.api.models import ParcelModel, StreetViewOverrideModel
    from backend.api.server import (
        _clean_streetview_address,
        lookup_parcel,
        save_parcel_streetview,
        get_streetview_override,
        save_streetview_override,
        ParcelCameraOverrideSchema,
        StreetViewOverrideSchema
    )
    from backend.scripts.migrate_streetview_to_parcels import migrate_overrides

# Ensure tables exist in active database
for table in Base.metadata.tables.values():
    try:
        table.create(bind=engine, checkfirst=True)
    except Exception:
        pass

def test_address_normalization():
    print("Running test_address_normalization...")
    assert _clean_streetview_address("3030 GORDON AVE, COQUITLAM, BC") == "3030 GORDON AVE"
    assert _clean_streetview_address("Unit 101 3030 Gordon Ave") == "3030 GORDON AVE"
    assert _clean_streetview_address("  1234  MARINER   WAY  ") == "1234 MARINER WAY"
    assert _clean_streetview_address("500 LOUGHEED HWY") == "500 LOUGHEED HIGHWAY"
    print("PASSED: test_address_normalization")

def test_parcel_model_nullable_gis_id():
    print("Running test_parcel_model_nullable_gis_id...")
    db = SessionLocal()
    existing = db.query(ParcelModel).filter(ParcelModel.clean_address == "100 TEST ST").first()
    if existing:
        db.delete(existing)
        db.commit()

    p = ParcelModel(
        gis_id=None,
        clean_address="100 TEST ST",
        front_lat=49.28,
        front_lng=-122.79,
        streetview_heading=180.0,
        streetview_pitch=10.0,
        streetview_fov=75.0,
        lock_box_notes="Keybox at North entrance",
        hazard_notes="Oxygen tanks stored inside",
        pre_plan_pdf_url="https://example.com/plan.pdf"
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    assert p.id is not None
    assert p.gis_id is None
    assert p.clean_address == "100 TEST ST"
    assert p.streetview_heading == 180.0
    assert p.lock_box_notes == "Keybox at North entrance"
    
    # Cleanup test row
    db.delete(p)
    db.commit()
    db.close()
    print("PASSED: test_parcel_model_nullable_gis_id")

def test_lookup_parcel_not_found():
    print("Running test_lookup_parcel_not_found...")
    db = SessionLocal()
    data = lookup_parcel(query="9999 NONEXISTENT ST", db=db)
    assert data["found"] is False
    assert data["parcel"] is None
    db.close()
    print("PASSED: test_lookup_parcel_not_found")

def test_save_and_lookup_parcel_streetview():
    print("Running test_save_and_lookup_parcel_streetview...")
    db = SessionLocal()
    payload = ParcelCameraOverrideSchema(
        clean_address="999 TEST DISPATCH BLVD, COQUITLAM",
        front_lat=49.2785,
        front_lng=-122.7932,
        heading=135.5,
        pitch=8.0,
        fov=85.0
    )
    data = save_parcel_streetview(payload=payload, db=db)
    assert data["status"] == "success"
    assert data["parcel"]["clean_address"] == "999 TEST DISPATCH BLVD"
    assert data["parcel"]["streetview_heading"] == 135.5
    assert data["parcel"]["front_lat"] == 49.2785

    # Test lookup endpoint hit
    lookup_res = lookup_parcel(query="999 TEST DISPATCH BLVD", db=db)
    assert lookup_res["found"] is True
    assert lookup_res["parcel"]["clean_address"] == "999 TEST DISPATCH BLVD"
    assert lookup_res["parcel"]["streetview_heading"] == 135.5

    # Cleanup test row
    p = db.query(ParcelModel).filter(ParcelModel.clean_address == "999 TEST DISPATCH BLVD").first()
    if p: db.delete(p)
    ov = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == "999 TEST DISPATCH BLVD").first()
    if ov: db.delete(ov)
    db.commit()
    db.close()
    print("PASSED: test_save_and_lookup_parcel_streetview")

def test_streetview_overrides_endpoint():
    print("Running test_streetview_overrides_endpoint...")
    db = SessionLocal()
    payload = ParcelCameraOverrideSchema(
        clean_address="888 MIGRATION ST",
        front_lat=49.29,
        front_lng=-122.78,
        heading=310.0,
        pitch=6.0,
        fov=80.0
    )
    save_parcel_streetview(payload=payload, db=db)

    override = get_streetview_override(address="888 MIGRATION ST", db=db)
    assert override["clean_address"] == "888 MIGRATION ST"
    assert override["heading"] == 310.0
    assert override["pitch"] == 6.0
    assert override["fov"] == 80.0
    assert override["front_lat"] == 49.29

    # Cleanup
    p = db.query(ParcelModel).filter(ParcelModel.clean_address == "888 MIGRATION ST").first()
    if p:
        db.delete(p)
        db.commit()
    db.close()
    print("PASSED: test_streetview_overrides_endpoint")

def test_legacy_post_streetview_overrides():
    print("Running test_legacy_post_streetview_overrides...")
    db = SessionLocal()
    payload = StreetViewOverrideSchema(
        clean_address="777 OVERRIDE RD",
        front_lat=49.25,
        front_lng=-122.75,
        heading=45.0,
        pitch=12.0,
        fov=70.0
    )
    save_streetview_override(payload=payload, db=db)

    res = lookup_parcel(query="777 OVERRIDE RD", db=db)
    assert res["found"] is True
    assert res["parcel"]["streetview_heading"] == 45.0
    assert res["parcel"]["front_lat"] == 49.25

    # Cleanup
    p = db.query(ParcelModel).filter(ParcelModel.clean_address == "777 OVERRIDE RD").first()
    if p:
        db.delete(p)
        db.commit()
    db.close()
    print("PASSED: test_legacy_post_streetview_overrides")

if __name__ == "__main__":
    print("\n--- Running Milestone 1 Parcels & Street View Test Harness ---")
    test_address_normalization()
    test_parcel_model_nullable_gis_id()
    test_lookup_parcel_not_found()
    test_save_and_lookup_parcel_streetview()
    test_streetview_overrides_endpoint()
    test_legacy_post_streetview_overrides()
    print("\n[SUCCESS] ALL MILESTONE 1 TESTS PASSED SUCCESSFULLY!\n")
