#!/usr/bin/env python3
"""
Test saving parcel with blank or invalid address targets
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
from api.server import save_parcel_streetview, ParcelCameraOverrideSchema

db = SessionLocal()

print("Testing save_parcel_streetview with empty address / gis_id:")

try:
    payload = ParcelCameraOverrideSchema(clean_address="", gis_id="")
    res = save_parcel_streetview(payload=payload, db=db)
    print(f"Empty clean_address & gis_id: {res}")
except Exception as e:
    print(f"Empty clean_address & gis_id Exception: {e}")

try:
    payload = ParcelCameraOverrideSchema(clean_address="   ", gis_id=None)
    res = save_parcel_streetview(payload=payload, db=db)
    print(f"Whitespace clean_address & None gis_id: {res}")
except Exception as e:
    print(f"Whitespace clean_address & None gis_id Exception: {e}")

db.close()
