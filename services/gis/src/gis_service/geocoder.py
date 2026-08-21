"""
services/gis/src/gis_service/geocoder.py
PostGIS-backed Address Geocoder and Spatial Validation Engine for CFR EVO.

Replaces GeoPandas shapefile loading with high-performance PostgreSQL/PostGIS queries.
Pre-caches small lookup tables (road names, landmarks, topological intersections)
and performs spatial queries for parcel addresses, zone lookups, boundary checks,
and road network metadata.
"""

import os
import re
import json
import logging
from typing import List, Tuple, Optional, Any

from sqlalchemy import create_engine, text

try:
    from thefuzz import fuzz
except ImportError:
    import difflib
    class _Fuzz:
        @staticmethod
        def token_set_ratio(s1, s2):
            return int(difflib.SequenceMatcher(None, str(s1).lower(), str(s2).lower()).ratio() * 100)
    fuzz = _Fuzz()

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
    """
    Authoritative Municipal Geocoder and Spatial Validation Engine.
    Queries containerized PostgreSQL 16 / PostGIS for parcels, intersections,
    emergency response zones, and city boundary containment.
    """

    def __init__(self, database_url: str = None, *args, **kwargs):
        db_url = database_url
        if not db_url or db_url.endswith('.shp') or db_url.endswith('.json'):
            db_url = os.environ.get('DATABASE_URL', 'postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch')
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        self.engine = create_engine(db_url, pool_size=5, pool_pre_ping=True)
        self.street_confidence_threshold = kwargs.get('street_confidence_threshold', 80)

        # Pre-cache small tables for fuzzy matching and fast lookups
        self._road_names_cache = self._load_road_names()
        self._landmark_cache = self._load_landmarks()
        self._intersection_keys_cache = self._load_intersection_keys()

        # Backward compatibility aliases
        self.landmarks = self._landmark_cache
        self.intersections_index = self._intersection_keys_cache

    def _load_road_names(self) -> List[str]:
        """Loads all road names from public.road_names into memory for fuzzy matching."""
        names = []
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("SELECT road_name FROM public.road_names ORDER BY road_name;")).fetchall()
                names = [r[0] for r in res if r[0]]
            logging.info(f"Loaded {len(names)} road names from PostgreSQL.")
        except Exception as e:
            logging.error(f"Failed to load road names from PostgreSQL: {e}")
        return names

    def _load_landmarks(self) -> dict:
        """Loads all landmarks from public.landmarks into memory for fuzzy matching."""
        landmarks = {}
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT name, name_normalized, address, lat, lng, category, metadata 
                    FROM public.landmarks;
                """)).fetchall()
                for row in res:
                    name, name_norm, address, lat, lng, category, meta = row
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            pass
                    entry = {
                        "name": name,
                        "name_normalized": name_norm or name.upper(),
                        "address": address or name,
                        "lat": float(lat),
                        "lng": float(lng),
                        "category": category,
                        "metadata": meta
                    }
                    landmarks[name.lower().strip()] = entry
                    if name_norm and name_norm.lower() != name.lower():
                        landmarks[name_norm.lower().strip()] = entry
            logging.info(f"Loaded {len(landmarks)} landmarks from PostgreSQL.")
        except Exception as e:
            logging.error(f"Failed to load landmarks from PostgreSQL: {e}")
        return landmarks

    def _load_intersection_keys(self) -> dict:
        """Loads all topological intersections from public.intersections into an O(1) candidate index."""
        index = {}
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT street_a, street_b, intersection_key, lat, lng, zone_id, candidate_index 
                    FROM public.intersections 
                    ORDER BY intersection_key, candidate_index;
                """)).fetchall()
                for row in res:
                    street_a, street_b, raw_key, lat, lng, zone_id, candidate_index = row
                    cand = {
                        "name": f"{street_a} & {street_b}".title(),
                        "lat": float(lat),
                        "lng": float(lng),
                        "grid": str(zone_id).strip() if zone_id is not None else None,
                        "description": f"{street_a} & {street_b}",
                        "candidate_index": int(candidate_index) if candidate_index is not None else 0
                    }
                    norm_key = normalize_intersection_key(street_a, street_b)
                    if norm_key not in index:
                        index[norm_key] = []
                    index[norm_key].append(cand)

                    raw_key_clean = raw_key.strip().upper()
                    if raw_key_clean != norm_key:
                        if raw_key_clean not in index:
                            index[raw_key_clean] = []
                        if cand not in index[raw_key_clean]:
                            index[raw_key_clean].append(cand)
            logging.info(f"Loaded {len(index)} unique intersection keys from PostgreSQL.")
        except Exception as e:
            logging.error(f"Failed to load intersections from PostgreSQL: {e}")
        return index

    def _lookup_intersection(self, parsed_address: str) -> Tuple[List[dict] | None, int]:
        """
        Parses intersection address and looks up candidates in normalized index.
        Returns (candidates, score).
        """
        if not self._intersection_keys_cache:
            return None, 0
        parts = split_intersection_parts(parsed_address)
        if not parts:
            return None, 0
        s1, s2 = parts
        norm_key = normalize_intersection_key(s1, s2)

        # 1. Exact match
        if norm_key in self._intersection_keys_cache:
            return self._intersection_keys_cache[norm_key], 100

        # 2. Road type alias match (e.g. RD <-> AVE)
        alias_replacements = [
            (" RD", " AVE"), (" AVE", " RD"),
            (" ST", " WAY"), (" WAY", " ST"),
            (" BLVD", " DR"), (" DR", " BLVD")
        ]
        for src, target in alias_replacements:
            if src in norm_key:
                alt_key = norm_key.replace(src, target)
                if alt_key in self._intersection_keys_cache:
                    return self._intersection_keys_cache[alt_key], 95

        # 3. Fuzzy matching across keys
        best_score = 0
        best_cands = None
        for key, cands in self._intersection_keys_cache.items():
            score = fuzz.token_set_ratio(norm_key, key)
            if score > best_score:
                best_score = score
                best_cands = cands

        if best_score >= 80 and best_cands is not None:
            return best_cands, best_score

        return None, 0

    def _resolve_candidates(self, candidates: List[dict], target_map_grid: str | int = None) -> dict | None:
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
        """Surgically checks if a parsed address exists in the local GIS database."""
        if not parsed_address:
            return 0, None

        # Check landmarks first (parks, schools, facilities)
        if self._landmark_cache:
            clean_addr_lower = parsed_address.strip().lower()
            best_l_match = None
            best_l_score = 0
            for name, details in self._landmark_cache.items():
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

        match = re.search(r'^(?P<number>\d+)\s+(?P<street>.*)', clean_address)
        if not match:
            return 0, None

        parsed_num, parsed_street_raw = match.group('number'), match.group('street').strip()
        parsed_street_raw = re.sub(r'\b(number|num|unit|suite|apt|apartment|#)\s+\w+\b.*', '', parsed_street_raw, flags=re.IGNORECASE).strip()
        parsed_street_raw = re.sub(r'\b(block|blk|of)\b', '', parsed_street_raw, flags=re.IGNORECASE).strip()
        parsed_street = normalize_street_name(parsed_street_raw)

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT house, street, streettype, address 
                    FROM public.parcels 
                    WHERE house = :house;
                """), {"house": parsed_num}).mappings().fetchall()

                best_score = 0
                best_match_full_address = None
                for row in rows:
                    db_street = f"{row['street']} {row['streettype'] or ''}".strip().upper()
                    db_norm = normalize_street_name(db_street)
                    score = fuzz.token_set_ratio(parsed_street, db_norm)
                    if score > best_score:
                        best_score = score
                        st_type = row['streettype'] or ""
                        best_match_full_address = f"{parsed_num} {row['street']} {st_type}".strip().title()

                logging.debug(f"GIS Lookup for '{parsed_address}': Best street match score = {best_score}%")
                if best_score >= self.street_confidence_threshold:
                    return best_score, best_match_full_address
                return best_score, None
        except Exception as e:
            logging.error(f"Error validating address in database: {e}")
            return 0, None

    def get_coordinates(self, parsed_address: str, target_map_grid: str | int = None) -> dict | None:
        """
        Primary geocoding entry point for local parcel address and municipal intersection resolution.
        Converts parsed address string to WGS84 coordinates, boundary rings, and candidate lists.
        Supports multi-junction disambiguation using target_map_grid.
        """
        if not parsed_address:
            return None

        # 1. Check landmarks first (parks, schools, facilities)
        if self._landmark_cache:
            clean_addr_lower = parsed_address.strip().lower()
            best_l_match = None
            best_l_score = 0
            for name, details in self._landmark_cache.items():
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

        # 2. Manual geocoding overrides
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

        # 3. Check intersection authority
        cands, score = self._lookup_intersection(parsed_address)
        if cands:
            res = self._resolve_candidates(cands, target_map_grid=target_map_grid)
            if res:
                res["confidence"] = float(score)
                return res
        elif split_intersection_parts(parsed_address) is not None:
            # Address was explicitly an intersection but unresolvable in local registry
            return None

        # 4. Parcels house + street resolution
        match = re.search(r'^(?P<number>\d+)\s+(?P<street>.*)', clean_address)
        if not match:
            return None

        parsed_num, parsed_street_raw = match.group('number'), match.group('street').strip()
        # Clean unit/suite numbers (e.g. "number 105", "unit B")
        parsed_street_raw = re.sub(r'\b(number|num|unit|suite|apt|apartment|#)\s+\w+\b.*', '', parsed_street_raw, flags=re.IGNORECASE).strip()
        # Clean block designations (e.g. "1080 block ponderosa street" or "1000 blk of ponderosa")
        parsed_street_raw = re.sub(r'\b(block|blk|of)\b', '', parsed_street_raw, flags=re.IGNORECASE).strip()
        parsed_street_raw = " ".join(parsed_street_raw.split())
        parsed_street = normalize_street_name(parsed_street_raw)

        words = parsed_street_raw.split()
        if len(words) >= 1:
            street_type_raw = words[-1]
            street_name_raw = " ".join(words[:-1])
            norm_type = SUFFIX_MAPPINGS.get(street_type_raw.upper(), street_type_raw.upper())
        else:
            street_name_raw = parsed_street_raw
            norm_type = ""

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT id, address, house, street, streettype, lat, lng,
                           front_lat, front_lng, entrance_lat, entrance_lng,
                           centroid_lat, centroid_lng, zone_id,
                           ST_AsGeoJSON(geom) as geom_geojson
                    FROM public.parcels
                    WHERE house = :house;
                """), {"house": parsed_num}).mappings().fetchall()

                best_score = 0
                best_row = None
                for row in rows:
                    db_street = f"{row['street']} {row['streettype'] or ''}".strip().upper()
                    db_norm = normalize_street_name(db_street)
                    score = fuzz.token_set_ratio(parsed_street, db_norm)
                    if score > best_score:
                        best_score = score
                        best_row = row

                if best_score >= self.street_confidence_threshold and best_row is not None:
                    # Routing priority: front_lat or entrance_lat or lat
                    dest_lat = best_row["front_lat"] or best_row["entrance_lat"] or best_row["lat"]
                    dest_lng = best_row["front_lng"] or best_row["entrance_lng"] or best_row["lng"]

                    rings = []
                    geojson_str = best_row["geom_geojson"]
                    if geojson_str:
                        try:
                            geom_data = json.loads(geojson_str)
                            gtype = geom_data.get("type")
                            if gtype == "Polygon":
                                rings = geom_data.get("coordinates", [])
                            elif gtype == "MultiPolygon":
                                rings = [r for poly in geom_data.get("coordinates", []) for r in poly]
                        except Exception:
                            rings = []

                    st_type = best_row["streettype"] or ""
                    clean_addr_val = f"{best_row['house']} {best_row['street']} {st_type}".strip().title()
                    try:
                        from cfr_dispatch.parser import normalize_street_suffix
                        clean_addr_val = normalize_street_suffix(clean_addr_val)
                    except Exception:
                        pass

                    return {
                        "address": clean_addr_val,
                        "lat": float(dest_lat),
                        "lng": float(dest_lng),
                        "rings": rings,
                        "confidence": float(best_score),
                        "is_ambiguous": False
                    }

                # 5. Centroid Fallback on Street if exact house number not found
                centroid_res = conn.execute(text("""
                    SELECT AVG(lat) as avg_lat, AVG(lng) as avg_lng, COUNT(*) as cnt
                    FROM public.parcels
                    WHERE UPPER(street) = UPPER(:street_name)
                      AND (UPPER(streettype) = UPPER(:norm_type) OR :norm_type = '');
                """), {"street_name": street_name_raw, "norm_type": norm_type}).mappings().fetchone()

                if centroid_res and centroid_res["cnt"] > 0 and centroid_res["avg_lat"] is not None:
                    avg_lat = float(centroid_res["avg_lat"])
                    avg_lng = float(centroid_res["avg_lng"])
                    logging.info(f"Local geocode exact match failed for '{parsed_address}'. Fell back to street centroid: Lat {avg_lat:.6f}, Lng {avg_lng:.6f}")
                    return {
                        "address": f"{parsed_num} {parsed_street_raw}".strip().title(),
                        "lat": avg_lat,
                        "lng": avg_lng,
                        "rings": [],
                        "confidence": 60.0,
                        "is_street_centroid": True,
                        "is_ambiguous": False
                    }

                # Try road centre lines centroid
                road_res = conn.execute(text("""
                    SELECT ST_Y(ST_Centroid(ST_Union(geom))) as lat,
                           ST_X(ST_Centroid(ST_Union(geom))) as lng
                    FROM public.roads
                    WHERE UPPER(fullname) = UPPER(:fullname) OR UPPER(roadname) = UPPER(:roadname);
                """), {"fullname": parsed_street_raw, "roadname": street_name_raw}).mappings().fetchone()

                if road_res and road_res["lat"] is not None:
                    return {
                        "address": f"{parsed_num} {parsed_street_raw}".strip().title(),
                        "lat": float(road_res["lat"]),
                        "lng": float(road_res["lng"]),
                        "rings": [],
                        "confidence": 60.0,
                        "is_street_centroid": True,
                        "is_ambiguous": False
                    }
        except Exception as e:
            logging.error(f"Error querying coordinates for '{parsed_address}': {e}", exc_info=True)

        return None

    def local_geocode(self, parsed_address: str, target_map_grid: str | int = None) -> dict | None:
        """Geocodes address locally; alias for get_coordinates."""
        return self.get_coordinates(parsed_address, target_map_grid=target_map_grid)

    def validate_point_in_grid(self, lat: float, lng: float = None, grid_id: str = None, lon: float = None) -> bool:
        """Determines if a given coordinate lies within the boundaries of a specific response grid map."""
        target_lng = lng if lng is not None else lon
        if not grid_id or lat is None or target_lng is None:
            return False
        clean_grid = re.sub(r'^(?:GRID|ZONE)\s*', '', str(grid_id).strip(), flags=re.IGNORECASE)
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT 1 
                    FROM public.zones 
                    WHERE UPPER(map_name) = UPPER(:grid_id)
                      AND ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
                    LIMIT 1;
                """), {"lat": float(lat), "lng": float(target_lng), "grid_id": clean_grid}).fetchone()
                return bool(res)
        except Exception as e:
            logging.error(f"Point-in-grid validation error: {e}", exc_info=True)
            return False

    def get_map_grid_for_point(self, lat: float, lng: float = None, lon: float = None) -> str | None:
        """Looks up the emergency response map grid ID containing the given lat/lng coordinates."""
        target_lng = lng if lng is not None else lon
        if lat is None or target_lng is None:
            return None
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT map_name 
                    FROM public.zones 
                    WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
                    LIMIT 1;
                """), {"lat": float(lat), "lng": float(target_lng)}).fetchone()
                if res:
                    return str(res[0]).strip()
        except Exception as e:
            logging.error(f"Point-to-grid spatial lookup error: {e}", exc_info=True)
        return None

    def get_streets_in_grid(self, grid_id: str) -> List[str]:
        """Returns the list of unique street names contained within a specific map grid."""
        if not grid_id:
            return []
        clean_grid = re.sub(r'^(?:GRID|ZONE)\s*', '', str(grid_id).strip(), flags=re.IGNORECASE)
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT DISTINCT UPPER(street) 
                    FROM public.parcels 
                    WHERE UPPER(zone_id) = UPPER(:grid_id) AND street IS NOT NULL AND street != ''
                    ORDER BY UPPER(street);
                """), {"grid_id": clean_grid}).fetchall()
                return [r[0] for r in res if r[0]]
        except Exception as e:
            logging.error(f"Error fetching streets in grid '{grid_id}': {e}", exc_info=True)
            return []

    def is_within_city(self, lat: float, lng: float = None, lon: float = None) -> bool:
        """Determines whether a coordinate lies within authoritative City of Coquitlam municipal boundary."""
        target_lng = lng if lng is not None else lon
        if lat is None or target_lng is None:
            return False
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
                    FROM public.city_boundary
                    LIMIT 1;
                """), {"lat": float(lat), "lng": float(target_lng)}).fetchone()
                if res and res[0] is not None:
                    return bool(res[0])
                # Fallback to municipal bounding box
                return (49.20 <= float(lat) <= 49.39) and (-122.92 <= float(target_lng) <= -122.70)
        except Exception as e:
            logging.error(f"Error checking is_within_city: {e}", exc_info=True)
            return (49.20 <= float(lat) <= 49.39) and (-122.92 <= float(target_lng) <= -122.70)

    def get_all_road_names(self) -> List[str]:
        """Returns list of all known road names."""
        if self._road_names_cache:
            return list(self._road_names_cache)
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("SELECT road_name FROM public.road_names ORDER BY road_name;")).fetchall()
                return [r[0] for r in res]
        except Exception as e:
            logging.error(f"Error fetching all road names: {e}")
            return []

    def get_top_street_names(self, limit: int = 100) -> List[str]:
        """Returns top street names by parcel frequency."""
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT street, COUNT(*) as cnt 
                    FROM public.parcels 
                    WHERE street IS NOT NULL AND street != ''
                    GROUP BY street 
                    ORDER BY cnt DESC 
                    LIMIT :limit;
                """), {"limit": limit}).fetchall()
                return [r[0] for r in res]
        except Exception as e:
            logging.error(f"Error fetching top street names: {e}")
            if self._road_names_cache:
                return self._road_names_cache[:limit]
            return []

    def get_road_metadata(self, road_name: str) -> dict | None:
        """Retrieves road network classification, speed limits, and traffic attributes from public.roads."""
        if not road_name:
            return None
        clean_name = road_name.strip()
        words = clean_name.split()
        base_name = " ".join(words[:-1]) if len(words) > 1 else clean_name

        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT fullname, roadname, roadtype, road_class, functional_class,
                           speed, num_lanes, truck_route, bus_route, status,
                           left_begin, left_end, right_begin, right_end
                    FROM public.roads
                    WHERE UPPER(fullname) = UPPER(:name)
                       OR UPPER(roadname) = UPPER(:name)
                       OR UPPER(roadname) = UPPER(:base_name)
                       OR UPPER(fullname) ILIKE :like_name
                    ORDER BY 
                       CASE WHEN UPPER(fullname) = UPPER(:name) THEN 1
                            WHEN UPPER(roadname) = UPPER(:name) THEN 2
                            WHEN UPPER(roadname) = UPPER(:base_name) THEN 3
                            ELSE 4 END
                    LIMIT 1;
                """), {
                    "name": clean_name,
                    "base_name": base_name,
                    "like_name": f"%{base_name}%"
                }).fetchone()

                if res:
                    return {
                        "fullname": res[0],
                        "roadname": res[1],
                        "roadtype": res[2],
                        "road_class": res[3],
                        "functional_class": res[4],
                        "speed": res[5],
                        "num_lanes": res[6],
                        "truck_route": bool(res[7]),
                        "bus_route": bool(res[8]),
                        "status": res[9],
                        "left_begin": res[10],
                        "left_end": res[11],
                        "right_begin": res[12],
                        "right_end": res[13]
                    }
        except Exception as e:
            logging.error(f"Error fetching road metadata for '{road_name}': {e}")
        return None

