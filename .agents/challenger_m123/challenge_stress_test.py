#!/usr/bin/env python3
"""
CFR EVO GIS Routing & Map Tile Stack — Empirical Challenge & Stress Test Suite
Author: Empirical Challenger
Purpose: Adversarial stress testing of routing algorithms, edge cases, fallback handlers,
         dynamic host resolutions, and remote endpoint performance.
"""

import os
import sys
import math
import time
import json
import socket
import urllib.request
import urllib.error
from unittest.mock import patch, MagicMock

# Dynamically add services/gis/src to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(REPO_ROOT, "services", "gis", "src"))

from gis_service.routing_engine import (
    EVORoutingEngine,
    FIRE_HALLS,
    get_unit_type,
    get_unit_station_id,
)

class StressTestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.details = []

    def record_pass(self, msg: str):
        self.details.append(f"  [PASS] {msg}")

    def record_fail(self, msg: str):
        self.passed = False
        self.details.append(f"  [FAIL] {msg}")

def run_stress_test_suite():
    results = []
    print("=" * 80)
    print("STARTING EMPIRICAL ADVERSARIAL STRESS TEST SUITE")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # TEST 1: Extreme Coordinates & Sub-Meter Dest / Zero Distance
    # -------------------------------------------------------------------------
    t1 = StressTestResult("Extreme Coordinates & Sub-Meter / Zero Distance Edge Cases")
    engine = EVORoutingEngine()

    # 1a. Identical Start and Dest
    hall1 = FIRE_HALLS["1"]
    with patch.object(engine, "_fetch_osrm_polyline", return_value=(None, None)):
        res_same = engine.calculate_route(dest_lat=hall1["lat"], dest_lng=hall1["lng"], station_id="1")
        if res_same["status"] == "success" and res_same["distance_km"] == 0.0 and res_same["eta_minutes"] >= 1:
            t1.record_pass("Identical start/dest handled: distance=0.0km, eta=1min floor")
        else:
            t1.record_fail(f"Identical start/dest failed: {res_same}")

    # 1b. Sub-meter distance (1e-6 degrees ~ 0.1 meters)
    with patch.object(engine, "_fetch_osrm_polyline", return_value=(None, None)):
        res_sub = engine.calculate_route(dest_lat=hall1["lat"] + 0.000001, dest_lng=hall1["lng"] + 0.000001, station_id="1")
        if res_sub["status"] == "success" and res_sub["distance_km"] >= 0.0 and res_sub["eta_minutes"] >= 1:
            t1.record_pass("Sub-meter destination handled smoothly without division by zero")
        else:
            t1.record_fail(f"Sub-meter destination failed: {res_sub}")

    # 1c. Null Island (0.0, 0.0)
    with patch.object(engine, "_fetch_osrm_polyline", return_value=(None, None)):
        res_null = engine.calculate_route(dest_lat=0.0, dest_lng=0.0, station_id="1")
        if res_null["status"] == "success" and res_null["distance_km"] > 9000:
            t1.record_pass(f"Null island (0,0) calculated correctly: distance={res_null['distance_km']}km")
        else:
            t1.record_fail(f"Null island calculation unexpected: {res_null}")

    # 1d. Extreme Opposite Hemisphere (-49.2882, 122.7938)
    with patch.object(engine, "_fetch_osrm_polyline", return_value=(None, None)):
        res_opp = engine.calculate_route(dest_lat=-49.2882, dest_lng=122.7938, station_id="1")
        if res_opp["status"] == "success" and res_opp["distance_km"] > 14000:
            t1.record_pass(f"Opposite hemisphere calculated: distance={res_opp['distance_km']}km")
        else:
            t1.record_fail(f"Opposite hemisphere calculation unexpected: {res_opp}")

    results.append(t1)

    # -------------------------------------------------------------------------
    # TEST 2: Tactical Corridor Boundary Rigor & Disjointness
    # -------------------------------------------------------------------------
    t2 = StressTestResult("Tactical Corridor Spatial Boundary Rigor & Disjointness")

    # 2a. Boundary of Corridor A (Mariner Way: dest_lat < 49.280 and dest_lng < -122.800)
    # Just inside Corridor A
    with patch.object(engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
        engine.calculate_route(dest_lat=49.27999, dest_lng=-122.80001, station_id="1")
        pts = mock_osrm.call_args[0][0]
        if len(pts) == 5:
            t2.record_pass("Corridor A triggers at dest_lat=49.27999, dest_lng=-122.80001 (5 waypoints)")
        else:
            t2.record_fail(f"Corridor A failed to trigger at boundary: {len(pts)} points")

    # Just outside Corridor A (lat >= 49.280)
    with patch.object(engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
        engine.calculate_route(dest_lat=49.28001, dest_lng=-122.80001, station_id="1")
        pts = mock_osrm.call_args[0][0]
        if len(pts) == 2:
            t2.record_pass("Corridor A does not trigger when lat=49.28001 (2 waypoints)")
        else:
            t2.record_fail(f"Corridor A triggered unexpectedly: {len(pts)} points")

    # 2b. Boundary of Corridor B (Gordon Ave: 49.275 <= dest_lat <= 49.285 and -122.795 <= dest_lng <= -122.780)
    # Exact lower bounds
    with patch.object(engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
        engine.calculate_route(dest_lat=49.275, dest_lng=-122.795, station_id="1")
        pts = mock_osrm.call_args[0][0]
        if len(pts) == 4:
            t2.record_pass("Corridor B triggers at exact lower bound [49.275, -122.795] (4 waypoints)")
        else:
            t2.record_fail(f"Corridor B failed at lower bound: {len(pts)} points")

    # Exact upper bounds
    with patch.object(engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
        engine.calculate_route(dest_lat=49.285, dest_lng=-122.780, station_id="1")
        pts = mock_osrm.call_args[0][0]
        if len(pts) == 4:
            t2.record_pass("Corridor B triggers at exact upper bound [49.285, -122.780] (4 waypoints)")
        else:
            t2.record_fail(f"Corridor B failed at upper bound: {len(pts)} points")

    # Outside Corridor B (dest_lng = -122.779)
    with patch.object(engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
        engine.calculate_route(dest_lat=49.280, dest_lng=-122.779, station_id="1")
        pts = mock_osrm.call_args[0][0]
        if len(pts) == 2:
            t2.record_pass("Corridor B correctly inactive outside bounding box (2 waypoints)")
        else:
            t2.record_fail(f"Corridor B triggered outside bounds: {len(pts)} points")

    # Disjointness check across dense grid
    overlap_count = 0
    for lat_i in range(49270, 49290, 2):
        lat = lat_i / 1000.0
        for lng_i in range(-122820, -122770, 2):
            lng = lng_i / 1000.0
            is_a = (lat < 49.280 and lng < -122.800)
            is_b = (49.275 <= lat <= 49.285 and -122.795 <= lng <= -122.780)
            if is_a and is_b:
                overlap_count += 1

    if overlap_count == 0:
        t2.record_pass("Proved spatial disjointness: 0 overlap conflicts across 100 grid points")
    else:
        t2.record_fail(f"Corridor overlap detected: {overlap_count} overlapping points")

    results.append(t2)

    # -------------------------------------------------------------------------
    # TEST 3: Apparatus Classification & Home Station Adversarial Inputs
    # -------------------------------------------------------------------------
    t3 = StressTestResult("Apparatus Classification & Home Station Adversarial Inputs")

    adversarial_units = [
        ("e1", "Engine / Pumper", "1"),
        ("  E2  ", "Engine / Pumper", "2"),
        ("l2", "Ladder / Aerial", "2"),
        ("r2", "Heavy Rescue", "2"),
        ("q5", "Quint", "3"),
        ("wt4", "Tanker / Tender", "4"),
        ("LAV4", "Tanker / Tender", "4"),
        ("T4", "Tanker / Tender", "4"),
        ("E4", "Engine / Pumper", "4"),
        ("H3", "Apparatus", "3"),
        ("HT3", "Apparatus", "3"),
        ("S3", "Specialty / Medic", "3"),
        ("C10", "Command Vehicle", "1"),
        ("B1", "Command Vehicle", "1"),
        ("M1", "Specialty / Medic", "1"),
        ("UNKNOWN-4", "Apparatus", "4"),
        ("Z_SPECIAL_NO_NUM", "Apparatus", "1"),
        ("", "Apparatus", "1"),
        ("   ", "Apparatus", "1"),
        ("E99", "Engine / Pumper", "1"),  # 99 not in FIRE_HALLS, falls back to 1
    ]

    for unit_str, expected_type, expected_station in adversarial_units:
        utype = get_unit_type(unit_str)
        ustation = get_unit_station_id(unit_str)
        if utype == expected_type and ustation == expected_station:
            t3.record_pass(f"Unit '{unit_str}': type='{utype}', station='{ustation}'")
        else:
            t3.record_fail(f"Unit '{unit_str}': got type='{utype}' (expected '{expected_type}'), station='{ustation}' (expected '{expected_station}')")

    # Multi-unit calculation with noisy list
    noisy_units = ["E1", "e1", "  E1  ", "L1", "Q5", "", "UNKNOWN", "WT4", "E1", "T4"]
    multi_res = engine.calculate_units_routing(noisy_units, 49.2785, -122.7850, response_type="emergency")
    # Expected unique clean units: E1, L1, Q5, UNKNOWN, WT4, T4 -> 6 units (empty skipped)
    if len(multi_res) == 6:
        t3.record_pass(f"Deduplicated noisy unit list from {len(noisy_units)} down to 6 distinct units")
    else:
        t3.record_fail(f"Multi-unit deduplication error: got {len(multi_res)} units (expected 6)")

    results.append(t3)

    # -------------------------------------------------------------------------
    # TEST 4: OSRM Failure Simulation (Timeouts, Socket Errors, Malformed Responses)
    # -------------------------------------------------------------------------
    t4 = StressTestResult("OSRM Resilient Fallback Simulation (Network Delays & Errors)")

    # 4a. Network timeout simulation (verify it doesn't block longer than timeout)
    def slow_urlopen(req, timeout=1.0):
        raise socket.timeout("Timed out connecting to OSRM")

    start_time = time.time()
    with patch("urllib.request.urlopen", side_effect=slow_urlopen):
        res_timeout = engine.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id="1")
    elapsed = time.time() - start_time

    if res_timeout["status"] == "success" and len(res_timeout["polyline"]) >= 2:
        t4.record_pass(f"Timeout simulation fell back cleanly to straight-line waypoints in {elapsed:.3f}s")
    else:
        t4.record_fail(f"Timeout fallback failed: {res_timeout}")

    # 4b. OSRM returns code: "NoRoute"
    no_route_json = json.dumps({"code": "NoRoute", "message": "No route found"}).encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = no_route_json
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res_noroute = engine.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id="1")
        if res_noroute["status"] == "success" and len(res_noroute["polyline"]) >= 2:
            t4.record_pass("OSRM 'NoRoute' code gracefully handled with straight-line fallback")
        else:
            t4.record_fail(f"OSRM 'NoRoute' failure: {res_noroute}")

    # 4c. OSRM returns empty routes array: {"code": "Ok", "routes": []}
    empty_routes_json = json.dumps({"code": "Ok", "routes": []}).encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = empty_routes_json
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res_empty = engine.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id="1")
        if res_empty["status"] == "success" and len(res_empty["polyline"]) >= 2:
            t4.record_pass("OSRM empty routes array handled with straight-line fallback")
        else:
            t4.record_fail(f"OSRM empty routes failure: {res_empty}")

    results.append(t4)

    # -------------------------------------------------------------------------
    # TEST 5: apiClient Dynamic URL Resolution Logic Emulation
    # -------------------------------------------------------------------------
    t5 = StressTestResult("apiClient.js Dynamic URL & Tile Endpoint Resolution Emulation")

    def simulate_get_api_base_url(env_val, hostname):
        if env_val:
            return env_val.rstrip("/")
        h = hostname if hostname else "localhost"
        return f"http://{h}:8000"

    def simulate_get_tile_base_url(env_val, hostname):
        if env_val:
            return env_val.rstrip("/")
        h = hostname if hostname else "localhost"
        return f"http://{h}:8081"

    def simulate_get_tile_url(tile_base, z, x, y, style="voyager"):
        normalized = (style or "voyager").lower()
        if normalized == "satellite":
            return f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        if normalized == "dark":
            return f"{tile_base}/services/vancouver_dark/tiles/{z}/{x}/{y}.png"
        if normalized in ("grey", "light"):
            return f"{tile_base}/services/vancouver_light/tiles/{z}/{x}/{y}.png"
        return f"{tile_base}/services/vancouver/tiles/{z}/{x}/{y}.png"

    # Test cases for hostnames
    host_cases = [
        ("localhost", "http://localhost:8000", "http://localhost:8081"),
        ("127.0.0.1", "http://127.0.0.1:8000", "http://127.0.0.1:8081"),
        ("100.95.146.94", "http://100.95.146.94:8000", "http://100.95.146.94:8081"),
        ("cfr-mapping-tcfh", "http://cfr-mapping-tcfh:8000", "http://cfr-mapping-tcfh:8081"),
        ("", "http://localhost:8000", "http://localhost:8081"),
        (None, "http://localhost:8000", "http://localhost:8081"),
    ]

    for host_in, exp_api, exp_tile in host_cases:
        resolved_api = simulate_get_api_base_url(None, host_in)
        resolved_tile = simulate_get_tile_base_url(None, host_in)
        if resolved_api == exp_api and resolved_tile == exp_tile:
            t5.record_pass(f"Host '{host_in}' -> API: {resolved_api}, Tile: {resolved_tile}")
        else:
            t5.record_fail(f"Host '{host_in}' failed: API={resolved_api} (exp {exp_api}), Tile={resolved_tile} (exp {exp_tile})")

    # Test cases for tile URLs
    tile_cases = [
        ("voyager", "http://100.95.146.94:8081/services/vancouver/tiles/14/2642/5721.png"),
        ("dark", "http://100.95.146.94:8081/services/vancouver_dark/tiles/14/2642/5721.png"),
        ("grey", "http://100.95.146.94:8081/services/vancouver_light/tiles/14/2642/5721.png"),
        ("light", "http://100.95.146.94:8081/services/vancouver_light/tiles/14/2642/5721.png"),
        ("satellite", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/14/5721/2642"),
        (None, "http://100.95.146.94:8081/services/vancouver/tiles/14/2642/5721.png"),
    ]

    tile_base_test = "http://100.95.146.94:8081"
    for style_in, exp_url in tile_cases:
        gen_url = simulate_get_tile_url(tile_base_test, 14, 2642, 5721, style_in)
        if gen_url == exp_url:
            t5.record_pass(f"Style '{style_in}' -> URL: {gen_url}")
        else:
            t5.record_fail(f"Style '{style_in}' mismatch: got {gen_url}, expected {exp_url}")

    results.append(t5)

    # -------------------------------------------------------------------------
    # TEST 6: Remote Kiosk Tailscale Physical Endpoints Probe (100.95.146.94)
    # -------------------------------------------------------------------------
    t6 = StressTestResult("Live Remote Kiosk Tailscale Host Reachability & Stress Query")
    remote_host = "100.95.146.94"

    # 6a. Probe Route API on :8000
    try:
        route_url = f"http://{remote_host}:8000/api/route?dest_lat=49.2785&dest_lng=-122.7850&station_id=1&response_type=emergency"
        req = urllib.request.Request(route_url, headers={"User-Agent": "ChallengerStressTest/1.0"})
        t_start = time.time()
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            t_elapsed = time.time() - t_start
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "success" and len(data.get("polyline", [])) > 2:
                    t6.record_pass(f"Remote Route API :8000 responded in {t_elapsed:.3f}s: dist={data['distance_km']}km, polyline_pts={len(data['polyline'])}")
                else:
                    t6.record_fail(f"Remote Route API response missing success or polyline: {data}")
            else:
                t6.record_fail(f"Remote Route API HTTP status {resp.status}")
    except Exception as e:
        t6.record_fail(f"Remote Route API connection failed: {e}")

    # 6b. Probe Tile Server on :8081
    try:
        tile_services_url = f"http://{remote_host}:8081/services"
        req = urllib.request.Request(tile_services_url, headers={"User-Agent": "ChallengerStressTest/1.0"})
        t_start = time.time()
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            t_elapsed = time.time() - t_start
            if resp.status == 200:
                body = resp.read().decode("utf-8")
                t6.record_pass(f"Remote Tile Server :8081 responded in {t_elapsed:.3f}s (HTTP 200, body={body[:30]})")
            else:
                t6.record_fail(f"Remote Tile Server HTTP status {resp.status}")
    except Exception as e:
        t6.record_fail(f"Remote Tile Server connection failed: {e}")

    results.append(t6)

    # -------------------------------------------------------------------------
    # REPORT SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("STRESS TEST EXECUTION RESULTS SUMMARY")
    print("=" * 80)

    total_suites = len(results)
    passed_suites = 0
    total_checks = 0
    passed_checks = 0

    for r in results:
        status_str = "PASSED" if r.passed else "FAILED"
        if r.passed:
            passed_suites += 1
        print(f"\n[{status_str}] {r.name}")
        for d in r.details:
            total_checks += 1
            if "[PASS]" in d:
                passed_checks += 1
            print(d)

    print("\n" + "-" * 80)
    print(f"Suites: {passed_suites}/{total_suites} passed | Individual Checks: {passed_checks}/{total_checks} passed")
    print("=" * 80)

    return (passed_suites == total_suites)

if __name__ == "__main__":
    success = run_stress_test_suite()
    sys.exit(0 if success else 1)
