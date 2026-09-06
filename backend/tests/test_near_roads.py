"""Near roads are resolved against the roads near the placed address, never the whole city (#56).

The pure part pins the matching order (exact, base name, nearby spelling, ambiguous, unresolved)
on candidate lists a real point produces. The live part runs the spatial queries against the
kiosk database (DATABASE_URL); skipped otherwise.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cfr_dispatch  # noqa: E402,F401
from cfr_dispatch.pipeline.near_roads import match_heard_road, apply_near_roads, NEAR_ROAD_RADIUS_M  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
NEEDS_DB = pytest.mark.skipif(not DATABASE_URL.startswith("postgres"), reason="needs the kiosk database: set DATABASE_URL")

# Roads within 400 m of 3080 Lincoln Ave, as public.roads names them (a real answer from the kiosk).
NEARBY = ["Lincoln Avenue", "Westwood Street", "Pipeline Road", "Glen Drive", "Pinetree Way",
          "The High Street", "Chartwell Green", "Chartwell Lane (PRIV)"]


@NEEDS_DB
def test_the_suffix_vocabulary_is_reachable():
    from gis_service.normalization import get_suffix_mappings
    assert get_suffix_mappings()


@NEEDS_DB
def test_exact_and_base_name_matches():
    assert match_heard_road("Westwood St", NEARBY) == ("Westwood Street", "exact")
    assert match_heard_road("westwood street", NEARBY) == ("Westwood Street", "exact")
    assert match_heard_road("Westwood", NEARBY) == ("Westwood Street", "base")          # suffix not heard
    assert match_heard_road("Pipeline Rd", NEARBY) == ("Pipeline Road", "exact")


@NEEDS_DB
def test_two_suffix_forms_of_one_name_are_ambiguous_not_guessed():
    resolved, how = match_heard_road("Chartwell Rd", NEARBY)
    assert resolved is None and how == "ambiguous"


@NEEDS_DB
def test_a_mishearing_within_the_nearby_set_is_matched_and_marked():
    resolved, how = match_heard_road("Westward Street", NEARBY)
    assert resolved == "Westwood Street" and how == "nearby-fuzzy"


@NEEDS_DB
def test_a_name_that_is_not_nearby_stays_as_heard():
    resolved, how = match_heard_road("Como Lake Avenue", NEARBY)   # real street, 3 km away
    assert resolved is None and how == "unresolved"


@NEEDS_DB
def test_apply_reports_what_it_did():
    class FakeValidator:
        def roads_near_point(self, lat, lng, r):
            assert r == NEAR_ROAD_RADIUS_M
            return NEARBY

        def roads_in_zone(self, z):
            return []
    out = apply_near_roads("Westwood St", "Como Lake Avenue", FakeValidator(), 49.2786, -122.7884)
    assert out["x_street_1"] == "Westwood Street" and out["x_street_2"] == "Como Lake Avenue"
    assert out["x_streets_how"] == ["exact", "unresolved"]
    assert out["xstreets_unresolved"] == 1 and out["xstreets_substituted"] == 0
    assert out["x_streets_heard"] == ["Westwood St", "Como Lake Avenue"]


@NEEDS_DB
def test_live_roads_near_3080_lincoln_and_in_its_zone():
    from gis_service import CoquitlamDataValidator
    v = CoquitlamDataValidator(database_url=DATABASE_URL)
    near = v.roads_near_point(49.27864, -122.78835, NEAR_ROAD_RADIUS_M)
    assert "Westwood Street" in near and "Pipeline Road" in near, near[:10]
    assert 5 <= len(near) <= 80, len(near)
    in_zone = v.roads_in_zone("82")
    assert "Westwood Street" in in_zone, in_zone[:10]
    out = apply_near_roads("westwood street", "pipeline road", v, 49.27864, -122.78835)
    assert out["x_street_1"] == "Westwood Street" and out["x_street_2"] == "Pipeline Road"
    assert out["xstreets_unresolved"] == 0
