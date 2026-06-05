# cfr_dispatch/gis.py
# GIS Shapefile parser, coordinates re-projector, and spatial grid validator

import re
import logging
import geopandas as gpd
from shapely.geometry import Point
from thefuzz import fuzz

from cfr_dispatch.config import (
    ADDRESS_HOUSE_NUM_COLUMN,
    ADDRESS_STREET_NAME_COLUMN,
    ADDRESS_STREET_TYPE_COLUMN,
    ADDRESS_FULL_ADDR_COLUMN,
    STREET_NAME_CONFIDENCE_THRESHOLD,
    ZONES_MAP_NAME_COLUMN
)

class CoquitlamDataValidator:
    def __init__(self, address_shp_path: str, zones_shp_path: str):
        self.addresses_gdf = None
        self.zones_gdf = None
        self.zones_crs = None
        self.zones_sindex = None
        self.house_number_index = {} # O(1) startup index
        
        self._load_data(address_shp_path, zones_shp_path)

    def _load_data(self, address_shp_path: str, zones_shp_path: str):
        # 1. Load Address Shapefiles
        try:
            logging.info(f"Loading Coquitlam address data from: {address_shp_path} (using pyogrio engine)")
            self.addresses_gdf = gpd.read_file(address_shp_path, engine="pyogrio")
            
            # Normalize shapefile fields
            self.addresses_gdf[ADDRESS_HOUSE_NUM_COLUMN] = self.addresses_gdf[ADDRESS_HOUSE_NUM_COLUMN].astype(str).str.strip()
            self.addresses_gdf[ADDRESS_STREET_NAME_COLUMN] = self.addresses_gdf[ADDRESS_STREET_NAME_COLUMN].astype(str).str.strip()
            self.addresses_gdf[ADDRESS_STREET_TYPE_COLUMN] = self.addresses_gdf[ADDRESS_STREET_TYPE_COLUMN].astype(str).str.strip()
            
            # Build fast in-memory lookups
            logging.info("Indexing address points into fast lookup dictionary...")
            self.house_number_index = {}
            for _, row in self.addresses_gdf.iterrows():
                house_num = row[ADDRESS_HOUSE_NUM_COLUMN]
                if house_num not in self.house_number_index:
                    self.house_number_index[house_num] = []
                self.house_number_index[house_num].append(row)
                
            logging.info(f"Successfully loaded and indexed {len(self.addresses_gdf)} Coquitlam addresses.")
        except Exception as e:
            logging.error(f"FATAL: Could not load or process Coquitlam address Shapefile: {e}", exc_info=True)
            self.addresses_gdf = None

        # 2. Load Zone Shapefiles
        try:
            logging.info(f"Loading Coquitlam emergency response zones from: {zones_shp_path} (using pyogrio engine)")
            self.zones_gdf = gpd.read_file(zones_shp_path, engine="pyogrio")
            self.zones_crs = self.zones_gdf.crs
            
            logging.info("Building spatial index for emergency zones...")
            self.zones_sindex = self.zones_gdf.sindex
            logging.info(f"Successfully loaded {len(self.zones_gdf)} Coquitlam emergency zones.")
        except Exception as e:
            logging.error(f"FATAL: Could not load Coquitlam emergency zones Shapefile: {e}", exc_info=True)
            self.zones_gdf = None

    def validate_address_exists(self, parsed_address: str) -> tuple[int, str | None]:
        """Surgically checks if a parsed address exists in our local GIS database."""
        if self.addresses_gdf is None or not parsed_address:
            return 0, None
            
        if " and " in parsed_address.lower() and not re.match(r'^\d+', parsed_address):
            return 100, parsed_address
            
        match = re.search(r'^(?P<number>\d+)\s+(?P<street>.*)', parsed_address.split(',')[0].strip())
        if not match:
            return 0, None
            
        parsed_num, parsed_street = match.group('number'), match.group('street').upper()
        
        # O(1) Dictionary Lookup
        possible_matches = self.house_number_index.get(parsed_num, [])
        if not possible_matches:
            return 0, None
            
        best_score = 0
        best_match_full_address = None
        for row in possible_matches:
            db_full_street = f"{row[ADDRESS_STREET_NAME_COLUMN]} {row[ADDRESS_STREET_TYPE_COLUMN]}".upper()
            score = fuzz.token_set_ratio(parsed_street, db_full_street.strip())
            if score > best_score:
                best_score = score
                best_match_full_address = row[ADDRESS_FULL_ADDR_COLUMN]
                
        logging.debug(f"GIS Lookup for '{parsed_address}': Best street match score = {best_score}%")
        if best_score >= STREET_NAME_CONFIDENCE_THRESHOLD:
            return best_score, best_match_full_address
        return best_score, None

    def local_geocode(self, parsed_address: str) -> dict | None:
        """
        Geocodes address string locally, converting parcel shape to WGS84 coordinates
        and extracting boundary rings. Returns None if unresolvable.
        """
        if self.addresses_gdf is None or not parsed_address:
            return None
            
        if " and " in parsed_address.lower() and not re.match(r'^\d+', parsed_address):
            return None
            
        match = re.search(r'^(?P<number>\d+)\s+(?P<street>.*)', parsed_address.split(',')[0].strip())
        if not match:
            return None
            
        parsed_num, parsed_street_raw = match.group('number'), match.group('street').strip()
        
        # Normalize suffix to map indices
        words = parsed_street_raw.split()
        if len(words) >= 1:
            street_type_raw = words[-1]
            street_name_raw = " ".join(words[:-1])
            type_mapping = {
                "crescent": "cres", "highway": "hwy", "street": "st",
                "avenue": "ave", "court": "crt", "place": "pl",
                "drive": "dr", "boulevard": "blvd", "lane": "ln", "road": "rd"
            }
            norm_type = type_mapping.get(street_type_raw.lower(), street_type_raw).upper()
            parsed_street = f"{street_name_raw} {norm_type}".upper().strip()
        else:
            parsed_street = parsed_street_raw.upper().strip()
            
        # O(1) Dictionary Lookup
        possible_matches = self.house_number_index.get(parsed_num, [])
        if not possible_matches:
            return None
            
        best_score = 0
        best_row = None
        for row in possible_matches:
            db_full_street = f"{row[ADDRESS_STREET_NAME_COLUMN]} {row[ADDRESS_STREET_TYPE_COLUMN]}".upper().strip()
            score = fuzz.token_set_ratio(parsed_street, db_full_street)
            if score > best_score:
                best_score = score
                best_row = row
                
        if best_score >= STREET_NAME_CONFIDENCE_THRESHOLD and best_row is not None:
            try:
                # Convert geometry to WGS84 (EPSG:4326)
                geom_gdf = gpd.GeoDataFrame([best_row], crs=self.addresses_gdf.crs)
                geom_gdf_wgs84 = geom_gdf.to_crs("EPSG:4326")
                matched_geom = geom_gdf_wgs84.geometry.iloc[0]
                centroid = matched_geom.centroid
                
                rings = []
                def extract_rings(geometry) -> list:
                    r = []
                    if geometry.geom_type == 'Polygon':
                        exterior = [[coord[0], coord[1]] for coord in geometry.exterior.coords]
                        r.append(exterior)
                        for interior in geometry.interiors:
                            r.append([[coord[0], coord[1]] for coord in interior.coords])
                    elif geometry.geom_type == 'MultiPolygon':
                        for polygon in geometry.geoms:
                            r.extend(extract_rings(polygon))
                    return r
                    
                rings = extract_rings(matched_geom)
                return {
                    "address": best_row[ADDRESS_FULL_ADDR_COLUMN],
                    "lat": centroid.y,
                    "lng": centroid.x,
                    "rings": rings,
                    "confidence": best_score
                }
            except Exception as e:
                logging.error(f"Error transforming coordinates for local geocode: {e}", exc_info=True)
                return None
        return None

    def validate_point_in_grid(self, lat: float, lon: float, grid_id: str) -> bool:
        """Determines if a given coordinate lies within the boundaries of a specific response grid map."""
        if self.zones_gdf is None or self.zones_sindex is None or not grid_id or lat is None or lon is None:
            return False
        try:
            point = Point(lon, lat)
            point_gdf = gpd.GeoDataFrame([{'geometry': point}], crs="EPSG:4326").to_crs(self.zones_crs)
            point_geom = point_gdf.geometry.iloc[0]
            possible_matches_idx = list(self.zones_sindex.intersection(point_geom.bounds))
            possible_matches = self.zones_gdf.iloc[possible_matches_idx]
            target_zone = possible_matches[possible_matches[ZONES_MAP_NAME_COLUMN] == grid_id]
            
            if target_zone.empty:
                return False
            return target_zone.geometry.contains(point_geom).any()
        except Exception as e:
            logging.error(f"Point-in-grid validation error: {e}", exc_info=True)
            return False
