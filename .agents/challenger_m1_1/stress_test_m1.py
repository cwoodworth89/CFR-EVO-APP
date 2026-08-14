#!/usr/bin/env python3
"""
Empirical Stress Test Harness for Milestone 1: Backend PostgreSQL & REST Overhaul
Author: Challenger 1 (Milestone 1)
"""
import os
import sys
import time
import math
import concurrent.futures
from typing import Dict, Any

script_dir = os.path.dirname(os.path.abspath(__file__))
app_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
backend_dir = os.path.join(app_root, "backend")

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if app_root not in sys.path:
    sys.path.insert(0, app_root)

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

# Ensure tables exist
for table in Base.metadata.tables.values():
    try:
        table.create(bind=engine, checkfirst=True)
    except Exception:
        pass

results = []

def record_test(name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "details": details})
    print(f"[{status}] {name}{': ' + details if details else ''}")

# --- CATEGORY 1: ADDRESS NORMALIZATION & LOOKUP EDGE CASES ---

def test_special_characters_address():
    print("\n--- Test 1.1: Special Characters in Address ---")
    test_cases = [
        ("3030 'GORDON' AVE", "3030 'GORDON' AVE"),
        ('3030 "GORDON" AVE', '3030 "GORDON" AVE'),
        ("3030 GORDON & MARINER ST", "3030 GORDON & MARINER ST"),
        ("3030-B GORDON AVE", "3030-B GORDON AVE"),
        ("3030/3032 GORDON AVE", "3030/3032 GORDON AVE"),
        ("3030 GORDON AVE #200", "3030 GORDON AVE #200"),
        ("3030 GORDÓN AVÉ", "3030 GORDÓN AVÉ"),
        ("3030 GORDON AVE %", "3030 GORDON AVE %"),
        ("3030 GORDON_AVE", "3030 GORDON_AVE"),
    ]
    all_passed = True
    failures = []
    
    db = SessionLocal()
    for raw_addr, expected_contains in test_cases:
        try:
            cleaned = _clean_streetview_address(raw_addr)
            # Save parcel with special character address
            payload = ParcelCameraOverrideSchema(
                clean_address=raw_addr,
                front_lat=49.278,
                front_lng=-122.793,
                heading=100.0
            )
            res = save_parcel_streetview(payload=payload, db=db)
            
            # Now lookup using raw address
            lookup_res = lookup_parcel(query=raw_addr, db=db)
            if not lookup_res["found"]:
                all_passed = False
                failures.append(f"Lookup failed for '{raw_addr}' (cleaned: '{cleaned}')")
            elif lookup_res["parcel"]["clean_address"] != cleaned:
                all_passed = False
                failures.append(f"Mismatch for '{raw_addr}': got '{lookup_res['parcel']['clean_address']}', expected '{cleaned}'")
        except Exception as e:
            all_passed = False
            failures.append(f"Exception on '{raw_addr}': {str(e)}")
            
    db.close()
    record_test("Special Characters in Address", all_passed, "; ".join(failures))

def test_whitespace_and_formatting():
    print("\n--- Test 1.2: Whitespace and Formatting Variants ---")
    db = SessionLocal()
    
    # Save a canonical parcel first
    canon_payload = ParcelCameraOverrideSchema(
        clean_address="1234 MARINER WAY",
        front_lat=49.280,
        front_lng=-122.790,
        heading=45.0
    )
    save_parcel_streetview(payload=canon_payload, db=db)
    
    whitespace_queries = [
        "  1234  MARINER   WAY  ",
        "\t1234 MARINER WAY\n",
        "1234  mariner   way",
        "1234 MARINER WAY, COQUITLAM, BC",
        "1234 MARINER WAY, PORT COQUITLAM, BRITISH COLUMBIA",
        "Unit 101 1234 MARINER WAY",
        "#5 1234 MARINER WAY",
        "APT 3B 1234 MARINER WAY",
    ]
    
    all_passed = True
    failures = []
    
    for q in whitespace_queries:
        try:
            lookup_res = lookup_parcel(query=q, db=db)
            if not lookup_res["found"]:
                all_passed = False
                failures.append(f"Failed to resolve formatted query '{repr(q)}'")
            else:
                found_addr = lookup_res["parcel"]["clean_address"]
                if found_addr != "1234 MARINER WAY":
                    all_passed = False
                    failures.append(f"Query '{repr(q)}' mapped to '{found_addr}' instead of '1234 MARINER WAY'")
        except Exception as e:
            all_passed = False
            failures.append(f"Exception on query '{repr(q)}': {str(e)}")
            
    db.close()
    record_test("Whitespace and Formatting Variants", all_passed, "; ".join(failures))

def test_missing_house_numbers_and_street_only():
    print("\n--- Test 1.3: Missing House Numbers & Street-Only Queries ---")
    db = SessionLocal()
    
    # Setup test parcel
    payload = ParcelCameraOverrideSchema(
        clean_address="500 LOUGHEED HIGHWAY",
        front_lat=49.260,
        front_lng=-122.810,
        heading=270.0
    )
    save_parcel_streetview(payload=payload, db=db)
    
    all_passed = True
    failures = []
    
    # Query without number
    lookup_res = lookup_parcel(query="LOUGHEED HWY", db=db)
    if not lookup_res["found"]:
        all_passed = False
        failures.append("Query 'LOUGHEED HWY' failed to hit partial ILIKE match for '500 LOUGHEED HIGHWAY'")
    elif lookup_res["parcel"]["clean_address"] != "500 LOUGHEED HIGHWAY":
        all_passed = False
        failures.append(f"Query 'LOUGHEED HWY' returned unexpected parcel '{lookup_res['parcel']['clean_address']}'")
        
    # Blank and empty queries
    blank_queries = ["", "   ", "\t\n", None]
    for bq in blank_queries:
        try:
            res = lookup_parcel(query=bq, db=db)
            if res["found"] or res["parcel"] is not None:
                all_passed = False
                failures.append(f"Blank query {repr(bq)} returned found=True")
        except Exception as e:
            all_passed = False
            failures.append(f"Exception on blank query {repr(bq)}: {str(e)}")
            
    db.close()
    record_test("Missing House Numbers & Street-Only Queries", all_passed, "; ".join(failures))


# --- CATEGORY 2: EXTREME FLOATING POINT CAMERA VECTORS ---

def test_extreme_floating_point_vectors():
    print("\n--- Test 2.1: Extreme Floating Point Camera Vectors ---")
    db = SessionLocal()
    
    extreme_vectors = [
        # heading, pitch, fov, description
        (359.99, -89.9, 120.0, "Boundary high heading / low pitch / wide fov"),
        (0.0, 0.0, 0.0, "Zero boundary values"),
        (360.0, 90.0, 180.0, "Full circle heading / top pitch / max fov"),
        (-180.0, -90.0, -10.0, "Negative angles and negative fov"),
        (720.5, 45.123456789, 75.999999, "Multi-turn heading and high float precision"),
        (-0.0001, 89.9999, 0.00001, "Near-zero float boundary"),
        (1e5, 1e2, 1e3, "Large scientific notation floats"),
    ]
    
    all_passed = True
    failures = []
    
    for idx, (h, p, f, desc) in enumerate(extreme_vectors):
        addr = f"99{idx} EXTREME VECTOR ST"
        try:
            payload = ParcelCameraOverrideSchema(
                clean_address=addr,
                front_lat=49.1234567,
                front_lng=-122.9876543,
                heading=h,
                pitch=p,
                fov=f
            )
            save_res = save_parcel_streetview(payload=payload, db=db)
            if save_res["status"] != "success":
                all_passed = False
                failures.append(f"[{desc}] Save returned non-success status")
                continue
                
            # Lookup and verify precision and values
            lookup_res = lookup_parcel(query=addr, db=db)
            if not lookup_res["found"]:
                all_passed = False
                failures.append(f"[{desc}] Lookup failed after save")
                continue
                
            p_data = lookup_res["parcel"]
            if not math.isclose(p_data["streetview_heading"], h, rel_tol=1e-5, abs_tol=1e-5):
                all_passed = False
                failures.append(f"[{desc}] Heading mismatch: saved {h}, retrieved {p_data['streetview_heading']}")
            if not math.isclose(p_data["streetview_pitch"], p, rel_tol=1e-5, abs_tol=1e-5):
                all_passed = False
                failures.append(f"[{desc}] Pitch mismatch: saved {p}, retrieved {p_data['streetview_pitch']}")
            if not math.isclose(p_data["streetview_fov"], f, rel_tol=1e-5, abs_tol=1e-5):
                all_passed = False
                failures.append(f"[{desc}] FOV mismatch: saved {f}, retrieved {p_data['streetview_fov']}")
                
            # Verify legacy table sync
            legacy_res = get_streetview_override(address=addr, db=db)
            if not math.isclose(legacy_res["heading"], h, rel_tol=1e-5, abs_tol=1e-5):
                all_passed = False
                failures.append(f"[{desc}] Legacy heading mismatch: saved {h}, retrieved {legacy_res['heading']}")
        except Exception as e:
            all_passed = False
            failures.append(f"[{desc}] Exception: {str(e)}")
            
    db.close()
    record_test("Extreme Floating Point Camera Vectors", all_passed, "; ".join(failures))


# --- CATEGORY 3: RAPID REPEATED UPSERTS & CONCURRENCY ---

def test_rapid_repeated_upserts():
    print("\n--- Test 3.1: Rapid Repeated Upserts (Update vs Insert Behavior) ---")
    db = SessionLocal()
    addr = "4000 RAPID REPEAT WAY"
    
    # Cleanup any pre-existing
    existing = db.query(ParcelModel).filter(ParcelModel.clean_address == addr).first()
    if existing:
        db.delete(existing)
        db.commit()
    existing_legacy = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == addr).first()
    if existing_legacy:
        db.delete(existing_legacy)
        db.commit()
        
    all_passed = True
    failures = []
    
    # Perform 50 rapid sequential updates
    start_time = time.time()
    for i in range(50):
        h = float(i * 5)
        p = float(i % 30 - 15)
        f = float(60 + (i % 40))
        payload = ParcelCameraOverrideSchema(
            clean_address=addr,
            front_lat=49.27 + (i * 0.0001),
            front_lng=-122.79 - (i * 0.0001),
            heading=h,
            pitch=p,
            fov=f
        )
        save_parcel_streetview(payload=payload, db=db)
        
    elapsed = time.time() - start_time
    
    # Verify row count in parcels table
    count_parcels = db.query(ParcelModel).filter(ParcelModel.clean_address == addr).count()
    count_legacy = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == addr).count()
    
    if count_parcels != 1:
        all_passed = False
        failures.append(f"Parcels row count is {count_parcels}, expected exactly 1 (duplicate rows inserted!)")
    if count_legacy != 1:
        all_passed = False
        failures.append(f"Legacy overrides row count is {count_legacy}, expected exactly 1")
        
    # Verify final values equal the 49th iteration values (h=245.0, p=4.0, f=69.0)
    final_p = db.query(ParcelModel).filter(ParcelModel.clean_address == addr).first()
    if final_p.streetview_heading != 245.0:
        all_passed = False
        failures.append(f"Final heading mismatch: got {final_p.streetview_heading}, expected 245.0")
        
    db.close()
    record_test("Rapid Repeated Upserts (50x)", all_passed, f"Completed in {elapsed:.3f}s. " + "; ".join(failures))

def test_concurrent_upserts_stress():
    print("\n--- Test 3.2: Concurrent Threaded Upserts (Race Condition Check) ---")
    addr = "5000 CONCURRENT ST"
    
    # Cleanup pre-existing
    db = SessionLocal()
    existing = db.query(ParcelModel).filter(ParcelModel.clean_address == addr).first()
    if existing:
        db.delete(existing)
        db.commit()
    existing_legacy = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == addr).first()
    if existing_legacy:
        db.delete(existing_legacy)
        db.commit()
    db.close()
    
    all_passed = True
    failures = []
    
    def upsert_worker(thread_id: int):
        thread_db = SessionLocal()
        try:
            payload = ParcelCameraOverrideSchema(
                clean_address=addr,
                front_lat=49.300 + (thread_id * 0.001),
                front_lng=-122.800 + (thread_id * 0.001),
                heading=float(thread_id * 10),
                pitch=5.0,
                fov=80.0
            )
            res = save_parcel_streetview(payload=payload, db=thread_db)
            return True, None
        except Exception as e:
            thread_db.rollback()
            return False, str(e)
        finally:
            thread_db.close()

    # Launch 10 concurrent threads simultaneously
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(upsert_worker, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
    successes = sum(1 for ok, _ in results if ok)
    errors = [err for ok, err in results if not ok and err is not None]
    
    # Check DB state
    db = SessionLocal()
    count_parcels = db.query(ParcelModel).filter(ParcelModel.clean_address == addr).count()
    count_legacy = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == addr).count()
    db.close()
    
    if count_parcels != 1:
        all_passed = False
        failures.append(f"Parcels count after concurrent upserts: {count_parcels} (expected 1)")
    if count_legacy != 1:
        all_passed = False
        failures.append(f"Legacy overrides count after concurrent upserts: {count_legacy} (expected 1)")
    if errors:
        failures.append(f"{len(errors)} threads threw errors: {errors[0]}")

    record_test("Concurrent Threaded Upserts (10 Workers)", all_passed, f"Successes: {successes}/10. " + "; ".join(failures))


# --- CATEGORY 4: DATABASE SCHEMAS & NULLABLE FIELD VALIDATION ---

def test_nullable_gis_id_uniqueness():
    print("\n--- Test 4.1: Nullable gis_id Multiple Rows Constraint ---")
    db = SessionLocal()
    all_passed = True
    failures = []
    
    try:
        # Create 3 distinct parcels, all with gis_id=None
        p1 = ParcelModel(clean_address="901 NULL GIS ST", gis_id=None, front_lat=49.1, front_lng=-122.1)
        p2 = ParcelModel(clean_address="902 NULL GIS ST", gis_id=None, front_lat=49.2, front_lng=-122.2)
        p3 = ParcelModel(clean_address="903 NULL GIS ST", gis_id=None, front_lat=49.3, front_lng=-122.3)
        
        db.add_all([p1, p2, p3])
        db.commit()
        
        assert p1.id is not None and p2.id is not None and p3.id is not None
        
        # Cleanup
        db.delete(p1)
        db.delete(p2)
        db.delete(p3)
        db.commit()
    except Exception as e:
        db.rollback()
        all_passed = False
        failures.append(f"Failed to insert multiple parcels with NULL gis_id: {str(e)}")
        
    db.close()
    record_test("Nullable gis_id Multiple Rows", all_passed, "; ".join(failures))

def test_address_normalization_edge_bugs():
    print("\n--- Test 4.2: Address Normalization Edge Cases ---")
    all_passed = True
    failures = []
    
    # Test suite of tricky addresses
    cases = [
        ("COQUITLAM, BC", ""),
        ("Unit 101", "UNIT 101"),
        ("Unit 101 ", "UNIT 101"),
        ("3030 GORDON AVE, COQUITLAM", "3030 GORDON AVE"),
        ("3030 GORDON AVE, PORT MOODY, BC", "3030 GORDON AVE"),
    ]
    
    for raw, expected in cases:
        actual = _clean_streetview_address(raw)
        if actual != expected:
            all_passed = False
            failures.append(f"Address '{raw}': got '{actual}', expected '{expected}'")
            
    record_test("Address Normalization Edge Cases", all_passed, "; ".join(failures))


if __name__ == "__main__":
    print("===============================================================")
    print("EMPIRICAL STRESS TEST SUITE FOR MILESTONE 1 (POSTGRES & REST)")
    print("===============================================================")
    
    test_special_characters_address()
    test_whitespace_and_formatting()
    test_missing_house_numbers_and_street_only()
    test_extreme_floating_point_vectors()
    test_rapid_repeated_upserts()
    test_concurrent_upserts_stress()
    test_nullable_gis_id_uniqueness()
    test_address_normalization_edge_bugs()
    
    print("\n===============================================================")
    passed_cnt = sum(1 for r in results if r["passed"])
    failed_cnt = sum(1 for r in results if not r["passed"])
    print(f"SUMMARY: {passed_cnt} PASSED, {failed_cnt} FAILED out of {len(results)} tests.")
    print("===============================================================")
