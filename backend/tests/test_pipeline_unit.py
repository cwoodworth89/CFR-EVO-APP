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
                      cross_street_1: str = None, cross_street_2: str = None):
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
    "Near, Anson, Avenue & Lincoln Ave" and stored as cross_streets ["Anson Ave"].
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

    def test_both_cross_streets_reach_the_dataclass(self):
        from cfr_dispatch.parser import parse_dispatch_announcement
        from cfr_dispatch.config.vocab import UNITS_VOCABULARY
        raw = ("Coquitlam Engine 1, Respond Emergency, Alarm Activated, High Risk, "
               "1, 1, 2, 3, Westwood St, Near, Anson, Avenue & Lincoln Ave, "
               "Use Talk Group, 5 Coquitlam, Map Grid, 8, 2")
        d = parse_dispatch_announcement(raw, UNITS_VOCABULARY)[0]
        self.assertEqual(d.cross_street_1, "Anson Avenue")
        self.assertEqual(d.cross_street_2, "Lincoln Ave")


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
