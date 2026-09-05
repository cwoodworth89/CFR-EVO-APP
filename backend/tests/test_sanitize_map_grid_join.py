"""The sanitizer must not glue the next clause's number onto a map grid.

DISP-2026-CF0CC2, replayed 2026-09-05 with "map grid" left out of the STT hotwords: the model
dropped the opening of round 2, so the transcript read "... map grid 82 10 combined response
...". The digit-join rule in sanitize_transcript made that "map grid 8210", which the parser
rejected as not a zone, and the call lost its grid (punch list #68). A map grid is at most
three digits (MAP_GRIDS, zones 1-134), so a join that would exceed three after "map grid" is
refused; "map grid 10 9" still becomes 109, and house numbers are untouched.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cfr_dispatch.config import UNITS_VOCABULARY  # noqa: E402
from cfr_dispatch.parser import (  # noqa: E402
    parse_dispatch_announcement,
    sanitize_transcript,
    split_rounds,
)

HEARD = ("coquitlam medic 1 respond emergency medical aid collapse 3025 lougheed highway near "
         "turning lane use talk group 10 combined response coquitlam map grid 82  10 combined "
         "response coquitlam map grid 82")


def first_grid(raw):
    """What production takes from a transcript: the first candidate carrying a grid."""
    cands = []
    for seg in split_rounds(sanitize_transcript(raw), UNITS_VOCABULARY):
        if len(seg.split()) > 2:
            cands.extend(parse_dispatch_announcement(seg, UNITS_VOCABULARY))
    return next((c.map_grid for c in cands if c.map_grid), None)


def test_grid_survives_a_lost_round_2_opening():
    assert "map grid 82 10 combined" in sanitize_transcript(HEARD)
    assert first_grid(HEARD) == "82"


def test_split_grid_digits_still_join():
    assert "map grid 109" in sanitize_transcript(
        "use talk group 10 combined response coquitlam map grid 10 9")


def test_house_numbers_still_join():
    assert "1378 oxford" in sanitize_transcript("medical aid 1, 3, 7, 8, oxford street")
    assert "1100 pinetree" in sanitize_transcript("structure fire 110 0 pinetree way")
