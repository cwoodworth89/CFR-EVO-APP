"""
Unit tests for the rewritten geocoder thin orchestrator and its sub-resolvers.
Mocks the database engine to verify the 8-step resolution cascade in pure isolation.
"""
import pytest
from unittest.mock import MagicMock, patch
from gis_service.geocoder import CoquitlamDataValidator
from gis_service.normalization import (
    normalize_street_name, normalize_intersection_key,
    split_intersection_parts, parse_house_and_street, extract_near_street,
    ParsedAddress
)
from cfr_dispatch.pipeline.payload_builder import build_dispatch_payload
from cfr_dispatch.config.models import DispatchData


class TestGeocoderOrchestrator:
    @pytest.fixture
    def mock_validator(self):
        with patch.object(CoquitlamDataValidator, '_load_road_names', return_value=["GORDON AVE", "MARINER WAY", "LOUGHEED HWY"]), \
\
             patch.object(CoquitlamDataValidator, '_load_intersection_keys', return_value={
                 "CHRISTMAS WAY & WESTWOOD ST": [{
                     "name": "Christmas Way & Westwood St", "lat": 49.27832, "lng": -122.79354,
                     "grid": "62", "description": "Christmas Way & Westwood St", "candidate_index": 0
                 }],
                 "LOUGHEED HWY & MARINER WAY": [
                     {"name": "Lougheed Hwy & Mariner Way", "lat": 49.23852, "lng": -122.81224, "grid": "74", "description": "South", "candidate_index": 0},
                     {"name": "Lougheed Hwy & Mariner Way", "lat": 49.24500, "lng": -122.81100, "grid": "62", "description": "North", "candidate_index": 1}
                 ]
             }):
            validator = CoquitlamDataValidator.__new__(CoquitlamDataValidator)
            validator.engine = MagicMock()
            validator.street_confidence_threshold = 80
            validator._road_names_cache = validator._load_road_names()
            validator._intersection_keys_cache = validator._load_intersection_keys()

            from gis_service.address_resolver import AddressResolver
            from gis_service.intersection_resolver import IntersectionResolver
            from gis_service.spatial_queries import SpatialQueryEngine

            validator.address = AddressResolver(validator.engine, 80)
            validator.intersection = IntersectionResolver(validator._intersection_keys_cache, 80)
            validator.spatial = SpatialQueryEngine(validator.engine, validator._road_names_cache)
            return validator

    def test_step1_exact_address(self, mock_validator):
        # Mock address.resolve_exact
        mock_validator.address.resolve_exact = MagicMock(return_value={
            "address": "3030 Gordon Ave", "lat": 49.278, "lng": -122.793,
            "rings": [[[49.278, -122.793]]], "confidence": 100.0, "is_ambiguous": False
        })
        res = mock_validator.get_coordinates("3030 Gordon Ave")
        assert res is not None
        assert res["address"] == "3030 Gordon Ave"
        assert res["confidence"] == 100.0
        mock_validator.address.resolve_exact.assert_called_once()

    def test_step2_intersection(self, mock_validator):
        res = mock_validator.get_coordinates("Christmas Way & Westwood St")
        assert res is not None
        assert res["address"] == "Christmas Way & Westwood St"
        assert abs(res["lat"] - 49.27832) < 0.0001
        assert res["is_ambiguous"] is False

    def test_step2_multi_junction_disambiguation(self, mock_validator):
        res_74 = mock_validator.get_coordinates("Lougheed Hwy & Mariner Way", target_map_grid="74")
        assert res_74 is not None
        assert res_74["grid"] == "74"
        assert abs(res_74["lat"] - 49.23852) < 0.0001

        res_62 = mock_validator.get_coordinates("Lougheed Hwy & Mariner Way", target_map_grid="62")
        assert res_62 is not None
        assert res_62["grid"] == "62"
        assert abs(res_62["lat"] - 49.24500) < 0.0001

    def test_step3_block_interpolation(self, mock_validator):
        mock_validator.address.resolve_exact = MagicMock(return_value=None)
        mock_validator.address.resolve_block = MagicMock(return_value={
            "address": "1050 Ponderosa St", "lat": 49.280, "lng": -122.790,
            "rings": [], "confidence": 70.0, "is_block_interpolated": True, "is_ambiguous": False
        })
        res = mock_validator.get_coordinates("1050 Ponderosa St")
        assert res is not None
        assert res["is_block_interpolated"] is True
        mock_validator.address.resolve_block.assert_called_once()

    def test_step4_crossroad_narrowing(self, mock_validator):
        mock_validator.address.resolve_exact = MagicMock(return_value=None)
        mock_validator.address.resolve_block = MagicMock(return_value=None)
        mock_validator.address.resolve_crossroad_narrow = MagicMock(return_value={
            "address": "Gordon Ave (between Pinetree Way & Westwood St)", "lat": 49.278, "lng": -122.791,
            "rings": [], "confidence": 75.0, "is_crossroad_narrowed": True, "is_ambiguous": False
        })
        res = mock_validator.get_coordinates("Gordon Ave", cross_street_1="Pinetree Way", cross_street_2="Westwood St")
        # Since 'Gordon Ave' has no house number, parse_house_and_street is None, so check if parsed
        # If input has house: '3000 Gordon Ave'
        res = mock_validator.get_coordinates("3000 Gordon Ave", cross_street_1="Pinetree Way", cross_street_2="Westwood St")
        assert res is not None
        assert res["is_crossroad_narrowed"] is True
        mock_validator.address.resolve_crossroad_narrow.assert_called_once()

    def test_step5_street_centroid(self, mock_validator):
        mock_validator.address.resolve_exact = MagicMock(return_value=None)
        mock_validator.address.resolve_block = MagicMock(return_value=None)
        # Step 4b (nearest civic address) sits ahead of these fallbacks
        mock_validator.address.resolve_nearest_civic = MagicMock(return_value=None)
        mock_validator.address.resolve_crossroad_narrow = MagicMock(return_value=None)
        mock_validator.address.resolve_street_centroid = MagicMock(return_value={
            "address": "Gordon Ave", "lat": 49.275, "lng": -122.792,
            "rings": [], "confidence": 50.0, "is_street_centroid": True, "is_ambiguous": False
        })
        res = mock_validator.get_coordinates("9999 Gordon Ave")
        assert res is not None
        assert res["is_street_centroid"] is True
        assert res["address"] == "9999 Gordon Ave"
        mock_validator.address.resolve_street_centroid.assert_called_once()

    def test_step6_road_centroid(self, mock_validator):
        mock_validator.address.resolve_exact = MagicMock(return_value=None)
        mock_validator.address.resolve_block = MagicMock(return_value=None)
        # Step 4b (nearest civic address) sits ahead of these fallbacks
        mock_validator.address.resolve_nearest_civic = MagicMock(return_value=None)
        mock_validator.address.resolve_crossroad_narrow = MagicMock(return_value=None)
        mock_validator.address.resolve_street_centroid = MagicMock(return_value=None)
        mock_validator.address.resolve_road_centroid = MagicMock(return_value={
            "address": "Gordon Ave", "lat": 49.275, "lng": -122.792,
            "rings": [], "confidence": 45.0, "is_street_centroid": True, "is_ambiguous": False
        })
        res = mock_validator.get_coordinates("9999 Gordon Ave")
        assert res is not None
        mock_validator.address.resolve_road_centroid.assert_called_once()

    def test_place_name_alone_does_not_geocode(self, mock_validator):
        """A bare place name must not resolve to coordinates.

        The custom-places fuzzy step was removed: its coordinates were script-generated
        and unverified (up to 1.8 km off a parcel), and it had no reachable use case --
        Locution always speaks the civic address before the place name
        ("1240 Lansdowne Drive Scott Creek Middle School"), so Step 1 resolves it against
        public.parcels and the name is carried as the sub-address.
        """
        mock_validator.address.resolve_exact = MagicMock(return_value=None)
        mock_validator.address.resolve_block = MagicMock(return_value=None)
        mock_validator.address.resolve_cross_road_narrowing = MagicMock(return_value=None)
        mock_validator.address.resolve_street_centroid = MagicMock(return_value=None)
        mock_validator.address.resolve_road_centroid = MagicMock(return_value=None)
        assert mock_validator.get_coordinates("Mundy Park") is None

    def test_no_hardcoded_destination_overrides(self, mock_validator):
        """Hardcoded string-match destinations were removed (CLAUDE.md §6.2).

        Port Mann Bridge, Riverview Hospital station numbers, the Coquitlam Central bus
        loop and 3080 Gordon Ave were matched by string comparison in application code.
        Destinations missing from municipal records belong in the database as real
        records. An address that resolves to nothing now returns None, which surfaces as
        the Tier 1 unresolved warning rather than a guessed coordinate.
        """
        mock_validator.address.resolve_exact = MagicMock(return_value=None)
        mock_validator.address.resolve_block = MagicMock(return_value=None)
        mock_validator.address.resolve_cross_road_narrowing = MagicMock(return_value=None)
        mock_validator.address.resolve_nearest_civic = MagicMock(return_value=None)
        mock_validator.address.resolve_street_centroid = MagicMock(return_value=None)
        mock_validator.address.resolve_road_centroid = MagicMock(return_value=None)
        assert mock_validator.get_coordinates("Port Mann Bridge") is None

    def test_validate_address_exists(self, mock_validator):
        # Intersection match
        score, addr = mock_validator.validate_address_exists("Christmas Way & Westwood St")
        assert score == 100
        assert addr == "Christmas Way & Westwood St"


    def test_spatial_delegation(self, mock_validator):
        mock_validator.spatial.get_map_grid_for_point = MagicMock(return_value="62")
        mock_validator.spatial.is_within_city = MagicMock(return_value=True)

        assert mock_validator.get_map_grid_for_point(49.28, -122.79) == "62"
        assert mock_validator.is_within_city(49.28, -122.79) is True
        assert mock_validator.get_all_road_names() == ["GORDON AVE", "MARINER WAY", "LOUGHEED HWY"]


class TestPayloadBuilderWithCrossStreets:
    def test_payload_builder_passes_cross_streets(self):
        mock_validator = MagicMock()
        mock_validator.local_geocode.return_value = {
            "address": "3030 Gordon Ave", "lat": 49.278, "lng": -122.793,
            "rings": [], "confidence": 95.0
        }

        candidate = DispatchData(
            raw_text="3030 Gordon Ave cross street Pinetree Way",
            address="3030 Gordon Ave",
            cross_street_1="Pinetree Way",
            cross_street_2="Westwood St",
            map_grid="62",
            radio_channel="TAC 1",
            units="E1"
        )

        payload, errors = build_dispatch_payload(
            dispatch_id="test-123",
            raw_transcript="Engine 1 response 3030 Gordon Ave",
            sanitized_transcript="Engine 1 response 3030 Gordon Ave",
            all_candidates=[candidate],
            validator=mock_validator
        )

        # Verify local_geocode was called with cross_street_1 and cross_street_2
        mock_validator.local_geocode.assert_called_once_with(
            "3030 Gordon Ave",
            target_map_grid="62",
            cross_street_1="Pinetree Way",
            cross_street_2="Westwood St"
        )
        assert payload["target"]["address"] == "3030 Gordon Ave"
        assert payload["target"]["cross_streets"] == ["Pinetree Way", "Westwood St"]
