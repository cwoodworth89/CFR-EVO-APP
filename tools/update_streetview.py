import sys
import os

import _repo  # noqa: F401  tools/_repo.py puts backend/ (the api package) on sys.path
sys.path.insert(0, "/app")

try:
    from api.database import SessionLocal
    from api.models import StreetViewOverrideModel, ParcelModel
except ImportError:
    try:
        from backend.api.database import SessionLocal
        from backend.api.models import StreetViewOverrideModel, ParcelModel
    except ImportError:
        from database import SessionLocal
        from models import StreetViewOverrideModel, ParcelModel

def update_override(address: str, front_lat: float, front_lng: float, heading: float, pitch: float = 5.0, fov: float = 80.0):
    db = SessionLocal()
    try:
        addr = address.strip().upper()
        p = db.query(ParcelModel).filter(
            (ParcelModel.address == addr) |
            (ParcelModel.address_normalized == addr.lower()) |
            (ParcelModel.gis_id == addr)
        ).first()
        if p:
            p.front_lat = front_lat
            p.front_lng = front_lng
            p.streetview_heading = heading
            p.streetview_pitch = pitch
            p.streetview_fov = fov
        else:
            p = ParcelModel(
                gis_id=addr,
                address=addr,
                address_normalized=addr.lower(),
                front_lat=front_lat,
                front_lng=front_lng,
                lat=front_lat,
                lng=front_lng,
                streetview_heading=heading,
                streetview_pitch=pitch,
                streetview_fov=fov
            )
            db.add(p)

        db.commit()
        print(f"SUCCESS: Saved {addr} -> lat={front_lat}, lng={front_lng}, heading={heading}, pitch={pitch}, fov={fov}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) >= 5:
        addr = sys.argv[1].upper()
        lat = float(sys.argv[2])
        lng = float(sys.argv[3])
        hdg = float(sys.argv[4])
        ptch = float(sys.argv[5]) if len(sys.argv) > 5 else 5.0
        fov = float(sys.argv[6]) if len(sys.argv) > 6 else 80.0
        update_override(addr, lat, lng, hdg, ptch, fov)
    else:
        # Default for 3030 Gordon Ave street frontage
        update_override("3030 GORDON AVE", 49.26995, -122.79190, 35.0, 10.0, 80.0)
