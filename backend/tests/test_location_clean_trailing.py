"""The trailing-junk strip in clean_location_text cuts at the last suffix word, not the first (#73).

"Gate" is a street suffix (Windsor Gate). When the STT heard Agate Place as "a gate place and
topas crt", the first-match strip cut everything after "gate": DISP-2026-5317C5, a live call on
2026-09-06, showed "Near A Gate (as heard)" and lost Topaz Court. Pure: no database, the real
vocabulary lists.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cfr_dispatch.parser.location import clean_location_text, normalize_street_suffix  # noqa: E402

UNITS = ["Engine", "Ladder", "Rescue", "Quint", "Car", "Medic", "Hazmat", "Hazmat Tender", "Squad"]
CALL_TYPES = ["Medical Aid - Breathing Problem", "Alarm Activated", "Stove Fire"]


def parts(text):
    cleaned = clean_location_text(text, CALL_TYPES, UNITS)
    return [normalize_street_suffix(p) for p in re.split(r'\s+(?:and|at|&)\s+', cleaned, flags=re.IGNORECASE) if p.strip()]


def test_the_live_call_keeps_both_near_roads():
    # As sanitised on the kiosk, round 1 and round 2 of the same broadcast.
    assert parts("a gate place and topas crt") == ["A Gate Pl", "Topas Crt"]
    assert parts("a gate place and topaz court") == ["A Gate Pl", "Topaz Crt"]


def test_a_correctly_heard_pair_is_unchanged():
    assert parts("agate place and topaz court") == ["Agate Pl", "Topaz Crt"]


def test_trailing_junk_after_the_only_suffix_is_still_stripped():
    assert clean_location_text("lougheed highway superstore", CALL_TYPES, UNITS) == "lougheed highway"
    assert clean_location_text("burlington drive 105", CALL_TYPES, UNITS) == "burlington drive"
    assert clean_location_text("3093 windsor gate number 2307 the windsor", CALL_TYPES, UNITS) == "3093 windsor gate"


def test_a_suffix_word_that_starts_a_name_no_longer_cuts_it():
    # The 2026-09-02 defect, now handled without the known_streets list.
    assert clean_location_text("1234 st laurence street", CALL_TYPES, UNITS) == "1234 st laurence street"
