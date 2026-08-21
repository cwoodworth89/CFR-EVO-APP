import os
import sys
import math
import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

try:
    import pytest
except ImportError:
    pytest = None

# Ensure sibling service path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/gis/src")))

from gis_service.routing_engine import (
    EVORoutingEngine,
    FIRE_HALLS,
    APPARATUS_TIERS,
    get_unit_type,
    get_unit_station_id,
    get_apparatus_profile_class,
)
from gis_service.geocoder import CoquitlamDataValidator


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
        assert "775 Mariner Way" in hall2["address"]

        hall3 = FIRE_HALLS["3"]
        assert hall3["id"] == 3
        assert "Austin Heights" in hall3["name"]
        assert "438 Nelson Street" in hall3["address"]

        hall4 = FIRE_HALLS["4"]
        assert hall4["id"] == 4
        assert "Burke Mountain" in hall4["name"]
        assert "3501 David Ave" in hall4["address"]

    def test_get_unit_type(self):
        assert get_unit_type("SQ1") == "Squad"
        assert get_unit_type("SQ4") == "Squad"
        assert get_unit_type("SQUAD2") == "Squad"
        assert get_unit_type("E1") == "Engine"
        assert get_unit_type("E4") == "Engine"
        assert get_unit_type("PUMPER1") == "Engine"
        assert get_unit_type("L1") == "Ladder"
        assert get_unit_type("L2") == "Ladder"
        assert get_unit_type("TOWER1") == "Ladder"
        assert get_unit_type("PLATFORM4") == "Ladder"
        assert get_unit_type("R1") == "Rescue"
        assert get_unit_type("R2") == "Rescue"
        assert get_unit_type("Q5") == "Quint"
        assert get_unit_type("C1") == "Chief"
        assert get_unit_type("C10") == "Chief"
        assert get_unit_type("CAR2") == "Chief"
        assert get_unit_type("COMMAND1") == "Chief"
        assert get_unit_type("M1") == "Medic"
        assert get_unit_type("S3") == "Specialty"
        assert get_unit_type("T4") == "Water Tender"
        assert get_unit_type("WT4") == "Water Tender"
        assert get_unit_type("TANKER2") == "Water Tender"
        assert get_unit_type("LAV4") == "Light Attack Vehicle"
        assert get_unit_type("UNKNOWN99") == "Apparatus"

    def test_get_apparatus_profile_class(self):
        # Light apparatus (5 tons)
        assert get_apparatus_profile_class("SQ1") == "light"
        assert get_apparatus_profile_class("SQ4") == "light"
        assert get_apparatus_profile_class("LAV4") == "light"
        assert get_apparatus_profile_class("C1") == "light"
        assert get_apparatus_profile_class("C10") == "light"
        assert get_apparatus_profile_class("CAR1") == "light"
        assert get_apparatus_profile_class("M1") == "light"
        assert get_apparatus_profile_class("S3") == "light"

        # General apparatus (22 tons)
        assert get_apparatus_profile_class("E1") == "general"
        assert get_apparatus_profile_class("E4") == "general"
        assert get_apparatus_profile_class("R1") == "general"
        assert get_apparatus_profile_class("R4") == "general"
        assert get_apparatus_profile_class("Q5") == "general"
        assert get_apparatus_profile_class("PUMPER2") == "general"

        # Heavy apparatus (35 tons)
        assert get_apparatus_profile_class("L1") == "heavy"
        assert get_apparatus_profile_class("L4") == "heavy"
        assert get_apparatus_profile_class("T4") == "heavy"
        assert get_apparatus_profile_class("WT4") == "heavy"
        assert get_apparatus_profile_class("TOWER1") == "heavy"

    def test_get_unit_station_id(self):
        assert get_unit_station_id("E1") == "1"
        assert get_unit_station_id("L1") == "1"
        assert get_unit_station_id("R1") == "1"
        assert get_unit_station_id("SQ1") == "1"
        assert get_unit_station_id("M1") == "1"
        assert get_unit_station_id("C10") == "1"
        assert get_unit_station_id("C1") == "1"

        assert get_unit_station_id("E2") == "2"
        assert get_unit_station_id("L2") == "2"
        assert get_unit_station_id("R2") == "2"
        assert get_unit_station_id("SQ2") == "2"

        assert get_unit_station_id("E3") == "3"
        assert get_unit_station_id("Q5") == "3"
        assert get_unit_station_id("H3") == "3"
        assert get_unit_station_id("HT3") == "3"
        assert get_unit_station_id("S3") == "3"
        assert get_unit_station_id("SQ3") == "3"

        assert get_unit_station_id("E4") == "4"
        assert get_unit_station_id("T4") == "4"
        assert get_unit_station_id("WT4") == "4"
        assert get_unit_station_id("LAV4") == "4"
        assert get_unit_station_id("SQ4") == "4"

        # Fallback to default hall 1
        assert get_unit_station_id("CHIEF") == "1"


class TestOSRMUrlConstructionAndPriorities:
    def test_osrm_default_endpoints_ordering(self):
        engine = EVORoutingEngine()
        with patch.dict(os.environ, {}, clear=True):
            endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
            # Offline-first default: local candidates only, no public WAN server.
            assert len(endpoints) == 3
            assert endpoints[0].startswith("http://osrm:5000/route/v1/driving/")
            assert endpoints[1].startswith("http://127.0.0.1:5000/route/v1/driving/")
            assert endpoints[2].startswith("http://localhost:5000/route/v1/driving/")
            assert not any("router.project-osrm.org" in u for u in endpoints)

    def test_osrm_query_parameters_are_stock(self):
        """Stock OSRM parameters only: no continue_straight override."""
        engine = EVORoutingEngine()
        endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
        for url in endpoints:
            assert "continue_straight" not in url
            assert "steps=true" in url
            assert "overview=full" in url
            assert "geometries=geojson" in url

    def test_osrm_env_variable_prioritization(self):
        engine = EVORoutingEngine()
        with patch.dict(os.environ, {"OSRM_ROUTER_URL": "http://custom-osrm-host:5000"}):
            endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
            assert endpoints[0].startswith("http://custom-osrm-host:5000/route/v1/driving/")
            assert "continue_straight" not in endpoints[0]

        with patch.dict(os.environ, {"OSRM_BACKEND_URL": "http://mld-backend:5000"}):
            endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
            assert endpoints[0].startswith("http://mld-backend:5000/route/v1/driving/")

        with patch.dict(os.environ, {"OSRM_URL": "http://osrm-url-env:5000"}):
            endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
            assert endpoints[0].startswith("http://osrm-url-env:5000/route/v1/driving/")

    def test_osrm_wan_fallback_is_opt_in(self):
        """WAN is suppressed by default and only appears when explicitly enabled."""
        engine = EVORoutingEngine()
        with patch.dict(os.environ, {"DISABLE_WAN_FALLBACK": "true"}):
            endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
            assert not any("router.project-osrm.org" in url for url in endpoints)
            assert len(endpoints) == 3

        with patch.dict(os.environ, {"DISABLE_WAN_FALLBACK": "false"}):
            endpoints = engine._get_osrm_endpoints("-122.790,49.291;-122.785,49.278")
            assert any("router.project-osrm.org" in url for url in endpoints)

    def test_fetch_osrm_route_empty_or_single_waypoint(self):
        engine = EVORoutingEngine()
        assert engine._fetch_osrm_route([]) == (None, None, None)
        assert engine._fetch_osrm_route([[49.2910, -122.7907]]) == (None, None, None)


class TestPhase1RouteFindingAndAprons:
    def test_pure_osrm_pathfinding_no_intermediate_corridor_injections(self):
        """Verifies that route finding does NOT inject brittle bounding box waypoints."""
        engine = EVORoutingEngine()
        dest_lat = 49.2650
        dest_lng = -122.8150

        with patch.object(engine, "_fetch_osrm_route") as mock_osrm:
            mock_osrm.return_value = (None, None, None)
            res = engine.calculate_route(
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                station_id="1"
            )

            mock_osrm.assert_called_once()
            called_waypoints = mock_osrm.call_args[0][0]

            # Exactly 2 waypoints: hall front apron and destination
            assert len(called_waypoints) == 2
            assert called_waypoints[0] == [FIRE_HALLS["1"]["lat"], FIRE_HALLS["1"]["lng"]]
            assert called_waypoints[1] == [dest_lat, dest_lng]

    def test_hall_apron_departure_is_direction_independent(self):
        """Departure is always the hall front apron, regardless of destination bearing.

        Direction of travel is OSRM's responsibility; the engine must not pick a
        different origin based on where the incident happens to be.
        """
        engine = EVORoutingEngine()
        apron = [FIRE_HALLS["1"]["lat"], FIRE_HALLS["1"]["lng"]]

        for dest_lat, dest_lng in [(49.2850, -122.7930), (49.3100, -122.7800)]:
            with patch.object(engine, "_fetch_osrm_route", return_value=(None, None, None)) as mock_osrm:
                res = engine.calculate_route(dest_lat=dest_lat, dest_lng=dest_lng, station_id="1")
                called_waypoints = mock_osrm.call_args[0][0]
                assert called_waypoints[0] == apron
                assert res["origin"] == {"lat": apron[0], "lng": apron[1]}
            assert abs(called_waypoints[0][1] - FIRE_HALLS["1"]["lng"]) < 0.0001

    def test_route_1300_pinetree_to_428_nelson_st(self):
        """Key verification: 1300 Pinetree Way (Hall 1) to 428 Nelson St."""
        engine = EVORoutingEngine()
        dest_lat = 49.24803974681661
        dest_lng = -122.86546062387211

        with patch.object(engine, "_fetch_osrm_route") as mock_osrm:
            mock_osrm.return_value = (
                [[49.2905, -122.7915], [49.2700, -122.8200], [49.2480, -122.8655]],
                9.42,
                14.8
            )
            res = engine.calculate_route(
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                station_id="1",
                response_type="emergency"
            )

            mock_osrm.assert_called_once()
            called_waypoints = mock_osrm.call_args[0][0]
            assert len(called_waypoints) == 2
            assert called_waypoints[0] == [FIRE_HALLS["1"]["lat"], FIRE_HALLS["1"]["lng"]]
            assert called_waypoints[1] == [dest_lat, dest_lng]
            assert res["status"] == "success"
            assert res["distance_km"] == 9.42
            assert res["eta_minutes"] == 15  # OSRM duration, not an estimate

    def test_route_hall_1_to_2968_glen_dr(self):
        """Key verification: Hall 1 to 2968 Glen Dr."""
        engine = EVORoutingEngine()
        dest_lat = 49.2800
        dest_lng = -122.7930

        with patch.object(engine, "_fetch_osrm_route") as mock_osrm:
            mock_osrm.return_value = ([[49.2905, -122.7915], [49.2800, -122.7930]], 1.45, 3.2)
            res = engine.calculate_route(dest_lat=dest_lat, dest_lng=dest_lng, station_id="1")
            assert res["status"] == "success"
            assert res["distance_km"] == 1.45
            assert res["origin"] == {"lat": FIRE_HALLS["1"]["lat"], "lng": FIRE_HALLS["1"]["lng"]}

    def test_route_hall_2_to_1475_pipeline_rd(self):
        """Key verification: Hall 2 (Mariner) to 1475 Pipeline Rd."""
        engine = EVORoutingEngine()
        dest_lat = 49.3095
        dest_lng = -122.7661

        with patch.object(engine, "_fetch_osrm_route") as mock_osrm:
            mock_osrm.return_value = (None, None, None)
            res = engine.calculate_route(dest_lat=dest_lat, dest_lng=dest_lng, station_id="2")
            called_waypoints = mock_osrm.call_args[0][0]
            assert len(called_waypoints) == 2
            assert abs(called_waypoints[0][0] - FIRE_HALLS["2"]["lat"]) < 0.0001
            assert abs(called_waypoints[0][1] - FIRE_HALLS["2"]["lng"]) < 0.0001


class TestStockOSRMMetrics:
    """Routing metrics come from OSRM. No hand-rolled physics is applied."""

    def test_eta_is_osrm_duration_not_recomputed(self):
        engine = EVORoutingEngine()
        # OSRM reports 9.42 km / 14.8 min; the engine must report exactly that.
        with patch.object(engine, "_fetch_osrm_route",
                          return_value=([[49.291, -122.790], [49.248, -122.865]], 9.42, 14.8)):
            res = engine.calculate_route(dest_lat=49.248, dest_lng=-122.865, station_id="1")
            assert res["distance_km"] == 9.42
            assert res["eta_minutes"] == 15  # round(14.8), not a speed/turn estimate
            assert res["routing_source"] == "osrm"
            assert res["status"] == "success"

    def test_apparatus_class_does_not_alter_eta(self):
        """Stock baseline: a ladder and a squad on the same road get the same OSRM ETA.

        Apparatus-specific adjustment is a planned CFR config feature, deliberately
        not applied at this stage.
        """
        engine = EVORoutingEngine()
        with patch.object(engine, "_fetch_osrm_route", return_value=([[49.29, -122.79], [49.278, -122.785]], 4.0, 6.0)):
            light = engine.calculate_unit_metrics("SQ1", 49.2785, -122.7850)
            heavy = engine.calculate_unit_metrics("L1", 49.2785, -122.7850)
            assert light["eta_minutes"] == heavy["eta_minutes"] == 6
            assert light["apparatus_class"] == "light"
            assert heavy["apparatus_class"] == "heavy"

    def test_unknown_eta_is_none_not_estimated(self):
        """If OSRM is unreachable, ETA is reported as unknown rather than guessed."""
        engine = EVORoutingEngine()
        with patch.object(engine, "_fetch_osrm_route", return_value=(None, None, None)):
            res = engine.calculate_route(dest_lat=49.2622, dest_lng=-122.8174, station_id="1")
            assert res["eta_minutes"] is None
            assert res["status"] == "degraded"
            assert res["routing_source"] == "degraded_no_router"
            assert res["distance_km"] > 0  # great-circle placeholder for display

            m = engine.calculate_unit_metrics("E1", 49.2622, -122.8174)
            assert m["eta_minutes"] is None
            assert m["routing_source"] == "degraded_no_router"

    def test_response_mode_label_is_reported(self):
        engine = EVORoutingEngine()
        with patch.object(engine, "_fetch_osrm_route", return_value=(None, None, None)):
            assert engine.calculate_route(
                dest_lat=49.2622, dest_lng=-122.8174, response_type="emergency"
            )["response_mode"] == "Emergency (Code 3)"
            assert engine.calculate_route(
                dest_lat=49.2622, dest_lng=-122.8174, response_type="routine"
            )["response_mode"] == "Routine (Code 1)"

    def test_unit_metrics_respects_supplied_road_distance(self):
        engine = EVORoutingEngine()
        with patch.object(engine, "_fetch_osrm_route", return_value=([[0, 0], [1, 1]], 9.9, 12.0)):
            m = engine.calculate_unit_metrics("E1", 49.2785, -122.7850, road_distance_km=3.5)
            assert m["road_distance_km"] == 3.5
            assert m["eta_minutes"] == 12

    def test_haversine_distance_calculation(self):
        engine = EVORoutingEngine()
        d = engine.calculate_distance_km(
            FIRE_HALLS["1"]["lat"], FIRE_HALLS["1"]["lng"],
            FIRE_HALLS["2"]["lat"], FIRE_HALLS["2"]["lng"]
        )
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
            assert res["polyline"][0] == [49.2910, -122.7907]
            assert res["polyline"][-1] == [49.2785, -122.7850]
            assert len(res["polyline"]) == 3

    def test_osrm_offline_fallback_handling(self):
        engine = EVORoutingEngine()
        with patch("urllib.request.urlopen", side_effect=URLError("Connection refused")):
            res = engine.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id="1")

            assert res["status"] == "degraded"
            assert res["distance_km"] > 0          # great-circle placeholder
            assert res["eta_minutes"] is None      # unknown, never estimated
            assert len(res["polyline"]) == 2
            assert res["origin"]["lat"] == FIRE_HALLS["1"]["lat"]  # Hall 1 front apron
            assert res["destination"]["lat"] == 49.2785

    def test_osrm_malformed_json_fallback(self):
        engine = EVORoutingEngine()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b"NOT_VALID_JSON"
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = engine.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id="1")
            assert res["status"] == "degraded"
            assert res["eta_minutes"] is None
            assert len(res["polyline"]) == 2

    def test_osrm_error_status_code_fallback(self):
        engine = EVORoutingEngine()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 500
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            res = engine.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id="1")
            assert res["status"] == "degraded"
            assert res["eta_minutes"] is None
            assert len(res["polyline"]) == 2

    def test_calculate_units_routing_multi_units(self):
        engine = EVORoutingEngine()
        units = ["E1", "L1", "Q5", "T4", "R2", "SQ3", "M1"]
        dest_lat = 49.2785
        dest_lng = -122.7850

        results = engine.calculate_units_routing(units, dest_lat, dest_lng, response_type="emergency")
        assert len(results) == 7
        unit_names = [r["unit"] for r in results]
        assert "E1" in unit_names
        assert "Q5" in unit_names
        assert "T4" in unit_names
        assert "R2" in unit_names
        assert "SQ3" in unit_names
        assert "M1" in unit_names

        hall_by_unit = {r["unit"]: r["origin_hall"] for r in results}
        assert hall_by_unit["E1"] == 1
        assert hall_by_unit["L1"] == 1
        assert hall_by_unit["Q5"] == 3
        assert hall_by_unit["T4"] == 4
        assert hall_by_unit["R2"] == 2
        assert hall_by_unit["SQ3"] == 3
        assert hall_by_unit["M1"] == 1

    def test_calculate_units_routing_edge_cases(self):
        engine = EVORoutingEngine()
        assert engine.calculate_units_routing([], 49.2785, -122.7850) == []
        assert engine.calculate_units_routing(["E1"], None, -122.7850) == []
        assert engine.calculate_units_routing(["E1"], 49.2785, None) == []

        res = engine.calculate_units_routing(["E1", "E1", "E1"], 49.2785, -122.7850)
        assert len(res) == 1
        assert res[0]["unit"] == "E1"

    def test_custom_start_coordinates(self):
        engine = EVORoutingEngine()
        custom_lat = 49.2500
        custom_lng = -122.8000
        dest_lat = 49.2800
        dest_lng = -122.7700

        with patch.object(engine, "_fetch_osrm_route", return_value=(None, None, None)):
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


class TestMunicipalIntersectionAuthorityAndDisambiguation:
    validator = None

    @classmethod
    def setup_class(cls):
        intersections_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/gis/intersections.json"))
        cls.validator = CoquitlamDataValidator(intersections_json_path=intersections_path)

    def setup_method(self):
        if self.validator is None:
            intersections_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/gis/intersections.json"))
            self.validator = CoquitlamDataValidator(intersections_json_path=intersections_path)

    def setUp(self):
        if self.validator is None:
            intersections_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/gis/intersections.json"))
            self.validator = CoquitlamDataValidator(intersections_json_path=intersections_path)

    def test_single_intersection_resolution(self):
        # 1. Christmas Way and Westwood St -> (49.27832, -122.79354)
        res = self.validator.get_coordinates("Christmas Way and Westwood St")
        assert res is not None
        assert abs(res["lat"] - 49.27832) < 0.0001
        assert abs(res["lng"] - (-122.79354)) < 0.0001
        assert res["is_ambiguous"] is False

        # Inverted street order
        res_inv = self.validator.get_coordinates("Westwood St & Christmas Way")
        assert res_inv is not None
        assert abs(res_inv["lat"] - 49.27832) < 0.0001
        assert abs(res_inv["lng"] - (-122.79354)) < 0.0001

    def test_multi_junction_grid_disambiguation(self):
        # 2. Lougheed Hwy & Mariner Way with Grid 74 -> south interchange
        res_74 = self.validator.get_coordinates("Lougheed Hwy & Mariner Way", target_map_grid="74")
        assert res_74 is not None
        assert abs(res_74["lat"] - 49.23852) < 0.0001
        assert abs(res_74["lng"] - (-122.81224)) < 0.0001
        assert res_74["grid"] == "74"
        assert res_74["is_ambiguous"] is False

        # 3. Lougheed Hwy & Mariner Way with Grid 62 -> north split
        res_62 = self.validator.get_coordinates("Lougheed Hwy & Mariner Way", target_map_grid=62)
        assert res_62 is not None
        assert abs(res_62["lat"] - 49.24415) < 0.0001
        assert abs(res_62["lng"] - (-122.81682)) < 0.0001
        assert res_62["grid"] == "62"
        assert res_62["is_ambiguous"] is False

    def test_multi_junction_missing_grid_ambiguity(self):
        # 4. Ambiguity detection when Grid is missing
        res_ambig = self.validator.get_coordinates("Lougheed Hwy & Mariner Way")
        assert res_ambig is not None
        assert res_ambig["is_ambiguous"] is True
        assert len(res_ambig["candidates"]) == 2
        # Primary candidate coordinates returned
        assert abs(res_ambig["lat"] - 49.23852) < 0.0001
        assert abs(res_ambig["lng"] - (-122.81224)) < 0.0001

    def test_other_major_intersections(self):
        # Austin Ave & Nelson St
        res_austin = self.validator.get_coordinates("Austin Ave & Nelson St")
        assert res_austin is not None
        assert abs(res_austin["lat"] - 49.24804) < 0.0001
        assert abs(res_austin["lng"] - (-122.86546)) < 0.0001

        # Pinetree Way & Guildford Way
        res_pinetree = self.validator.get_coordinates("Pinetree Way & Guildford Way")
        assert res_pinetree is not None
        assert abs(res_pinetree["lat"] - 49.28624) < 0.0001
        assert abs(res_pinetree["lng"] - (-122.79321)) < 0.0001

        # Validation existence checks
        score, name = self.validator.validate_address_exists("Christmas Way and Westwood St")
        assert score >= 80
        assert name == "Christmas Way & Westwood St"


if __name__ == "__main__":
    if pytest is not None:
        sys.exit(pytest.main(["-v", __file__]))
    else:
        suite = unittest.TestSuite()
        for name, cls in list(globals().items()):
            if isinstance(cls, type) and name.startswith("Test"):
                for method_name in dir(cls):
                    if method_name.startswith("test_"):
                        def make_test(c, m):
                            def test_func(self=None):
                                if hasattr(c, "setup_class"):
                                    c.setup_class()
                                inst = c()
                                if hasattr(inst, "setUp"):
                                    inst.setUp()
                                elif hasattr(inst, "setup_method"):
                                    inst.setup_method()
                                getattr(inst, m)()
                            return test_func
                        setattr(cls, f"unittest_{method_name}", make_test(cls, method_name))
                        case = unittest.FunctionTestCase(make_test(cls, method_name))
                        suite.addTest(case)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
