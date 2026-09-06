"""Rule A: a preliminary payload carries a location only when it resolved to a parcel or a junction.

Punch list #72, the operator's rule: unknown beats a guess. Measured on 507 recordings
replayed in the listener's chunks, withholding fallback placements from the first payload
removes 48 of the 52 wrong streets shown in the first minute for 81 unknown cards. Phase 2
places the call from the full recording.

Read-only against the kiosk database (DATABASE_URL); skipped otherwise. The transcripts are
real chunks and real announcement shapes from 2026-09-05.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cfr_dispatch  # noqa: E402,F401
from cfr_dispatch.config import UNITS_VOCABULARY  # noqa: E402
from cfr_dispatch.parser import sanitize_transcript, split_rounds, parse_dispatch_announcement  # noqa: E402
from cfr_dispatch.pipeline.payload_builder import build_dispatch_payload  # noqa: E402
from cfr_dispatch.pipeline.review_flags import LOCATION_UNRESOLVED, LOCATION_SUBSTITUTED  # noqa: E402
from gis_service import CoquitlamDataValidator  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL.startswith("postgres"),
                                reason="needs the kiosk database: set DATABASE_URL")

CUT_FIRE = ("coquitlam engine 1 engine 4 engine 2 rescue 2 quint 5 car 8 respond emergency structure fire "
            "166 coquitlam map grid 68")                                    # DISP-2026-33D8C2 at 23 s
PARCEL = ("coquitlam medic 1 respond emergency medical aid back pain 3080 lincoln avenue number 2507 "
          "near westwood street use talk group 10 combined response coquitlam map grid 68")
JUNCTION = ("coquitlam engine 1 respond emergency motor vehicle incident pinetree way and barnet highway "
            "use talk group 10 combined response coquitlam map grid 82")
TWO_JUNCTIONS = ("coquitlam engine 1 respond emergency motor vehicle incident westwood street and lougheed "
                 "highway use talk group 10 combined response coquitlam map grid 82")
BLOCK_ONLY = ("coquitlam engine 1 respond emergency medical aid 2905 lougheed highway near turning lane "
              "use talk group 10 combined response coquitlam map grid 82")   # no 2905 parcel (#64)


@pytest.fixture(scope="module")
def validator():
    return CoquitlamDataValidator(database_url=DATABASE_URL)


def preliminary(validator, raw):
    san = sanitize_transcript(raw)
    cands = []
    for seg in split_rounds(san, UNITS_VOCABULARY):
        if len(seg.split()) > 2:
            cands.extend(parse_dispatch_announcement(seg, UNITS_VOCABULARY))
    payload, _ = build_dispatch_payload("TEST", raw, san, cands, validator, UNITS_VOCABULARY, preliminary=True)
    return payload["target"]


def test_a_completion_that_is_not_a_place_is_withheld(validator):
    t = preliminary(validator, CUT_FIRE)
    assert t["location_pending"] is True and t["lat"] is None and t["lng"] is None
    assert t["address"] == "166 Coquitlam"           # what was heard stays visible
    assert LOCATION_UNRESOLVED in t["review_flags"] and LOCATION_SUBSTITUTED not in t["review_flags"]
    assert t["map_grid"] is None and t["routing_metrics"] == []


def test_a_parcel_goes_out(validator):
    t = preliminary(validator, PARCEL)
    assert t["location_pending"] is False and t["lat"] is not None
    assert t["address"] == "3080 Lincoln Ave" and t["map_grid_source"] == "parcel-zone"


def test_an_exact_junction_goes_out(validator):
    t = preliminary(validator, JUNCTION)
    assert t["location_pending"] is False and t["lat"] is not None
    assert t["address"] == "Pinetree Way & Barnet Hwy"


def test_several_junctions_go_out_for_the_operator_to_choose(validator):
    t = preliminary(validator, TWO_JUNCTIONS)
    assert t["location_pending"] is False and t["lat"] is not None


def test_a_number_the_city_does_not_have_is_withheld(validator):
    t = preliminary(validator, BLOCK_ONLY)
    assert t["location_pending"] is True and t["lat"] is None
    assert t["address"] == "2905 Lougheed Hwy"


def test_the_final_payload_is_not_gated(validator):
    san = sanitize_transcript(BLOCK_ONLY)
    cands = []
    for seg in split_rounds(san, UNITS_VOCABULARY):
        if len(seg.split()) > 2:
            cands.extend(parse_dispatch_announcement(seg, UNITS_VOCABULARY))
    payload, _ = build_dispatch_payload("TEST", BLOCK_ONLY, san, cands, validator, UNITS_VOCABULARY)
    t = payload["target"]
    assert t["location_pending"] is False and t["lat"] is not None   # phase 2 places it, note and all
    assert t.get("resolution_note")
