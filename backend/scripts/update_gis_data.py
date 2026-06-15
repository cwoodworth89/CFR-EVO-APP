# ==============================================================================
# update_gis_data.py
# Monthly Maintenance Script to Update Coquitlam GIS Shapefiles (100% Offline)
# ==============================================================================
import os
import sys

# Ensure working directory is the agent folder so relative data paths and imports resolve correctly
script_dir = os.path.dirname(os.path.abspath(__file__))
agent_dir = os.path.dirname(script_dir)
os.chdir(agent_dir)
if agent_dir not in sys.path:
    sys.path.append(agent_dir)

import zipfile
import urllib.request
import urllib.parse
import json
import logging
import shutil
import geopandas as gpd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("gis_maintenance.log", mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- Configuration & Default Portal URLs ---
# These default URLs point to the City of Coquitlam's ArcGIS Hub datasets.
# They can be overridden via environment variables if the portal hashes change.
ADDRESS_ZIP_URL = os.environ.get(
    "ADDRESS_DATA_URL",
    "https://opendata.arcgis.com/api/v3/datasets/3df0090289aa4503bd8d234d7ee0c182_0/downloads/data?format=shp&spatialRefId=4326"
)
ZONES_ZIP_URL = os.environ.get(
    "ZONES_DATA_URL",
    "https://opendata.arcgis.com/api/v3/datasets/109ad5fa4cb149ab93a1f9a2de88f34d_0/downloads/data?format=shp&spatialRefId=4326"
)

TEMP_DIR = "data/temp_maintenance"
DATA_DIR = "data"
ADDRESS_DEST_DIR = "data/Property_Information"
ZONES_DEST_DIR = "data/Emergency_Response_Zones"

def download_file(url: str, dest_path: str):
    logging.info(f"Downloading dataset from: {url}")
    # Use urllib with custom User-Agent to avoid blockage
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)
    logging.info(f"Successfully downloaded to: {dest_path}")

def extract_and_clean(zip_path: str, dest_dir: str):
    logging.info(f"Extracting {zip_path} to {dest_dir}...")
    if os.path.exists(dest_dir):
        # Backup old directory before wiping
        backup_dir = f"{dest_dir}_backup"
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        shutil.copytree(dest_dir, backup_dir)
        shutil.rmtree(dest_dir)
        
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dest_dir)
    logging.info(f"Successfully extracted dataset to {dest_dir}")

def fix_winding_order(dest_dir: str):
    # Locate shapefile inside the directory
    shp_file = None
    for file in os.listdir(dest_dir):
        if file.endswith(".shp"):
            shp_file = os.path.join(dest_dir, file)
            break
            
    if not shp_file:
        logging.warning(f"No .shp file found in {dest_dir} to correct winding order.")
        return
        
    logging.info(f"Correcting polygon winding order for: {shp_file}...")
    try:
        # Load and re-save using geopandas. Winding order errors are corrected in memory.
        gdf = gpd.read_file(shp_file)
        gdf.to_file(shp_file, driver='ESRI Shapefile')
        logging.info("Winding order correction complete.")
    except Exception as e:
        logging.error(f"Failed to correct winding order: {e}", exc_info=True)

def update_hydrant_data():
    logging.info("=== Starting Coquitlam Fire Hydrants Database Update ===")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "..", "frontend", "public", "data")
    output_path = os.path.join(output_dir, "hydrants.json")
    
    # 1. Load existing hydrants if file exists
    old_hydrants = {}
    if os.path.exists(output_path):
        try:
            with open(output_path, "r") as f:
                old_list = json.load(f)
                old_hydrants = {h["id"]: h for h in old_list if "id" in h}
            logging.info(f"Loaded {len(old_hydrants)} existing hydrants from cache.")
        except Exception as e:
            logging.warning(f"Could not load existing hydrants file: {e}")
            
    # 2. Download fresh list from Coquitlam ArcGIS server
    url = "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Water/MapServer/2/query"
    fresh_features = []
    offset = 0
    limit = 1000
    
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
            
            logging.info(f"Fetching hydrants from server, offset {offset}...")
            encoded_params = urllib.parse.urlencode(params)
            req = urllib.request.Request(
                f"{url}?{encoded_params}",
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                
            if "error" in data:
                logging.error(f"ArcGIS server returned error: {data['error']}")
                return
                
            features = data.get("features", [])
            if not features:
                break
                
            fresh_features.extend(features)
            if len(features) < limit:
                break
            offset += limit
            
    except Exception as e:
        logging.error(f"Failed to query new hydrant listings from server: {e}")
        return
        
    logging.info(f"Fetched {len(fresh_features)} fresh hydrants from MapServer.")
    
    # 3. Process fresh hydrants
    new_hydrants_list = []
    new_hydrants_dict = {}
    
    for f in fresh_features:
        attribs = f.get("attributes", {})
        geometry = f.get("geometry", {})
        
        obj_id = attribs.get("OBJECTID")
        if not obj_id or not geometry or "x" not in geometry or "y" not in geometry:
            continue
            
        hyd = {
            "id": obj_id,
            "gisId": attribs.get("gis_id") or "Unknown",
            "status": attribs.get("status") or "OPERATING",
            "flowClass": attribs.get("flow_class") or "",
            "lng": geometry.get("x"),
            "lat": geometry.get("y")
        }
        new_hydrants_list.append(hyd)
        new_hydrants_dict[obj_id] = hyd
        
    # 4. Compare old and new datasets
    added = []
    deleted = []
    modified = []
    
    for obj_id, new_hyd in new_hydrants_dict.items():
        if obj_id not in old_hydrants:
            added.append(new_hyd)
        else:
            old_hyd = old_hydrants[obj_id]
            changes = []
            for key in ["gisId", "status", "flowClass", "lat", "lng"]:
                if old_hyd.get(key) != new_hyd.get(key):
                    changes.append(f"{key}: {old_hyd.get(key)} -> {new_hyd.get(key)}")
            if changes:
                modified.append((new_hyd, changes))
                
    for obj_id, old_hyd in old_hydrants.items():
        if obj_id not in new_hydrants_dict:
            deleted.append(old_hyd)
            
    # 5. Log change summary
    logging.info("\n=== Hydrants Change Summary ===")
    logging.info(f"Additions: {len(added)}")
    for a in added[:10]:
        logging.info(f"  [+] Added: ID {a['id']} (GIS ID {a['gisId']}), status={a['status']}, flowClass={a['flowClass']}")
    if len(added) > 10:
        logging.info(f"  ... and {len(added) - 10} more.")
        
    logging.info(f"Deletions: {len(deleted)}")
    for d in deleted[:10]:
        logging.info(f"  [-] Deleted: ID {d['id']} (GIS ID {d['gisId']})")
    if len(deleted) > 10:
        logging.info(f"  ... and {len(deleted) - 10} more.")
        
    logging.info(f"Status/Metadata Changes: {len(modified)}")
    for m, changes in modified[:10]:
        logging.info(f"  [*] Changed: ID {m['id']} (GIS ID {m['gisId']}) - {', '.join(changes)}")
    if len(modified) > 10:
        logging.info(f"  ... and {len(modified) - 10} more.")
    logging.info("================================\n")
    
    # 6. Save updated file
    os.makedirs(output_dir, exist_ok=True)
    try:
        with open(output_path, "w") as out_f:
            json.dump(new_hydrants_list, out_f, indent=2)
        logging.info(f"Successfully updated cached hydrant database at: {output_path}")
    except Exception as e:
        logging.error(f"Failed to write updated hydrants file: {e}")

def main():
    logging.info("=== Starting Coquitlam GIS Database Monthly Update ===")
    
    # Create temp directory
    os.makedirs(TEMP_DIR, exist_ok=True)
    address_zip = os.path.join(TEMP_DIR, "addresses.zip")
    zones_zip = os.path.join(TEMP_DIR, "zones.zip")
    
    # 1. Update shapefile layers (address and response zones)
    try:
        logging.info("Updating shapefile layers (address and response zones)...")
        # Download datasets
        download_file(ADDRESS_ZIP_URL, address_zip)
        download_file(ZONES_ZIP_URL, zones_zip)
        
        # Extract and wipe temp dirs
        extract_and_clean(address_zip, ADDRESS_DEST_DIR)
        extract_and_clean(zones_zip, ZONES_DEST_DIR)
        
        # Post-Download shapefile correction
        fix_winding_order(ADDRESS_DEST_DIR)
        fix_winding_order(ZONES_DEST_DIR)
        
        logging.info("Shapefile layers successfully updated!")
        
        # Clean up backups if exists
        for folder in [ADDRESS_DEST_DIR, ZONES_DEST_DIR]:
            backup = f"{folder}_backup"
            if os.path.exists(backup):
                shutil.rmtree(backup)
                
    except Exception as e:
        logging.error(f"Shapefile update failed! Reverting to backups. Error: {e}", exc_info=True)
        # Revert folders from backups if error occurred
        for folder in [ADDRESS_DEST_DIR, ZONES_DEST_DIR]:
            backup = f"{folder}_backup"
            if os.path.exists(backup):
                if os.path.exists(folder):
                    shutil.rmtree(folder)
                shutil.copytree(backup, folder)
                shutil.rmtree(backup)
                logging.info(f"Reverted {folder} from backup.")
                
    # 2. Update fire hydrants database (independent of shapefile status)
    try:
        update_hydrant_data()
    except Exception as e:
        logging.error(f"Fire hydrant database update failed. Error: {e}", exc_info=True)
        
    finally:
        # Clean up temp downloads directory
        if os.path.exists(TEMP_DIR):
            try:
                shutil.rmtree(TEMP_DIR)
            except Exception:
                pass
        logging.info("=== GIS Update Process Complete ===")

if __name__ == "__main__":
    main()
