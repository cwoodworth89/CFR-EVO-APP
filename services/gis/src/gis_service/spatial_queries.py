"""PostGIS spatial queries for zone lookups, city boundary, road metadata, and grid operations."""
import re
import logging
from typing import List, Optional
from sqlalchemy import text


class SpatialQueryEngine:
    def __init__(self, engine, road_names_cache: list = None):
        self.engine = engine
        self._road_names_cache = road_names_cache or []

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
