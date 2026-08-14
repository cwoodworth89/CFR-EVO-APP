#!/usr/bin/env python3
"""
Deep Empirical Stress Test & Verification Suite (Recheck 2)
Author: Challenger 1 (Recheck 2)
"""

import os
import sys
import concurrent.futures
from fastapi import HTTPException

# Ensure backend directory is in path
script_dir = os.path.dirname(os.path.abspath(__file__))
app_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
backend_dir = os.path.join(app_root, "backend")

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if app_root not in sys.path:
    sys.path.insert(0, app_root)

from api.database import SessionLocal
from api.models import ParcelModel, StreetViewOverrideModel
from api.server import (
    _clean_streetview_address,
    save_parcel_streetview,
    lookup_parcel,
    ParcelCameraOverrideSchema
)

def run_tests():
    print("===============================================================")
    print("STARTING DEEP EMPIRICAL VERIFICATION (RECHECK 2)")
    print("===============================================================")

    db = SessionLocal()

    # 1. Clean Address Normalization Matrix (Standard Clean Variants)
    print("\n--- Test 1: Standard Unit & Street Address Normalization ---")
    test_cases_std = [
        ("3030 Gordon Ave, Suite 500-X", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Ste. 101", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Ste 101", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Unit #101", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Unit # 101", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Apt # 202", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Apt. 202", "3030 GORDON AVE"),
        ("3030 Gordon Ave - Apt 202", "3030 GORDON AVE"),
        ("3030 Gordon Ave #303", "3030 GORDON AVE"),
        ("3030 Gordon Ave, #303", "3030 GORDON AVE"),
        ("Unit 101, 3030 Gordon Ave", "3030 GORDON AVE"),
        ("Unit #101, 3030 Gordon Ave", "3030 GORDON AVE"),
        ("Ste 101, 3030 Gordon Ave", "3030 GORDON AVE"),
        ("Ste. 101, 3030 Gordon Ave", "3030 GORDON AVE"),
        ("Apt 202-B - 3030 Gordon Ave", "3030 GORDON AVE"),
        ("Apt. 202-B - 3030 Gordon Ave", "3030 GORDON AVE"),
        ("#303-C, 3030 Gordon Ave", "3030 GORDON AVE"),
        ("Suite 400A - 3030 Gordon Ave, Port Coquitlam, British Columbia", "3030 GORDON AVE"),
        ("3030 Gordon Ave Unit 101B", "3030 GORDON AVE"),
        ("3030 Gordon Ave Ste. 101-A", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Coquitlam, BC", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Port Coquitlam, British Columbia", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Port Moody BC", "3030 GORDON AVE"),
        ("3030 GORDON AVE, SUITE 500-X", "3030 GORDON AVE"),
        ("3030 GORDON AVE - APT 202", "3030 GORDON AVE"),
        ("123 MAIN ST", "123 MAIN ST"),
        ("100 1ST AVE", "100 1ST AVE"),
    ]

    t1_pass = True
    for raw_input, expected in test_cases_std:
        actual = _clean_streetview_address(raw_input)
        if actual != expected:
            print(f"[FAIL] Input '{raw_input}': Expected '{expected}', Got '{actual}'")
            t1_pass = False
        else:
            print(f"[PASS] Input '{raw_input}' -> '{actual}'")

    # 1B. Trailing Punctuation and Trailing Whitespace after Unit Suffix
    print("\n--- Test 1B: Trailing Comma/Punctuation/Space After Unit Suffix ---")
    test_cases_trailing = [
        ("3030 Gordon Ave, Suite 500-X,", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Unit 101,", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Ste. 101,", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Apt 202,", "3030 GORDON AVE"),
        ("3030 Gordon Ave, #101,", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Suite 500-X.", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Suite 500-X   ", "3030 GORDON AVE"),
        ("  3030   GORDON   AVE  ,  SUITE   100  ", "3030 GORDON AVE"),
    ]

    t1b_pass = True
    for raw_input, expected in test_cases_trailing:
        actual = _clean_streetview_address(raw_input)
        if actual != expected:
            print(f"[FAIL] Trailing Punctuation/Space Input '{raw_input}': Expected '{expected}', Got '{actual}'")
            t1b_pass = False
        else:
            print(f"[PASS] Trailing Punctuation/Space Input '{raw_input}' -> '{actual}'")

    # 2. Parcel DB Lookup via Address Variants
    print("\n--- Test 2: Database Lookup via Variants ---")
    save_parcel_streetview(
        ParcelCameraOverrideSchema(
            clean_address="3030 GORDON AVE",
            front_lat=49.2785,
            front_lng=-122.7932,
            heading=270.0,
            pitch=5.0,
            fov=90.0
        ),
        db=db
    )

    lookup_variants = [
        "3030 Gordon Ave",
        "3030 Gordon Ave, Suite 500-X",
        "Ste. 101, 3030 Gordon Ave",
        "Unit #101, 3030 Gordon Ave, Coquitlam, BC",
        "3030 Gordon Ave - Apt 202-B",
        "3030 GORDON AVE, PORT COQUITLAM, BRITISH COLUMBIA",
    ]

    t2_pass = True
    for var in lookup_variants:
        res = lookup_parcel(query=var, db=db)
        if not res.get("found") or not res.get("parcel"):
            print(f"[FAIL] Lookup failed for variant: '{var}'")
            t2_pass = False
        else:
            found_addr = res["parcel"]["clean_address"]
            if found_addr != "3030 GORDON AVE":
                print(f"[FAIL] Lookup returned wrong parcel address: '{found_addr}' for query '{var}'")
                t2_pass = False
            else:
                print(f"[PASS] Lookup query '{var}' correctly matched '3030 GORDON AVE'")

    # 3. Empty & Invalid Address Handling
    print("\n--- Test 3: Empty & Invalid Address Handling ---")
    invalid_inputs = [
        "",
        "   ",
        "\t\n  ",
        "COQUITLAM, BC",
        "PORT MOODY, BRITISH COLUMBIA",
        "   COQUITLAM, BC   ",
        ",,, --- ...",
    ]

    t3_pass = True
    for inv in invalid_inputs:
        try:
            payload = ParcelCameraOverrideSchema(clean_address=inv)
            save_parcel_streetview(payload=payload, db=db)
            print(f"[FAIL] Invalid input {repr(inv)} was wrongfully accepted!")
            t3_pass = False
        except HTTPException as e:
            if e.status_code == 400:
                print(f"[PASS] Invalid input {repr(inv)} correctly rejected HTTP 400 ({e.detail})")
            else:
                print(f"[FAIL] Invalid input {repr(inv)} returned HTTP {e.status_code} instead of 400")
                t3_pass = False
        except Exception as e:
            print(f"[FAIL] Invalid input {repr(inv)} threw unhandled exception: {e}")
            t3_pass = False

    # 4. High-Concurrency Concurrent Upserts (50 Parallel Workers)
    print("\n--- Test 4: High-Concurrency Stress Test (50 Workers) ---")
    stress_target = "8888 HIGHWAY 7"
    
    # Cleanup target if present
    p_exist = db.query(ParcelModel).filter(ParcelModel.clean_address == stress_target).first()
    if p_exist:
        db.delete(p_exist)
    s_exist = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == stress_target).first()
    if s_exist:
        db.delete(s_exist)
    db.commit()
    db.close()

    def stress_worker(i: int):
        thread_db = SessionLocal()
        variants = [
            f"8888 Highway 7, Suite {i}",
            f"Unit {i}, 8888 Highway 7, Coquitlam, BC",
            f"Ste. {i}-B - 8888 Highway 7",
            f"8888 Highway 7 Apt #{i}",
            f"# {i}, 8888 Highway 7, Port Coquitlam"
        ]
        chosen = variants[i % len(variants)]
        try:
            payload = ParcelCameraOverrideSchema(
                clean_address=chosen,
                front_lat=49.2000 + (i * 0.0001),
                front_lng=-122.8000 - (i * 0.0001),
                heading=float((i * 13) % 360),
                pitch=float(i % 15),
                fov=85.0
            )
            save_parcel_streetview(payload=payload, db=thread_db)
            return True, None
        except Exception as e:
            thread_db.rollback()
            return False, str(e)
        finally:
            thread_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(stress_worker, i) for i in range(50)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    success_count = sum(1 for ok, _ in results if ok)
    fail_errors = [err for ok, err in results if not ok]

    db = SessionLocal()
    p_count = db.query(ParcelModel).filter(ParcelModel.clean_address == stress_target).count()
    s_count = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == stress_target).count()
    
    # Retrieve saved parcel to verify data
    saved_p = db.query(ParcelModel).filter(ParcelModel.clean_address == stress_target).first()
    db.close()

    t4_pass = True
    if success_count != 50 or fail_errors:
        print(f"[FAIL] 50 Concurrent workers result: {success_count}/50 succeeded. Errors: {fail_errors[:5]}")
        t4_pass = False
    elif p_count != 1 or s_count != 1:
        print(f"[FAIL] DB Row count mismatch: Parcel count={p_count}, Legacy count={s_count} (Expected 1 each)")
        t4_pass = False
    else:
        print(f"[PASS] 50 Concurrent workers executed cleanly with 0 errors! Parcels row count = 1, Legacy row count = 1")
        if saved_p:
            print(f"       Final Parcel Camera State: Heading={saved_p.streetview_heading}, Pitch={saved_p.streetview_pitch}, FOV={saved_p.streetview_fov}")

    # Final Verdict Summary
    all_passed = t1_pass and t1b_pass and t2_pass and t3_pass and t4_pass
    print("\n===============================================================")
    print(f"EMPIRICAL RECHECK 2 RESULT: {'PASS - ALL SUITES GREEN' if all_passed else 'FAIL - ISSUES DETECTED'}")
    print("===============================================================")
    return all_passed

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
