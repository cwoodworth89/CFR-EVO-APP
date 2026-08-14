#!/usr/bin/env python3
"""
Extended Adversarial Verification Suite for Milestone 1 Recheck
Author: Challenger 1 (Re-check)
"""
import os
import sys
import concurrent.futures
from fastapi import HTTPException

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

def run_adversarial_checks():
    print("===============================================================")
    print("RUNNING EXTENDED ADVERSARIAL RE-CHECK TESTS")
    print("===============================================================")
    
    db = SessionLocal()
    
    # Save standard parcel 3030 GORDON AVE
    save_parcel_streetview(
        ParcelCameraOverrideSchema(
            clean_address="3030 GORDON AVE",
            front_lat=49.2785,
            front_lng=-122.7932,
            heading=180.0
        ),
        db=db
    )
    
    # 1. Complex Unit & Separator Variants
    print("\n--- Test A1: Complex Unit & Separator Variants ---")
    test_variants = [
        "Unit 101, 3030 Gordon Ave, Coquitlam, BC",
        "Apt 202-B - 3030 Gordon Ave",
        "#303-C, 3030 Gordon Ave",
        "Suite 400A - 3030 Gordon Ave, Port Coquitlam, British Columbia",
        "3030 Gordon Ave Unit 101B",
        "3030 Gordon Ave, Suite 500-X",
        "3030 Gordon Ave - Apt 202",
        "3030 Gordon Ave #303",
        "3030 Gordon Ave, #303",
        "Unit #101, 3030 Gordon Ave",
        "Ste 101, 3030 Gordon Ave",
        "Apt. 202 - 3030 Gordon Ave"
    ]
    
    all_a1_pass = True
    for var in test_variants:
        cleaned = _clean_streetview_address(var)
        res = lookup_parcel(query=var, db=db)
        found = res["found"]
        found_addr = res["parcel"]["clean_address"] if found else None
        if not found or found_addr != "3030 GORDON AVE":
            print(f"[FAIL] Variant '{var}': Cleaned='{cleaned}', Found={found}, FoundAddress='{found_addr}'")
            all_a1_pass = False
        else:
            print(f"[PASS] Variant '{var}': Cleaned='{cleaned}', Found={found}")
            
    # 2. Empty & Whitespace Rejection Validation
    print("\n--- Test A2: Empty & Whitespace Address Rejection ---")
    invalid_addresses = ["", "   ", "\t\n  ", "   COQUITLAM, BC   ", "  PORT MOODY, BRITISH COLUMBIA  "]
    all_a2_pass = True
    for inv in invalid_addresses:
        try:
            payload = ParcelCameraOverrideSchema(clean_address=inv, gis_id=None)
            save_parcel_streetview(payload=payload, db=db)
            print(f"[FAIL] Invalid address {repr(inv)} was accepted by save_parcel_streetview!")
            all_a2_pass = False
        except HTTPException as e:
            if e.status_code == 400:
                print(f"[PASS] Invalid address {repr(inv)} rejected with HTTP 400: {e.detail}")
            else:
                print(f"[FAIL] Invalid address {repr(inv)} raised HTTP {e.status_code} instead of 400")
                all_a2_pass = False
        except Exception as e:
            print(f"[FAIL] Unexpected exception on {repr(inv)}: {e}")
            all_a2_pass = False
            
    # 3. High-Concurrency Stress Test (50 Parallel Workers with Address Variants)
    print("\n--- Test A3: High-Concurrency Stress (50 Workers with Address Variants) ---")
    target_addr = "9999 ADVERSARIAL WAY"
    
    # Cleanup target address if exists
    p_exist = db.query(ParcelModel).filter(ParcelModel.clean_address == target_addr).first()
    if p_exist:
        db.delete(p_exist)
        db.commit()
    s_exist = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == target_addr).first()
    if s_exist:
        db.delete(s_exist)
        db.commit()
    db.close()

    def worker_func(i: int):
        thread_db = SessionLocal()
        variants = [
            f"Unit {i}, 9999 Adversarial Way",
            f"Apt {i} - 9999 Adversarial Way, Coquitlam",
            f"9999 Adversarial Way Unit {i}",
            f"# {i}, 9999 Adversarial Way",
            f"9999 Adversarial Way Suite {i}"
        ]
        var_addr = variants[i % len(variants)]
        try:
            payload = ParcelCameraOverrideSchema(
                clean_address=var_addr,
                front_lat=49.100 + i * 0.0001,
                front_lng=-122.100 - i * 0.0001,
                heading=float(i * 7 % 360),
                pitch=float(i % 10),
                fov=80.0
            )
            save_parcel_streetview(payload=payload, db=thread_db)
            return True, None
        except Exception as e:
            thread_db.rollback()
            return False, str(e)
        finally:
            thread_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(worker_func, i) for i in range(50)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
    successes = sum(1 for ok, _ in results if ok)
    errors = [err for ok, err in results if not ok]
    
    db = SessionLocal()
    p_cnt = db.query(ParcelModel).filter(ParcelModel.clean_address == target_addr).count()
    s_cnt = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == target_addr).count()
    db.close()
    
    all_a3_pass = True
    if successes != 50 or errors:
        print(f"[FAIL] 50 Concurrent workers result: {successes}/50 succeeded. Errors: {errors[:3]}")
        all_a3_pass = False
    elif p_cnt != 1 or s_cnt != 1:
        print(f"[FAIL] DB Row count mismatch: Parcels={p_cnt}, Legacy={s_cnt} (expected 1 each)")
        all_a3_pass = False
    else:
        print(f"[PASS] 50 Concurrent workers succeeded cleanly with 0 errors! DB row count = 1.")

    print("\n===============================================================")
    overall_pass = all_a1_pass and all_a2_pass and all_a3_pass
    print(f"EXTENDED ADVERSARIAL STATUS: {'ALL PASSED' if overall_pass else 'FAILURES DETECTED'}")
    print("===============================================================")
    return overall_pass

if __name__ == "__main__":
    success = run_adversarial_checks()
    sys.exit(0 if success else 1)
