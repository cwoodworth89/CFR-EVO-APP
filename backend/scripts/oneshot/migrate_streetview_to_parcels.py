#!/usr/bin/env python3
"""
Migration script: Backfill legacy `streetview_overrides` into `parcels` table.
Run inside container stack: docker exec -it cfr_api python /app/scripts/migrate_streetview_to_parcels.py
"""
import sys
import os
import re

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from api.database import SessionLocal
    from api.models import StreetViewOverrideModel, ParcelModel
    from api.server import _clean_streetview_address
except ModuleNotFoundError:
    from backend.api.database import SessionLocal
    from backend.api.models import StreetViewOverrideModel, ParcelModel
    from backend.api.server import _clean_streetview_address

def migrate_overrides(db_session=None):
    db = db_session or SessionLocal()
    try:
        overrides = db.query(StreetViewOverrideModel).all()
        print(f"[MIGRATE] Found {len(overrides)} legacy Street View override records to migrate...")

        migrated_count = 0
        created_count = 0

        for r in overrides:
            raw_addr = r.clean_address.strip().upper()
            clean_addr = _clean_streetview_address(r.clean_address) or raw_addr
            
            # Find matching parcel
            parcel = db.query(ParcelModel).filter(
                (ParcelModel.clean_address == clean_addr) |
                (ParcelModel.clean_address == raw_addr) |
                (ParcelModel.gis_id == clean_addr) |
                (ParcelModel.gis_id == raw_addr)
            ).first()

            if not parcel and clean_addr:
                parcel = db.query(ParcelModel).filter(
                    ParcelModel.clean_address.ilike(f"%{clean_addr}%")
                ).first()

            if not parcel:
                # Create parcel entry for this override
                parcel = ParcelModel(
                    gis_id=clean_addr,
                    clean_address=clean_addr,
                    front_lat=r.front_lat,
                    front_lng=r.front_lng,
                    streetview_heading=r.heading,
                    streetview_pitch=r.pitch,
                    streetview_fov=r.fov
                )
                db.add(parcel)
                created_count += 1
            else:
                parcel.streetview_heading = r.heading
                parcel.streetview_pitch = r.pitch
                parcel.streetview_fov = r.fov
                if not parcel.front_lat: parcel.front_lat = r.front_lat
                if not parcel.front_lng: parcel.front_lng = r.front_lng
                migrated_count += 1

        db.commit()
        print(f"[OK] Migration complete! Updated {migrated_count} existing parcels, created {created_count} new parcel records.")
        return migrated_count, created_count
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Migration failed: {e}")
        raise e
    finally:
        if not db_session:
            db.close()

if __name__ == "__main__":
    migrate_overrides()
