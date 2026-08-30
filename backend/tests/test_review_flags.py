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


class TestFlagLifecycle:
    """Where flags live, and how phase 2 supersedes phase 1.

    The operator asked: if phase 1 flags a missing map grid and phase 2's second
    round picks it up, is the stale flag cleared? Answering it exposed a real bug --
    the flags were being written at the TOP LEVEL of the payload, where the API drops
    them, because there is no review_flags column and updates are applied with
    `setattr` over a Pydantic model_dump. They now live in `target`, which is what
    the frontend reads and what phase 2 replaces wholesale.
    """

    def test_flags_are_written_into_target_not_the_top_level(self):
        """A top-level key with no schema field is silently discarded by the API."""
        import inspect
        from cfr_dispatch.pipeline import payload_builder

        src = inspect.getsource(payload_builder)
        target_block = src[src.index("target_payload = {"):src.index("db_payload = {")]
        db_block = src[src.index("db_payload = {"):]

        assert '"review_flags": review_flags,' in target_block, \
            "review_flags must be inside target_payload or the API drops them"
        assert '"review_flags"' not in db_block.split("}")[0], \
            "review_flags must NOT be a top-level db_payload key"

    def test_phase2_recomputes_rather_than_clearing(self):
        """Phase 2 confirming an ADDRESS says nothing about a missing talk group.

        The earlier code set confidence_score = 100.0 here, which erased metadata
        problems it had not looked at.
        """
        import inspect
        from cfr_dispatch.pipeline import phase2

        src = inspect.getsource(phase2)
        assert src.count("compute_review_flags(") >= 2, \
            "each phase 2 update path must recompute flags, not assume them away"
        # Comments still name confidence_score to explain what was removed, so this
        # checks executable lines only rather than the raw source.
        code = "\n".join(
            line for line in src.splitlines()
            if not line.lstrip().startswith("#")
        )
        assert "confidence_score" not in code, \
            "confidence_score must not survive in executable phase 2 code"

    def test_a_resolved_grid_clears_the_flag(self):
        """The operator's example: phase 1 has no grid, phase 2 hears it."""
        p1 = compute_review_flags(**{**CLEAN, "map_grid": ""})
        assert NO_MAP_GRID in p1

        # Phase 2 recomputes with the grid it heard on the second round.
        p2 = compute_review_flags(**{**CLEAN, "map_grid": "88"})
        assert NO_MAP_GRID not in p2
        assert p2 == [], "no other flag should appear from resolving the grid"

    def test_resolving_one_field_does_not_clear_the_others(self):
        """Superseding must be a recompute, not a reset."""
        p1 = compute_review_flags(**{**CLEAN, "map_grid": "", "radio_channel": ""})
        assert set(p1) == {NO_MAP_GRID, NO_TALK_GROUP}

        p2 = compute_review_flags(**{**CLEAN, "map_grid": "88", "radio_channel": ""})
        assert p2 == [NO_TALK_GROUP], \
            "the talk group is still missing and must survive the grid being resolved"
