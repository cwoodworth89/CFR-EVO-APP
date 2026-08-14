import os
import math
import logging
import re
import urllib.request
import json
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

def get_unit_type(unit: str) -> str:
    """Returns human-readable apparatus type."""
    u = str(unit).strip().upper()
    if u.startswith('T') or u.startswith('WT') or u.startswith('LAV'): return 'Tanker / Tender'
    if u.startswith('E'): return 'Engine / Pumper'
    if u.startswith('L'): return 'Ladder / Aerial'
    if u.startswith('R'): return 'Heavy Rescue'
    if u.startswith('Q'): return 'Quint'
    if u.startswith('C') or u.startswith('B'): return 'Command Vehicle'
    if u.startswith('S') or u.startswith('M'): return 'Specialty / Medic'
    return 'Apparatus'

def get_unit_station_id(unit_str: str) -> str:
    """Extracts home station ID from unit abbreviation (e.g. M1 -> 1, E3 -> 3, WT4 -> 4, Q5 -> 3)."""
    clean_unit = str(unit_str).strip().upper()
    if re.match(r'^(E2|L2|R2)', clean_unit):
        return "2"
    if re.match(r'^(E3|Q5|H3|HT3|S3)', clean_unit):
        return "3"
    if re.match(r'^(E4|T4|WT4|LAV4)', clean_unit):
        return "4"
    match = re.search(r'\d+', clean_unit)
    if match:
        station_num = match.group(0)
        if station_num in FIRE_HALLS:
            return station_num
    return "1"

class EVORoutingEngine:
    """
    Embedded routing engine for Emergency Vehicle Operators.
    Computes emergency road driving distance, response ETA, and high-resolution polyline per dispatched unit.
    """
    def __init__(self, default_station_id: str = "1"):
        self.default_hall_key = str(default_station_id) if str(default_station_id) in FIRE_HALLS else "1"
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

    def _get_osrm_endpoints(self, loc_str: str) -> List[str]:
        """Constructs prioritized candidate endpoints with continue_straight=true."""
        query_params = "overview=full&geometries=geojson&continue_straight=true&steps=true"
        
        disable_wan = os.environ.get("DISABLE_WAN_FALLBACK", "false").lower() in ("true", "1", "yes")

        candidates = []
        for env_key in ("OSRM_BACKEND_URL", "OSRM_ROUTER_URL", "OSRM_URL"):
            env_val = os.environ.get(env_key)
            if env_val and env_val.strip():
                candidates.append(env_val.strip().rstrip("/"))
        
        # Local container & localhost fallbacks
        candidates.extend([
            "http://osrm:5000",
            "http://127.0.0.1:5000",
            "http://localhost:5000",
        ])

        # Public WAN fallback (suppressed when DISABLE_WAN_FALLBACK=true)
        if not disable_wan:
            candidates.append("https://router.project-osrm.org")
        
        endpoints = []
        seen = set()
        for base in candidates:
            if base not in seen:
                seen.add(base)
                endpoints.append(f"{base}/route/v1/driving/{loc_str}?{query_params}")
        return endpoints

    def _fetch_osrm_polyline(self, waypoints: List[List[float]]) -> Tuple[Optional[List[List[float]]], Optional[float]]:
        if not waypoints or len(waypoints) < 2:
            return None, None
        
        # Format coordinates as lng,lat;lng,lat...
        loc_str = ";".join([f"{pt[1]},{pt[0]}" for pt in waypoints])
        endpoints = self._get_osrm_endpoints(loc_str)
        
        for url in endpoints:
            is_local = any(h in url for h in ["osrm:5000", "127.0.0.1:5000", "localhost:5000"])
            timeout = 1.0 if is_local else 2.5
            try:
                req = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'CFREVOApp/1.0 (Coquitlam Fire EVO Routing)'}
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode('utf-8'))
                        if data.get("code") == "Ok" and data.get("routes"):
                            route = data["routes"][0]
                            coords = route["geometry"]["coordinates"]
                            lat_lngs = [[pt[1], pt[0]] for pt in coords]
                            dist_km = round(route["distance"] / 1000.0, 2)
                            return lat_lngs, dist_km
            except Exception as e:
                logging.debug(f"OSRM query attempt failed for {url}: {e}")
        
        return None, None

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
          - Emergency (Code 3): EmTrac/Opticom signal preemption, Code 3 speed (~45 km/h avg, 1.35x road factor, 0.0m turnout buffer).
          - Routine (Code 1): Standard public drive times, obeying traffic signals & speed limits (~32 km/h avg, 1.45x road factor, 0.0m turnout buffer).
        """
        clean_unit = str(unit).strip().upper()
        station_id = get_unit_station_id(clean_unit)
        hall = self.get_hall_location(station_id)
        
        crow_km = self.calculate_distance_km(hall["lat"], hall["lng"], dest_lat, dest_lng)
        is_routine = str(response_type).lower().strip() == "routine"
        road_factor = 1.45 if is_routine else 1.35
        avg_speed_kmh = 32.0 if is_routine else 45.0
        turnout_minutes = 0.0

        road_km = round(crow_km * road_factor, 2)
        total_minutes = (road_km / avg_speed_kmh) * 60.0 + turnout_minutes
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
        """Calculates routing metrics for a list of responding units."""
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
    ) -> Dict[str, Any]:
        """
        Calculates origin-to-destination response route, querying OSRM for street polyline with tactical corridor injection.
        Falls back to straight-line waypoints if OSRM is unreachable.
        """
        if start_lat is None or start_lng is None:
            hall = self.get_hall_location(station_id)
            start_lat = hall["lat"]
            start_lng = hall["lng"]

        dist_km = self.calculate_distance_km(start_lat, start_lng, dest_lat, dest_lng)
        is_routine = str(response_type).lower().strip() == "routine"
        road_factor = 1.45 if is_routine else 1.35
        avg_speed_kmh = 32.0 if is_routine else 45.0
        turnout_minutes = 0.0

        fallback_road_km = round(dist_km * road_factor, 2)

        # Tactical Corridor Waypoint Injection for Hall 1 Departures
        waypoint_pts = [[start_lat, start_lng]]
        is_hall_1 = (abs(start_lat - 49.291) < 0.005 and abs(start_lng - (-122.790)) < 0.005) or (str(station_id) == "1")

        if is_hall_1:
            # Corridor A: Mariner Way / Southwest Sector (Take Guildford -> Johnson St -> Mariner)
            if dest_lat < 49.280 and dest_lng < -122.800:
                waypoint_pts.append([49.2847, -122.7915])  # Pinetree & Guildford
                waypoint_pts.append([49.2845, -122.8055])  # Guildford & Johnson St
                waypoint_pts.append([49.2785, -122.8125])  # Johnson St & Mariner Way
            # Corridor B: Gordon Ave / Town Centre Sector (Pinetree South -> Lougheed -> Christmas Way -> Gordon)
            elif 49.270 <= dest_lat <= 49.285 and -122.795 <= dest_lng <= -122.780:
                waypoint_pts.append([49.2890, -122.7912])  # Pinetree Way Southbound
                waypoint_pts.append([49.2847, -122.7915])  # Pinetree & Guildford
                waypoint_pts.append([49.2785, -122.7912])  # Pinetree & Lougheed
                waypoint_pts.append([49.2780, -122.7854])  # Lougheed & Christmas Way

        waypoint_pts.append([dest_lat, dest_lng])

        # Resolve detailed street network polyline via OSRM
        osrm_polyline, osrm_km = self._fetch_osrm_polyline(waypoint_pts)

        if osrm_polyline and len(osrm_polyline) > 2:
            final_polyline = osrm_polyline
            road_km = osrm_km or fallback_road_km
        else:
            final_polyline = waypoint_pts
            road_km = fallback_road_km

        eta_minutes = max(1, round((road_km / avg_speed_kmh) * 60 + turnout_minutes))

        return {
            "status": "success",
            "distance_km": road_km,
            "eta_minutes": eta_minutes,
            "response_mode": "Routine (Code 1)" if is_routine else "Emergency (Code 3)",
            "origin": {"lat": start_lat, "lng": start_lng},
            "destination": {"lat": dest_lat, "lng": dest_lng},
            "polyline": final_polyline
        }

