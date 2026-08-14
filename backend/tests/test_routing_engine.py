import os
import sys
import math
import json
import pytest
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

# Ensure sibling service path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/gis/src")))

from gis_service.routing_engine import (
    EVORoutingEngine,
    FIRE_HALLS,
    get_unit_type,
    get_unit_station_id,
    get_apparatus_profile_class,
)


class TestFireHallsAndApparatusMapping:
    def test_fire_halls_master_directory(self):
        assert "1" in FIRE_HALLS
        assert "2" in FIRE_HALLS
        assert "3" in FIRE_HALLS
        assert "4" in FIRE_HALLS

        hall1 = FIRE_HALLS["1"]
        assert hall1["id"] == 1
        assert "Town Centre" in hall1["name"]
        assert "1300 Pinetree Way" in hall1["address"]
        assert abs(hall1["lat"] - 49.291) < 0.01
        assert abs(hall1["lng"] - (-122.790)) < 0.01

        hall2 = FIRE_HALLS["2"]
        assert hall2["id"] == 2
        assert "Mariner" in hall2["name"]

        hall3 = FIRE_HALLS["3"]
        assert hall3["id"] == 3
        assert "Austin Heights" in hall3["name"]

        hall4 = FIRE_HALLS["4"]
        assert hall4["id"] == 4
        assert "Burke Mountain" in hall4["name"]

    def test_get_unit_type(self):
        assert get_unit_type("E1") == "Engine / Pumper"
        assert get_unit_type("E4") == "Engine / Pumper"
        assert get_unit_type("L1") == "Ladder / Aerial"
        assert get_unit_type("L2") == "Ladder / Aerial"
        assert get_unit_type("R1") == "Heavy Rescue"
        assert get_unit_type("R2") == "Heavy Rescue"
        assert get_unit_type("Q5") == "Quint"
        assert get_unit_type("C10") == "Command Vehicle"
        assert get_unit_type("B1") == "Command Vehicle"
        assert get_unit_type("M1") == "Specialty / Medic"
        assert get_unit_type("S3") == "Specialty / Medic"
        assert get_unit_type("T4") == "Tanker / Tender"
        assert get_unit_type("WT4") == "Tanker / Tender"
        assert get_unit_type("LAV4") == "Light Attack Vehicle"
        assert get_unit_type("UNKNOWN99") == "Apparatus"

    def test_get_apparatus_profile_class(self):
        assert get_apparatus_profile_class("LAV4") == "light"
        assert get_apparatus_profile_class("C1") == "light"
        assert get_apparatus_profile_class("C10") == "light"
        assert get_apparatus_profile_class("M1") == "light"
        assert get_apparatus_profile_class("S3") == "light"

        assert get_apparatus_profile_class("E1") == "standard"
        assert get_apparatus_profile_class("E4") == "standard"
        assert get_apparatus_profile_class("R1") == "standard"

        assert get_apparatus_profile_class("L1") == "heavy"
        assert get_apparatus_profile_class("Q5") == "heavy"
        assert get_apparatus_profile_class("T4") == "heavy"
        assert get_apparatus_profile_class("WT4") == "heavy"

    def test_get_unit_station_id(self):
        assert get_unit_station_id("E1") == "1"
        assert get_unit_station_id("L1") == "1"
        assert get_unit_station_id("R1") == "1"
        assert get_unit_station_id("M1") == "1"
        assert get_unit_station_id("C10") == "1"

        assert get_unit_station_id("E2") == "2"
        assert get_unit_station_id("L2") == "2"
        assert get_unit_station_id("R2") == "2"

        assert get_unit_station_id("E3") == "3"
        assert get_unit_station_id("Q5") == "3"
        assert get_unit_station_id("H3") == "3"
        assert get_unit_station_id("HT3") == "3"
        assert get_unit_station_id("S3") == "3"

        assert get_unit_station_id("E4") == "4"
        assert get_unit_station_id("T4") == "4"
        assert get_unit_station_id("WT4") == "4"
        assert get_unit_station_id("LAV4") == "4"

        # Fallback to default hall 1
        assert get_unit_station_id("CHIEF") == "1"


class TestOSRMUrlConstructionAndPriorities:
    def test_osrm_default_endpoints_ordering(self):
        engine = EVORoutingEngine()
        # Ensure no env var override
        with patch.dict(os.environ, {}, clear=True):
            endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
            assert len(endpoints) >= 4
            assert endpoints[0].startswith("http://osrm:5000/route/v1/driving/")
            assert endpoints[1].startswith("http://127.0.0.1:5000/route/v1/driving/")
            assert endpoints[2].startswith("http://localhost:5000/route/v1/driving/")
            assert endpoints[3].startswith("https://router.project-osrm.org/route/v1/driving/")

    def test_osrm_query_parameters_momentum_preservation(self):
        engine = EVORoutingEngine()
        endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
        for url in endpoints:
            assert "continue_straight=false" in url
            assert "steps=true" in url
            assert "overview=full" in url
            assert "geometries=geojson" in url

    def test_osrm_env_variable_prioritization(self):
        engine = EVORoutingEngine()
        with patch.dict(os.environ, {"OSRM_ROUTER_URL": "http://custom-osrm-host:5000"}):
            endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
            assert endpoints[0].startswith("http://custom-osrm-host:5000/route/v1/driving/")
            assert "continue_straight=false" in endpoints[0]

        with patch.dict(os.environ, {"OSRM_BACKEND_URL": "http://mld-backend:5000"}):
            endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
            assert endpoints[0].startswith("http://mld-backend:5000/route/v1/driving/")

        with patch.dict(os.environ, {"OSRM_URL": "http://osrm-url-env:5000"}):
            endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
            assert endpoints[0].startswith("http://osrm-url-env:5000/route/v1/driving/")

    def test_osrm_disable_wan_fallback_suppression(self):
        engine = EVORoutingEngine()
        with patch.dict(os.environ, {"DISABLE_WAN_FALLBACK": "true"}):
            endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
            assert not any("router.project-osrm.org" in url for url in endpoints)
            assert len(endpoints) == 3

    def test_fetch_osrm_polyline_empty_or_single_waypoint(self):
        engine = EVORoutingEngine()
        assert engine._fetch_osrm_polyline([]) == (None, None)
        assert engine._fetch_osrm_polyline([[49.2910, -122.7907]]) == (None, None)


class TestTacticalCorridors:
    def test_station_1_mariner_corridor_injection(self):
        engine = EVORoutingEngine()
        # Destination in Mariner Way / Southwest Sector: dest_lat < 49.280 and dest_lng < -122.800
        dest_lat = 49.2650
        dest_lng = -122.8150

        with patch.object(engine, "_fetch_osrm_polyline") as mock_osrm:
            mock_osrm.return_value = (None, None)
            res = engine.calculate_route(
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                station_id="1"
            )

            # Check that _fetch_osrm_polyline was called with the injected corridor points
            mock_osrm.assert_called_once()
            called_waypoints = mock_osrm.call_args[0][0]

            assert len(called_waypoints) == 5  # start, 3 corridor waypoints, dest
            # Start is Hall 1
            assert abs(called_waypoints[0][0] - FIRE_HALLS["1"]["lat"]) < 0.001
            # Corridor A: Guildford -> Johnson -> Mariner
            assert called_waypoints[1] == [49.2847, -122.7915]  # Pinetree & Guildford
            assert called_waypoints[2] == [49.2845, -122.8055]  # Guildford & Johnson St
            assert called_waypoints[3] == [49.2785, -122.8125]  # Johnson St & Mariner Way
            # Destination
            assert called_waypoints[4] == [dest_lat, dest_lng]

    def test_station_1_gordon_corridor_injection(self):
        engine = EVORoutingEngine()
        # Destination in Gordon Ave / Town Centre Sector: 49.275 <= dest_lat <= 49.285 and -122.795 <= dest_lng <= -122.780
        dest_lat = 49.2785
        dest_lng = -122.7850

        with patch.object(engine, "_fetch_osrm_polyline") as mock_osrm:
            mock_osrm.return_value = (None, None)
            res = engine.calculate_route(
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                station_id="1"
            )

            mock_osrm.assert_called_once()
            called_waypoints = mock_osrm.call_args[0][0]

            assert len(called_waypoints) == 4  # start, 2 corridor waypoints, dest
            assert abs(called_waypoints[0][0] - FIRE_HALLS["1"]["lat"]) < 0.001
            # Corridor B: Pinetree -> Lougheed -> Christmas Way
            assert called_waypoints[1] == [49.2785, -122.7915]  # Pinetree & Lougheed
            assert called_waypoints[2] == [49.2785, -122.7850]  # Lougheed & Christmas Way
            assert called_waypoints[3] == [dest_lat, dest_lng]

    def test_non_hall_1_no_corridor_injection(self):
        engine = EVORoutingEngine()
        dest_lat = 49.2650
        dest_lng = -122.8150

        with patch.object(engine, "_fetch_osrm_polyline") as mock_osrm:
            mock_osrm.return_value = (None, None)
            res = engine.calculate_route(
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                station_id="4"
            )

            mock_osrm.assert_called_once()
            called_waypoints = mock_osrm.call_args[0][0]
            assert len(called_waypoints) == 2  # Only start and dest


class TestResponsePhysicsAndETAs:
    def test_code3_vs_code1_physics(self):
        engine = EVORoutingEngine()
        dest_lat = 49.2622
        dest_lng = -122.8174

        with patch.object(engine, "_fetch_osrm_polyline") as mock_osrm:
            mock_osrm.return_value = (None, None)

            # Emergency (Code 3)
            res_code3 = engine.calculate_route(dest_lat=dest_lat, dest_lng=dest_lng, response_type="emergency")
            # Routine (Code 1)
            res_code1 = engine.calculate_route(dest_lat=dest_lat, dest_lng=dest_lng, response_type="routine")

            assert res_code3["response_mode"] == "Emergency (Code 3)"
            assert res_code1["response_mode"] == "Routine (Code 1)"

            # Code 3 road factor is 1.35 vs Code 1 is 1.45 (shorter fallback road km)
            assert res_code3["distance_km"] <= res_code1["distance_km"]

            # Code 3 speed is 45 km/h vs Code 1 is 32 km/h (faster ETA)
            assert res_code3["eta_minutes"] <= res_code1["eta_minutes"]

    def test_unit_metrics_calculation(self):
        engine = EVORoutingEngine()
        dest_lat = 49.2785
        dest_lng = -122.7850

        metric_e1 = engine.calculate_unit_metrics("E1", dest_lat, dest_lng, response_type="emergency")
        assert metric_e1["unit"] == "E1"
        assert metric_e1["origin_hall"] == 1
        assert metric_e1["speed_kmh"] == 45.0
        assert metric_e1["road_distance_km"] > 0
        assert metric_e1["eta_minutes"] >= 1

        metric_q5 = engine.calculate_unit_metrics("Q5", dest_lat, dest_lng, response_type="emergency")
        assert metric_q5["unit"] == "Q5"
        assert metric_q5["origin_hall"] == 3  # Austin Heights Hall 3
        assert metric_q5["unit_type"] == "Quint"

        metric_t4 = engine.calculate_unit_metrics("T4", dest_lat, dest_lng, response_type="routine")
        assert metric_t4["unit"] == "T4"
        assert metric_t4["origin_hall"] == 4  # Burke Mountain Hall 4
        assert metric_t4["speed_kmh"] == 32.0

    def test_haversine_distance_calculation(self):
        engine = EVORoutingEngine()
        # Distance between Hall 1 (49.2911, -122.7907) and Hall 2 (49.2622, -122.8175)
        d = engine.calculate_distance_km(
            FIRE_HALLS["1"]["lat"], FIRE_HALLS["1"]["lng"],
            FIRE_HALLS["2"]["lat"], FIRE_HALLS["2"]["lng"]
        )
        # Expected distance is ~3.7 - 3.8 km
        assert 3.5 <= d <= 4.0


class TestOSRMResponsesAndFallback:
    def test_osrm_mocked_success_polyline(self):
        engine = EVORoutingEngine()
        mock_coords = [[-122.7907, 49.2910], [-122.7900, 49.2850], [-122.7850, 49.2785]]
        mock_response_data = {
            "code": "Ok",
            "routes": [
                {
                    "geometry": {
                        "coordinates": mock_coords
                    },
                    "distance": 2540.0,
                    "duration": 210.0
                }
            ]
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = engine.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id="1")

            assert res["status"] == "success"
            assert res["distance_km"] == 2.54
            # Coordinates returned should be converted to [lat, lng]
            assert res["polyline"][0] == [49.2910, -122.7907]
            assert res["polyline"][-1] == [49.2785, -122.7850]
            assert len(res["polyline"]) == 3

    def test_osrm_offline_fallback_handling(self):
        engine = EVORoutingEngine()
        with patch("urllib.request.urlopen", side_effect=URLError("Connection refused")):
            res = engine.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id="1")

            assert res["status"] == "success"
            assert res["distance_km"] > 0
            assert res["eta_minutes"] >= 1
            # When offline, returns injected corridor waypoints as straight-line polyline
            assert len(res["polyline"]) >= 2
            assert res["origin"]["lat"] == FIRE_HALLS["1"]["lat"]
            assert res["destination"]["lat"] == 49.2785

    def test_osrm_malformed_json_fallback(self):
        engine = EVORoutingEngine()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b"NOT_VALID_JSON"
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = engine.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id="1")
            assert res["status"] == "success"
            assert len(res["polyline"]) >= 2

    def test_osrm_error_status_code_fallback(self):
        engine = EVORoutingEngine()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 500
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = engine.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id="1")
            assert res["status"] == "success"
            assert len(res["polyline"]) >= 2

    def test_calculate_units_routing_multi_units(self):
        engine = EVORoutingEngine()
        units = ["E1", "L1", "Q5", "T4", "R2"]
        dest_lat = 49.2785
        dest_lng = -122.7850

        results = engine.calculate_units_routing(units, dest_lat, dest_lng, response_type="emergency")
        assert len(results) == 5
        unit_names = [r["unit"] for r in results]
        assert "E1" in unit_names
        assert "Q5" in unit_names
        assert "T4" in unit_names
        assert "R2" in unit_names

        # Verify hall mappings
        hall_by_unit = {r["unit"]: r["origin_hall"] for r in results}
        assert hall_by_unit["E1"] == 1
        assert hall_by_unit["L1"] == 1
        assert hall_by_unit["Q5"] == 3
        assert hall_by_unit["T4"] == 4
        assert hall_by_unit["R2"] == 2

    def test_calculate_units_routing_edge_cases(self):
        engine = EVORoutingEngine()
        # Empty units or missing coords
        assert engine.calculate_units_routing([], 49.2785, -122.7850) == []
        assert engine.calculate_units_routing(["E1"], None, -122.7850) == []
        assert engine.calculate_units_routing(["E1"], 49.2785, None) == []

        # Deduplication of identical units
        res = engine.calculate_units_routing(["E1", "E1", "E1"], 49.2785, -122.7850)
        assert len(res) == 1
        assert res[0]["unit"] == "E1"

    def test_custom_start_coordinates(self):
        engine = EVORoutingEngine()
        custom_lat = 49.2500
        custom_lng = -122.8000
        dest_lat = 49.2800
        dest_lng = -122.7700

        with patch.object(engine, "_fetch_osrm_polyline", return_value=(None, None)):
            res = engine.calculate_route(
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                start_lat=custom_lat,
                start_lng=custom_lng
            )
            assert res["origin"]["lat"] == custom_lat
            assert res["origin"]["lng"] == custom_lng
            assert res["destination"]["lat"] == dest_lat
            assert res["destination"]["lng"] == dest_lng
