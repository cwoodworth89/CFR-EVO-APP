import os
import unittest
import time
from cfr_dispatch.pipeline.payload_builder import clean_address_string, build_dispatch_payload
from cfr_dispatch.pipeline.phase1 import is_round_1_complete_check
from cfr_dispatch.pipeline.models import PipelineTimer, Phase1Result, Phase2Result
from cfr_dispatch.worker import DispatchSessionManager
from cfr_dispatch.config.models import DispatchData

class MockValidator:
    """Mock GIS validator for fast, offline unit testing."""
    def local_geocode(self, parsed_address: str, target_map_grid=None,
                      x_street_1: str = None, x_street_2: str = None):
        # Signature must track gis_service.geocoder.CoquitlamDataValidator.local_geocode.
        # It gained target_map_grid in the geocoder 2.0 work and the cross_street_*
        # arguments with cross-road narrowing; this mock kept the old one-argument form
        # and the real call site raised TypeError.
        address = parsed_address
        if "Sandstone" in address:
            return {
                "address": "2648 Sandstone Cres, Coquitlam, BC",
                "lat": 49.2781,
                "lng": -122.8123,
                "rings": [[[49.2781, -122.8123], [49.2782, -122.8124]]],
                "confidence": 100.0
            }
        return None

    def get_map_grid_for_point(self, lat: float, lng: float):
        return "118"

class TestPipelineUnit(unittest.TestCase):

    def test_clean_address_string(self):
        self.assertEqual(clean_address_string("2648 Sandstone Cres, Coquitlam, BC V3E 2W1"), "2648 Sandstone Cres")
        self.assertEqual(clean_address_string("1963 Lougheed Hwy, Port Coquitlam, BC"), "1963 Lougheed Hwy")
        self.assertEqual(clean_address_string("Austin Ave & Mariner Way, Coquitlam"), "Austin Ave & Mariner Way")

    def test_is_round_1_complete_check(self):
        # 1. Complete round with grid
        candidate_with_grid = DispatchData(
            raw_text="Engine 1, Rescue 1 respond medical 2648 Sandstone map grid 118",
            units="Engine 1, Rescue 1",
            response_type="routine",
            call_type="Medical Aid",
            address="2648 Sandstone",
            map_grid="118"
        )
        self.assertTrue(is_round_1_complete_check([candidate_with_grid], candidate_with_grid.raw_text))

        # 2. Incomplete round (no units or call type)
        incomplete_candidate = DispatchData(
            raw_text="2648 Sandstone Cres",
            address="2648 Sandstone Cres"
        )
        self.assertFalse(is_round_1_complete_check([incomplete_candidate], incomplete_candidate.raw_text))

        # 3. Unit repetition fallback trigger
        rep_candidate = DispatchData(
            raw_text="Engine 1 respond medical 2648 Sandstone. Repeating Engine 1 for medical.",
            units="Engine 1",
            response_type="emergency",
            call_type="Medical Aid",
            address="2648 Sandstone"
        )
        self.assertTrue(is_round_1_complete_check([rep_candidate], rep_candidate.raw_text))

    def test_build_dispatch_payload_option2(self):
        validator = MockValidator()
        candidate = DispatchData(
            raw_text="Engine 1 respond medical 2648 Sandstone",
            units="Engine 1",
            response_type="emergency",
            call_type="Medical Aid",
            address="2648 Sandstone",
            radio_channel="Tac 1"
        )
        payload, units = build_dispatch_payload(
            dispatch_id="DISP-TEST-001",
            raw_transcript="Engine 1 respond medical 2648 Sandstone",
            sanitized_transcript="Engine 1 respond medical 2648 Sandstone",
            all_candidates=[candidate],
            validator=validator,
            units_vocabulary=["Engine 1"]
        )
        
        self.assertEqual(payload["dispatch_id"], "DISP-TEST-001")
        self.assertEqual(payload["incident_type"], "Medical Aid")
        self.assertIn("target", payload)
        self.assertEqual(payload["target"]["address"], "2648 Sandstone Cres")
        self.assertIsNotNone(payload["target"]["lat"])
        self.assertIsNotNone(payload["target"]["lng"])
        self.assertEqual(payload["target"]["map_grid"], "118")

    def test_pipeline_timer(self):
        with PipelineTimer("test_timer") as timer:
            time.sleep(0.01)
        self.assertGreater(timer.elapsed_ms, 5.0)
        self.assertGreater(timer.elapsed_s, 0.005)

    def test_dispatch_session_manager(self):
        mgr = DispatchSessionManager(max_history=10)
        self.assertFalse(mgr.is_phase_1_triggered("DISP-001"))
        
        mgr.record_phase_1_success(
            dispatch_id="DISP-001",
            buffer_len=15,
            raw_transcript="raw",
            transcript="sanitized",
            candidates=[],
            units=["E1"],
            target={"address": "2648 Sandstone Cres"}
        )
        self.assertTrue(mgr.is_phase_1_triggered("DISP-001"))
        self.assertEqual(mgr.get_phase_1_data("DISP-001")["units"], ["E1"])
        
        mgr.cleanup_session("DISP-001")
        self.assertFalse(mgr.is_phase_1_triggered("DISP-001"))

if __name__ == "__main__":
    unittest.main()


class TestAmpersandSurvivesSanitize(unittest.TestCase):
    """`&` separates two cross streets and must survive sanitisation as a word.

    Measured on DISP-2026-AAFDB8 (2026-08-30), announced
    "Near, Anson, Avenue & Lincoln Ave" and stored as x_streets ["Anson Ave"].
    `sanitize_transcript` stripped the ampersand to nothing, leaving
    "near anson avenue lincoln ave" with no separator at all; clean_location_text
    then correctly removed "lincoln ave" as trailing junk after a street type.

    Locution speaks the same clause both ways -- this call's second round said
    "Anson Ave, and Lincoln Ave", which parses fine -- and round 1 wins the address
    (punch-list #44), so the broken form was the one kept.
    """

    def test_ampersand_becomes_a_word_not_nothing(self):
        from cfr_dispatch.parser.sanitize import sanitize_transcript
        out = sanitize_transcript("Westwood St, Near, Anson, Avenue & Lincoln Ave")
        self.assertIn("anson avenue and lincoln ave", out)
        self.assertNotIn("avenue lincoln", out)

    def test_both_x_streets_reach_the_dataclass(self):
        from cfr_dispatch.parser import parse_dispatch_announcement
        from cfr_dispatch.config.vocab import UNITS_VOCABULARY
        raw = ("Coquitlam Engine 1, Respond Emergency, Alarm Activated, High Risk, "
               "1, 1, 2, 3, Westwood St, Near, Anson, Avenue & Lincoln Ave, "
               "Use Talk Group, 5 Coquitlam, Map Grid, 8, 2")
        d = parse_dispatch_announcement(raw, UNITS_VOCABULARY)[0]
        # Both in the abbreviated house form. This asserted "Anson Avenue" when written,
        # pinning a second bug: fuzzy_correct_street returned the expanded municipal name
        # while the untouched leg kept "Lincoln Ave", so one clause held both conventions.
        # Fixed with the suffix-doubling bug (punch-list #56).
        self.assertEqual(d.x_street_1, "Anson Ave")
        self.assertEqual(d.x_street_2, "Lincoln Ave")


class TestCrossRoadCleaning(unittest.TestCase):
    """`clean_location_text` strips trailing junk after a street type.

    It must not treat the second cross street as junk. These cover the lookahead
    guard in location.py, which is defence in depth: sanitisation now rewrites `&`
    to " and " before this function sees it, so the ampersand case is unreachable
    from the announcement path and these pin the behaviour rather than the fix.
    """

    CALL_TYPES = ["Alarm Activated", "Medical Aid", "Structure Fire"]
    UNITS = ["Engine 1", "Rescue 2"]

    def _clean(self, text):
        from cfr_dispatch.parser.location import clean_location_text
        return clean_location_text(text, self.CALL_TYPES, self.UNITS)

    def test_ampersand_keeps_the_second_cross_street(self):
        self.assertEqual(self._clean("Anson, Avenue & Lincoln Ave"),
                         "Anson, Avenue & Lincoln Ave")

    def test_and_form_still_keeps_both(self):
        self.assertEqual(self._clean("Anson Ave, and Lincoln Ave"),
                         "Anson Ave, and Lincoln Ave")

    def test_trailing_unit_number_is_still_stripped(self):
        self.assertEqual(self._clean("Burlington Drive 105"), "Burlington Drive")

    def test_trailing_business_name_is_still_stripped(self):
        self.assertEqual(self._clean("Lougheed Highway Superstore"), "Lougheed Highway")

    def test_near_clause_is_still_protected(self):
        self.assertEqual(self._clean("Westwood Street near Anson Ave"),
                         "Westwood Street near Anson Ave")


class TestCoalesceAcrossRounds(unittest.TestCase):
    """Phase 2 recovers a field one round lost from the round that kept it.

    Locution announces every call twice and Phase 2 re-transcribes the whole
    recording, so each field is observed independently more than once. STT damages
    the rounds differently. Before this, XStreets and subaddress were taken only
    from the first candidate carrying an address -- round 1 -- so anything round 1
    dropped was lost even when round 2 had it (punch-list #44).
    """

    def _cand(self, **kw):
        from cfr_dispatch.config.models import DispatchData
        kw.setdefault("raw_text", "")
        return DispatchData(**kw)

    def test_round_2_supplies_what_round_1_dropped(self):
        from cfr_dispatch.pipeline.phase2 import _coalesce_across_rounds
        r1 = self._cand(address="1123 Westwood St", x_street_1="Anson Ave")
        r2 = self._cand(address="1123 Westwood St", x_street_1="Anson Ave",
                        x_street_2="Lincoln Ave")
        x1, x2, sub = _coalesce_across_rounds([r1, r2], None, {})
        self.assertEqual(x1, "Anson Ave")
        self.assertEqual(x2, "Lincoln Ave")

    def test_round_1_still_wins_when_both_rounds_have_it(self):
        from cfr_dispatch.pipeline.phase2 import _coalesce_across_rounds
        r1 = self._cand(x_street_1="Anson Avenue", x_street_2="Lincoln Ave")
        r2 = self._cand(x_street_1="Anson Ave", x_street_2="Lincoln Avenue")
        x1, x2, _ = _coalesce_across_rounds([r1, r2], None, {})
        self.assertEqual(x1, "Anson Avenue")
        self.assertEqual(x2, "Lincoln Ave")

    def test_subaddress_recovered_from_either_round(self):
        from cfr_dispatch.pipeline.phase2 import _coalesce_across_rounds
        r1 = self._cand(address="1457 Hockaday St")
        r2 = self._cand(address="1457 Hockaday St", subaddress="Unit 203")
        _, _, sub = _coalesce_across_rounds([r1, r2], None, {})
        self.assertEqual(sub, "Unit 203")

    def test_falls_back_to_phase_1_candidate_then_target(self):
        from cfr_dispatch.pipeline.phase2 import _coalesce_across_rounds
        p1 = self._cand(x_street_1="Anson Ave")
        x1, x2, sub = _coalesce_across_rounds(
            [self._cand(address="1123 Westwood St")], p1, {"subaddress": "Unit 5"})
        self.assertEqual(x1, "Anson Ave")
        self.assertIsNone(x2)
        self.assertEqual(sub, "Unit 5")

    def test_no_candidates_is_not_an_error(self):
        from cfr_dispatch.pipeline.phase2 import _coalesce_across_rounds
        self.assertEqual(_coalesce_across_rounds([], None, None), (None, None, None))


class TestStreetSuffixDoubling(unittest.TestCase):
    """fuzzy_correct_street must not re-append a suffix the municipal name already has.

    Its docstring said it matched against "known Coquitlam BASE street names". The list
    actually holds FULL names, so it split the announced name into base + suffix, scored
    the base against full names, and re-appended the caller's suffix to the winner --
    "Christmas Way" -> "Christmas Way Way". Ten of the 23 unmatched cross streets in the
    corpus were this, every one of them a real street (punch-list #56).
    """

    # A stand-in for COQUITLAM_STREETS: full municipal names, as the real list holds them.
    STREETS = [
        "Christmas Way", "King Edward Street", "King Edward Slip Lane", "Pinetree Way",
        "Pinetree Close", "Burlington Drive", "Turnberry Lane", "Honeysuckle Lane",
        "Austin Avenue", "Tahsis Avenue", "Gordon Avenue",
    ]

    def _f(self, name):
        from cfr_dispatch.parser.location import fuzzy_correct_street
        return fuzzy_correct_street(name, self.STREETS)

    def test_suffix_is_not_doubled(self):
        for announced, expected in [
            ("Christmas Way", "Christmas Way"),
            ("King Edward Street", "King Edward St"),
            ("Pinetree Way", "Pinetree Way"),
            ("Burlington Drive", "Burlington Dr"),
            ("Turnberry Lane", "Turnberry Ln"),
            ("Honeysuckle Lane", "Honeysuckle Ln"),
        ]:
            self.assertEqual(self._f(announced), expected)

    def test_same_base_different_suffix_does_not_swap(self):
        """Both bases score 100; without the tie-break the vocabulary order would decide."""
        self.assertEqual(self._f("Pinetree Way"), "Pinetree Way")
        self.assertEqual(self._f("Pinetree Close"), "Pinetree Close")

    def test_a_real_misspelling_is_still_corrected(self):
        # The correction the project documented as worth keeping.
        self.assertEqual(self._f("Tasis Ave"), "Tahsis Ave")

    def test_an_unmatched_name_degrades_to_raw_text(self):
        self.assertEqual(self._f("Nonexistent Boulevard"), "Nonexistent Boulevard")

    def test_cross_road_clause_round_trips(self):
        from cfr_dispatch.parser.location import fuzzy_correct_x_streets
        self.assertEqual(
            fuzzy_correct_x_streets("Christmas Way and Gordon Ave", self.STREETS),
            "Christmas Way and Gordon Ave")
