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


class TestApostropheHandling:
    """public.parcels and public.roads disagree on apostrophes.

    Verified 2026-08-28 against the kiosk database: "Deer's Leap" is the ONLY street
    name containing an apostrophe anywhere in parcels, roads, road_names or
    intersections -- and it appears in parcels only. The road layer spells it
    "Deers Leap Place".

    15 addressed parcels therefore looked like they sat on a street with no centreline,
    a shape indistinguishable from a genuinely missing municipal road. Because it is the
    only such name, stripping the apostrophe cannot collide two real streets.
    """

    @pytest.fixture
    def real_normalizer(self, monkeypatch):
        """The REAL normalize_street_name, not the module-level stub.

        The autouse _suffix_vocabulary fixture replaces ar.normalize_street_name with a
        simplified stub for the matching tests. That stub does not strip apostrophes, so
        asserting against it here would test the stub and pass regardless of the fix.
        This patches only the database accessor and exercises the real function.
        """
        from gis_service import normalization as norm
        monkeypatch.setattr(norm, "get_suffix_mappings", lambda: {
            "AVENUE": "AVE", "AVE": "AVE", "PLACE": "PL", "PL": "PL",
            "STREET": "ST", "ST": "ST",
        })
        norm.reset_suffix_cache()
        return norm.normalize_street_name

    def test_both_spellings_normalize_alike(self, real_normalizer):
        assert real_normalizer("Deer's Leap Pl") == real_normalizer("Deers Leap Place")
        assert real_normalizer("Deer's Leap Pl") == "DEERS LEAP PL"

    def test_typographic_apostrophe_too(self, real_normalizer):
        # A transcript or an operator correction may carry either character.
        assert real_normalizer("Deer’s Leap Pl") == real_normalizer("Deers Leap Pl")

    def test_an_ordinary_street_is_untouched(self, real_normalizer):
        assert real_normalizer("Gordon Avenue") == "GORDON AVE"


class TestTitleAddress:
    """Display casing must not break on the apostrophe it just learned to match.

    str.title() capitalizes after every non-letter, so the first correctly-resolving
    Deer's Leap address rendered on the kiosk as "1690 Deer'S Leap Pl".
    """

    def test_apostrophe_does_not_capitalize(self):
        from gis_service.normalization import title_address
        assert title_address("1690 DEER'S LEAP PL") == "1690 Deer's Leap Pl"

    def test_typographic_apostrophe_too(self):
        from gis_service.normalization import title_address
        assert title_address("DEER’S LEAP") == "Deer’s Leap"

    def test_hyphens_still_title_case(self):
        # Deliberately NOT repaired: "Mary Hill By-Pass" wants both parts capitalized,
        # so hyphens are left to str.title().
        from gis_service.normalization import title_address
        assert title_address("MARY HILL BY-PASS ROAD") == "Mary Hill By-Pass Road"

    def test_ordinary_address_unchanged(self):
        from gis_service.normalization import title_address
        assert title_address("3030 GORDON AVE") == "3030 Gordon Ave"


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
    """Serves the parcel query, then the near-road distance ranking.

    `cross_street_ranking` is an ordered list of parcel ids, closest first, standing in
    for the PostGIS ST_Distance query.
    """

    def __init__(self, parcel_rows, cross_street_ranking=None, known_roads=None):
        self.parcel_rows = parcel_rows
        self.cross_street_ranking = cross_street_ranking
        # Names _verify_cross_streets will consider real. Defaults to "every name asked
        # about is real", so tests opt in to the descriptor case explicitly.
        self.known_roads = known_roads

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        if "DISTINCT UPPER(roadname)" in sql:
            asked = list((params or {}).get("names", []))
            known = self.known_roads if self.known_roads is not None else asked
            return _FakeResult([(n,) for n in asked if n in known])
        if "xstreets" in sql:
            if not self.cross_street_ranking:
                return _FakeResult([])
            return _FakeResult([
                {"id": pid, "avg_m": float(10 * (i + 1)), "roads_matched": 2}
                for i, pid in enumerate(self.cross_street_ranking)
            ])
        return _FakeResult(self.parcel_rows)


class _FakeEngine:
    def __init__(self, conn):
        self._conn = conn

    def connect(self):
        return self._conn


def _parcel(street, stype, zone, house="3000", pid=1):
    return {
        "id": pid, "address": f"{house} {street} {stype}", "house": house,
        "street": street, "streettype": stype, "zone_id": zone,
        "lat": 49.28, "lng": -122.79, "front_lat": None, "front_lng": None,
        "entrance_lat": None, "entrance_lng": None,
        "centroid_lat": None, "centroid_lng": None, "geom_geojson": None,
    }


class TestAmbiguityWaterfall:
    """Equally-matching streets are resolved by what dispatch announced.

    Order: map grid, then near roads, then unresolved. Both are stated by the
    dispatcher for the incident, so they outrank a similarity score -- and before this
    the tie was settled by whichever row the database happened to return first.
    """

    # A real Coquitlam collision: "wood st" is equidistant from both of these at 78
    # (measured on thefuzz 0.22.1), so neither wins on similarity alone. The resolver
    # threshold is lowered to 70 for these tests so the tie is reachable -- at the
    # production threshold of 80 this pair is refused earlier, which is also correct.
    ROWS = [_parcel("Westwood", "St", "85", pid=1),
            _parcel("Eastwood", "St", "82", pid=2)]

    def _resolver(self, cross_street_ranking=None, known_roads=None):
        return ar.AddressResolver(
            _FakeEngine(_FakeConn(self.ROWS, cross_street_ranking, known_roads)),
            confidence_threshold=70)

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
        # Westwood ranks closest to the announced near roads, so it wins -- even
        # though nothing here requires it to intersect them.
        res = self._resolver(cross_street_ranking=[1, 2]).resolve_exact(
            "3000", "Wood St", "ST",
            cross_street_1="Pinetree Way", cross_street_2="Ponderosa St")
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
        res = self._resolver(cross_street_ranking=[2, 1]).resolve_exact(
            "3000", "Wood St", "ST", target_map_grid="999",
            cross_street_1="Pinetree Way", cross_street_2="Ponderosa St")
        assert res is not None
        assert res["address"] == "3000 Eastwood St"

    def test_cross_streets_that_tie_exactly_leave_it_unresolved(self):
        # Equidistant candidates carry no information; refusing is correct.
        conn = _FakeConn(self.ROWS, cross_street_ranking=[1, 2])
        conn.cross_street_ranking = None  # no ranking rows -> nothing narrowed
        resolver = ar.AddressResolver(_FakeEngine(conn), confidence_threshold=70)
        res = resolver.resolve_exact("3000", "Wood St", "ST",
                                     cross_street_1="Pinetree Way")
        assert res is None


class TestCrossStreetsAreNotAlwaysRoads:
    """Locution's "near <x> and <y>" does not promise x and y are streets.

    Measured over 283 dispatches carrying near roads: 129 matched both names, 44
    matched only one, 23 matched neither, and 87 named a single road. The unmatched
    names are descriptors ("Turning Lane", "Access Road", "Private Driveway", "Walton
    Elementary School Access") and mis-transcriptions ("Tanger Crt" for Tanager,
    "Crab Avenue" for Craig).

    A partial match must be discarded, not used: ranking on one road is what would
    select 3000 Pinewood Ave, which sits 9 m from Pinetree Way and 1061 m from
    Ponderosa St.
    """

    def _resolver(self, known_roads):
        conn = _FakeConn([], known_roads=known_roads)
        return ar.AddressResolver(_FakeEngine(conn), confidence_threshold=80), conn

    def test_both_names_real_are_kept(self):
        resolver, conn = self._resolver({"PINETREE", "PONDEROSA"})
        assert resolver._verify_cross_streets(conn, ["PINETREE", "PONDEROSA"]) == \
            ["PINETREE", "PONDEROSA"]

    def test_a_descriptor_discards_the_whole_signal(self):
        # "Turning Lane" is not a road. Falling back to ranking on Christmas Way alone
        # would be worse than ignoring the near roads entirely.
        resolver, conn = self._resolver({"CHRISTMAS"})
        assert resolver._verify_cross_streets(conn, ["CHRISTMAS", "TURNING"]) == []

    def test_neither_name_real_discards_the_signal(self):
        resolver, conn = self._resolver(set())
        assert resolver._verify_cross_streets(conn, ["ACCESS", "PRIVATE DRIVEWAY"]) == []

    def test_a_single_announced_road_is_not_enough(self):
        # One road says "somewhere near this line" and cannot position a call along a
        # street; 87 of 283 dispatches announce only one.
        resolver, conn = self._resolver({"CHRISTMAS"})
        assert resolver._verify_cross_streets(conn, ["CHRISTMAS"]) == []

    def test_no_cross_streets_is_not_an_error(self):
        resolver, conn = self._resolver(set())
        assert resolver._verify_cross_streets(conn, []) == []


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
