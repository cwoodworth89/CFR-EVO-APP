"""The street-suffix vocabulary in public.vocabulary folds typed variants onto the City's forms.

Read-only against the kiosk database (DATABASE_URL); skipped otherwise. "Ct" is what the
operator types in review; "CRT" is what the City's parcel and road layers carry
(migration 2026-09-05_street_suffix_ct_alias.sql, punch list #71).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cfr_dispatch  # noqa: E402,F401
from gis_service.normalization import normalize_street_name, reset_suffix_cache  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL.startswith("postgres"),
                                reason="needs the kiosk database: set DATABASE_URL")


def setup_module(_):
    reset_suffix_cache()


def test_typed_ct_is_the_citys_crt():
    assert normalize_street_name("Sugarpine Ct") == "SUGARPINE CRT"
    assert normalize_street_name("Sugarpine Court") == "SUGARPINE CRT"
    assert normalize_street_name("Sugarpine Crt") == "SUGARPINE CRT"


def test_the_hand_typed_forms_in_the_verified_column_fold_onto_one_street():
    # Every last word the verified column used on 2026-09-05, other than places.
    pairs = [("Lougheed Highway", "Lougheed Hwy"), ("Gordon Avenue", "Gordon Ave"),
             ("Pollard Street", "Pollard St"), ("Runnel Drive", "Runnel Dr"),
             ("Kensal Place", "Kensal Pl"), ("Pipeline Road", "Pipeline Rd"),
             ("Silver Springs Boulevard", "Silver Springs Blvd"), ("Princess Crescent", "Princess Cres")]
    for typed, city in pairs:
        assert normalize_street_name(typed) == normalize_street_name(city), (typed, city)
