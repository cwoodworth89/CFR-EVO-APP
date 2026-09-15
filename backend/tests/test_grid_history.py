"""Map-grid retention's rules, without a database (grid_history, operator ruling 2026-09-13/14).

  * one verified call is enough;
  * the call's own unit first, then the whole address;
  * calls that disagree give no answer, so phase 1 keeps the lot's zone.

The unit cases are 2601 Lougheed Hwy as the corpus has it (2026-09-13): Number 24 was dispatched 53
twice, Number 29 55 twice, the address without a unit 55.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cfr_dispatch  # noqa: E402,F401  (puts services/*/src on sys.path)
from cfr_dispatch.pipeline.grid_history import address_key, choose_grid, unit_key  # noqa: E402

LOUGHEED_2601 = [("55", None), ("53", "24"), ("55", "29"), ("55", "29"), ("53", "24")]


def test_unit_wordings_compare_equal():
    assert unit_key("Number 24") == unit_key("Unit 24") == unit_key("#24") == unit_key("suite 24") == "24"
    assert unit_key("Number 2507") == "2507"
    assert unit_key(None) is None and unit_key("") is None and unit_key("   ") is None


def test_a_verified_address_and_the_resolved_one_share_a_key():
    assert address_key("1300 Pinetree Way") == address_key("1300 PINETREE WAY")
    assert address_key("1300 Pinetree Way") != address_key("1310 Pinetree Way")
    assert address_key("Pinetree Way") is None  # no house number, no key


def test_one_verified_call_is_enough():
    assert choose_grid([("86", None)], None) == ("86", "address", 1)


def test_agreeing_calls_are_counted():
    assert choose_grid([("86", None)] * 6, None) == ("86", "address", 6)


def test_a_units_own_history_comes_first():
    assert choose_grid(LOUGHEED_2601, "24") == ("53", "unit", 2)
    assert choose_grid(LOUGHEED_2601, "29") == ("55", "unit", 2)


def test_a_unit_with_no_history_falls_to_the_address_and_disagreement_gives_nothing():
    assert choose_grid(LOUGHEED_2601, "30") is None
    assert choose_grid(LOUGHEED_2601, None) is None


def test_a_unit_whose_own_calls_disagree_gives_nothing():
    assert choose_grid([("53", "24"), ("55", "24")], "24") is None


def test_no_history_gives_nothing():
    assert choose_grid([], None) is None and choose_grid([], "24") is None
