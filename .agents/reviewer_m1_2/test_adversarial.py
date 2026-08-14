import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
backend_dir = os.path.join(root_dir, "backend")

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

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

def run_adversarial_tests():
    print("--- Starting Adversarial Stress Tests ---")
    db = SessionLocal()
    
    # 1. SQL Injection attempts in lookup query
    sqli_payloads = [
        "' OR '1'='1",
        "3030 GORDON'; DROP TABLE parcels; --",
        "1 UNION SELECT 1,2,3--",
        "%' AND 1=1 --",
        "\\'; SELECT pg_sleep(5); --"
    ]
    
    for sqli in sqli_payloads:
        try:
            res = lookup_parcel(query=sqli, db=db)
            assert res["found"] is False
            print(f"[PASS] SQLi Payload handled safely: {sqli!r}")
        except Exception as e:
            print(f"[FAIL] Exception on SQLi payload {sqli!r}: {e}")
            raise e

    # 2. SQL Injection in get_streetview_override
    for sqli in sqli_payloads:
        try:
            get_streetview_override(address=sqli, db=db)
            print(f"[FAIL] Expected 404 for SQLi payload {sqli!r}, but succeeded")
        except Exception as e:
            assert "404" in str(e)
            print(f"[PASS] SQLi Payload 404 handled: {sqli!r}")

    # 3. Unicode and special character address normalization
    special_addrs = [
        " 1234  Main  St.  ",
        "Unit #402, 500 Lougheed Hwy, Coquitlam, BC",
        "Apt 12B - 700 Mariner Way",
        "  "
    ]
    for sa in special_addrs:
        cleaned = _clean_streetview_address(sa)
        print(f"Cleaned {sa!r} -> {cleaned!r}")

    # 4. Save parcel with minimal fields & verify fallbacks
    payload = ParcelCameraOverrideSchema(
        clean_address="999 ADVERSARIAL WAY",
        heading=270.0,
        pitch=-5.0,
        fov=60.0
        # front_lat & front_lng omitted (None)
    )
    save_res = save_parcel_streetview(payload=payload, db=db)
    assert save_res["status"] == "success"
    assert save_res["parcel"]["clean_address"] == "999 ADVERSARIAL WAY"
    assert save_res["parcel"]["streetview_heading"] == 270.0
    
    # Verify legacy override table received sync record with default 0.0 lat/lng
    leg = db.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == "999 ADVERSARIAL WAY").first()
    assert leg is not None
    assert leg.heading == 270.0
    assert leg.front_lat == 0.0
    assert leg.front_lng == 0.0
    print("[PASS] Save with omitted lat/lng & legacy sync handled correctly.")

    # Cleanup test data
    p = db.query(ParcelModel).filter(ParcelModel.clean_address == "999 ADVERSARIAL WAY").first()
    if p: db.delete(p)
    if leg: db.delete(leg)
    db.commit()
    db.close()

    print("--- ALL ADVERSARIAL STRESS TESTS PASSED ---")

if __name__ == "__main__":
    run_adversarial_tests()
