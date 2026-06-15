# NOTE: For information about the source shapefile downloads, paths, and metadata, see docs/gis_endpoints.md
import geopandas as gpd
import logging

def load_addresses(address_shp_path: str, house_num_col: str, street_name_col: str, street_type_col: str) -> tuple[gpd.GeoDataFrame | None, dict]:
    try:
        logging.info(f"Loading Coquitlam address data from: {address_shp_path} (using pyogrio engine)")
        addresses_gdf = gpd.read_file(address_shp_path, engine="pyogrio")
        
        # Normalize shapefile fields
        addresses_gdf[house_num_col] = addresses_gdf[house_num_col].astype(str).str.strip()
        addresses_gdf[street_name_col] = addresses_gdf[street_name_col].astype(str).str.strip()
        addresses_gdf[street_type_col] = addresses_gdf[street_type_col].astype(str).str.strip()
        
        # Build fast in-memory lookup index
        logging.info("Indexing address points into fast lookup dictionary...")
        house_number_index = {}
        for _, row in addresses_gdf.iterrows():
            house_num = row[house_num_col]
            if house_num not in house_number_index:
                house_number_index[house_num] = []
            house_number_index[house_num].append(row)
            
        logging.info(f"Successfully loaded and indexed {len(addresses_gdf)} Coquitlam addresses.")
        return addresses_gdf, house_number_index
    except Exception as e:
        logging.error(f"FATAL: Could not load or process Coquitlam address Shapefile: {e}", exc_info=True)
        return None, {}

def load_zones(zones_shp_path: str) -> tuple[gpd.GeoDataFrame | None, any, any]:
    try:
        logging.info(f"Loading Coquitlam emergency response zones from: {zones_shp_path} (using pyogrio engine)")
        zones_gdf = gpd.read_file(zones_shp_path, engine="pyogrio")
        zones_crs = zones_gdf.crs
        zones_sindex = zones_gdf.sindex
        logging.info(f"Successfully loaded {len(zones_gdf)} Coquitlam emergency zones.")
        return zones_gdf, zones_crs, zones_sindex
    except Exception as e:
        logging.error(f"FATAL: Could not load Coquitlam emergency zones Shapefile: {e}", exc_info=True)
        return None, None, None
