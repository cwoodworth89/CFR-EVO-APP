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


# --- Descriptors: the things dispatch announces that are not streets -------------------------
#
# public.vocabulary category `xstreet_descriptor`, seeded 2026-08-23 and unread until
# 2026-09-12. Operator: "I don't want turning lane or mall access road to throw errors if that
# is what the system hears", and "street first, descriptor only if no street matches".
# These rows mirror the live vocabulary so the ordering is pinned without a database.
VOCAB = [
    {"term": "Turning Lane", "normalized": "TURNING LANE", "kind": "generic"},
    {"term": "Turning Ln", "normalized": "TURNING LANE", "kind": "generic"},
    {"term": "Access Road", "normalized": "ACCESS ROAD", "kind": "generic"},
    {"term": "Access Rd", "normalized": "ACCESS ROAD", "kind": "generic"},
    {"term": "Private Driveway", "normalized": "PRIVATE DRIVEWAY", "kind": "generic"},
    {"term": "School Access", "normalized": "SCHOOL ACCESS", "kind": "prefixed"},
    {"term": "Mall Access", "normalized": "MALL ACCESS", "kind": "ambiguous"},
]


class _Validator:
    """Stands in for the geocoder: the candidate roads and the descriptor vocabulary."""

    def __init__(self, candidates, vocab=VOCAB):
        self._candidates, self._vocab = candidates, vocab

    def roads_near_point(self, lat, lng, radius_m):
        return self._candidates

    def roads_in_zone(self, zone_id):
        return []

    def xstreet_descriptors(self):
        return self._vocab


def test_a_descriptor_is_its_own_outcome_not_an_unresolved_road():
    from cfr_dispatch.pipeline.near_roads import resolve_near_roads
    # DISP-2026-11DB02: "2929 barnet highway Coquitlam Center Mall, near mall access and
    # turning lane". Candidates are the roads public.roads has within 400 m of the mall.
    mall = ["Aberdeen", "Anson", "Barnet", "Bus Depot", "Christmas", "Conley", "Dufferin",
            "Hansard", "Johnson", "Lougheed", "Mariner", "Packard", "Pinetree"]
    out = resolve_near_roads(["Mall Access", "Turning Ln"], _Validator(mall), 49.2800, -122.8000)
    assert [n["how"] for n in out] == ["descriptor", "descriptor"]
    # Shown in the vocabulary's canonical spelling, not as the fake street "Turning Ln".
    assert out[1]["resolved"] == "Turning Lane"
    assert out[0]["kind"] == "ambiguous" and out[1]["kind"] == "generic"


def test_a_descriptor_does_not_count_toward_the_review_flag():
    mall = ["Aberdeen", "Anson", "Barnet", "Dufferin", "Pinetree"]
    got = apply_near_roads("Mall Access", "Turning Ln", _Validator(mall), 49.2800, -122.8000)
    assert got["xstreets_unresolved"] == 0      # XSTREET_UNRESOLVED no longer fires
    assert got["xstreets_substituted"] == 0     # nor was anything rewritten to a street
    assert got["xstreets_descriptors"] == 2
    assert got["x_street_1"] == "Mall Access" and got["x_street_2"] == "Turning Lane"


def test_a_prefixed_descriptor_keeps_the_facility_it_names():
    from cfr_dispatch.pipeline.near_roads import match_descriptor
    # DISP-2026-D0437C: "near private driveway and summit middle school access". The facility
    # is the useful half, so a prefixed match keeps the heard text rather than "School Access".
    text, kind = match_descriptor("Summit Middle School Access", VOCAB)
    assert (text, kind) == ("Summit Middle School Access", "prefixed")
    assert match_descriptor("School Access", VOCAB)[0] == "School Access"


def test_a_street_wins_over_a_descriptor():
    """Operator ruling 2026-09-12. The order is what keeps a mishearing from being accepted:
    Whisper writes "near a gate" for Agate, and were "a gate" ever added to the vocabulary,
    checking descriptors first would pass a wrong street through with no flag at all."""
    from cfr_dispatch.pipeline.near_roads import resolve_near_roads
    vocab = VOCAB + [{"term": "Access Road", "normalized": "ACCESS ROAD", "kind": "generic"}]
    out = resolve_near_roads(["Access Rd"], _Validator(["Access Road", "Barnet"], vocab), 49.28, -122.80)
    assert out[0]["how"] == "exact"
    assert out[0]["resolved"] == "Access Road"


def test_a_mistranscription_is_still_flagged():
    from cfr_dispatch.pipeline.near_roads import resolve_near_roads
    # Not in the vocabulary and not a road nearby: exactly what the flag is for.
    for heard in ("Nice Drum Crt", "Lorension Cres", "A Gate"):
        out = resolve_near_roads([heard], _Validator(["Agate", "Diamond", "Panorama"]), 49.30, -122.81)
        assert out[0]["how"] != "descriptor", heard
        assert out[0]["resolved"] is None, heard


def test_a_term_absent_from_the_vocabulary_still_flags():
    """A descriptor nobody has curated yet is seen once, then added. That is the intended
    behaviour, and it is why the vocabulary is data: "Unnamed Lane" flagged until the operator
    ruled it in on 2026-09-12 (migration 2026-09-12_xstreet_descriptor_unnamed_lane.sql)."""
    from cfr_dispatch.pipeline.near_roads import resolve_near_roads
    out = resolve_near_roads(["Some New Thing Access Way"], _Validator(["Pinewood", "Pinetree"]), 49.28, -122.79)
    assert out[0]["how"] == "unresolved"


def test_unnamed_lane_is_a_descriptor_now():
    """DISP-2026-0093AD: "near pinewood avenue and unnamed lane". Both spellings, because
    suffix normalisation turns the spoken "Lane" into "Ln" before this sees it."""
    from cfr_dispatch.pipeline.near_roads import resolve_near_roads
    vocab = VOCAB + [
        {"term": "Unnamed Lane", "normalized": "UNNAMED LANE", "kind": "generic"},
        {"term": "Unnamed Ln", "normalized": "UNNAMED LANE", "kind": "generic"},
    ]
    nearby = ["Delahaye", "Julian", "Pinetree", "Pinewood", "Town Centre", "Walton"]
    out = resolve_near_roads(["Pinewood Ave", "Unnamed Ln"], _Validator(nearby, vocab), 49.2810, -122.7930)
    assert out[0]["how"] == "base"                 # the real road still wins on its own merits
    assert out[1]["how"] == "descriptor"
    assert out[1]["resolved"] == "Unnamed Lane"
