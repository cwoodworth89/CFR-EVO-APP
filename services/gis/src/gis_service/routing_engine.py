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
        "southbound_apron": {
            "lat": 49.2905,
            "lng": -122.7915,
        },
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

# 3-Tier Apparatus Physics Profiles
APPARATUS_TIERS: Dict[str, Dict[str, Any]] = {
    "light": {
        "key": "LIGHT",
        "name": "Light Apparatus",
        "weight_tons": 5,
        "speed_code3_kmh": 52.0,
        "speed_code1_kmh": 38.0,
        "road_factor_code3": 1.25,
        "road_factor_code1": 1.35,
        "turn_penalty_sec": 3.0,
    },
    "general": {
        "key": "GENERAL",
        "name": "General Apparatus",
        "weight_tons": 22,
        "speed_code3_kmh": 45.0,
        "speed_code1_kmh": 32.0,
        "road_factor_code3": 1.35,
        "road_factor_code1": 1.45,
        "turn_penalty_sec": 5.0,
    },
    "heavy": {
        "key": "HEAVY",
        "name": "Heavy Apparatus",
        "weight_tons": 35,
        "speed_code3_kmh": 38.0,
        "speed_code1_kmh": 28.0,
        "road_factor_code3": 1.45,
        "road_factor_code1": 1.55,
        "turn_penalty_sec": 8.0,
    },
}


def get_unit_type(unit: str) -> str:
    """Returns clean, real-world apparatus type for Coquitlam Fire Rescue."""
    u = str(unit).strip().upper()
    if u.startswith('SQ') or 'SQUAD' in u:
        return 'Squad'
    if u.startswith('LAV'):
        return 'Light Attack Vehicle'
    if u.startswith('TOWER') or u.startswith('PLATFORM') or u.startswith('L') or 'LADDER' in u:
        return 'Ladder'
    if u.startswith('WT') or u.startswith('T') or 'TENDER' in u or 'TANKER' in u:
        return 'Water Tender'
    if u.startswith('E') or 'ENGINE' in u or 'PUMPER' in u:
        return 'Engine'
    if u.startswith('R') or 'RESCUE' in u:
        return 'Rescue'
    if u.startswith('Q') or 'QUINT' in u:
        return 'Quint'
    if u.startswith('C') or u.startswith('CAR') or u.startswith('CHIEF') or 'COMMAND' in u:
        return 'Chief'
    if u.startswith('M') or 'MEDIC' in u:
        return 'Medic'
    if u.startswith('S') or 'SPECIALTY' in u:
        return 'Specialty'
    return 'Apparatus'


def get_apparatus_profile_class(unit_str: str) -> str:
    """
    Classifies apparatus into 3-tier routing profile classes:
      - light: Squad (SQ1-4), Medic (M1), Command (C1, C10, CAR, CHIEF), LAV, Specialty (S1-4)
      - general: Engine (E1-4), Rescue (R1-4), Quint (Q5), Pumper
      - heavy: Ladder (L1-4, Tower Platform), Water Tender (T1-4, WT4)
    """
    u = str(unit_str).strip().upper()
    if u.startswith('SQ') or 'SQUAD' in u:
        return "light"
    if u.startswith('LAV'):
        return "light"
    if u.startswith('C') or u.startswith('CAR') or u.startswith('CHIEF') or 'COMMAND' in u:
        return "light"
    if u.startswith('M') or 'MEDIC' in u:
        return "light"
    if u.startswith('S') or 'SPECIALTY' in u:
        return "light"
    if u.startswith('L') or 'LADDER' in u or 'TOWER' in u or 'PLATFORM' in u:
        return "heavy"
    if u.startswith('WT') or u.startswith('T') or 'TENDER' in u or 'TANKER' in u:
        return "heavy"
    if u.startswith('E') or 'ENGINE' in u or 'PUMPER' in u or u.startswith('R') or 'RESCUE' in u or u.startswith('Q') or 'QUINT' in u:
        return "general"
    return "general"


def get_unit_station_id(unit_str: str) -> str:
    """Extracts home station ID from unit abbreviation (e.g. M1 -> 1, E2 -> 2, Q5 -> 3, WT4 -> 4)."""
    clean_unit = str(unit_str).strip().upper()
    if re.match(r'^(E2|L2|R2|SQ2|T2|WT2)', clean_unit):
        return "2"
    if re.match(r'^(E3|Q5|H3|HT3|S3|SQ3)', clean_unit):
        return "3"
    if re.match(r'^(E4|T4|WT4|LAV4|SQ4)', clean_unit):
        return "4"
    match = re.search(r'\d+', clean_unit)
    if match:
        station_num = match.group(0)
        if station_num in FIRE_HALLS:
            return station_num
    return "1"


class EVORoutingEngine:
    """
    Two-Phase Emergency Apparatus Routing Engine for Coquitlam Fire Rescue.
    
    Phase 1: Pure OSRM street network route finding with vehicle momentum preservation (continue_straight=true)
             and station apron departure geometry.
    Phase 2: Apparatus-aware ETA assessment, road physics, turn penalties, and EMTRAC signal preemption.
    """
    def __init__(self, default_station_id: str = "1"):
        self.default_hall_key = str(default_station_id) if str(default_station_id) in FIRE_HALLS else "1"
        self.default_hall = FIRE_HALLS[self.default_hall_key]

    def get_hall_location(self, hall_key: Optional[str] = None) -> Dict[str, Any]:
        key = str(hall_key) if str(hall_key) in FIRE_HALLS else self.default_hall_key
        return FIRE_HALLS.get(key, self.default_hall)

    def calculate_distance_km(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Haversine great-circle distance in kilometers."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
        return R * c

    def _get_osrm_endpoints(self, loc_str: str) -> List[str]:
        """Constructs prioritized candidate endpoints with continue_straight=true for vehicle forward momentum preservation."""
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
        """Phase 1: Queries OSRM for optimal street polyline and road distance."""
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
        response_type: str = "emergency",
        road_distance_km: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Phase 2: Calculates apparatus dynamics, road distance, and ETA for a specific unit from its Home Fire Hall.

        3-Tier Apparatus Profiles:
          - Light (5 tons): Squad (SQ1-4), Medic (M1), Command (C1, C10), LAV -> 52 km/h Code 3, 1.25x road factor, 3s turn penalty
          - General (22 tons): Engine (E1-4), Rescue (R1-4), Quint (Q5), Pumper -> 45 km/h Code 3, 1.35x road factor, 5s turn penalty
          - Heavy (35 tons): Ladder (L1-4), Tower Platform, Water Tender (T1-4, WT4) -> 38 km/h Code 3, 1.45x road factor, 8s turn penalty
        """
        clean_unit = str(unit).strip().upper()
        station_id = get_unit_station_id(clean_unit)
        hall = self.get_hall_location(station_id)
        profile_class = get_apparatus_profile_class(clean_unit)
        tier_data = APPARATUS_TIERS.get(profile_class, APPARATUS_TIERS["general"])
        
        crow_km = self.calculate_distance_km(hall["lat"], hall["lng"], dest_lat, dest_lng)
        is_routine = str(response_type).lower().strip() == "routine"

        if is_routine:
            avg_speed_kmh = tier_data["speed_code1_kmh"]
            road_factor = tier_data["road_factor_code1"]
        else:
            avg_speed_kmh = tier_data["speed_code3_kmh"]
            road_factor = tier_data["road_factor_code3"]

        turn_penalty_sec = tier_data["turn_penalty_sec"]
        turnout_minutes = 0.0

        if road_distance_km is not None and road_distance_km > 0:
            road_km = round(road_distance_km, 2)
        else:
            road_km = round(crow_km * road_factor, 2)

        est_turns = round(road_km * 1.2)
        turn_delay_min = (est_turns * turn_penalty_sec) / 60.0
        travel_time_min = (road_km / avg_speed_kmh) * 60.0 + turn_delay_min + turnout_minutes
        eta_minutes = max(1, round(travel_time_min))

        return {
            "unit": clean_unit,
            "unit_type": get_unit_type(clean_unit),
            "apparatus_class": profile_class,
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
        response_type: str = "emergency",
        unit: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculates origin-to-destination response route using 2-phase architecture:
          Phase 1: Pure OSRM street network routing with station apron exit alignment.
          Phase 2: Apparatus dynamics and ETA calculation on the resulting polyline distance.
        """
        if start_lat is None or start_lng is None:
            hall_key = station_id or (get_unit_station_id(unit) if unit else self.default_hall_key)
            hall = self.get_hall_location(hall_key)
            start_lat = hall["lat"]
            start_lng = hall["lng"]

        is_routine = str(response_type).lower().strip() == "routine"
        profile_class = get_apparatus_profile_class(unit) if unit else "general"
        tier_data = APPARATUS_TIERS.get(profile_class, APPARATUS_TIERS["general"])

        if is_routine:
            avg_speed_kmh = tier_data["speed_code1_kmh"]
            road_factor = tier_data["road_factor_code1"]
        else:
            avg_speed_kmh = tier_data["speed_code3_kmh"]
            road_factor = tier_data["road_factor_code3"]

        turn_penalty_sec = tier_data["turn_penalty_sec"]

        # Station 1 Dual-Carriageway Apron Resolution:
        # Station 1 (1300 Pinetree Way) sits on the east side of Pinetree Way (divided arterial).
        # For southbound calls (dest_lat < 49.290), depart from the Southbound Apron Exit (49.2905, -122.7915)
        # to cleanly enter the divided carriageway without median snapping traps or U-turn loops.
        is_hall_1 = (abs(start_lat - 49.291) < 0.008 and abs(start_lng - (-122.790)) < 0.008) or (str(station_id) == "1")

        departure_lat = start_lat
        departure_lng = start_lng
        if is_hall_1 and dest_lat < 49.290:
            departure_lat = 49.2905
            departure_lng = -122.7915

        # Phase 1: Pure OSRM route pathfinding (No brittle intermediate waypoint injections!)
        waypoint_pts = [[departure_lat, departure_lng], [dest_lat, dest_lng]]
        osrm_polyline, osrm_km = self._fetch_osrm_polyline(waypoint_pts)

        dist_km = self.calculate_distance_km(departure_lat, departure_lng, dest_lat, dest_lng)
        fallback_road_km = round(dist_km * road_factor, 2)

        if osrm_polyline and len(osrm_polyline) >= 2:
            final_polyline = osrm_polyline
            road_km = osrm_km if osrm_km is not None else fallback_road_km
        else:
            final_polyline = waypoint_pts
            road_km = fallback_road_km

        # Phase 2: Apparatus ETA Dynamics on road distance
        est_turns = round(road_km * 1.2)
        turn_delay_min = (est_turns * turn_penalty_sec) / 60.0
        travel_time_min = (road_km / avg_speed_kmh) * 60.0 + turn_delay_min
        eta_minutes = max(1, round(travel_time_min))

        return {
            "status": "success",
            "distance_km": road_km,
            "eta_minutes": eta_minutes,
            "response_mode": "Routine (Code 1)" if is_routine else "Emergency (Code 3)",
            "origin": {"lat": departure_lat, "lng": departure_lng},
            "destination": {"lat": dest_lat, "lng": dest_lng},
            "polyline": final_polyline
        }
