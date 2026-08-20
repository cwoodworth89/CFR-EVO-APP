# NOTE: For shapefile details, offline geocoding layouts, and zone boundaries details, see docs/gis_endpoints.md
import os
import re
import json
import logging
from typing import List, Tuple, Any

try:
    import geopandas as gpd
    from shapely.geometry import Point
except ImportError:
    gpd = None
    Point = None

try:
    from thefuzz import fuzz
except ImportError:
    import difflib
    class _Fuzz:
        @staticmethod
        def token_set_ratio(s1, s2):
            return int(difflib.SequenceMatcher(None, str(s1).lower(), str(s2).lower()).ratio() * 100)
    fuzz = _Fuzz()

try:
    from gis_service.shapefile_loader import load_addresses, load_zones
except (ImportError, ModuleNotFoundError):
    def load_addresses(*args, **kwargs):
        return None, {}
    def load_zones(*args, **kwargs):
        return None, None, None

SUFFIX_MAPPINGS = {
    "AVENUE": "AVE", "AVE": "AVE",
    "STREET": "ST", "ST": "ST",
    "ROAD": "RD", "RD": "RD",
    "DRIVE": "DR", "DR": "DR",
    "BOULEVARD": "BLVD", "BLVD": "BLVD",
    "HIGHWAY": "HWY", "HWY": "HWY",
    "WAY": "WAY",
    "CRESCENT": "CRES", "CRES": "CRES",
    "COURT": "CRT", "CRT": "CRT",
    "PLACE": "PL", "PL": "PL",
    "LANE": "LN", "LN": "LN",
    "PROMENADE": "PROM", "PROM": "PROM",
    "RAMP": "RAMP",
    "ALLEY": "ALLEY",
}

INTERSECTION_SPLIT_REGEX = re.compile(
    r'\s+(?:and|&|/|near|at|@)\s+|\s*[/&@]\s*',
    re.IGNORECASE
)

def normalize_street_name(name: str) -> str:
    """Normalizes street name suffix to municipal abbreviation."""
    if not name:
        return ""
    clean = re.sub(r'[,.]', '', name.strip()).upper()
    clean = re.sub(r'\b(?:BLOCK|BLK|OF)\b', '', clean).strip()
    words = clean.split()
    if not words:
        return ""
    if len(words) > 1 and words[-1] in SUFFIX_MAPPINGS:
        words[-1] = SUFFIX_MAPPINGS[words[-1]]
    return " ".join(words)

def normalize_intersection_key(street1: str, street2: str) -> str:
    """Forms a canonical, alphabetically sorted intersection key."""
    s1 = normalize_street_name(street1)
    s2 = normalize_street_name(street2)
    streets = sorted([s1, s2])
    return f"{streets[0]} & {streets[1]}"

def split_intersection_parts(address_str: str) -> Tuple[str, str] | None:
    """Detects and extracts the two street components from an intersection query."""
    if not address_str:
        return None
    clean_addr = address_str.split(',')[0].strip()
    if not re.search(r'\b(?:and|&|/|near|at|@)\b', clean_addr, re.IGNORECASE) and not any(c in clean_addr for c in ['&', '/', '@']):
        return None
    parts = INTERSECTION_SPLIT_REGEX.split(clean_addr)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None


class CoquitlamDataValidator:
    def __init__(self, 
                 address_shp_path: str = None, 
                 zones_shp_path: str = None,
                 house_num_col: str = "HOUSE",
                 street_name_col: str = "STREET",
                 street_type_col: str = "STREETTYPE",
                 full_addr_col: str = "ADDRESS",
                 zone_map_name_col: str = "MAP_NAME",
                 street_confidence_threshold: int = 80,
                 intersections_json_path: str = None):
        
        self.house_num_col = house_num_col
        self.street_name_col = street_name_col
        self.street_type_col = street_type_col
        self.full_addr_col = full_addr_col
        self.zone_map_name_col = zone_map_name_col
        self.street_confidence_threshold = street_confidence_threshold
        
        self.addresses_gdf, self.house_number_index = load_addresses(
            address_shp_path, house_num_col, street_name_col, street_type_col
        ) if address_shp_path else (None, {})
        self.zones_gdf, self.zones_crs, self.zones_sindex = load_zones(zones_shp_path) if zones_shp_path else (None, None, None)

        # Pre-compute spatial grid-to-streets index for fast low-confidence disambiguation
        self.grid_to_streets = {}
        try:
            if self.addresses_gdf is not None and self.zones_gdf is not None and gpd is not None:
                zones_matching = self.zones_gdf.to_crs(self.addresses_gdf.crs) if self.addresses_gdf.crs != self.zones_crs else self.zones_gdf
                joined = gpd.sjoin(self.addresses_gdf, zones_matching[[self.zone_map_name_col, 'geometry']], how="inner", predicate="within")
                for grid_id, group in joined.groupby(self.zone_map_name_col):
                    grid_key = str(grid_id).strip()
                    streets = set(group[self.street_name_col].fillna('').astype(str).str.upper().unique()) - {''}
                    self.grid_to_streets[grid_key] = streets
                logging.info(f"Pre-computed spatial street indexes for {len(self.grid_to_streets)} emergency response grids.")
        except Exception as e:
            logging.error(f"Failed to pre-compute spatial grid-to-street index: {e}")

        # Load landmarks configuration if it exists
        self.landmarks = {}
        try:
            landmarks_path = None
            if address_shp_path:
                cand_landmarks = os.path.join(os.path.dirname(os.path.dirname(address_shp_path)), "vocabulary", "landmarks.json")
                if os.path.exists(cand_landmarks):
                    landmarks_path = cand_landmarks
            if not landmarks_path:
                defaults = [
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../backend/data/vocabulary/landmarks.json")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../backend/data/vocabulary/landmarks.json")),
                    os.path.abspath(os.path.join(os.getcwd(), "backend/data/vocabulary/landmarks.json")),
                ]
                for p in defaults:
                    if os.path.exists(p):
                        landmarks_path = p
                        break
            if landmarks_path and os.path.exists(landmarks_path):
                with open(landmarks_path, 'r', encoding='utf-8') as f:
                    self.landmarks = json.load(f)
                logging.info(f"Loaded {len(self.landmarks)} landmarks from {landmarks_path}")
        except Exception as e:
            logging.error(f"Failed to load landmarks.json: {e}")

        # Load authoritative intersections dataset
        self.intersections = {}
        self.intersections_index = {}
        try:
            intersections_path = intersections_json_path
            if not intersections_path and address_shp_path:
                cand_gis = os.path.join(os.path.dirname(os.path.dirname(address_shp_path)), "gis", "intersections.json")
                if os.path.exists(cand_gis):
                    intersections_path = cand_gis
                else:
                    cand_vocab = os.path.join(os.path.dirname(os.path.dirname(address_shp_path)), "vocabulary", "intersections.json")
                    if os.path.exists(cand_vocab):
                        intersections_path = cand_vocab
            if not intersections_path:
                defaults = [
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../backend/data/gis/intersections.json")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../backend/data/gis/intersections.json")),
                    os.path.abspath(os.path.join(os.getcwd(), "backend/data/gis/intersections.json")),
                    os.path.abspath(os.path.join(os.getcwd(), "frontend/public/data/intersections.json")),
                ]
                for p in defaults:
                    if os.path.exists(p):
                        intersections_path = p
                        break
            if intersections_path and os.path.exists(intersections_path):
                with open(intersections_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                self._build_intersections_index(raw_data)
                logging.info(f"Loaded {len(self.intersections_index)} unique intersection keys from {intersections_path}")
        except Exception as e:
            logging.error(f"Failed to load intersections.json: {e}")

    def _build_intersections_index(self, raw_data: dict | list):
        """Builds an O(1) normalized index where keys are sorted alphabetically."""
        self.intersections_index = {}
        if isinstance(raw_data, dict):
            for raw_key, candidates in raw_data.items():
                cand_list = candidates if isinstance(candidates, list) else [candidates]
                parts = split_intersection_parts(raw_key)
                if parts:
                    norm_key = normalize_intersection_key(parts[0], parts[1])
                else:
                    norm_key = raw_key.strip().upper()

                formatted_cands = []
                for c in cand_list:
                    formatted_cands.append({
                        "name": c.get("name", raw_key),
                        "lat": float(c["lat"]),
                        "lng": float(c["lng"]),
                        "grid": str(c.get("grid", "")).strip() if c.get("grid") is not None else None,
                        "description": c.get("description", "")
                    })
                self.intersections_index[norm_key] = formatted_cands

        elif isinstance(raw_data, list):
            for item in raw_data:
                name = item.get("name", "")
                parts = split_intersection_parts(name)
                if parts:
                    norm_key = normalize_intersection_key(parts[0], parts[1])
                else:
                    norm_key = name.strip().upper()

                cand = {
                    "name": name,
                    "lat": float(item["lat"]),
                    "lng": float(item["lng"]),
                    "grid": str(item.get("grid", "")).strip() if item.get("grid") is not None else None,
                    "description": item.get("description", "")
                }
                if norm_key not in self.intersections_index:
                    self.intersections_index[norm_key] = []
                self.intersections_index[norm_key].append(cand)

    def _lookup_intersection(self, parsed_address: str) -> Tuple[List[dict] | None, int]:
        """
        Parses intersection address and looks up candidates in normalized index.
        Returns (candidates, score).
        """
        if not self.intersections_index:
            return None, 0
        parts = split_intersection_parts(parsed_address)
        if not parts:
            return None, 0
        s1, s2 = parts
        norm_key = normalize_intersection_key(s1, s2)
        
        # 1. Exact match
        if norm_key in self.intersections_index:
            return self.intersections_index[norm_key], 100
        
        # 2. Road type alias match (e.g. RD <-> AVE)
        alias_replacements = [
            (" RD", " AVE"), (" AVE", " RD"),
            (" ST", " WAY"), (" WAY", " ST"),
            (" BLVD", " DR"), (" DR", " BLVD")
        ]
        for src, target in alias_replacements:
            if src in norm_key:
                alt_key = norm_key.replace(src, target)
                if alt_key in self.intersections_index:
                    return self.intersections_index[alt_key], 95
        
        # 3. Fuzzy matching across keys
        best_score = 0
        best_cands = None
        for key, cands in self.intersections_index.items():
            score = fuzz.token_set_ratio(norm_key, key)
            if score > best_score:
                best_score = score
                best_cands = cands
                
        if best_score >= 80 and best_cands is not None:
            return best_cands, best_score
            
        return None, 0

    def _resolve_candidates(self, candidates: List[dict], target_map_grid: str | int = None) -> dict:
        """
        Disambiguates candidate list using target_map_grid if provided.
        Returns formatted coordinate payload.
        """
        if not candidates:
            return None
            
        if len(candidates) == 1:
            c = candidates[0]
            return {
                "address": c["name"],
                "lat": c["lat"],
                "lng": c["lng"],
                "rings": [],
                "grid": c.get("grid"),
                "is_ambiguous": False,
                "candidates": candidates,
                "confidence": 100.0
            }
            
        # Multiple candidates (e.g., dual-junction corridor)
        if target_map_grid is not None:
            target_grid_clean = re.sub(r'^(?:GRID|ZONE)\s*', '', str(target_map_grid).strip(), flags=re.IGNORECASE)
            for c in candidates:
                cand_grid = str(c.get("grid", "")).strip()
                if cand_grid and cand_grid.lower() == target_grid_clean.lower():
                    return {
                        "address": c["name"],
                        "lat": c["lat"],
                        "lng": c["lng"],
                        "rings": [],
                        "grid": c.get("grid"),
                        "is_ambiguous": False,
                        "candidates": candidates,
                        "confidence": 100.0
                    }
                    
        # No grid or grid unmatched: return primary candidate with is_ambiguous=True
        primary = candidates[0]
        return {
            "address": primary["name"],
            "lat": primary["lat"],
            "lng": primary["lng"],
            "rings": [],
            "grid": primary.get("grid"),
            "is_ambiguous": True,
            "candidates": candidates,
            "confidence": 100.0
        }

    def validate_address_exists(self, parsed_address: str) -> Tuple[int, str | None]:
        """Surgically checks if a parsed address exists in our local GIS database."""
        if not parsed_address:
            return 0, None

        # Check landmarks first (parks, schools, facilities)
        if self.landmarks:
            clean_addr_lower = parsed_address.strip().lower()
            best_l_match = None
            best_l_score = 0
            for name, details in self.landmarks.items():
                score = fuzz.token_set_ratio(clean_addr_lower, name)
                if score > best_l_score:
                    best_l_score = score
                    best_l_match = details
            
            if best_l_score >= 85:
                return best_l_score, best_l_match["address"]

        # Manual geocoding override for 3080 Gordon Ave
        clean_address = parsed_address.split(',')[0].strip().upper()
        if clean_address == "3080 GORDON AVE":
            return 100, "3080 GORDON AVE"

        # Check intersection authority
        cands, score = self._lookup_intersection(parsed_address)
        if cands and score >= self.street_confidence_threshold:
            return score, cands[0]["name"]
        elif split_intersection_parts(parsed_address) is not None:
            # Address was explicitly formatted as an intersection but was not found in municipal registry
            return 0, None

        if self.addresses_gdf is None and not self.house_number_index:
            return 0, None

        match = re.search(r'^(?P<number>\d+)\s+(?P<street>.*)', clean_address)
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

    def get_coordinates(self, parsed_address: str, target_map_grid: str | int = None) -> dict | None:
        """
        Primary geocoding entry point for local parcel address and municipal intersection resolution.
        Converts parsed address string to WGS84 coordinates, boundary rings, and candidate lists.
        Supports multi-junction disambiguation using target_map_grid.
        """
        if not parsed_address:
            return None

        # Check landmarks first (parks, schools, facilities)
        if self.landmarks:
            clean_addr_lower = parsed_address.strip().lower()
            best_l_match = None
            best_l_score = 0
            for name, details in self.landmarks.items():
                score = fuzz.token_set_ratio(clean_addr_lower, name)
                if score > best_l_score:
                    best_l_score = score
                    best_l_match = details
            
            if best_l_score >= 85:
                return {
                    "address": best_l_match["address"],
                    "lat": best_l_match["lat"],
                    "lng": best_l_match["lng"],
                    "rings": [],
                    "confidence": float(best_l_score),
                    "is_ambiguous": False
                }

        # Manual geocoding overrides
        clean_address = parsed_address.split(',')[0].strip().upper()
        if clean_address == "3080 GORDON AVE":
            res = self.get_coordinates("3030 GORDON AVE", target_map_grid=target_map_grid)
            if res:
                res["address"] = "3080 GORDON AVE"
                return res
        if "2900 BARNET" in clean_address:
            return {
                "address": "2900 Barnet Hwy (Coquitlam Central Bus Loop)",
                "lat": 49.2765771,
                "lng": -122.8003925,
                "rings": [],
                "confidence": 100.0,
                "is_ambiguous": False
            }
        if "PORT MANN" in clean_address or "PORTMAN" in clean_address:
            return {
                "address": "Port Mann Bridge, Coquitlam, BC",
                "lat": 49.2237874,
                "lng": -122.8152597,
                "rings": [],
                "confidence": 100.0,
                "is_ambiguous": False
            }
            
        # Manual Riverview Station overrides (e.g. "Station 15", "Station 37", etc.)
        if "RIVERVIEW" in clean_address or "STATION" in clean_address:
            station_match = re.search(r'\bSTATION\s*(\d+)\b', clean_address, re.IGNORECASE)
            if station_match or clean_address in ["BROOKSIDE", "CENTRALE", "CREASE CLINIC"]:
                station_num = station_match.group(1) if station_match else ""
                label = f"Station {station_num}, Riverview Hospital (2601 Lougheed Hwy)" if station_num else f"{clean_address.title()}, Riverview Hospital (2601 Lougheed Hwy)"
                return {
                    "address": label,
                    "lat": 49.245830,
                    "lng": -122.805330,
                    "rings": [],
                    "confidence": 100.0,
                    "is_ambiguous": False
                }

        # Check intersection authority
        cands, score = self._lookup_intersection(parsed_address)
        if cands:
            res = self._resolve_candidates(cands, target_map_grid=target_map_grid)
            if res:
                res["confidence"] = float(score)
                return res
        elif split_intersection_parts(parsed_address) is not None:
            # Address was explicitly an intersection but unresolvable in local registry
            return None

        if self.addresses_gdf is None and not self.house_number_index:
            return None

        match = re.search(r'^(?P<number>\d+)\s+(?P<street>.*)', clean_address)
        if not match:
            return None
            
        parsed_num, parsed_street_raw = match.group('number'), match.group('street').strip()
        # Clean unit/suite numbers (e.g. "number 105", "unit B") to ensure parcel match
        parsed_street_raw = re.sub(r'\b(number|num|unit|suite|apt|apartment|#)\s+\w+\b.*', '', parsed_street_raw, flags=re.IGNORECASE).strip()
        
        # Clean block designations (e.g. "1080 block ponderosa street" or "1000 blk of ponderosa")
        parsed_street_raw = re.sub(r'\b(block|blk|of)\b', '', parsed_street_raw, flags=re.IGNORECASE).strip()
        parsed_street_raw = " ".join(parsed_street_raw.split())
        
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
            norm_type = ""
            street_name_raw = parsed_street_raw
            
        # O(1) Dictionary Lookup
        possible_matches = self.house_number_index.get(parsed_num, [])
        best_score = 0
        best_row = None
        
        if possible_matches:
            for row in possible_matches:
                db_full_street = f"{row[self.street_name_col]} {row[self.street_type_col]}".upper().strip()
                score = fuzz.token_set_ratio(parsed_street, db_full_street)
                if score > best_score:
                    best_score = score
                    best_row = row
                
        if best_score >= self.street_confidence_threshold and best_row is not None and gpd is not None and self.addresses_gdf is not None:
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
                
                street_type_val = best_row[self.street_type_col]
                if street_type_val:
                    clean_addr_val = f"{best_row[self.house_num_col]} {best_row[self.street_name_col]} {street_type_val}"
                else:
                    clean_addr_val = f"{best_row[self.house_num_col]} {best_row[self.street_name_col]}"
                
                clean_addr_val = " ".join(clean_addr_val.strip().split()).title()
                try:
                    from cfr_dispatch.parser import normalize_street_suffix
                    clean_addr_val = normalize_street_suffix(clean_addr_val)
                except Exception:
                    pass

                return {
                    "address": clean_addr_val,
                    "lat": centroid.y,
                    "lng": centroid.x,
                    "rings": rings,
                    "confidence": best_score,
                    "is_ambiguous": False
                }
            except Exception as e:
                logging.error(f"Error transforming coordinates for local geocode: {e}", exc_info=True)
                return None
                
        # Fallback to Street Centroid if no exact address is found
        try:
            if self.addresses_gdf is not None and gpd is not None:
                street_matches = self.addresses_gdf[
                    (self.addresses_gdf[self.street_name_col].astype(str).str.upper() == street_name_raw.upper()) &
                    (self.addresses_gdf[self.street_type_col].astype(str).str.upper() == norm_type.upper())
                ]
                if not street_matches.empty:
                    centroids = street_matches.geometry.centroid
                    mean_x = centroids.x.mean()
                    mean_y = centroids.y.mean()
                    centroid_proj = Point(mean_x, mean_y)
                    point_gdf = gpd.GeoDataFrame([{'geometry': centroid_proj}], crs=self.addresses_gdf.crs)
                    point_wgs84 = point_gdf.to_crs("EPSG:4326").geometry.iloc[0]
                    logging.info(f"Local geocode exact match failed for '{parsed_address}'. Fell back to street centroid: Lat {point_wgs84.y:.6f}, Lng {point_wgs84.x:.6f}")
                    return {
                        "address": f"{parsed_num} {parsed_street_raw}".strip(),
                        "lat": point_wgs84.y,
                        "lng": point_wgs84.x,
                        "rings": [],
                        "confidence": 60.0,
                        "is_street_centroid": True,
                        "is_ambiguous": False
                    }
        except Exception as e:
            logging.warning(f"Error computing fallback street centroid for '{parsed_address}': {e}")
            
        return None

    def local_geocode(self, parsed_address: str, target_map_grid: str | int = None) -> dict | None:
        """Geocodes address locally; alias for get_coordinates."""
        return self.get_coordinates(parsed_address, target_map_grid=target_map_grid)

    def validate_point_in_grid(self, lat: float, lon: float, grid_id: str) -> bool:
        """Determines if a given coordinate lies within the boundaries of a specific response grid map."""
        if self.zones_gdf is None or self.zones_sindex is None or not grid_id or lat is None or lon is None or Point is None:
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

    def get_map_grid_for_point(self, lat: float, lon: float) -> str | None:
        """Looks up the emergency response map grid ID containing the given lat/lon coordinates."""
        if self.zones_gdf is None or self.zones_sindex is None or lat is None or lon is None or Point is None:
            return None
        try:
            point = Point(lon, lat)
            point_gdf = gpd.GeoDataFrame([{'geometry': point}], crs="EPSG:4326").to_crs(self.zones_crs)
            point_geom = point_gdf.geometry.iloc[0]
            possible_matches_idx = list(self.zones_sindex.intersection(point_geom.bounds))
            possible_matches = self.zones_gdf.iloc[possible_matches_idx]
            match = possible_matches[possible_matches.geometry.contains(point_geom)]
            if not match.empty:
                grid_id = str(match.iloc[0][self.zone_map_name_col]).strip()
                return grid_id
            return None
        except Exception as e:
            logging.error(f"Point-to-grid spatial lookup error: {e}", exc_info=True)
            return None

    def get_streets_in_grid(self, grid_id: str) -> List[str]:
        """Returns the list of unique street names contained within a specific map grid."""
        if not grid_id:
            return []
        grid_key = str(grid_id).strip()
        return sorted(list(self.grid_to_streets.get(grid_key, [])))

