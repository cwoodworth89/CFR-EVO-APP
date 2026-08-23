"""
services/gis/src/gis_service/geocoder.py
PostGIS-backed Geocoder Orchestrator for CFR EVO.

Thin orchestrator that delegates to specialized resolver modules.
Resolution chain: exact address → intersection → block interpolation →
cross-road narrowing → street centroid → road centroid → custom places → manual overrides.
"""
import os
import re
import json
import logging
from typing import List, Tuple, Optional, Any

from sqlalchemy import create_engine, text

from .normalization import (
    normalize_street_name, normalize_intersection_key,
    split_intersection_parts, parse_house_and_street, extract_near_street,
    ParsedAddress
)
from .address_resolver import AddressResolver
from .intersection_resolver import IntersectionResolver
from .spatial_queries import SpatialQueryEngine


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

        # Pre-cache small tables
        self._road_names_cache = self._load_road_names()
        self._intersection_keys_cache = self._load_intersection_keys()

        # Initialize sub-resolvers
        self.address = AddressResolver(self.engine, self.street_confidence_threshold)
        self.intersection = IntersectionResolver(
            self._intersection_keys_cache, self.street_confidence_threshold, engine=self.engine)
        self.spatial = SpatialQueryEngine(self.engine, self._road_names_cache)

    def _load_road_names(self) -> List[str]:
        """Loads all road names from public.road_names."""
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("SELECT road_name FROM public.road_names ORDER BY road_name;")).fetchall()
                names = [r[0] for r in res if r[0]]
                logging.info(f"Loaded {len(names)} road names from PostgreSQL.")
                return names
        except Exception as e:
            logging.error(f"Failed to load road names: {e}")
            return []

    def _load_intersection_keys(self) -> dict:
        """Loads all topological intersections from public.intersections."""
        index = {}
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("""
                    -- The grid is DERIVED, not stored. intersections.zone_id was a
                    -- denormalized copy of this same function's result and was free to
                    -- drift from the geometry it came from, so the column was dropped.
                    SELECT street_a, street_b, intersection_key, lat, lng,
                           public.zone_for_point(geom) AS zone_id, candidate_index
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
                logging.info(f"Loaded {len(index)} intersection keys from PostgreSQL.")
        except Exception as e:
            logging.error(f"Failed to load intersections: {e}")
        return index

    def get_coordinates(self, parsed_address: str, target_map_grid=None,
                        cross_street_1: str = None, cross_street_2: str = None) -> dict | None:
        """
        Primary geocoding entry point — cascading resolution chain.
        
        Resolution order:
        1. Exact address (parcel house+street)
        2. Intersection (cross streets as destination)
        3. Block interpolation (road segment address ranges)
        4. Cross-road narrowing (use nearby cross streets)
        5. Street centroid (average parcel positions)
        6. Road centroid (centerline geometry centroid)
        7. Custom places (manually curated locations)
        8. Manual overrides (hardcoded special cases)
        """
        if not parsed_address:
            return None

        clean = parsed_address.split(',')[0].strip().upper()

        # Detect address pattern
        is_intersection_pattern = split_intersection_parts(parsed_address) is not None
        parsed = parse_house_and_street(clean)

        # === STEP 1: Exact address (requires house number) ===
        if parsed:
            # The map grid and cross streets are announced for this incident, so they
            # are passed in to break ties between equally-matching streets rather than
            # letting a similarity score decide alone.
            result = self.address.resolve_exact(
                parsed.house, parsed.raw, parsed.street_type,
                target_map_grid=target_map_grid,
                cross_street_1=cross_street_1,
                cross_street_2=cross_street_2,
            )
            if result:
                return result

        # === STEP 2: Intersection lookup ===
        if is_intersection_pattern:
            # 2a. "<street> and <street>" -- the same street in both slots. This is a
            # Locution/CAD artifact for "no cross street given", not a self-intersection
            # (ST_IsSimple is true for these roads; they do not cross themselves). The
            # answer is the stretch of that street inside the announced map grid, which
            # the kiosk highlights. Without a grid it stays unresolved: the whole street
            # is not a location.
            section = self._street_section_if_self_paired(parsed_address, target_map_grid)
            if section:
                return section

            cands, score = self.intersection.lookup(parsed_address)
            if cands:
                result = self.intersection.resolve_candidates(
                    cands, target_map_grid, requested_address=parsed_address,
                    cross_streets=[s for s in (cross_street_1, cross_street_2) if s])
                if result:
                    # Do NOT overwrite confidence for a suggested match: resolve_candidates
                    # already set it to the per-street match score, and stamping the
                    # lookup score over it would report a near-miss as more certain than
                    # it is (the pattern punch-list #12 flags for steps 5 and 6).
                    if result.get('resolution_note') is None:
                        result['confidence'] = float(score)
                    return result
            # Explicitly an intersection but not found — don't fall through to street matching
            return None

        # === STEP 3: Block interpolation (has house number but no exact parcel match) ===
        if parsed:
            result = self.address.resolve_block(parsed.house, parsed.street, parsed.street_type)
            if result:
                return result

        # === STEP 4: Cross-road narrowing ===
        if parsed and (cross_street_1 or cross_street_2):
            result = self.address.resolve_crossroad_narrow(
                parsed.street, parsed.street_type,
                cross_street_1=cross_street_1,
                cross_street_2=cross_street_2
            )
            if result:
                return result

        # === STEP 4b: Nearest civic address on the street ===
        # For a numbered address that exists in neither the parcel table nor any road
        # segment's address range, the nearest real civic number beats a whole-street
        # average. Deliberately does NOT overwrite result['address'] with the requested
        # address: the operator must see which parcel was actually used, and
        # resolution_note says why.
        if parsed and parsed.house:
            result = self.address.resolve_nearest_civic(parsed.house, parsed.street, parsed.street_type)
            if result:
                return result

        # === STEP 5: Street centroid fallback ===
        # Deliberately does NOT overwrite result['address'] with the requested address.
        # Doing so made an average of every parcel on the street display exactly like an
        # exact parcel match -- "3415 Harbour Dr" was shown as though found, when the
        # number does not exist on that street and the pin was the street's midpoint
        # (punch-list #12). Step 4b already established the honest pattern: report the
        # location actually used, and say why in resolution_note (§6.1).
        if parsed:
            result = self.address.resolve_street_centroid(parsed.street, parsed.street_type)
            if result:
                result['requested_address'] = f"{parsed.house} {parsed.raw}".strip().title() \
                    if parsed.house else result['address']
                result['resolution_note'] = (
                    f"{result['requested_address']} could not be placed on this street. "
                    f"Showing the midpoint of {result['address']}, not a specific address. "
                    f"Verify on arrival."
                )
                return result

        # === STEP 6: Road centroid fallback ===
        if parsed:
            result = self.address.resolve_road_centroid(parsed.street, parsed.street_type)
            if result:
                result['requested_address'] = f"{parsed.house} {parsed.raw}".strip().title() \
                    if parsed.house else result['address']
                result['resolution_note'] = (
                    f"{result['requested_address']} could not be placed on this street. "
                    f"Showing the centreline midpoint of {result['address']}, not a "
                    f"specific address. Verify on arrival."
                )
                return result

        # No further fallbacks. Two former steps were removed:
        #   - custom places: script-generated coordinates, up to 1.8 km off a parcel,
        #     and unreachable because Locution always speaks the civic address first.
        #   - manual overrides: hardcoded string matches for Port Mann Bridge, Riverview
        #     Hospital, the Coquitlam Central bus loop and 3080 Gordon Ave. Destinations
        #     missing from municipal records belong in the database as real records, not
        #     as string comparisons in application code (CLAUDE.md §6.2).
        #
        # An address that reaches this point is genuinely unresolved and returns None,
        # which surfaces as the Tier 1 warning rather than a guessed location (§6.1).
        return None

    def local_geocode(self, parsed_address: str, target_map_grid=None,
                      cross_street_1: str = None, cross_street_2: str = None) -> dict | None:
        """Geocodes address locally; alias for get_coordinates."""
        return self.get_coordinates(
            parsed_address, target_map_grid=target_map_grid,
            cross_street_1=cross_street_1, cross_street_2=cross_street_2
        )

    def _street_section_if_self_paired(self, parsed_address: str,
                                       target_map_grid=None) -> dict | None:
        """Handle "<street> and <street>" by highlighting that street inside the grid."""
        parts = split_intersection_parts(parsed_address)
        if not parts:
            return None
        a = normalize_street_name(parts[0])
        b = normalize_street_name(parts[1])
        if not a or a != b:
            return None

        if target_map_grid is None:
            logging.info("%r names one street twice with no map grid; unresolved.",
                         parsed_address)
            return None

        section = self.spatial.resolve_street_section_in_grid(a, target_map_grid)
        if not section:
            logging.info("%r: %s does not enter map grid %s; unresolved.",
                         parsed_address, a, target_map_grid)
            return None

        section.update({
            "address": f"{a.title()} (map grid {section['grid']})",
            "requested_address": parsed_address,
            "rings": [],
            "is_ambiguous": False,
            # Not a point match. The confidence reflects that this is a bounded section,
            # not a located incident, and must not read like an exact parcel hit.
            "confidence": 50.0,
            "resolution_note": (
                f"No cross street was given -- the announcement named "
                f"{a.title()} in both slots. Highlighting the {section['length_m']} m of "
                f"{a.title()} inside map grid {section['grid']}. This is a street "
                f"section, not a located incident; route to the nearer end."
            ),
        })
        return section

    def validate_address_exists(self, parsed_address: str) -> Tuple[int, str | None]:
        """Checks if a parsed address exists in the local GIS database."""
        if not parsed_address:
            return 0, None

        # Check intersections
        cands, score = self.intersection.lookup(parsed_address)
        if cands and score >= self.street_confidence_threshold:
            return score, cands[0]['name']
        elif split_intersection_parts(parsed_address) is not None:
            return 0, None

        # Check parcels
        clean = parsed_address.split(',')[0].strip().upper()
        parsed = parse_house_and_street(clean)
        if not parsed:
            return 0, None

        return self.address.validate_address_exists(parsed.house, parsed.raw, parsed.street_type)

    # === Delegated spatial methods ===

    def get_map_grid_for_point(self, lat, lng=None, lon=None):
        return self.spatial.get_map_grid_for_point(lat, lng if lng is not None else lon)

    def validate_point_in_grid(self, lat, lng=None, grid_id=None, lon=None):
        return self.spatial.validate_point_in_grid(lat, lng if lng is not None else lon, grid_id)

    def get_streets_in_grid(self, grid_id):
        return self.spatial.get_streets_in_grid(grid_id)

    def is_within_city(self, lat, lng=None, lon=None):
        return self.spatial.is_within_city(lat, lng if lng is not None else lon)

    def get_all_road_names(self):
        return self.spatial.get_all_road_names()

    def get_top_street_names(self, limit=100):
        return self.spatial.get_top_street_names(limit)

    def get_road_metadata(self, road_name):
        return self.spatial.get_road_metadata(road_name)
