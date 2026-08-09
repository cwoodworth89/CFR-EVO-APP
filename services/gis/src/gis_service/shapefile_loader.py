import geopandas as gpd
import logging

# GIS Domain Default Column Names
DEFAULT_ADDRESS_COLUMN = "ADDRESS"
DEFAULT_HOUSE_NUM_COLUMN = "HOUSE"
DEFAULT_STREET_NAME_COLUMN = "STREET"
DEFAULT_STREET_TYPE_COLUMN = "STREETTYPE"
DEFAULT_ZONE_MAP_NAME_COLUMN = "MAP_NAME"

def load_addresses(address_shp_path: str, house_num_col: str = DEFAULT_HOUSE_NUM_COLUMN, street_name_col: str = DEFAULT_STREET_NAME_COLUMN, street_type_col: str = DEFAULT_STREET_TYPE_COLUMN) -> tuple[gpd.GeoDataFrame | None, dict]:
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
        records = addresses_gdf[[house_num_col, street_name_col, street_type_col, 'geometry']].to_dict('records')
        for rec in records:
            house_num = rec[house_num_col]
            if house_num not in house_number_index:
                house_number_index[house_num] = []
            house_number_index[house_num].append(rec)
            
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
