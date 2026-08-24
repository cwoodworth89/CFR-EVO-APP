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

# 3-Tier Apparatus Physics Profiles.
#
# NOT CURRENTLY APPLIED. Routing runs on stock OSRM: distance and duration come
# straight from the router. This table is retained as the seed data for the
# planned CFR customized route configuration feature, which will layer apparatus
# adjustments on top of the OSRM baseline. Do not wire it back in ad hoc.
#
# PROVENANCE REQUIRED (CLAUDE.md 6.3): the speed, road-factor, and turn-penalty
# figures below are inherited and currently carry no cited source. Before this data
# is applied to any operational output it must be sourced -- NFPA 1710 response-time
# objectives, department policy, or measurement on this system -- or replaced.
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
             and hall front-apron departure geometry.
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
        """Constructs prioritized OSRM endpoints using stock routing parameters.

        No continue_straight override: OSRM's default lets the profile decide, which
        is correct for point-to-point routing. Forcing it to true forbids U-turns at
        via points and can introduce large detours on multi-waypoint queries.
        """
        query_params = "overview=full&geometries=geojson&steps=true"

        # Offline-first (CLAUDE.md S1): the public OSRM demo server is opt-in only.
        disable_wan = os.environ.get("DISABLE_WAN_FALLBACK", "true").lower() in ("true", "1", "yes")

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

    def _fetch_osrm_route(self, waypoints: List[List[float]]) -> Tuple[Optional[List[List[float]]], Optional[float], Optional[float]]:
        """Queries OSRM and returns (polyline, distance_km, duration_min) as reported by the router.

        OSRM computes duration from per-segment speeds, road classification, and real
        turn costs on the actual graph. It is the authoritative travel-time answer;
        we do not recompute it.
        """
        if not waypoints or len(waypoints) < 2:
            return None, None, None
        
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
                            dur_min = round(route["duration"] / 60.0, 2)
                            return lat_lngs, dist_km, dur_min
            except Exception as e:
                logging.debug(f"OSRM query attempt failed for {url}: {e}")

        return None, None, None

    def calculate_unit_metrics(
        self,
        unit: str,
        dest_lat: float,
        dest_lng: float,
        response_type: str = "emergency",
        road_distance_km: Optional[float] = None
    ) -> Dict[str, Any]:
        """Returns OSRM routing metrics for one unit, from its home hall to the incident.

        Stock OSRM: distance and ETA are the router's own figures. Apparatus-class
        adjustments are deliberately not applied here (see APPARATUS_TIERS).

        If OSRM is unreachable, distance falls back to great-circle and eta_minutes is
        None. An unknown ETA is reported as unknown, never as a plausible estimate.
        """
        clean_unit = str(unit).strip().upper()
        station_id = get_unit_station_id(clean_unit)
        hall = self.get_hall_location(station_id)

        crow_km = self.calculate_distance_km(hall["lat"], hall["lng"], dest_lat, dest_lng)
        # Anything that is not the literal "routine" — including an unparsed None — routes at
        # emergency speed. Operator decision 2026-08-23 (CLAUDE.md §6.3 tier 4, department
        # operational policy): most calls are emergency and time-critical, so emergency speed
        # is the conservative assumption when the response type is unknown.
        #
        # This is a stated assumption in the *calculation*, not a stored value. The parsed
        # response type stays NULL in `target` and the kiosk shows it as UNKNOWN on an amber
        # border — do not write "emergency" back to the record to make this simpler.
        # See punch-list #31.
        is_routine = str(response_type).lower().strip() == "routine"

        if road_distance_km is not None and road_distance_km > 0:
            # Caller already resolved the road distance via OSRM for this origin.
            road_km = round(road_distance_km, 2)
            _, _, dur_min = self._fetch_osrm_route(
                [[hall["lat"], hall["lng"]], [dest_lat, dest_lng]]
            )
        else:
            _, osrm_km, dur_min = self._fetch_osrm_route(
                [[hall["lat"], hall["lng"]], [dest_lat, dest_lng]]
            )
            road_km = osrm_km if osrm_km is not None else round(crow_km, 2)

        eta_minutes = max(1, round(dur_min)) if dur_min is not None else None
        routing_source = "osrm" if dur_min is not None else "degraded_no_router"

        return {
            "unit": clean_unit,
            "unit_type": get_unit_type(clean_unit),
            "apparatus_class": get_apparatus_profile_class(clean_unit),
            "origin_hall": hall["id"],
            "hall_name": hall["name"],
            "hall_address": hall["address"],
            "origin_coords": [hall["lat"], hall["lng"]],
            "destination_coords": [dest_lat, dest_lng],
            "crow_distance_km": round(crow_km, 2),
            "road_distance_km": road_km,
            "eta_minutes": eta_minutes,
            "routing_source": routing_source,
            "response_mode": "Routine (Code 1)" if is_routine else "Emergency (Code 3)",
            "calculated_at": datetime.now(timezone.utc).isoformat()
        }

    def _nearest_destination(self, unit: str,
                             options: List[List[float]]) -> Optional[List[float]]:
        """The [lng, lat] option closest to this unit's hall, by straight-line distance.

        Straight-line rather than a routed distance on purpose: this only has to pick
        which end of a section to aim at, and asking OSRM for a route to every endpoint
        of every section for every unit would multiply routing calls for a choice that
        the crow-flies answer gets right. The route that is actually reported is still
        OSRM's, to the chosen end (CLAUDE.md 6.2).
        """
        import math
        if not options:
            return None
        hall = self.get_hall_location(get_unit_station_id(str(unit).strip().upper()))
        o_lat = (hall or {}).get('lat')
        o_lng = (hall or {}).get('lng')
        if o_lat is None or o_lng is None:
            return options[0]

        def d(opt):
            R = 6371000.0
            p1, p2 = math.radians(float(o_lat)), math.radians(float(opt[1]))
            dp = p2 - p1
            dl = math.radians(float(opt[0]) - float(o_lng))
            h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
            return 2 * R * math.asin(math.sqrt(h))

        return min(options, key=d)

    def calculate_units_routing(
        self,
        responding_units: List[str],
        dest_lat: Optional[float],
        dest_lng: Optional[float],
        response_type: str = "emergency",
        destination_options: Optional[List[List[float]]] = None
    ) -> List[Dict[str, Any]]:
        """Calculates routing metrics for a list of responding units.

        `destination_options` is used when the location is a street SECTION rather than a
        point (a "<street> and <street>" dispatch with no cross street -- see
        SpatialQueryEngine.resolve_street_section_in_grid). Each entry is a [lng, lat]
        end of the highlighted section, and every unit is routed to whichever end is
        nearest ITS OWN hall, so a crew arrives at the near edge of the section and works
        along it rather than driving to a midpoint that may already be past the incident.
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
                    u_lat, u_lng = dest_lat, dest_lng
                    if destination_options:
                        picked = self._nearest_destination(clean, destination_options)
                        if picked:
                            u_lng, u_lat = picked
                    m = self.calculate_unit_metrics(clean, u_lat, u_lng, response_type=response_type)
                    if destination_options:
                        m['destination_note'] = (
                            'Street section: routed to the nearer end of the highlighted '
                            'stretch, not to a located incident.'
                        )
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
        """Calculates the hall-to-incident response route using stock OSRM.

        Distance, duration, and geometry are the router's own output. If OSRM is
        unreachable the result is marked degraded: a straight-line placeholder
        geometry with great-circle distance and eta_minutes = None.
        """
        if start_lat is None or start_lng is None:
            hall_key = station_id or (get_unit_station_id(unit) if unit else self.default_hall_key)
            hall = self.get_hall_location(hall_key)
            start_lat = hall["lat"]
            start_lng = hall["lng"]

        # Anything that is not the literal "routine" — including an unparsed None — routes at
        # emergency speed. Operator decision 2026-08-23 (CLAUDE.md §6.3 tier 4, department
        # operational policy): most calls are emergency and time-critical, so emergency speed
        # is the conservative assumption when the response type is unknown.
        #
        # This is a stated assumption in the *calculation*, not a stored value. The parsed
        # response type stays NULL in `target` and the kiosk shows it as UNKNOWN on an amber
        # border — do not write "emergency" back to the record to make this simpler.
        # See punch-list #31.
        is_routine = str(response_type).lower().strip() == "routine"

        # Departure is always the hall's verified front-apron GPS coordinate.
        # Direction of travel is OSRM's job, not ours: the router decides how to
        # leave the apron based on the actual road network.
        waypoint_pts = [[start_lat, start_lng], [dest_lat, dest_lng]]
        osrm_polyline, osrm_km, osrm_min = self._fetch_osrm_route(waypoint_pts)

        if osrm_polyline and len(osrm_polyline) >= 2:
            final_polyline = osrm_polyline
            road_km = osrm_km
            eta_minutes = max(1, round(osrm_min)) if osrm_min is not None else None
            status = "success"
            routing_source = "osrm"
        else:
            final_polyline = waypoint_pts
            road_km = round(self.calculate_distance_km(start_lat, start_lng, dest_lat, dest_lng), 2)
            eta_minutes = None
            status = "degraded"
            routing_source = "degraded_no_router"

        return {
            "status": status,
            "routing_source": routing_source,
            "distance_km": road_km,
            "eta_minutes": eta_minutes,
            "response_mode": "Routine (Code 1)" if is_routine else "Emergency (Code 3)",
            "origin": {"lat": start_lat, "lng": start_lng},
            "destination": {"lat": dest_lat, "lng": dest_lng},
            "polyline": final_polyline
        }
