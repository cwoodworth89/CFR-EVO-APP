"""Hotword street terms: one street per term, suffix in the municipal form, intersections split.

Punch list #71: on 2026-09-05 seven of the twelve HITL terms in the live hotword list were whole
intersection strings at about eight tokens each, and the frequency ranking carried five suffix
pairs of one street in its top 60. These are the real strings from that list and from the
verified column.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cfr_dispatch  # noqa: E402,F401  sibling services on sys.path
from cfr_dispatch.stt.bias_prompt import street_terms, dedupe_terms  # noqa: E402


def test_an_intersection_gives_its_two_streets():
    assert street_terms("Westwood St & Lougheed Hwy") == ["Westwood St", "Lougheed Hwy"]
    assert street_terms("Ozada Avenue And Tahsis Ave") == ["Ozada Ave", "Tahsis Ave"]
    assert street_terms("Gatensbury St And Grover Ave") == ["Gatensbury St", "Grover Ave"]


def test_house_number_and_locality_are_dropped():
    assert street_terms("3080 Lincoln Ave, Coquitlam, BC") == ["Lincoln Ave"]
    assert street_terms("105-3000 Riverbend Dr") == ["Riverbend Dr"]
    assert street_terms("Pinetree Way") == ["Pinetree Way"]


def test_suffix_variants_are_one_street():
    assert street_terms("2747 LOUGHEED HIGHWAY") == street_terms("2747 Lougheed Hwy") == ["Lougheed Hwy"]
    assert dedupe_terms(["Lougheed Hwy", "Barnet Hwy", "Lougheed Highway", "Barnet Highway", "Kensal Pl"]) == \
        ["Lougheed Hwy", "Barnet Hwy", "Kensal Pl"]


def test_not_a_street_gives_nothing():
    assert street_terms("") == []
    assert street_terms(None) == []
    assert street_terms("Unknown Location") == ["Unknown Location"]  # still a term; the tally never sees it
    assert street_terms("1234") == []
