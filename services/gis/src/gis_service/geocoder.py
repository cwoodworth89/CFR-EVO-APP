# NOTE: For shapefile details, offline geocoding layouts, and zone boundaries details, see docs/gis_endpoints.md
import re
import logging
import geopandas as gpd
from shapely.geometry import Point
from thefuzz import fuzz
from typing import List, Tuple

from gis_service.shapefile_loader import load_addresses, load_zones

class CoquitlamDataValidator:
    def __init__(self, 
                 address_shp_path: str, 
                 zones_shp_path: str,
                 house_num_col: str = "HOUSE",
                 street_name_col: str = "STREET",
                 street_type_col: str = "STREETTYPE",
                 full_addr_col: str = "ADDRESS",
                 zone_map_name_col: str = "MAP_NAME",
                 street_confidence_threshold: int = 80):
        
        self.house_num_col = house_num_col
        self.street_name_col = street_name_col
        self.street_type_col = street_type_col
        self.full_addr_col = full_addr_col
        self.zone_map_name_col = zone_map_name_col
        self.street_confidence_threshold = street_confidence_threshold
        
        self.addresses_gdf, self.house_number_index = load_addresses(
            address_shp_path, house_num_col, street_name_col, street_type_col
        )
        self.zones_gdf, self.zones_crs, self.zones_sindex = load_zones(zones_shp_path)

    def validate_address_exists(self, parsed_address: str) -> Tuple[int, str | None]:
        """Surgically checks if a parsed address exists in our local GIS database."""
        if self.addresses_gdf is None or not parsed_address:
            return 0, None

        # Manual geocoding override for 3080 Gordon Ave
        clean_address = parsed_address.split(',')[0].strip().upper()
        if clean_address == "3080 GORDON AVE":
            return 100, "3080 GORDON AVE"
            
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
            db_full_street = f"{row[self.street_name_col]} {row[self.street_type_col]}".upper()
            score = fuzz.token_set_ratio(parsed_street, db_full_street.strip())
            if score > best_score:
                best_score = score
                # Construct a clean address string without database suite/unit numbers
                st_type = row[self.street_type_col] or ""
                best_match_full_address = f"{parsed_num} {row[self.street_name_col]} {st_type}".strip().title()
                
        logging.debug(f"GIS Lookup for '{parsed_address}': Best street match score = {best_score}%")
        if best_score >= self.street_confidence_threshold:
            return best_score, best_match_full_address
        return best_score, None

    def local_geocode(self, parsed_address: str) -> dict | None:
        """
        Geocodes address string locally, converting parcel shape to WGS84 coordinates
        and extracting boundary rings. Returns None if unresolvable.
        """
        if self.addresses_gdf is None or not parsed_address:
            return None

        # Manual geocoding override for 3080 Gordon Ave
        clean_address = parsed_address.split(',')[0].strip().upper()
        if clean_address == "3080 GORDON AVE":
            res = self.local_geocode("3030 GORDON AVE")
            if res:
                res["address"] = "3080 GORDON AVE"
                return res
            
        if " and " in parsed_address.lower() and not re.match(r'^\d+', parsed_address):
            return None
            
        match = re.search(r'^(?P<number>\d+)\s+(?P<street>.*)', parsed_address.split(',')[0].strip())
        if not match:
            return None
            
        parsed_num, parsed_street_raw = match.group('number'), match.group('street').strip()
        # Clean unit/suite numbers (e.g. "number 105", "unit B") to ensure parcel match
        parsed_street_raw = re.sub(r'\b(number|num|unit|suite|apt|apartment|#)\s+\w+\b.*', '', parsed_street_raw, flags=re.IGNORECASE).strip()
        
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
            db_full_street = f"{row[self.street_name_col]} {row[self.street_type_col]}".upper().strip()
            score = fuzz.token_set_ratio(parsed_street, db_full_street)
            if score > best_score:
                best_score = score
                best_row = row
                
        if best_score >= self.street_confidence_threshold and best_row is not None:
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
                    "address": best_row[self.full_addr_col],
                    "lat": centroid.y,
                    "lng": centroid.x,
                    "rings": rings,
                    "confidence": best_score
                }
            except Exception as e:
                logging.error(f"Error transforming coordinates for local geocode: {e}", exc_info=True)
                return None
                
        # Fallback to Street Centroid if no exact address is found
        try:
            street_matches = self.addresses_gdf[
                (self.addresses_gdf[self.street_name_col].astype(str).str.upper() == street_name_raw.upper()) &
                (self.addresses_gdf[self.street_type_col].astype(str).str.upper() == norm_type.upper())
            ]
            if not street_matches.empty:
                centroids = street_matches.geometry.centroid
                mean_x = centroids.x.mean()
                mean_y = centroids.y.mean()
                from shapely.geometry import Point
                centroid_proj = Point(mean_x, mean_y)
                point_gdf = gpd.GeoDataFrame([{'geometry': centroid_proj}], crs=self.addresses_gdf.crs)
                point_wgs84 = point_gdf.to_crs("EPSG:4326").geometry.iloc[0]
                logging.info(f"Local geocode exact match failed for '{parsed_address}'. Fell back to street centroid: Lat {point_wgs84.y:.6f}, Lng {point_wgs84.x:.6f}")
                return {
                    "address": f"{parsed_num} {parsed_street_raw} (Street Centroid)",
                    "lat": point_wgs84.y,
                    "lng": point_wgs84.x,
                    "rings": [],
                    "confidence": 60.0
                }
        except Exception as e:
            logging.warning(f"Error computing fallback street centroid for '{parsed_address}': {e}")
            
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
            target_zone = possible_matches[possible_matches[self.zone_map_name_col] == grid_id]
            
            if target_zone.empty:
                return False
            return target_zone.geometry.contains(point_geom).any()
        except Exception as e:
            logging.error(f"Point-in-grid validation error: {e}", exc_info=True)
            return False
