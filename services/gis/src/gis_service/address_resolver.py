"""Address resolution: exact parcel match, block interpolation, cross-road narrowing, and centroid fallbacks."""
import json
import logging
import re
from typing import Optional, Tuple, List, Any
from sqlalchemy import text
from .normalization import normalize_street_name, get_suffix_mappings

try:
    from thefuzz import fuzz
except ImportError:
    import difflib
    class _Fuzz:
        @staticmethod
        def ratio(s1, s2):
            return int(difflib.SequenceMatcher(None, str(s1).lower(), str(s2).lower()).ratio() * 100)

        @staticmethod
        def token_set_ratio(s1, s2):
            return int(difflib.SequenceMatcher(None, str(s1).lower(), str(s2).lower()).ratio() * 100)
    fuzz = _Fuzz()


def _suffix_tokens() -> set:
    """Every token that is only a street-type word, both spellings.

    Sourced from public.vocabulary category 'street_suffix' -- the same table the
    normalizer uses, so the two cannot drift (CLAUDE.md §6.2).
    """
    mappings = get_suffix_mappings()
    return {k.upper() for k in mappings.keys()} | {v.upper() for v in mappings.values()}


def street_name_tokens(parsed_street: str) -> list:
    """The tokens that actually name a street, with street-type words removed.

    "WALTON AVE" -> ["WALTON"];  "AVENUE AVE" -> [];  "AVE" -> [].
    """
    if not parsed_street:
        return []
    suffixes = _suffix_tokens()
    return [t for t in parsed_street.upper().split() if t not in suffixes]


def query_street(street_raw: str, street_type: str) -> str:
    """Normalized street for matching, from a caller's (raw, type) pair.

    Geocoder step 1 passes ParsedAddress.raw -- which already ends in the street type --
    together with the separately normalized type, so the naive join yields
    "GORDON AVE AVE". token_set_ratio hid this because a token *set* discards the
    duplicate; fuzz.ratio does not, and scored a perfect match as 83. Collapse repeated
    adjacent tokens so the comparison sees the street as spoken.

    Also drops a trailing unit designator ("PIPELINE RD 205", "DUFFERIN ST 204D").
    The house number arrives separately, so any number left on the street is a unit,
    and no street name in public.parcels contains a numeric token -- verified
    2026-08-23: `SELECT count(*) FROM public.parcels WHERE street ~ '(^|\\s)[0-9]+(\\s|$)'`
    returns 0. Left in place these cost real margin: "PIPELINE RD 205" scores 85
    against "PIPELINE RD", and a longer unit would drop a correct address below the
    threshold entirely.
    """
    joined = f"{street_raw} {street_type}".strip() if street_type else (street_raw or "")
    normalized = normalize_street_name(joined)
    tokens = normalized.split()
    while tokens and re.fullmatch(r"\d+[A-Za-z]?", tokens[-1]):
        tokens.pop()
    out = []
    for tok in tokens:
        if not out or out[-1] != tok:
            out.append(tok)
    return " ".join(out)


def score_street(parsed_street: str, db_norm: str) -> int:
    """Similarity between a spoken street and a municipal one.

    Deliberately fuzz.ratio, NOT fuzz.token_set_ratio. Verified against the installed
    thefuzz 0.22.1 on 2026-08-23 (CLAUDE.md §7.3a):

        token_set_ratio("AVE", "WALTON AVE")   = 100   <- subset scores a perfect match
        token_set_ratio("AVE", "ANSON AVE")    = 100      against every avenue at once
        ratio("AVE", "WALTON AVE")             =  46
        ratio("GORDEN AVE", "GORDON AVE")      =  90   <- real STT noise still passes

    token_set_ratio returns 100 whenever one token set is a subset of the other,
    because the intersection then equals one side by construction. Any street fragment
    therefore matched every street sharing its suffix, at maximum confidence. See
    docs/standards/dependency-behaviour.md.
    """
    return fuzz.ratio(parsed_street, db_norm)


class AddressResolver:
    def __init__(self, engine, confidence_threshold=80):
        self.engine = engine
        self.confidence_threshold = confidence_threshold

    def resolve_exact(self, house: str, street_raw: str, street_type: str) -> dict | None:
        """Step 1: Exact parcel match — house number + fuzzy street name."""
        parsed_street = query_street(street_raw, street_type)

        # A street type with no street name identifies nothing. "3000 avenue" (STT
        # dropped the name) must not resolve to whichever avenue happens to have a
        # 3000 block -- there were three, and the old scoring rated all of them 100.
        # Unresolved is the correct answer here and surfaces as the Tier 1 card (§6.1).
        if not street_name_tokens(parsed_street):
            logging.info(
                "Address '%s %s' carries no street name after normalization "
                "('%s'); refusing to guess which street.", house, street_raw, parsed_street
            )
            return None

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT id, address, house, street, streettype, lat, lng,
                           front_lat, front_lng, entrance_lat, entrance_lng,
                           centroid_lat, centroid_lng, zone_id,
                           ST_AsGeoJSON(geom) as geom_geojson
                    FROM public.parcels
                    WHERE house = :house
                    ORDER BY street, streettype, id;
                """), {"house": str(house)}).mappings().fetchall()

                best_score = 0
                best_row = None
                tied_streets = set()
                for row in rows:
                    db_street = f"{row['street']} {row['streettype'] or ''}".strip().upper()
                    db_norm = normalize_street_name(db_street)
                    score = score_street(parsed_street, db_norm)
                    if score > best_score:
                        best_score = score
                        best_row = row
                        tied_streets = {db_norm}
                    elif score == best_score and best_row is not None:
                        tied_streets.add(db_norm)

                # Two different streets scoring identically is a genuine ambiguity, not
                # a winner. Previously the first row of an unordered query won silently.
                if best_score >= self.confidence_threshold and len(tied_streets) > 1:
                    logging.warning(
                        "Address '%s %s' matches %d streets equally (%s) at score %s; "
                        "returning ambiguous rather than picking one.",
                        house, parsed_street, len(tied_streets),
                        ", ".join(sorted(tied_streets)), best_score
                    )
                    return None

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

                    # Interpolate point along the road centreline.
                    #
                    # public.roads stores geom as MULTILINESTRING (all 3,214 rows), but
                    # ST_LineInterpolatePoint requires a LINESTRING and raises
                    # "1st arg isn't a line" otherwise -- this step previously threw on
                    # every call. ST_LineMerge stitches 3,184 of 3,214 into a single
                    # LINESTRING; the remaining 30 are genuinely disjoint, so fall back
                    # to their longest component rather than failing the lookup.
                    point = conn.execute(text("""
                        WITH merged AS (
                            SELECT ST_LineMerge(geom) AS g
                            FROM public.roads WHERE id = :road_id
                        ),
                        line AS (
                            SELECT CASE
                                     WHEN GeometryType(g) = 'LINESTRING' THEN g
                                     ELSE (
                                       SELECT d.geom FROM ST_Dump(g) AS d
                                       ORDER BY ST_Length(d.geom) DESC LIMIT 1
                                     )
                                   END AS g
                            FROM merged
                        )
                        SELECT ST_Y(ST_LineInterpolatePoint(g, :fraction)) as lat,
                               ST_X(ST_LineInterpolatePoint(g, :fraction)) as lng
                        FROM line WHERE g IS NOT NULL;
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

    def resolve_nearest_civic(self, house: str, street: str, street_type: str) -> dict | None:
        """Step 4b: Nearest civic address on the street, by house number.

        Used when a dispatched address is not in the municipal records and its house
        number falls outside the road segment's address range, so block interpolation
        cannot place it (e.g. 3080 Gordon Ave: the segment carries 3001-3061 and
        3030-3030, and no 3080 parcel exists).

        Returns the *actual* nearest parcel and says so. The address string is the
        parcel that was used, not the one that was asked for, and `resolution_note`
        carries the reason -- an operator must be able to see that a substitution
        happened and why (CLAUDE.md §6.1).

        Preferred over the street centroid, which averages the whole street and can sit
        far from the target: for 3080 Gordon Ave the centroid is 178 m from the nearest
        civic address on a 308 m street, and on the wrong side of it.
        """
        if not house or not str(house).isdigit():
            return None
        try:
            with self.engine.connect() as conn:
                row = conn.execute(text("""
                    SELECT address, house, lat, lng,
                           ABS((house)::int - (:house)::int) AS house_delta
                    FROM public.parcels
                    WHERE UPPER(street) = UPPER(:street)
                      AND (UPPER(streettype) = UPPER(:stype) OR :stype = '')
                      AND house ~ '^[0-9]+$'
                      AND (unit IS NULL OR unit = '')
                      AND lat IS NOT NULL AND lng IS NOT NULL
                    ORDER BY house_delta ASC, (house)::int ASC
                    LIMIT 1;
                """), {"house": str(house), "street": street, "stype": street_type or ''}).mappings().fetchone()

                if not row:
                    return None

                requested = f"{house} {street} {street_type}".strip().title()
                delta = int(row['house_delta'])

                # The substitute must be in the same hundred-block as the dispatched
                # number. Without this there was no bound at all: 3415 Harbour Dr
                # (DISP-2026-1388CD) resolved to 1869 Harbour Dr, 1546 numbers away,
                # and "6 Silver Springs Blvd" (DISP-2026-74813F, STT dropped the
                # leading digits) resolved to 2951, 2945 away. Both were presented as
                # locations with a reassuring note attached.
                #
                # PROVENANCE: the hundred-block is the addressing unit in this
                # jurisdiction, not a tuned constant -- Coquitlam civic numbering
                # allocates one hundred-block per block face, and Locution dispatch
                # itself announces block-level locations that way ("1080 Block
                # Ponderosa St", DISP-2026-266B57). Nothing in docs/standards/ governs
                # substitution distance; this is a municipal-data-derived rule, not a
                # published standard (CLAUDE.md §7.2).
                #
                # Known limitation: two adjacent numbers that straddle a block boundary
                # (3099 -> 3101) are refused. Refusing a near miss costs an operator
                # one Tier 1 card; accepting a far one sends apparatus to the wrong
                # block, so the asymmetry is deliberate.
                requested_block = int(house) // 100
                nearest_block = int(row['house']) // 100
                if requested_block != nearest_block:
                    logging.info(
                        "Nearest civic address to %s is %s, in the %d00 block rather "
                        "than the %d00 block (%d off). Refusing the substitution; "
                        "the address is unresolved.",
                        requested, row['address'], nearest_block, requested_block, delta
                    )
                    return None

                # Confidence degrades with how far the substituted number is from the
                # one dispatched. Deliberately never approaches the 100.0 an exact
                # parcel match earns.
                confidence = 70.0 if delta <= 20 else (60.0 if delta <= 100 else 55.0)

                return {
                    "address": row['address'],
                    "lat": float(row['lat']),
                    "lng": float(row['lng']),
                    "rings": [],
                    "confidence": confidence,
                    "is_nearest_civic": True,
                    "requested_address": requested,
                    "resolution_note": (
                        f"{requested} is not in City of Coquitlam address records. "
                        f"Routed to {row['address']}, the nearest civic address on this "
                        f"street ({delta} off the dispatched number). Verify on arrival."
                    ),
                    "is_ambiguous": False
                }
        except Exception as e:
            logging.error(f"Error in nearest civic address fallback: {e}", exc_info=True)
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
        parsed_street = query_street(street_raw, street_type)

        # Same guard as resolve_exact. This is the *validator*, so the old behaviour was
        # the worse half of the defect: given a bare suffix it returned a confident
        # match and thereby confirmed an address that had never been spoken.
        if not street_name_tokens(parsed_street):
            return 0, None

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT house, street, streettype, address
                    FROM public.parcels WHERE house = :house
                    ORDER BY street, streettype, address;
                """), {"house": str(house)}).mappings().fetchall()
                best_score = 0
                best_addr = None
                tied_streets = set()
                for row in rows:
                    db_street = f"{row['street']} {row['streettype'] or ''}".strip().upper()
                    db_norm = normalize_street_name(db_street)
                    score = score_street(parsed_street, db_norm)
                    if score > best_score:
                        best_score = score
                        st = row['streettype'] or ''
                        best_addr = f"{house} {row['street']} {st}".strip().title()
                        tied_streets = {db_norm}
                    elif score == best_score and best_addr is not None:
                        tied_streets.add(db_norm)
                if best_score >= self.confidence_threshold and len(tied_streets) > 1:
                    return best_score, None
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
