"""Subaddress / business-name extraction in cfr_dispatch.parser.location.

Two defects found 2026-09-02 while spell-checking the operator's verified transcripts
against public.roads (backend/scripts/check_verified_transcripts.py). Both produced a
plausible, wrong street rather than an error -- the failure mode CLAUDE.md s6 exists to
prevent -- and neither had a test.

  1. The extractor's hand-typed suffix regex lacked "crt", so
     "1200 glen pine crt Glen Pine Pavilion" came back whole as the street. The live
     system had been getting it right only because Whisper said "Court"; the fine-tuned
     model is trained on the operator's transcripts, which write "crt".
  2. It matched the FIRST suffix word, so "1234 st laurence street unit 5" -- a real
     street -- became address "1234 St", subaddress "Laurence Street Unit 5".

The fix prefers the longest municipal street name after the house number, and falls back
to suffix scanning (now from the single _SUFFIX_EQUIV list) only when no name matches.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cfr_dispatch.parser.location import (  # noqa: E402
    extract_subaddress_info,
    split_street_base_suffix,
)

# Real Coquitlam street names (public.road_names shape: full municipal form), plus one
# synthetic shorter prefix so the longest-match rule is exercised explicitly.
KNOWN = [
    "Glen Pine Court",
    "Glen Court",                 # synthetic prefix of the one above
    "St Laurence Street",
    "Gordon Avenue",
    "Town Centre Boulevard",
    "Pinetree Way",
    "Main Street",
]


@pytest.mark.parametrize("text, expected", [
    # defect 1: operator's abbreviation, business name follows
    ("1200 glen pine crt glen pine pavilion", ("1200 glen pine crt", "Glen Pine Pavilion")),
    # same call as Whisper used to say it
    ("1200 glen pine court glen pine pavilion", ("1200 glen pine court", "Glen Pine Pavilion")),
    # defect 2: a street whose first word is itself a suffix
    ("1234 st laurence street unit 5", ("1234 st laurence street", "Unit 5")),
    # business name after a full municipal name
    ("3030 gordon avenue rain city housing", ("3030 gordon avenue", "Rain City Housing")),
    # bare trailing number becomes a unit
    ("1252 town centre blvd 125", ("1252 town centre blvd", "Unit 125")),
    # nothing trailing
    ("3030 gordon avenue", ("3030 gordon avenue", None)),
])
def test_known_street_splits_at_the_municipal_name(text, expected):
    assert extract_subaddress_info(text, KNOWN) == expected


def test_longest_municipal_name_wins_over_a_shorter_prefix():
    # "Glen Court" is a prefix of "Glen Pine Court"; the longer one must win, or the
    # street becomes "1200 glen" with "Pine Crt ..." demoted to a business name.
    addr, sub = extract_subaddress_info("1200 glen pine crt glen pine pavilion", KNOWN)
    assert addr == "1200 glen pine crt"
    assert sub == "Glen Pine Pavilion"


def test_intersection_tail_is_not_a_subaddress():
    text = "1234 main st and pinetree way"
    assert extract_subaddress_info(text, KNOWN) == (text, None)


def test_misheard_street_falls_back_to_suffix_scan_and_now_knows_crt():
    # "norbur" is not a municipal name (Norbury is), so the known-street path misses and
    # the suffix scan runs -- which must now recognise "crt" as well as "pl".
    assert extract_subaddress_info("2886 norbur pl unit 3", KNOWN) == ("2886 norbur pl", "Unit 3")
    assert extract_subaddress_info("1200 glen pine crt glen pine pavilion") == (
        "1200 glen pine crt", "Glen Pine Pavilion")


def test_without_known_streets_st_laurence_is_still_wrong_and_that_is_documented():
    # The fallback cannot get this right -- it is why the municipal list is preferred.
    # Documented here so a future "simplification" that drops known_streets fails loudly.
    addr, _ = extract_subaddress_info("1234 st laurence street unit 5")
    assert addr == "1234 st"


def test_split_street_base_suffix_knows_crt():
    assert split_street_base_suffix("Glen Pine Crt") == ("Glen Pine", "Crt")
    assert split_street_base_suffix("Glen Pine Court") == ("Glen Pine", "Court")
