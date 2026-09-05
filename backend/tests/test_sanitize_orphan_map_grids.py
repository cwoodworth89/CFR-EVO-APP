"""The sanitizer drops "map grid N" phrases the STT inserted mid-round (punch-list #63).

Every transcript below is a real one from the 2026-09-05 chain-harness run of the model in
service (`tools/harness_chain.py --only-csv`), lightly cut to the round in question; none is
synthesised (CLAUDE.md 6.5). The verified map grid is the operator's. Before the fix the
parser read the first "map grid" it saw and split_rounds cut the round there, so each of
these lost the grid and, in most, the cross streets.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cfr_dispatch.config import UNITS_VOCABULARY  # noqa: E402
from cfr_dispatch.parser import (  # noqa: E402
    parse_dispatch_announcement,
    sanitize_transcript,
    split_rounds,
)

HEAD = "coquitlam engine 1 respond emergency "


def grid_and_address(raw):
    """What production takes from a transcript: first candidate carrying each value."""
    san = sanitize_transcript(raw)
    cands = []
    for seg in split_rounds(san, UNITS_VOCABULARY):
        if len(seg.split()) > 2:
            cands.extend(parse_dispatch_announcement(seg, UNITS_VOCABULARY))
    grid = next((c.map_grid for c in cands if c.map_grid), None)
    addr = next((c.address or c.intersection for c in cands if c.address or c.intersection), None)
    return grid, addr


@pytest.mark.parametrize("heard, grid", [
    # DISP-2026-CC6490: insertion between the address and its cross streets
    ("medical aid, chest pain 2950 glen drive near coquitlam map grid 68 pacific street & the high "
     "street use talk group 10 combined response coquitlam map grid 82", "82"),
    # DISP-2026-32C106: two insertions, one with a stray "respond"
    ("medical aid, headache 1442 coquitlam map grid 101 respond coquitlam map grid 101 near sultan "
     "place & forecourt use talk group 10 combined response coquitlam map grid 103", "103"),
    # DISP-2026-FA8817
    ("medical aid. chest pain 1339 coquitlam map grid 1 under delahay drive & alvis court use talk "
     "group 10 combined response coquitlam map grid 87", "87"),
    # DISP-2026-C0B563: the talk-group clause was lost entirely; the last phrase still wins
    ("medical aid. collapse 3239 chrome coquitlam map grid 62 coquitlam map grid 100", "100"),
    # DISP-2026-C56F81
    ("alarm activated 3166 coquitlam map grid 65 silver throne drive near halum court & arosmith "
     "place use talk group 5 coquitlam map grid 95", "95"),
])
def test_inserted_map_grid_phrases_are_dropped(heard, grid):
    got_grid, _ = grid_and_address(HEAD + heard)
    assert got_grid == grid


def test_the_address_survives_once_the_insertion_is_gone():
    # DISP-2026-C56F81: before the fix the round was cut at "map grid 65" and the address
    # was "3166" with nothing after it.
    _, addr = grid_and_address(HEAD + "alarm activated 3166 coquitlam map grid 65 silver throne "
                               "drive near halum court & arosmith place use talk group 5 "
                               "coquitlam map grid 95")
    assert addr and addr.startswith("3166 Silver")


def test_two_genuine_rounds_are_untouched():
    # DISP-2026-870660 shape: the same round twice, each grid anchored by its talk group.
    rnd = ("medical aid fall 2930 barnet highway use talk group 10 combined response coquitlam "
           "map grid 82 ")
    san = sanitize_transcript(HEAD + rnd + HEAD + rnd)
    rounds = split_rounds(san, UNITS_VOCABULARY)
    assert len(rounds) == 2
    grids = [next((c.map_grid for c in parse_dispatch_announcement(r, UNITS_VOCABULARY) if c.map_grid), None)
             for r in rounds]
    assert grids == ["82", "82"]
