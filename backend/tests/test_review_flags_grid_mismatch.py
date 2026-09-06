"""GRID_MISMATCH: phase 1 published the parcel's zone, phase 2 heard a different grid (#72).

Pure: compute_review_flags takes every input by keyword. The two grids compare without leading
zeros, as round_comparison does, so "082" and "82" are the same zone.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cfr_dispatch.pipeline.review_flags import (  # noqa: E402
    GRID_MISMATCH, NO_MAP_GRID, FLAG_LABELS, compute_review_flags)

BASE = dict(lat=49.28, lng=-122.79, responding_units=["E1"], incident_type="Structure Fire",
            radio_channel="10 Combined Response", response_type="emergency")


def test_spoken_grid_that_differs_from_the_parcels_zone_is_flagged():
    flags = compute_review_flags(map_grid="68", derived_map_grid="82", **BASE)
    assert GRID_MISMATCH in flags and NO_MAP_GRID not in flags


def test_agreement_is_not_flagged():
    assert GRID_MISMATCH not in compute_review_flags(map_grid="82", derived_map_grid="82", **BASE)
    assert GRID_MISMATCH not in compute_review_flags(map_grid="082", derived_map_grid="82", **BASE)


def test_no_derived_grid_means_nothing_to_compare():
    assert GRID_MISMATCH not in compute_review_flags(map_grid="68", derived_map_grid=None, **BASE)
    flags = compute_review_flags(map_grid=None, derived_map_grid="82", **BASE)
    assert NO_MAP_GRID in flags and GRID_MISMATCH not in flags


def test_the_flag_has_operator_wording():
    assert GRID_MISMATCH in FLAG_LABELS and "zone" in FLAG_LABELS[GRID_MISMATCH]
