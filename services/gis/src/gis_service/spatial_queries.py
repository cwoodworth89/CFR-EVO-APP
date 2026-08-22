"""PostGIS spatial queries for zone lookups, city boundary, road metadata, and grid operations."""
import re
import logging
from typing import List, Optional
from sqlalchemy import text


class SpatialQueryEngine:
    def __init__(self, engine, road_names_cache: list = None):
        self.engine = engine
        self._road_names_cache = road_names_cache or []

    def resolve_street_section_in_grid(self, street: str, grid_id: str) -> Optional[dict]:
        """The stretch of one street that lies inside one emergency response map grid.

        WHY THIS EXISTS
        Locution sometimes announces a location as "<street> and <street>" -- the same
        street in both the address slot and the "near" cross-street slot -- when the CAD
        record has no cross street. DISP-2026-546B9E is the recorded example: "lougheed
        highway and lougheed highway, near lougheed highway and lougheed highway ... map
        grid 49".

        That is not a self-intersection. ST_IsSimple on Lougheed Hwy's centreline is true,
        so the road never crosses itself in the municipal data. It means "somewhere on
        this street, no cross street given" -- a CAD artifact the dispatch system has to
        adapt to, not an intersection to be found.

        The honest answer is the section of that street inside the announced grid: for
        grid 49 that is 533 m of Lougheed Hwy. Returns the geometry so the kiosk can
        highlight it, plus the endpoints so routing can send apparatus to whichever end
        is nearest the responding hall. There is deliberately no single "the location"
        point: inventing one would restate an unknown as a coordinate (CLAUDE.md 6.1).

        Returns None when the grid is missing or the street does not enter it. Without a
        grid the section is the whole street -- up to 14 km of Lougheed Hwy -- which is
        not a location, so it surfaces as the section 5 Tier 1 card instead.
        """
        if not street or not grid_id:
            return None
        clean_grid = re.sub(r'^(?:GRID|ZONE)\s*', '', str(grid_id).strip(), flags=re.IGNORECASE)
        try:
            with self.engine.connect() as conn:
                row = conn.execute(text("""
                    WITH sfx AS (
                        SELECT upper(btrim(term)) f, upper(btrim(term_normalized)) a
                        FROM public.vocabulary
                        WHERE category = 'street_suffix' AND is_active
                    ),
                    street AS (
                        SELECT btrim(regexp_replace(upper(btrim(r.roadname)), '[,.]', '', 'g')
                                     || ' ' || COALESCE(s.a, upper(btrim(COALESCE(r.roadtype,'')))))
                                 AS canon,
                               ST_Union(r.geom) AS geom
                        FROM public.roads r
                        LEFT JOIN sfx s ON s.f = upper(btrim(r.roadtype))
                        WHERE r.roadname IS NOT NULL AND btrim(r.roadname) <> ''
                        GROUP BY 1
                    ),
                    z AS (SELECT geom FROM public.zones WHERE UPPER(map_name) = UPPER(:grid))
                    SELECT ST_AsGeoJSON(ST_Intersection(street.geom, z.geom)) AS seg,
                           ST_Length(ST_Intersection(street.geom, z.geom)::geography) AS len_m,
                           ST_Y(ST_PointOnSurface(ST_Intersection(street.geom, z.geom))) AS mid_lat,
                           ST_X(ST_PointOnSurface(ST_Intersection(street.geom, z.geom))) AS mid_lng
                    FROM street, z
                    WHERE street.canon = UPPER(:street)
                      AND NOT ST_IsEmpty(ST_Intersection(street.geom, z.geom))
                    LIMIT 1;
                """), {"street": street.strip().upper(), "grid": clean_grid}).mappings().fetchone()
                if not row or not row["seg"]:
                    return None

                import json
                geo = json.loads(row["seg"])
                lines = (geo["coordinates"] if geo["type"] == "MultiLineString"
                         else [geo["coordinates"]] if geo["type"] == "LineString" else [])
                if not lines:
                    return None
                # Every piece's two ends, so routing can send apparatus to whichever is
                # nearest the responding hall. The section is usually a MultiLineString
                # -- 4 disjoint pieces for Lougheed Hwy in grid 49, where ramps and the
                # zone edge split it -- so taking only the first and last point of the
                # whole collection is wrong: those two happened to lie 36 m apart on the
                # same piece, not at the extremes of the 533 m section.
                endpoints = []
                for line in lines:
                    if not line:
                        continue
                    for pt in (line[0], line[-1]):
                        if pt not in endpoints:
                            endpoints.append(pt)

                return {
                    "location_type": "street_section",
                    "street": street.strip().upper(),
                    "grid": clean_grid,
                    "segment": lines,                 # [[ [lng,lat], ... ], ...]
                    "endpoints": endpoints,           # [[lng,lat], ...] every piece's ends
                    "length_m": round(float(row["len_m"] or 0)),
                    # Representative point for map centring and zone lookup ONLY. It is
                    # NOT the incident location and must not be used as a routing target.
                    "lat": float(row["mid_lat"]),
                    "lng": float(row["mid_lng"]),
                }
        except Exception as e:
            logging.error(f"Street-section-in-grid lookup failed: {e}", exc_info=True)
            return None

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
                # public.zone_for_point is the single canonical definition (see
                # backend/migrations/2026-08-22_canonical_zone_for_point.sql). This used
                # ST_Contains, which tests the strict interior; zone polygons are bounded
                # by roads, so a point at an intersection sits ON a boundary and returned
                # NULL. That silently cost 155 of 1,784 intersections their map grid.
                res = conn.execute(text("""
                    SELECT public.zone_for_point(
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326));
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
