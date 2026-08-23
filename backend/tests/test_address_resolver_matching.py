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


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Serves the parcel query, then answers intersection lookups from a fixed set."""

    def __init__(self, parcel_rows, meeting_streets=()):
        self.parcel_rows = parcel_rows
        self.meeting_streets = {s.upper() for s in meeting_streets}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        if "public.intersections" in sql:
            street = (params or {}).get("s1", "").upper()
            return _FakeResult([(1,)] if street in self.meeting_streets else [])
        return _FakeResult(self.parcel_rows)


class _FakeEngine:
    def __init__(self, conn):
        self._conn = conn

    def connect(self):
        return self._conn


def _parcel(street, stype, zone, house="3000"):
    return {
        "id": 1, "address": f"{house} {street} {stype}", "house": house,
        "street": street, "streettype": stype, "zone_id": zone,
        "lat": 49.28, "lng": -122.79, "front_lat": None, "front_lng": None,
        "entrance_lat": None, "entrance_lng": None,
        "centroid_lat": None, "centroid_lng": None, "geom_geojson": None,
    }


class TestAmbiguityWaterfall:
    """Equally-matching streets are resolved by what dispatch announced.

    Order: map grid, then cross streets, then refuse. Both signals are stated by the
    dispatcher for the incident, so they outrank a similarity score -- and before this
    the tie was settled by whichever row the database happened to return first.
    """

    # A real Coquitlam collision: "wood st" is equidistant from both of these at 78
    # (measured on thefuzz 0.22.1), so neither wins on similarity alone. The resolver
    # threshold is lowered to 70 for these tests so the tie is reachable -- at the
    # production threshold of 80 this pair is refused earlier, which is also correct.
    ROWS = [_parcel("Westwood", "St", "85"), _parcel("Eastwood", "St", "82")]

    def _resolver(self, meeting_streets=()):
        return ar.AddressResolver(
            _FakeEngine(_FakeConn(self.ROWS, meeting_streets)), confidence_threshold=70)

    def test_the_pair_really_does_tie(self):
        # Guards the premise: if these stop tying, the tests below stop testing
        # anything and would pass for the wrong reason.
        assert ar.score_street("WOOD ST", "WESTWOOD ST") == \
            ar.score_street("WOOD ST", "EASTWOOD ST")

    def test_map_grid_breaks_the_tie(self):
        res = self._resolver().resolve_exact(
            "3000", "Wood St", "ST", target_map_grid="82")
        assert res is not None
        assert res["address"] == "3000 Eastwood St"

    def test_cross_streets_break_the_tie_when_grid_is_absent(self):
        res = self._resolver(meeting_streets={"WESTWOOD ST"}).resolve_exact(
            "3000", "Wood St", "ST", cross_street_1="Pinetree Way")
        assert res is not None
        assert res["address"] == "3000 Westwood St"

    def test_refuses_when_nothing_narrows_it(self):
        # No grid, no cross streets: unresolved is correct. Picking one would be the
        # original defect, which produced a confident wrong street.
        res = self._resolver().resolve_exact("3000", "Wood St", "ST")
        assert res is None

    def test_grid_that_matches_nothing_falls_through_to_cross_streets(self):
        # A grid naming a zone none of the candidates sit in must not empty the set;
        # it falls through to the next signal rather than resolving to nothing.
        res = self._resolver(meeting_streets={"EASTWOOD ST"}).resolve_exact(
            "3000", "Wood St", "ST",
            target_map_grid="999", cross_street_1="Pinetree Way")
        assert res is not None
        assert res["address"] == "3000 Eastwood St"


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
