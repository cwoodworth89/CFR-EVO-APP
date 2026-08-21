"""Address resolution: exact parcel match, block interpolation, cross-road narrowing, and centroid fallbacks."""
import json
import logging
import re
from typing import Optional, Tuple, List, Any
from sqlalchemy import text
from .normalization import normalize_street_name, SUFFIX_MAPPINGS

try:
    from thefuzz import fuzz
except ImportError:
    import difflib
    class _Fuzz:
        @staticmethod
        def token_set_ratio(s1, s2):
            return int(difflib.SequenceMatcher(None, str(s1).lower(), str(s2).lower()).ratio() * 100)
    fuzz = _Fuzz()


class AddressResolver:
    def __init__(self, engine, confidence_threshold=80):
        self.engine = engine
        self.confidence_threshold = confidence_threshold

    def resolve_exact(self, house: str, street_raw: str, street_type: str) -> dict | None:
        """Step 1: Exact parcel match — house number + fuzzy street name."""
        parsed_street = normalize_street_name(f"{street_raw} {street_type}".strip() if street_type else street_raw)
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT id, address, house, street, streettype, lat, lng,
                           front_lat, front_lng, entrance_lat, entrance_lng,
                           centroid_lat, centroid_lng, zone_id,
                           ST_AsGeoJSON(geom) as geom_geojson
                    FROM public.parcels
                    WHERE house = :house;
                """), {"house": str(house)}).mappings().fetchall()

                best_score = 0
                best_row = None
                for row in rows:
                    db_street = f"{row['street']} {row['streettype'] or ''}".strip().upper()
                    db_norm = normalize_street_name(db_street)
                    score = fuzz.token_set_ratio(parsed_street, db_norm)
                    if score > best_score:
                        best_score = score
                        best_row = row

                if best_score >= self.confidence_threshold and best_row is not None:
                    dest_lat = best_row['front_lat'] or best_row['entrance_lat'] or best_row['lat']
                    dest_lng = best_row['front_lng'] or best_row['entrance_lng'] or best_row['lng']
                    rings = self._extract_rings(best_row['geom_geojson'])
                    st_type = best_row['streettype'] or ''
                    clean_addr = f"{best_row['house']} {best_row['street']} {st_type}".strip().title()
                    return {
                        "address": clean_addr,
                        "lat": float(dest_lat),
                        "lng": float(dest_lng),
                        "rings": rings,
                        "confidence": float(best_score),
                        "is_ambiguous": False
                    }
        except Exception as e:
            logging.error(f"Error in exact address resolution: {e}", exc_info=True)
        return None

    def resolve_block(self, house: str, street_raw: str, street_type: str) -> dict | None:
        """Step 3: Block interpolation using road address ranges.
        
        Uses left_begin/left_end/right_begin/right_end from public.roads to find
        the road segment containing the given house number, then interpolates
        position along the segment's LineString geometry.
        """
        fullname = f"{street_raw} {street_type}".strip()
        try:
            house_num = int(house)
        except (ValueError, TypeError):
            return None

        try:
            with self.engine.connect() as conn:
                # Find road segments where the house number falls within address ranges
                row = conn.execute(text("""
                    SELECT id, fullname, left_begin, left_end, right_begin, right_end,
                           ST_Length(geom::geography) as seg_length,
                           ST_AsGeoJSON(geom) as geom_geojson
                    FROM public.roads
                    WHERE (UPPER(fullname) = UPPER(:fullname) OR UPPER(roadname) = UPPER(:street_name))
                      AND (
                        (left_begin IS NOT NULL AND left_end IS NOT NULL AND
                         LEAST(left_begin, left_end) <= :house AND GREATEST(left_begin, left_end) >= :house)
                        OR
                        (right_begin IS NOT NULL AND right_end IS NOT NULL AND
                         LEAST(right_begin, right_end) <= :house AND GREATEST(right_begin, right_end) >= :house)
                      )
                    LIMIT 1;
                """), {"fullname": fullname, "street_name": street_raw, "house": house_num}).mappings().fetchone()

                if row:
                    # Determine which side the house falls on and interpolate
                    lb, le = row['left_begin'] or 0, row['left_end'] or 0
                    rb, re_val = row['right_begin'] or 0, row['right_end'] or 0
                    
                    # Use whichever side contains the house number
                    if lb and le and min(lb, le) <= house_num <= max(lb, le):
                        range_begin, range_end = min(lb, le), max(lb, le)
                    elif rb and re_val and min(rb, re_val) <= house_num <= max(rb, re_val):
                        range_begin, range_end = min(rb, re_val), max(rb, re_val)
                    else:
                        range_begin, range_end = 0, 1
                    
                    # Calculate proportional position along segment
                    if range_end != range_begin:
                        fraction = (house_num - range_begin) / (range_end - range_begin)
                    else:
                        fraction = 0.5
                    fraction = max(0.0, min(1.0, fraction))  # Clamp to [0,1]

                    # Interpolate point along the LineString
                    point = conn.execute(text("""
                        SELECT ST_Y(ST_LineInterpolatePoint(geom, :fraction)) as lat,
                               ST_X(ST_LineInterpolatePoint(geom, :fraction)) as lng
                        FROM public.roads WHERE id = :road_id;
                    """), {"fraction": fraction, "road_id": row['id']}).mappings().fetchone()

                    if point and point['lat'] is not None:
                        return {
                            "address": f"{house} {fullname}".strip().title(),
                            "lat": float(point['lat']),
                            "lng": float(point['lng']),
                            "rings": [],
                            "confidence": 70.0,
                            "is_block_interpolated": True,
                            "is_ambiguous": False
                        }
        except Exception as e:
            logging.error(f"Error in block interpolation: {e}", exc_info=True)
        return None

    def resolve_crossroad_narrow(self, street: str, street_type: str,
                                  cross_street_1: str = None, cross_street_2: str = None) -> dict | None:
        """Step 4: Narrow location using nearby cross streets.
        
        Finds intersection points where the primary street meets the cross streets,
        then returns the midpoint between them (or the single intersection point).
        """
        if not cross_street_1:
            return None
        
        fullname = normalize_street_name(f"{street} {street_type}".strip())
        cross_1_norm = normalize_street_name(cross_street_1)
        
        try:
            with self.engine.connect() as conn:
                # Find intersection(s) of primary street with cross street(s)
                points = []
                for cross in [cross_1_norm, normalize_street_name(cross_street_2) if cross_street_2 else None]:
                    if not cross:
                        continue
                    # Check both orderings of the intersection key
                    row = conn.execute(text("""
                        SELECT lat, lng FROM public.intersections
                        WHERE (UPPER(street_a) = UPPER(:s1) AND UPPER(street_b) = UPPER(:s2))
                           OR (UPPER(street_a) = UPPER(:s2) AND UPPER(street_b) = UPPER(:s1))
                        LIMIT 1;
                    """), {"s1": fullname, "s2": cross}).mappings().fetchone()
                    if row and row['lat'] is not None and row['lng'] is not None:
                        points.append((float(row['lat']), float(row['lng'])))
                
                if len(points) == 2:
                    # Midpoint between two cross-street intersections
                    mid_lat = (points[0][0] + points[1][0]) / 2
                    mid_lng = (points[0][1] + points[1][1]) / 2
                    return {
                        "address": f"{street} {street_type} (between {cross_street_1} & {cross_street_2})".strip().title(),
                        "lat": mid_lat,
                        "lng": mid_lng,
                        "rings": [],
                        "confidence": 75.0,
                        "is_crossroad_narrowed": True,
                        "is_ambiguous": False
                    }
                elif len(points) == 1:
                    return {
                        "address": f"{street} {street_type} (near {cross_street_1})".strip().title(),
                        "lat": points[0][0],
                        "lng": points[0][1],
                        "rings": [],
                        "confidence": 72.0,
                        "is_crossroad_narrowed": True,
                        "is_ambiguous": False
                    }
        except Exception as e:
            logging.error(f"Error in cross-road narrowing: {e}", exc_info=True)
        return None

    def resolve_street_centroid(self, street: str, street_type: str) -> dict | None:
        """Step 5: Fallback — average of all parcel centroids on this street."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT AVG(lat) as avg_lat, AVG(lng) as avg_lng, COUNT(*) as cnt
                    FROM public.parcels
                    WHERE UPPER(street) = UPPER(:street)
                      AND (UPPER(streettype) = UPPER(:stype) OR :stype = '');
                """), {"street": street, "stype": street_type or ''}).mappings().fetchone()
                if result and result['cnt'] > 0 and result['avg_lat'] is not None:
                    return {
                        "address": f"{street} {street_type}".strip().title(),
                        "lat": float(result['avg_lat']),
                        "lng": float(result['avg_lng']),
                        "rings": [],
                        "confidence": 50.0,
                        "is_street_centroid": True,
                        "is_ambiguous": False
                    }
        except Exception as e:
            logging.error(f"Error in street centroid fallback: {e}", exc_info=True)
        return None

    def resolve_road_centroid(self, street: str, street_type: str) -> dict | None:
        """Step 6: Fallback — centroid of road centerline geometry."""
        fullname = f"{street} {street_type}".strip()
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT ST_Y(ST_Centroid(ST_Union(geom))) as lat,
                           ST_X(ST_Centroid(ST_Union(geom))) as lng
                    FROM public.roads
                    WHERE UPPER(fullname) = UPPER(:fullname) OR UPPER(roadname) = UPPER(:street);
                """), {"fullname": fullname, "street": street}).mappings().fetchone()
                if result and result['lat'] is not None:
                    return {
                        "address": f"{street} {street_type}".strip().title(),
                        "lat": float(result['lat']),
                        "lng": float(result['lng']),
                        "rings": [],
                        "confidence": 45.0,
                        "is_street_centroid": True,
                        "is_ambiguous": False
                    }
        except Exception as e:
            logging.error(f"Error in road centroid fallback: {e}", exc_info=True)
        return None

    def validate_address_exists(self, house: str, street_raw: str, street_type: str) -> Tuple[int, str | None]:
        """Checks if an address exists in the parcels database. Returns (score, matched_address)."""
        parsed_street = normalize_street_name(f"{street_raw} {street_type}".strip() if street_type else street_raw)
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT house, street, streettype, address
                    FROM public.parcels WHERE house = :house;
                """), {"house": str(house)}).mappings().fetchall()
                best_score = 0
                best_addr = None
                for row in rows:
                    db_street = f"{row['street']} {row['streettype'] or ''}".strip().upper()
                    db_norm = normalize_street_name(db_street)
                    score = fuzz.token_set_ratio(parsed_street, db_norm)
                    if score > best_score:
                        best_score = score
                        st = row['streettype'] or ''
                        best_addr = f"{house} {row['street']} {st}".strip().title()
                if best_score >= self.confidence_threshold:
                    return best_score, best_addr
                return best_score, None
        except Exception as e:
            logging.error(f"Error validating address: {e}")
            return 0, None

    @staticmethod
    def _extract_rings(geojson_str: str) -> list:
        if not geojson_str:
            return []
        try:
            geom = json.loads(geojson_str)
            gtype = geom.get('type')
            if gtype == 'Polygon':
                return geom.get('coordinates', [])
            elif gtype == 'MultiPolygon':
                return [r for poly in geom.get('coordinates', []) for r in poly]
        except Exception:
            pass
        return []
