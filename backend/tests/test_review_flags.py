"""Tests for the named review flags that replaced confidence_score (punch-list #45).

The old score could not be tested meaningfully: it was one number blending address
correctness with metadata completeness, so no assertion could say what it meant.
Each flag here is a single named condition, which is the point.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cfr_dispatch.pipeline.review_flags import (  # noqa: E402
    compute_review_flags,
    LOCATION_UNRESOLVED, LOCATION_SUBSTITUTED, STREET_SECTION_ONLY,
    NO_TALK_GROUP, NO_MAP_GRID, NO_UNITS, UNKNOWN_CALL_TYPE,
    RESPONSE_TYPE_UNKNOWN, FLAG_LABELS,
)

CLEAN = dict(
    lat=49.2963, lng=-122.7802,
    responding_units=["E1", "L1"],
    incident_type="Alarm Activated - High Risk",
    map_grid="88",
    radio_channel="Talk Group 5 Coquitlam",
    response_type="emergency",
)


def test_a_complete_dispatch_raises_nothing():
    assert compute_review_flags(**CLEAN) == []


@pytest.mark.parametrize("override,expected", [
    ({"lat": None}, LOCATION_UNRESOLVED),
    ({"lng": None}, LOCATION_UNRESOLVED),
    ({"radio_channel": ""}, NO_TALK_GROUP),
    ({"map_grid": ""}, NO_MAP_GRID),
    ({"responding_units": []}, NO_UNITS),
    ({"responding_units": ["Unknown Unit"]}, NO_UNITS),
    ({"incident_type": ""}, UNKNOWN_CALL_TYPE),
    ({"incident_type": "EMERGENCY DISPATCH"}, UNKNOWN_CALL_TYPE),
    ({"incident_type": "Unknown Incident"}, UNKNOWN_CALL_TYPE),
    ({"response_type": None}, RESPONSE_TYPE_UNKNOWN),
    ({"response_type": ""}, RESPONSE_TYPE_UNKNOWN),
])
def test_each_condition_raises_its_own_flag(override, expected):
    flags = compute_review_flags(**{**CLEAN, **override})
    assert expected in flags


def test_routine_is_not_a_flag():
    """A routine call is complete, not deficient. Only an UNKNOWN response flags."""
    assert compute_review_flags(**{**CLEAN, "response_type": "routine"}) == []


def test_the_string_none_counts_as_missing():
    """Several upstream paths stringify a missing value rather than passing None.

    A bare falsiness check would let "None" through as a real talk group, which is
    exactly the kind of plausible-looking wrong answer CLAUDE.md 6.1 forbids.
    """
    assert NO_TALK_GROUP in compute_review_flags(**{**CLEAN, "radio_channel": "None"})
    assert NO_MAP_GRID in compute_review_flags(**{**CLEAN, "map_grid": "none"})


def test_resolver_substitution_and_street_section():
    assert LOCATION_SUBSTITUTED in compute_review_flags(
        **CLEAN, resolution_note="Snapped to nearest addressed parcel")
    assert STREET_SECTION_ONLY in compute_review_flags(
        **CLEAN, location_type="street_section")


def test_flags_accumulate_and_are_stable():
    """Multiple problems produce multiple flags, sorted so the order never churns."""
    flags = compute_review_flags(
        **{**CLEAN, "lat": None, "lng": None, "radio_channel": "",
           "map_grid": "", "response_type": None})
    assert set(flags) == {LOCATION_UNRESOLVED, NO_TALK_GROUP,
                          NO_MAP_GRID, RESPONSE_TYPE_UNKNOWN}
    assert flags == sorted(flags)


def test_every_flag_has_operator_facing_wording():
    """A flag with no label would surface as a raw identifier on the kiosk."""
    emitted = compute_review_flags(
        **{**CLEAN, "lat": None, "lng": None, "responding_units": [],
           "incident_type": "", "map_grid": "", "radio_channel": "",
           "response_type": None},
        resolution_note="substituted", location_type="street_section")
    for flag in emitted:
        assert flag in FLAG_LABELS, f"{flag} has no label"
    assert len(emitted) == 8, "expected every flag to fire on a worst-case dispatch"
