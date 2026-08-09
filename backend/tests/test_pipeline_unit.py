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
    def local_geocode(self, address: str):
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
