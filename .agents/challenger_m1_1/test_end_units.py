#!/usr/bin/env python3
"""
Test unit number at the end of address
"""
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
app_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
backend_dir = os.path.join(app_root, "backend")

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if app_root not in sys.path:
    sys.path.insert(0, app_root)

from api.database import SessionLocal
from api.server import _clean_streetview_address, lookup_parcel

db = SessionLocal()

end_unit_variants = [
    "3030 Gordon Ave Unit 101",
    "3030 Gordon Ave Apt 202",
    "3030 Gordon Ave #303",
    "3030 Gordon Ave Suite 400",
]

print("Testing End-Unit Address Variants against saved '3030 GORDON AVE':")
for v in end_unit_variants:
    cleaned = _clean_streetview_address(v)
    res = lookup_parcel(query=v, db=db)
    found = res["found"]
    clean_in_db = res["parcel"]["clean_address"] if found else "NONE"
    print(f"Variant: '{v}' -> Cleaned: '{cleaned}' -> Found: {found} (Address: {clean_in_db})")

db.close()
