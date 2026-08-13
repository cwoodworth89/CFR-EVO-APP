import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cfr_dispatch.database import get_db_session
from api.models import StreetViewOverrideModel, ParcelModel

def update_override(clean_address: str, front_lat: float, front_lng: float, heading: float, pitch: float = 5.0, fov: float = 80.0):
    with get_db_session() as session:
        # Update or insert in StreetViewOverrideModel
        r = session.query(StreetViewOverrideModel).filter(StreetViewOverrideModel.clean_address == clean_address).first()
        if not r:
            r = StreetViewOverrideModel(clean_address=clean_address, front_lat=front_lat, front_lng=front_lng, heading=heading, pitch=pitch, fov=fov)
            session.add(r)
        else:
            r.front_lat = front_lat
            r.front_lng = front_lng
            r.heading = heading
            r.pitch = pitch
            r.fov = fov
        
        # Also update ParcelModel if exists
        p = session.query(ParcelModel).filter(ParcelModel.clean_address == clean_address).first()
        if p:
            p.front_lat = front_lat
            p.front_lng = front_lng
            p.streetview_heading = heading
            p.streetview_pitch = pitch
            p.streetview_fov = fov

        session.commit()
        print(f"SUCCESS: Saved {clean_address} -> lat={front_lat}, lng={front_lng}, heading={heading}, pitch={pitch}, fov={fov}")

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
        # Default test for 3030 Gordon Ave
        update_override("3030 GORDON AVE", 49.26995, -122.79190, 35.0, 10.0, 80.0)
