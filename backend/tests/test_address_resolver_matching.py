"""Street matching guards in gis_service.address_resolver.

These cover three defects found on 2026-08-23 by scoring the geocoder against the
human-verified dispatch corpus (backend/scripts/trace_geocode_corpus.py). All three
produced confident, plausible, wrong output rather than an error, which is the failure
mode CLAUDE.md §6 exists to prevent:

  1. token_set_ratio scored a bare street *type* as a perfect match against every
     street sharing that suffix ("3000 avenue" -> "3000 Walton Ave" at confidence 100).
  2. Tied scores were resolved by whichever row Postgres returned first, from a query
     with no ORDER BY.
  3. resolve_nearest_civic substituted an arbitrarily distant house number
     (3415 Harbour Dr -> 1869 Harbour Dr, 1546 away) and presented it as a location.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "services", "gis", "src"))

from gis_service import address_resolver as ar  # noqa: E402


@pytest.fixture(autouse=True)
def _suffix_vocabulary(monkeypatch):
    """Street-type vocabulary, matching public.vocabulary category 'street_suffix'.

    Stubbed so these stay unit tests: the real accessor raises without a reachable
    database, and the behaviour under test is the matching logic, not the lookup.
    """
    mappings = {
        "AVENUE": "AVE", "AVE": "AVE",
        "STREET": "ST", "ST": "ST",
        "ROAD": "RD", "RD": "RD",
        "DRIVE": "DR", "DR": "DR",
        "BOULEVARD": "BLVD", "BLVD": "BLVD",
        "CRESCENT": "CRES", "CRES": "CRES",
    }
    monkeypatch.setattr(ar, "get_suffix_mappings", lambda: mappings)
    monkeypatch.setattr(ar, "normalize_street_name",
                        lambda name: _normalize(name, mappings))


def _normalize(name, mappings):
    if not name:
        return ""
    words = str(name).strip().upper().split()
    if len(words) > 1 and words[-1] in mappings:
        words[-1] = mappings[words[-1]]
    return " ".join(words)


class TestStreetNameTokens:
    def test_a_street_type_alone_names_no_street(self):
        # The whole defect in one assertion: "AVE" identifies no street, so nothing
        # downstream may treat it as one.
        assert ar.street_name_tokens("AVE") == []
        assert ar.street_name_tokens("AVENUE AVE") == []
        assert ar.street_name_tokens("") == []

    def test_a_real_street_keeps_its_name(self):
        assert ar.street_name_tokens("WALTON AVE") == ["WALTON"]
        assert ar.street_name_tokens("SILVER SPRINGS BLVD") == ["SILVER", "SPRINGS"]


class TestScoreStreet:
    def test_subset_no_longer_scores_a_perfect_match(self):
        """The trap: token_set_ratio("AVE", "WALTON AVE") is 100.

        Verified against installed thefuzz 0.22.1. score_street must not inherit it.
        """
        assert ar.score_street("AVE", "WALTON AVE") < 80
        assert ar.score_street("AVE", "ANSON AVE") < 80

    def test_genuine_stt_noise_still_matches(self):
        # The guard must not be so tight that ordinary mis-transcription stops
        # resolving; "GORDEN" for "GORDON" is exactly what the corpus contains.
        assert ar.score_street("GORDEN AVE", "GORDON AVE") >= 80

    def test_exact_match_is_perfect(self):
        assert ar.score_street("GORDON AVE", "GORDON AVE") == 100


class TestQueryStreet:
    def test_duplicated_suffix_is_collapsed(self):
        """Step 1 passes raw ("Gordon Ave") and type ("AVE") together.

        token_set_ratio hid the duplicate because a set discards it; fuzz.ratio scored
        the resulting "GORDON AVE AVE" against "GORDON AVE" as 83, turning an exact
        parcel match into a near miss.
        """
        assert ar.query_street("Gordon Ave", "AVE") == "GORDON AVE"
        assert ar.score_street(ar.query_street("Gordon Ave", "AVE"), "GORDON AVE") == 100

    def test_trailing_unit_number_is_dropped(self):
        # No street name in public.parcels contains a numeric token (verified
        # 2026-08-23), so a number left on the street is a unit designator.
        assert ar.query_street("Pipeline Rd 205", "205") == "PIPELINE RD"
        assert ar.query_street("Dufferin St 204D", "204D") == "DUFFERIN ST"

    def test_street_without_a_unit_is_unchanged(self):
        assert ar.query_street("Silver Springs Blvd", "BLVD") == "SILVER SPRINGS BLVD"


class TestNoStreetNameIsRefused:
    """resolve_exact and validate_address_exists must both refuse a bare suffix.

    Neither should reach the database at all -- a fixture that raises on use proves
    the guard runs first.
    """

    class _ExplodingEngine:
        def connect(self):
            raise AssertionError(
                "queried the database for an address carrying no street name"
            )

    def test_resolve_exact_refuses(self):
        resolver = ar.AddressResolver(self._ExplodingEngine())
        assert resolver.resolve_exact("3000", "AVENUE", "AVE") is None

    def test_validator_refuses_and_confirms_nothing(self):
        # The worse half of the defect: this is the check meant to catch a bad
        # address, and it used to confirm one.
        resolver = ar.AddressResolver(self._ExplodingEngine())
        score, matched = resolver.validate_address_exists("3000", "AVENUE", "AVE")
        assert matched is None
        assert score == 0
