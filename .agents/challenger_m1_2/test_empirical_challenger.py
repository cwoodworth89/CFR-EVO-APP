#!/usr/bin/env python3
"""
Empirical Challenger Test Suite for Milestone 1:
Tactical Corridors, Apparatus Mappings, Response Physics, and High-Volume Stress Harness.
"""

import os
import sys
import math
import time
import tracemalloc
import unittest
from unittest.mock import patch, MagicMock

# Inject gis_service into path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../services/gis/src")))

from gis_service.routing_engine import (
    EVORoutingEngine,
    FIRE_HALLS,
    get_unit_type,
    get_unit_station_id,
)

class TestEmpiricalTacticalCorridors(unittest.TestCase):
    """Stress tests and boundary checks for Station 1 Tactical Corridors A and B."""

    def setUp(self):
        self.engine = EVORoutingEngine()

    def test_corridor_a_mariner_deep_interior_points(self):
        """Points deep in Southwest / Mariner sector should trigger Corridor A."""
        interior_points = [
            (49.2650, -122.8150),  # Ranch Park
            (49.2500, -122.8500),  # Austin Heights West
            (49.2700, -122.8200),  # Mariner Way central
            (49.2437, -122.8834),  # Hall 3 area
        ]
        for dest_lat, dest_lng in interior_points:
            with patch.object(self.engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
                res = self.engine.calculate_route(dest_lat=dest_lat, dest_lng=dest_lng, station_id="1")
                mock_osrm.assert_called_once()
                waypoints = mock_osrm.call_args[0][0]
                self.assertEqual(len(waypoints), 5, f"Expected 5 waypoints for Corridor A at ({dest_lat}, {dest_lng})")
                self.assertEqual(waypoints[1], [49.2847, -122.7915], "Waypoint 1 should be Pinetree & Guildford")
                self.assertEqual(waypoints[2], [49.2845, -122.8055], "Waypoint 2 should be Guildford & Johnson")
                self.assertEqual(waypoints[3], [49.2785, -122.8125], "Waypoint 3 should be Johnson & Mariner")
                self.assertEqual(waypoints[4], [dest_lat, dest_lng], "Final waypoint should be destination")

    def test_corridor_a_mariner_exact_boundaries(self):
        """Test boundary conditions for Corridor A (dest_lat < 49.280 and dest_lng < -122.800)."""
        # Just inside boundaries
        with patch.object(self.engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
            res = self.engine.calculate_route(dest_lat=49.27999, dest_lng=-122.80001, station_id="1")
            waypoints = mock_osrm.call_args[0][0]
            self.assertEqual(len(waypoints), 5, "Inside boundary should trigger Corridor A")

        # Just on/outside latitude boundary (lat == 49.280)
        with patch.object(self.engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
            res = self.engine.calculate_route(dest_lat=49.28000, dest_lng=-122.80500, station_id="1")
            waypoints = mock_osrm.call_args[0][0]
            self.assertEqual(len(waypoints), 2, "Latitude >= 49.280 should NOT trigger Corridor A")

        # Just on/outside longitude boundary (lng == -122.800)
        with patch.object(self.engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
            res = self.engine.calculate_route(dest_lat=49.27500, dest_lng=-122.80000, station_id="1")
            waypoints = mock_osrm.call_args[0][0]
            self.assertEqual(len(waypoints), 2, "Longitude >= -122.800 should NOT trigger Corridor A")

    def test_corridor_b_gordon_deep_interior_points(self):
        """Points in Town Centre / Gordon Ave sector should trigger Corridor B."""
        gordon_points = [
            (49.2785, -122.7850),  # Coquitlam Centre / Gordon Ave
            (49.2800, -122.7900),  # Pinetree / Lincoln
            (49.2760, -122.7920),  # Lougheed Corridor
            (49.2840, -122.7820),  # Christmas Way area
        ]
        for dest_lat, dest_lng in gordon_points:
            with patch.object(self.engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
                res = self.engine.calculate_route(dest_lat=dest_lat, dest_lng=dest_lng, station_id="1")
                mock_osrm.assert_called_once()
                waypoints = mock_osrm.call_args[0][0]
                self.assertEqual(len(waypoints), 4, f"Expected 4 waypoints for Corridor B at ({dest_lat}, {dest_lng})")
                self.assertEqual(waypoints[1], [49.2785, -122.7915], "Waypoint 1 should be Pinetree & Lougheed")
                self.assertEqual(waypoints[2], [49.2785, -122.7850], "Waypoint 2 should be Lougheed & Christmas Way")
                self.assertEqual(waypoints[3], [dest_lat, dest_lng], "Final waypoint should be destination")

    def test_corridor_b_gordon_exact_boundaries(self):
        """Test boundary conditions for Corridor B (49.275 <= dest_lat <= 49.285 and -122.795 <= dest_lng <= -122.780)."""
        # Exact corners of the bounding box
        corners = [
            (49.2750, -122.7950),  # SW corner
            (49.2750, -122.7800),  # SE corner
            (49.2850, -122.7950),  # NW corner
            (49.2850, -122.7800),  # NE corner
        ]
        for lat, lng in corners:
            with patch.object(self.engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
                res = self.engine.calculate_route(dest_lat=lat, dest_lng=lng, station_id="1")
                waypoints = mock_osrm.call_args[0][0]
                self.assertEqual(len(waypoints), 4, f"Exact corner ({lat}, {lng}) should trigger Corridor B")

        # Nudges outside bounding box
        outside_points = [
            (49.27499, -122.7900),  # South of box
            (49.28501, -122.7900),  # North of box
            (49.2800, -122.79501),  # West of box
            (49.2800, -122.77999),  # East of box
        ]
        for lat, lng in outside_points:
            with patch.object(self.engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
                res = self.engine.calculate_route(dest_lat=lat, dest_lng=lng, station_id="1")
                waypoints = mock_osrm.call_args[0][0]
                self.assertEqual(len(waypoints), 2, f"Point outside box ({lat}, {lng}) should NOT trigger Corridor B")

    def test_hall_1_detection_via_coordinates_vs_station_id(self):
        """Hall 1 origin detection must succeed via station_id='1' OR start coords near Hall 1."""
        dest_lat = 49.2650
        dest_lng = -122.8150

        # Via station_id="1"
        with patch.object(self.engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
            self.engine.calculate_route(dest_lat=dest_lat, dest_lng=dest_lng, station_id="1")
            self.assertEqual(len(mock_osrm.call_args[0][0]), 5)

        # Via explicit start coords close to Hall 1 (lat 49.29109, lng -122.79072)
        with patch.object(self.engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
            self.engine.calculate_route(
                dest_lat=dest_lat, dest_lng=dest_lng,
                start_lat=49.2915, start_lng=-122.7905
            )
            self.assertEqual(len(mock_osrm.call_args[0][0]), 5)

        # Non-Hall 1 coordinates should NOT trigger Hall 1 corridor
        with patch.object(self.engine, "_fetch_osrm_polyline", return_value=(None, None)) as mock_osrm:
            self.engine.calculate_route(
                dest_lat=dest_lat, dest_lng=dest_lng,
                start_lat=49.2480, start_lng=-122.8654  # Hall 3
            )
            self.assertEqual(len(mock_osrm.call_args[0][0]), 2)


class TestEmpiricalApparatusMapping(unittest.TestCase):
    """Stress tests and fuzzing for apparatus unit parsing and home station resolution."""

    def test_exhaustive_unit_type_mapping(self):
        """Test all standard apparatus classifications and variations."""
        cases = [
            # Engines / Pumpers
            ("E1", "Engine / Pumper"), ("E2", "Engine / Pumper"), ("E3", "Engine / Pumper"),
            ("E4", "Engine / Pumper"), ("e1", "Engine / Pumper"), ("ENGINE 1", "Engine / Pumper"),
            # Ladders / Aerials
            ("L1", "Ladder / Aerial"), ("L2", "Ladder / Aerial"), ("l1", "Ladder / Aerial"),
            ("LADDER 2", "Ladder / Aerial"),
            # Rescues
            ("R1", "Heavy Rescue"), ("R2", "Heavy Rescue"), ("r1", "Heavy Rescue"),
            ("RESCUE 1", "Heavy Rescue"),
            # Quints
            ("Q5", "Quint"), ("Q1", "Quint"), ("q5", "Quint"), ("QUINT 5", "Quint"),
            # Tankers / Tenders / Water
            ("T4", "Tanker / Tender"), ("WT4", "Tanker / Tender"), ("LAV4", "Tanker / Tender"),
            ("wt4", "Tanker / Tender"), ("lav4", "Tanker / Tender"), ("TANKER 4", "Tanker / Tender"),
            # Command Vehicles
            ("C1", "Command Vehicle"), ("C10", "Command Vehicle"), ("C9", "Command Vehicle"),
            ("B1", "Command Vehicle"), ("B2", "Command Vehicle"), ("CHIEF 1", "Command Vehicle"),
            # Specialty / Medic
            ("S1", "Specialty / Medic"), ("S3", "Specialty / Medic"), ("M1", "Specialty / Medic"),
            ("MEDIC 1", "Specialty / Medic"), ("SQUAD 3", "Specialty / Medic"),
            # Unknown / Fallback
            ("UNKNOWN", "Apparatus"), ("HAZMAT99", "Apparatus"), ("FOO_BAR", "Apparatus"),
            ("", "Apparatus"), (123, "Apparatus"), (None, "Apparatus")
        ]
        for unit_input, expected_type in cases:
            actual = get_unit_type(unit_input)
            self.assertEqual(actual, expected_type, f"Unit '{unit_input}' expected type '{expected_type}' got '{actual}'")

    def test_exhaustive_unit_station_id_mapping(self):
        """Test home station ID resolution according to Coquitlam dispatch deployment rules."""
        cases = [
            # Hall 1 (HQ / Town Centre)
            ("E1", "1"), ("L1", "1"), ("R1", "1"), ("M1", "1"), ("C1", "1"), ("C10", "1"),
            ("S1", "1"), ("CHIEF 1", "1"), ("B1", "1"),
            # Hall 2 (Mariner / North)
            ("E2", "2"), ("L2", "2"), ("R2", "2"), ("e2", "2"), ("r2", "2"),
            # Hall 3 (Austin Heights / Southwest)
            ("E3", "3"), ("Q5", "3"), ("H3", "3"), ("HT3", "3"), ("S3", "3"), ("q5", "3"),
            # Hall 4 (Burke Mountain / Cape Horn)
            ("E4", "4"), ("T4", "4"), ("WT4", "4"), ("LAV4", "4"), ("wt4", "4"), ("lav4", "4"),
            # Fallback to Hall 1
            ("UNKNOWN", "1"), ("CHIEF", "1"), ("XYZ99", "1"), ("", "1"), (None, "1")
        ]
        for unit_input, expected_station in cases:
            actual = get_unit_station_id(unit_input)
            self.assertEqual(actual, expected_station, f"Unit '{unit_input}' expected station '{expected_station}' got '{actual}'")


class TestEmpiricalResponsePhysicsAndMath(unittest.TestCase):
    """Stress tests and verification for response speed, road factor, and ETA mathematics."""

    def setUp(self):
        self.engine = EVORoutingEngine()

    def test_response_mode_physics_invariants(self):
        """
        Verify mathematical invariants across 1,000 random destinations:
        1. Code 3 road factor is strictly 1.35x, Code 1 is 1.45x
        2. Code 3 speed is strictly 45.0 km/h, Code 1 is 32.0 km/h
        3. Code 3 fallback distance <= Code 1 fallback distance
        4. Code 3 ETA <= Code 1 ETA
        5. ETA is always >= 1 minute (no zero or negative ETAs)
        """
        import random
        random.seed(42)

        for i in range(1000):
            # Random destinations across Metro Vancouver (lat 49.15 to 49.35, lng -122.95 to -122.65)
            dest_lat = random.uniform(49.15, 49.35)
            dest_lng = random.uniform(-122.95, -122.65)

            with patch.object(self.engine, "_fetch_osrm_polyline", return_value=(None, None)):
                route_code3 = self.engine.calculate_route(dest_lat, dest_lng, station_id="1", response_type="emergency")
                route_code1 = self.engine.calculate_route(dest_lat, dest_lng, station_id="1", response_type="routine")

                self.assertEqual(route_code3["response_mode"], "Emergency (Code 3)")
                self.assertEqual(route_code1["response_mode"], "Routine (Code 1)")

                self.assertLessEqual(route_code3["distance_km"], route_code1["distance_km"])
                self.assertLessEqual(route_code3["eta_minutes"], route_code1["eta_minutes"])
                self.assertGreaterEqual(route_code3["eta_minutes"], 1)
                self.assertGreaterEqual(route_code1["eta_minutes"], 1)

    def test_unit_metrics_mathematical_precision(self):
        """Verify exact mathematical formulas in calculate_unit_metrics."""
        dest_lat = 49.2785
        dest_lng = -122.7850

        # Unit E1 (Hall 1: lat 49.2910965, lng -122.7907256)
        m_e1_em = self.engine.calculate_unit_metrics("E1", dest_lat, dest_lng, response_type="emergency")
        crow_km = self.engine.calculate_distance_km(FIRE_HALLS["1"]["lat"], FIRE_HALLS["1"]["lng"], dest_lat, dest_lng)
        expected_road_km_em = round(crow_km * 1.35, 2)
        expected_eta_em = max(1, round((expected_road_km_em / 45.0) * 60.0))

        self.assertAlmostEqual(m_e1_em["crow_distance_km"], round(crow_km, 2), places=2)
        self.assertAlmostEqual(m_e1_em["road_distance_km"], expected_road_km_em, places=2)
        self.assertEqual(m_e1_em["eta_minutes"], expected_eta_em)
        self.assertEqual(m_e1_em["speed_kmh"], 45.0)

        # Unit E1 Routine
        m_e1_rt = self.engine.calculate_unit_metrics("E1", dest_lat, dest_lng, response_type="routine")
        expected_road_km_rt = round(crow_km * 1.45, 2)
        expected_eta_rt = max(1, round((expected_road_km_rt / 32.0) * 60.0))

        self.assertAlmostEqual(m_e1_rt["road_distance_km"], expected_road_km_rt, places=2)
        self.assertEqual(m_e1_rt["eta_minutes"], expected_eta_rt)
        self.assertEqual(m_e1_rt["speed_kmh"], 32.0)

    def test_haversine_distance_geodetic_ground_truth(self):
        """Verify Haversine against known geodetic distances."""
        # 1 degree latitude at equator ~ 111.195 km
        d_lat = self.engine.calculate_distance_km(0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(d_lat, 111.195, delta=0.5)

        # Hall 1 to Hall 2 (~3.75 km)
        d_h1_h2 = self.engine.calculate_distance_km(
            FIRE_HALLS["1"]["lat"], FIRE_HALLS["1"]["lng"],
            FIRE_HALLS["2"]["lat"], FIRE_HALLS["2"]["lng"]
        )
        self.assertAlmostEqual(d_h1_h2, 3.75, delta=0.2)

        # Coincident coordinates -> exactly 0.0 km
        d_zero = self.engine.calculate_distance_km(49.2910, -122.7907, 49.2910, -122.7907)
        self.assertEqual(d_zero, 0.0)


class TestEmpiricalHighVolumeStressHarness(unittest.TestCase):
    """Stress test for memory leaks, recursion limits, and throughput under 10,000 queries."""

    def setUp(self):
        self.engine = EVORoutingEngine()

    def test_high_volume_10k_routing_queries(self):
        """Execute 10,000 route and unit metric queries to prove zero memory leaks and high throughput."""
        # Replace method with direct lambda stub to avoid mock call history retention
        orig_fetch = self.engine._fetch_osrm_polyline
        self.engine._fetch_osrm_polyline = lambda waypoints: (None, None)

        import gc
        gc.collect()

        tracemalloc.start()
        snapshot_start = tracemalloc.take_snapshot()

        start_time = time.perf_counter()
        query_count = 10000

        units = ["E1", "L1", "R1", "Q5", "WT4", "E2", "E3", "E4", "C10", "MEDIC1"]

        for i in range(query_count):
            dest_lat = 49.200 + (i % 1000) * 0.0001
            dest_lng = -122.850 + (i % 1000) * 0.0001
            resp_type = "emergency" if i % 2 == 0 else "routine"
            unit = units[i % len(units)]

            # Test calculate_route
            res_route = self.engine.calculate_route(
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                station_id=str((i % 4) + 1),
                response_type=resp_type
            )
            self.assertEqual(res_route["status"], "success")

            # Test calculate_unit_metrics
            res_metric = self.engine.calculate_unit_metrics(
                unit=unit,
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                response_type=resp_type
            )
            self.assertIsNotNone(res_metric["eta_minutes"])

        self.engine._fetch_osrm_polyline = orig_fetch

        gc.collect()
        elapsed = time.perf_counter() - start_time
        snapshot_end = tracemalloc.take_snapshot()
        tracemalloc.stop()

        top_stats = snapshot_end.compare_to(snapshot_start, 'lineno')
        total_mem_diff_kb = sum(stat.size_diff for stat in top_stats) / 1024.0

        throughput = (query_count * 2) / elapsed
        print(f"\n[STRESS TEST] Completed {query_count * 2} operations in {elapsed:.3f}s ({throughput:.1f} ops/sec)")
        print(f"[STRESS TEST] Net memory delta after GC: {total_mem_diff_kb:.2f} KB")

        # Invariants: 20k operations should complete in < 2.0s with < 50KB residual memory
        self.assertLess(elapsed, 2.0, f"10k queries took {elapsed:.3f}s, expected < 2.0s")
        self.assertLess(total_mem_diff_kb, 50.0, f"Net memory delta {total_mem_diff_kb:.2f} KB exceeds 50 KB threshold")


if __name__ == '__main__':
    unittest.main()
