import os
import sys
import json
import urllib.request
import urllib.parse
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def sync_hydrants(mode="full"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "..", "..", "frontend", "public", "data")
    output_path = os.path.join(output_dir, "hydrants.json")
    os.makedirs(output_dir, exist_ok=True)

    old_hydrants = {}
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                old_list = json.load(f)
                old_hydrants = {h["id"]: h for h in old_list if "id" in h}
            logging.info(f"Loaded {len(old_hydrants)} existing hydrants from local cache.")
        except Exception as e:
            logging.warning(f"Could not read existing hydrants file: {e}")

    url = "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Water/MapServer/2/query"
    fresh_features = []
    offset = 0
    limit = 1000

    logging.info(f"Fetching fresh hydrant data (mode={mode}) from geodata.coquitlam.ca...")
    try:
        while True:
            params = {
                "where": "1=1",
                "outFields": "OBJECTID,gis_id,status,flow_class",
                "resultOffset": str(offset),
                "resultRecordCount": str(limit),
                "outSR": "4326",
                "f": "json"
            }
            encoded = urllib.parse.urlencode(params)
            req = urllib.request.Request(f"{url}?{encoded}", headers={'User-Agent': 'Mozilla/5.0'})
            
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                
            if "error" in data:
                logging.error(f"ArcGIS Error: {data['error']}")
                return False
                
            features = data.get("features", [])
            if not features:
                break
                
            fresh_features.extend(features)
            if len(features) < limit:
                break
            offset += limit
            
    except Exception as e:
        logging.error(f"Failed to fetch hydrants from server: {e}")
        return False

    logging.info(f"Fetched {len(fresh_features)} hydrants from ArcGIS MapServer.")

    new_hydrants_list = []
    for f in fresh_features:
        attribs = f.get("attributes", {})
        geometry = f.get("geometry", {})
        obj_id = attribs.get("OBJECTID")
        if not obj_id or not geometry or "x" not in geometry or "y" not in geometry:
            continue
            
        hyd = {
            "id": obj_id,
            "gisId": attribs.get("gis_id") or f"H-{obj_id}",
            # No defaults. Verified against the City ArcGIS source 2026-08-21: private
            # hydrants return flow_class = null. Defaulting to "AA" told crews an
            # unrated hydrant was the highest NFPA 291 class -- the most dangerous
            # direction for a substitution (CLAUDE.md 6.1). Defaulting status to
            # "OPERATING" likewise showed a hydrant of unknown condition as in service.
            "status": attribs.get("status"),
            "flowClass": attribs.get("flow_class"),
            "lng": round(geometry.get("x"), 6),
            "lat": round(geometry.get("y"), 6),
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        new_hydrants_list.append(hyd)

    with open(output_path, "w", encoding="utf-8") as out_f:
        json.dump(new_hydrants_list, out_f, indent=2)

    logging.info(f"Successfully saved {len(new_hydrants_list)} hydrants to {output_path}!")

    unrated = sum(1 for h in new_hydrants_list if not h["flowClass"])
    no_status = sum(1 for h in new_hydrants_list if not h["status"])
    logging.info(
        f"  {unrated} hydrants have no NFPA 291 flow class and {no_status} have no "
        f"status at source; these are stored NULL and must render as UNRATED/UNKNOWN."
    )

    _write_hydrants_to_db(new_hydrants_list)
    return True


def _write_hydrants_to_db(hydrants: list) -> None:
    """Upserts the synced hydrants into public.hydrants.

    public.hydrants is the source of truth; the JSON file is a browser cache that the
    kiosk still fetches directly. Unknown status/flow_class are written NULL.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logging.warning("DATABASE_URL not set; skipping public.hydrants upsert.")
        return

    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(db_url)
        with engine.begin() as conn:
            for h in hydrants:
                conn.execute(text("""
                    INSERT INTO public.hydrants
                        (object_id, gis_id, status, flow_class, lat, lng, geom, synced_at)
                    VALUES
                        (:oid, :gid, :status, :flow, :lat, :lng,
                         ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), CURRENT_TIMESTAMP)
                    ON CONFLICT (object_id) DO UPDATE SET
                        gis_id     = EXCLUDED.gis_id,
                        status     = EXCLUDED.status,
                        flow_class = EXCLUDED.flow_class,
                        lat        = EXCLUDED.lat,
                        lng        = EXCLUDED.lng,
                        geom       = EXCLUDED.geom,
                        synced_at  = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                """), {
                    "oid": h["id"], "gid": h["gisId"], "status": h["status"],
                    "flow": h["flowClass"], "lat": h["lat"], "lng": h["lng"],
                })

            conn.execute(text("""
                UPDATE public.hydrants h SET zone_id = z.map_name
                FROM public.zones z
                WHERE h.zone_id IS DISTINCT FROM z.map_name
                  AND ST_Contains(z.geom, h.geom)
            """))

        logging.info(f"  Upserted {len(hydrants)} hydrants into public.hydrants.")
    except Exception as e:
        logging.error(f"  Failed to write hydrants to public.hydrants: {e}")
    return True

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    sync_hydrants(mode)
