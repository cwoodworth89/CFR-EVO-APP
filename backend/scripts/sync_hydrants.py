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
            "status": attribs.get("status") or "OPERATING",
            "flowClass": attribs.get("flow_class") or "AA",
            "lng": round(geometry.get("x"), 6),
            "lat": round(geometry.get("y"), 6),
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        new_hydrants_list.append(hyd)

    with open(output_path, "w", encoding="utf-8") as out_f:
        json.dump(new_hydrants_list, out_f, indent=2)

    logging.info(f"Successfully saved {len(new_hydrants_list)} hydrants to {output_path}!")
    return True

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    sync_hydrants(mode)
