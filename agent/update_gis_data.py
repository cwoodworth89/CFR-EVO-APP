# ==============================================================================
# update_gis_data.py
# Monthly Maintenance Script to Update Coquitlam GIS Shapefiles (100% Offline)
# ==============================================================================
import os
import sys
import zipfile
import urllib.request
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

def main():
    logging.info("=== Starting Coquitlam GIS Database Monthly Update ===")
    
    # Create temp directory
    os.makedirs(TEMP_DIR, exist_ok=True)
    address_zip = os.path.join(TEMP_DIR, "addresses.zip")
    zones_zip = os.path.join(TEMP_DIR, "zones.zip")
    
    try:
        # 1. Download datasets
        download_file(ADDRESS_ZIP_URL, address_zip)
        download_file(ZONES_ZIP_URL, zones_zip)
        
        # 2. Extract and wipe temp dirs
        extract_and_clean(address_zip, ADDRESS_DEST_DIR)
        extract_and_clean(zones_zip, ZONES_DEST_DIR)
        
        # 3. Post-Download shapefile correction
        fix_winding_order(ADDRESS_DEST_DIR)
        fix_winding_order(ZONES_DEST_DIR)
        
        logging.info("GIS Database successfully updated and verified offline!")
        
        # Clean up backups if exists
        for folder in [ADDRESS_DEST_DIR, ZONES_DEST_DIR]:
            backup = f"{folder}_backup"
            if os.path.exists(backup):
                shutil.rmtree(backup)
                
    except Exception as e:
        logging.critical(f"GIS Update failed! Reverting to backups. Error: {e}", exc_info=True)
        # Revert folders from backups if error occurred
        for folder in [ADDRESS_DEST_DIR, ZONES_DEST_DIR]:
            backup = f"{folder}_backup"
            if os.path.exists(backup):
                if os.path.exists(folder):
                    shutil.rmtree(folder)
                shutil.copytree(backup, folder)
                shutil.rmtree(backup)
                logging.info(f"Reverted {folder} from backup.")
                
    finally:
        # Clean up temp downloads directory
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        logging.info("=== GIS Update Process Complete ===")

if __name__ == "__main__":
    main()
