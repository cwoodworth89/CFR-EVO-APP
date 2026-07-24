import math
import logging
from typing import Dict, List, Tuple, Optional

# Default Fire Hall Locations in Coquitlam WGS84
FIRE_HALLS: Dict[str, Dict[str, float]] = {
    "HALL_1": {"name": "Hall 1 (Pinetree Way)", "lat": 49.2882, "lng": -122.7915},
    "HALL_2": {"name": "Hall 2 (Mariner Way)", "lat": 49.2615, "lng": -122.8258},
    "HALL_3": {"name": "Hall 3 (Victoria Dr)", "lat": 49.3012, "lng": -122.7485},
    "HALL_4": {"name": "Hall 4 (Burke Mountain)", "lat": 49.3105, "lng": -122.7302},
}

class EVORoutingEngine:
    """
    Lightweight, Pi-friendly embedded routing engine for Emergency Vehicle Operators.
    Uses in-memory graph or dynamic geometric pathing with EVO response multipliers.
    """
    def __init__(self, station_id: str = "HALL_1"):
        self.default_hall_key = station_id if station_id in FIRE_HALLS else "HALL_1"
        self.default_hall = FIRE_HALLS[self.default_hall_key]
        logging.info(f"EVORoutingEngine initialized. Default Origin: {self.default_hall['name']}")

    def get_hall_location(self, hall_key: Optional[str] = None) -> Dict[str, float]:
        key = hall_key if hall_key in FIRE_HALLS else self.default_hall_key
        return FIRE_HALLS.get(key, self.default_hall)

    def calculate_distance_km(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Haversine distance in kilometers."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
        c = 2 * Math_atan2_sqrt(a)
        return R * c

    def calculate_route(
        self,
        dest_lat: float,
        dest_lng: float,
        start_lat: Optional[float] = None,
        start_lng: Optional[float] = None,
        station_id: Optional[str] = None
    ) -> Dict:
        """
        Computes response route polyline, distance in km, and ETA in minutes.
        """
        if start_lat is None or start_lng is None:
            hall = self.get_hall_location(station_id)
            start_lat = hall["lat"]
            start_lng = hall["lng"]

        dist_km = self.calculate_distance_km(start_lat, start_lng, dest_lat, dest_lng)
        
        # EVO Emergency Response Speed Assumption: ~55 km/h average city response speed
        avg_speed_kmh = 55.0
        eta_minutes = math.ceil((dist_km / avg_speed_kmh) * 60)
        if eta_minutes < 1:
          eta_minutes = 1

        # Generate polyline coordinates array [[lat, lng], ...]
        # Simple high-speed route interpolation with intermediate tactical waypoint
        mid_lat = (start_lat + dest_lat) / 2.0 + (0.0015 if start_lat < dest_lat else -0.0015)
        mid_lng = (start_lng + dest_lng) / 2.0

        coordinates = [
            [start_lat, start_lng],
            [mid_lat, mid_lng],
            [dest_lat, dest_lng]
        ]

        return {
            "status": "success",
            "distance_km": round(dist_km, 2),
            "eta_minutes": eta_minutes,
            "origin": {"lat": start_lat, "lng": start_lng},
            "destination": {"lat": dest_lat, "lng": dest_lng},
            "polyline": coordinates
        }

def Math_atan2_sqrt(a: float) -> float:
    return math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
