#!/usr/bin/env python3
"""
Deep Empirical Stress Test Suite — Challenger 1 (Recheck 3)
Focus: Trailing Punctuation, Unit Prefixes/Suffixes (hashes, dots, dashes),
Database Lookup & High-Concurrency Upserts (100 parallel workers).
"""

import os
import sys
import concurrent.futures
from fastapi import HTTPException

# Ensure backend directory is in python path
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

def run_recheck3_suite():
    print("===============================================================")
    print("STARTING EMPIRICAL ADVERSARIAL STRESS SUITE (RECHECK 3)")
    print("===============================================================")

    db = SessionLocal()

    # SECTION 1: Exhaustive Trailing Punctuation & Unit Clean Matrix
    print("\n--- Section 1: Trailing Punctuation & Complex Unit Patterns ---")
    test_cases = [
        # User specified prompt requirements
        ("3030 Gordon Ave, Suite 500-X,", "3030 GORDON AVE"),
        ("3030 Gordon Ave, #303,", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Unit 101,", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Ste. 101,", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Apt 202,", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Suite 500-X.", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Suite 500-X   ", "3030 GORDON AVE"),
        ("  3030   GORDON   AVE  ,  SUITE   100  ", "3030 GORDON AVE"),
        
        # Additional complex combinations with trailing commas/dots/dashes
        ("3030 Gordon Ave, Ste. 101-B,", "3030 GORDON AVE"),
        ("3030 Gordon Ave - Apt #202-C.", "3030 GORDON AVE"),
        ("3030 Gordon Ave #303-A...", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Apt # 202-B,", "3030 GORDON AVE"),
        ("3030 Gordon Ave - Suite 300, Coquitlam, BC.", "3030 GORDON AVE"),
        ("3030 Gordon Ave, Unit # 101-X, Port Coquitlam, British Columbia,", "3030 GORDON AVE"),
        
        # Unit Prefixes at Beginning of string with trailing punctuation
        ("Unit 101, 3030 Gordon Ave,", "3030 GORDON AVE"),
        ("Unit #101-A, 3030 Gordon Ave, BC", "3030 GORDON AVE"),
        ("Ste. 500-X - 3030 Gordon Ave, Port Moody, BC.", "3030 GORDON AVE"),
        ("Apt #202-B, 3030 Gordon Ave, Coquitlam,", "3030 GORDON AVE"),
        ("#303-C, 3030 Gordon Ave.", "3030 GORDON AVE"),

        # Other typical Coquitlam / Port Coquitlam addresses
        ("1234 Mariner Way, Unit 12,", "1234 MARINER WAY"),
        ("500 Lougheed Hwy, Ste 400,", "500 LOUGHEED HIGHWAY"),
        ("2000 Barnet Hwy, Apt. 301-B.", "2000 BARNET HIGHWAY"),
    ]

    sec1_pass = True
    for raw_input, expected in test_cases:
        actual = _clean_streetview_address(raw_input)
        if actual != expected:
            print(f"[FAIL] Input '{raw_input}': Expected '{expected}', Got '{actual}'")
            sec1_pass = False
        else:
            print(f"[PASS] Input '{raw_input}' -> '{actual}'")

    # SECTION 2: Database Lookup Resolution for Trailing Punctuation Strings
    print("\n--- Section 2: DB Lookup Resolution with Trailing Punctuation ---")
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

    lookup_queries = [
        "3030 Gordon Ave, Suite 500-X,",
        "3030 Gordon Ave, #303,",
        "3030 Gordon Ave, Ste. 101-B,",
        "Unit #101-A, 3030 Gordon Ave, BC,",
        "3030 Gordon Ave - Apt #202-C.",
        "3030 Gordon Ave, Port Coquitlam, British Columbia.",
    ]

    sec2_pass = True
    for q in lookup_queries:
        res = lookup_parcel(query=q, db=db)
        if not res.get("found") or not res.get("parcel"):
            print(f"[FAIL] Lookup failed for query: '{q}'")
            sec2_pass = False
        else:
            found_addr = res["parcel"]["clean_address"]
            if found_addr != "3030 GORDON AVE":
                print(f"[FAIL] Query '{q}' returned wrong address '{found_addr}'")
                sec2_pass = False
            else:
                print(f"[PASS] Query '{q}' resolved to '3030 GORDON AVE'")

    # SECTION 3: 100-Thread Concurrent Database Upserts
    print("\n--- Section 3: High-Concurrency Stress (100 Threads) ---")
    stress_addr = "7777 RECHECK THREE BLVD"

    # Cleanup target
    p_exist = db.query(ParcelModel).filter(ParcelModel.clean_address == stress_addr).first()
    if p_exist:
        db.delete(p_exist)
    s_exist = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == stress_addr).first()
    if s_exist:
        db.delete(s_exist)
    db.commit()
    db.close()

    def worker_func(i: int):
        thread_db = SessionLocal()
        variants = [
            f"7777 Recheck Three Blvd, Suite {i}-X,",
            f"Unit #{i}, 7777 Recheck Three Blvd, Coquitlam, BC.",
            f"7777 Recheck Three Blvd - Ste. {i}-B,",
            f"Apt #{i} - 7777 Recheck Three Blvd.",
            f"# {i}, 7777 Recheck Three Blvd, Port Coquitlam,"
        ]
        raw_addr = variants[i % len(variants)]
        try:
            payload = ParcelCameraOverrideSchema(
                clean_address=raw_addr,
                front_lat=49.2500 + (i * 0.0001),
                front_lng=-122.7500 - (i * 0.0001),
                heading=float((i * 17) % 360),
                pitch=float(i % 20),
                fov=85.0
            )
            save_parcel_streetview(payload=payload, db=thread_db)
            return True, None
        except Exception as e:
            thread_db.rollback()
            return False, str(e)
        finally:
            thread_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(worker_func, i) for i in range(100)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    success_cnt = sum(1 for ok, _ in results if ok)
    errors = [err for ok, err in results if not ok]

    db = SessionLocal()
    p_count = db.query(ParcelModel).filter(ParcelModel.clean_address == stress_addr).count()
    s_count = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == stress_addr).count()
    db.close()

    sec3_pass = True
    if success_cnt != 100 or errors:
        print(f"[FAIL] 100 Concurrent workers: {success_cnt}/100 succeeded. Errors: {errors[:3]}")
        sec3_pass = False
    elif p_count != 1 or s_count != 1:
        print(f"[FAIL] DB Row count mismatch: Parcels={p_count}, Legacy={s_count} (Expected 1 each)")
        sec3_pass = False
    else:
        print(f"[PASS] 100 Concurrent workers succeeded cleanly with 0 errors! DB row count = 1.")

    all_passed = sec1_pass and sec2_pass and sec3_pass
    print("\n===============================================================")
    print(f"RECHECK 3 SUITE RESULT: {'PASS - ALL SUITES GREEN' if all_passed else 'FAIL - ISSUES DETECTED'}")
    print("===============================================================")
    return all_passed

if __name__ == "__main__":
    success = run_recheck3_suite()
    sys.exit(0 if success else 1)
