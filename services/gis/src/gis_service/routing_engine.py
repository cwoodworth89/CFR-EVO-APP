import math
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional, Any

# Official Coquitlam Fire Halls with verified driveway front-apron GPS coordinates
FIRE_HALLS: Dict[str, Dict[str, Any]] = {
    "1": {
        "id": 1,
        "name": "Town Centre Fire Hall (Hall 1)",
        "address": "1300 Pinetree Way",
        "lat": 49.29109654571679,
        "lng": -122.79072561861948,
    },
    "2": {
        "id": 2,
        "name": "Mariner Fire Hall (Hall 2)",
        "address": "775 Mariner Way",
        "lat": 49.2622197420057,
        "lng": -122.81747986099539,
    },
    "3": {
        "id": 3,
        "name": "Austin Heights Fire Hall (Hall 3)",
        "address": "438 Nelson Street",
        "lat": 49.24803974681661,
        "lng": -122.86546062387211,
    },
    "4": {
        "id": 4,
        "name": "Burke Mountain Fire Hall (Hall 4)",
        "address": "3501 David Ave",
        "lat": 49.29510006403205,
        "lng": -122.74247651791484,
    },
}

def get_unit_type(unit_str: str) -> str:
    """Returns human-readable apparatus type."""
    u = unit_str.upper().strip()
    if u.startswith("M"):
        return "Medic"
    if u.startswith("L"):
        return "Ladder"
    if u.startswith("E"):
        return "Engine"
    if u.startswith("R"):
        return "Rescue"
    if u.startswith("C") or u.startswith("B"):
        return "Chief"
    if u.startswith("WT") or u.startswith("W"):
        return "Water Tender"
    if u.startswith("SQ"):
        return "Squad"
    if u.startswith("Q"):
        return "Quint"
    return "Apparatus"

def get_unit_station_id(unit_str: str) -> str:
    """Extracts home station ID from unit abbreviation (e.g. M1 -> 1, E3 -> 3, WT4 -> 4)."""
    match = re.search(r'\d+', str(unit_str))
    if match:
        station_num = match.group(0)
        if station_num in FIRE_HALLS:
            return station_num
    return "1"

class EVORoutingEngine:
    """
    Embedded routing engine for Emergency Vehicle Operators.
    Computes emergency road driving distance, response ETA, and polyline per dispatched unit.
    """
    def __init__(self, default_station_id: str = "1"):
        self.default_hall_key = default_station_id if default_station_id in FIRE_HALLS else "1"
        self.default_hall = FIRE_HALLS[self.default_hall_key]

    def get_hall_location(self, hall_key: Optional[str] = None) -> Dict[str, Any]:
        key = str(hall_key) if str(hall_key) in FIRE_HALLS else self.default_hall_key
        return FIRE_HALLS.get(key, self.default_hall)

    def calculate_distance_km(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Haversine distance in kilometers."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
        return R * c

    def calculate_unit_metrics(
        self,
        unit: str,
        dest_lat: float,
        dest_lng: float,
        response_type: str = "emergency"
    ) -> Dict[str, Any]:
        """
        Calculates driving distance, road routing factor, and ETA for a specific unit from its Home Fire Hall.

        Response Modes:
          - Emergency (Code 3): EmTrac/Opticom signal preemption, Code 3 speed (~45 km/h avg, 1.35x road factor, 0.5m turnout).
          - Routine (Code 1): Standard public drive times, obeying traffic signals & speed limits (~32 km/h avg, 1.45x road factor, 1.0m turnout).
        """
        clean_unit = str(unit).strip().upper()
        station_id = get_unit_station_id(clean_unit)
        hall = self.get_hall_location(station_id)

        crow_km = self.calculate_distance_km(hall["lat"], hall["lng"], dest_lat, dest_lng)
        
        is_routine = str(response_type).lower().strip() == "routine"
        road_factor = 1.45 if is_routine else 1.35
        avg_speed_kmh = 32.0 if is_routine else 45.0
        turnout_minutes = 0.0  # Strictly enroute drive times (turnout buffer excluded)

        road_km = round(crow_km * road_factor, 2)
        total_minutes = (road_km / avg_speed_kmh) * 60 + turnout_minutes
        eta_minutes = max(1, round(total_minutes))

        return {
            "unit": clean_unit,
            "unit_type": get_unit_type(clean_unit),
            "origin_hall": hall["id"],
            "hall_name": hall["name"],
            "hall_address": hall["address"],
            "origin_coords": [hall["lat"], hall["lng"]],
            "destination_coords": [dest_lat, dest_lng],
            "crow_distance_km": round(crow_km, 2),
            "road_distance_km": road_km,
            "eta_minutes": eta_minutes,
            "speed_kmh": avg_speed_kmh,
            "response_mode": "Routine (Code 1)" if is_routine else "Emergency (Code 3)",
            "calculated_at": datetime.now(timezone.utc).isoformat()
        }

    def calculate_units_routing(
        self,
        responding_units: List[str],
        dest_lat: Optional[float],
        dest_lng: Optional[float],
        response_type: str = "emergency"
    ) -> List[Dict[str, Any]]:
        """
        Generates structured routing metrics for all dispatched units.
        """
        if not dest_lat or not dest_lng or not responding_units:
            return []

        metrics = []
        seen = set()
        for unit in responding_units:
            clean = str(unit).strip().upper()
            if clean and clean not in seen:
                seen.add(clean)
                try:
                    m = self.calculate_unit_metrics(clean, dest_lat, dest_lng, response_type=response_type)
                    metrics.append(m)
                except Exception as e:
                    logging.warning(f"Failed to calculate routing for unit {clean}: {e}")
        return metrics

    def calculate_route(
        self,
        dest_lat: float,
        dest_lng: float,
        start_lat: Optional[float] = None,
        start_lng: Optional[float] = None,
        station_id: Optional[str] = None,
        response_type: str = "emergency"
    ) -> Dict:
        """
        Computes response route polyline, distance in km, and ETA in minutes.
        """
        if start_lat is None or start_lng is None:
            hall = self.get_hall_location(station_id)
            start_lat = hall["lat"]
            start_lng = hall["lng"]

        dist_km = self.calculate_distance_km(start_lat, start_lng, dest_lat, dest_lng)
        is_routine = str(response_type).lower().strip() == "routine"
        road_factor = 1.45 if is_routine else 1.35
        avg_speed_kmh = 32.0 if is_routine else 45.0
        turnout_minutes = 0.0  # Strictly enroute drive times (turnout buffer excluded)

        road_km = round(dist_km * road_factor, 2)
        eta_minutes = max(1, round((road_km / avg_speed_kmh) * 60 + turnout_minutes))

        # Tactical Corridor Waypoint Injection for Hall 1 Departures
        coordinates = [[start_lat, start_lng]]

        # Check if departing from Hall 1 (Town Centre)
        is_hall_1 = (abs(start_lat - 49.291) < 0.005 and abs(start_lng - (-122.790)) < 0.005) or (str(station_id) == "1")

        if is_hall_1:
            # Corridor A: Mariner Way / Southwest Sector (Take Guildford -> Johnson St -> Mariner to avoid Lougheed traffic medians)
            if dest_lat < 49.280 and dest_lng < -122.800:
                coordinates.append([49.2847, -122.7915])  # Pinetree & Guildford
                coordinates.append([49.2845, -122.8055])  # Guildford & Johnson St
                coordinates.append([49.2785, -122.8125])  # Johnson St & Mariner Way
            # Corridor B: Gordon Ave / Town Centre Sector (Pinetree South -> Lougheed -> Christmas Way -> Gordon)
            elif 49.275 <= dest_lat <= 49.285 and -122.795 <= dest_lng <= -122.780:
                coordinates.append([49.2785, -122.7915])  # Pinetree & Lougheed
                coordinates.append([49.2785, -122.7850])  # Lougheed & Christmas Way
            else:
                mid_lat = (start_lat + dest_lat) / 2.0 + (0.0015 if start_lat < dest_lat else -0.0015)
                mid_lng = (start_lng + dest_lng) / 2.0
                coordinates.append([mid_lat, mid_lng])
        else:
            mid_lat = (start_lat + dest_lat) / 2.0 + (0.0015 if start_lat < dest_lat else -0.0015)
            mid_lng = (start_lng + dest_lng) / 2.0
            coordinates.append([mid_lat, mid_lng])

        coordinates.append([dest_lat, dest_lng])

        return {
            "status": "success",
            "distance_km": road_km,
            "eta_minutes": eta_minutes,
            "response_mode": "Routine (Code 1)" if is_routine else "Emergency (Code 3)",
            "origin": {"lat": start_lat, "lng": start_lng},
            "destination": {"lat": dest_lat, "lng": dest_lng},
            "polyline": coordinates
        }
