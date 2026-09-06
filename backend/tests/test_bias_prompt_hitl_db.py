"""The misheard-street list comes from the whole corpus, not the API's last 200 rows (#71 step 2).

Read-only against the kiosk database (DATABASE_URL); skipped otherwise. The two Thor Crt calls
(2026-08-08 and 08-14, heard as "four") and the Kensal Pl calls were outside the API window on
2026-09-05 and are the reason the source moved.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cfr_dispatch  # noqa: E402,F401
from cfr_dispatch.stt import bias_prompt as bp  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL.startswith("postgres"),
                                reason="needs the kiosk database: set DATABASE_URL")


@pytest.fixture(scope="module")
def streets():
    from sqlalchemy import create_engine
    bp._cached_hitl_streets, bp._last_hitl_fetch_time = [], 0.0  # bypass the 10-minute cache
    engine = create_engine(DATABASE_URL)
    try:
        return bp.get_hitl_verified_streets(engine)
    finally:
        engine.dispose()


def test_the_streets_misheard_twice_are_in_the_list(streets):
    assert "Thor Crt" in streets
    assert "Kensal Pl" in streets


def test_every_entry_is_one_street_in_the_municipal_form(streets):
    assert streets, "no reviewed dispatches with a verified address?"
    for s in streets:
        assert "&" not in s and " And " not in s and " and " not in s, s
        assert not s[0].isdigit(), s
        assert s == s.title() or any(ch.isdigit() for ch in s), s


def test_most_misheard_first(streets):
    # Kensal Pl was wrong on three of its four calls; Thor Crt on both of its two.
    assert streets.index("Kensal Pl") < streets.index("Thor Crt")
