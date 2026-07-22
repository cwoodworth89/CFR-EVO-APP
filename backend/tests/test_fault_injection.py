# backend/tests/test_fault_injection.py
# CFR EVO Automated Fault Injection & System Resilience Test Suite

import os
import sys
import unittest
import numpy as np
from unittest.mock import patch, MagicMock

# Ensure backend and sibling services directories are in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

workspace_dir = os.path.dirname(backend_dir)
services_dir = os.path.join(workspace_dir, "services")
for s in ["gis", "audio_analysis", "dispatch_notifications"]:
    p = os.path.abspath(os.path.join(services_dir, s, "src"))
    if os.path.exists(p) and p not in sys.path:
        sys.path.append(p)

import cfr_dispatch
from gis_service import CoquitlamDataValidator
from audio_service.dsp_tone_spotter import analyze_live_audio
from cfr_dispatch.config import UNITS_VOCABULARY, AUDIO_SAMPLE_RATE
from cfr_dispatch.parser import parse_dispatch_announcement, sanitize_transcript
from cfr_dispatch.health_watchdog import check_disk_space, check_network_connectivity, check_audio_interface

class TestFaultInjection(unittest.TestCase):

    def test_01_silent_audio_hardware_fault(self):
        """Verify health watchdog detects silent / 0 RMS audio input."""
        with patch("sounddevice.rec") as mock_rec, patch("sounddevice.wait"):
            # Return 0 RMS silence buffer
            mock_rec.return_value = np.zeros((8000, 1), dtype=np.int16)
            audit = check_audio_interface()
            self.assertIn("status", audit)
            self.assertEqual(audit["rms_level"], 0.0)

    def test_02_static_noise_dsp_rejection(self):
        """Verify white noise bursts do not trigger false positive tone spotter matches."""
        # Generate 2 seconds of high-amplitude Gaussian static noise as int16 bytes
        noise_samples = np.random.normal(0, 3000, AUDIO_SAMPLE_RATE * 2).astype(np.int16)
        detected_freqs = analyze_live_audio(noise_samples.tobytes(), AUDIO_SAMPLE_RATE, num_peaks=5)
        
        # High static noise (broadband) should NOT produce clean pure tone frequency peaks
        self.assertEqual(len(detected_freqs), 0, f"Static noise falsely produced tone peaks: {detected_freqs}")

    def test_03_garbled_speech_sanitization_safety(self):
        """Verify heavily garbled and punctuated speech does not crash parser."""
        garbled_text = "Coquitlam,,??? engine! 1 respond, #emergency, $$$ medical aid... ??? 12344 fake st???"
        
        # Should sanitize cleanly without throwing exceptions
        sanitized = sanitize_transcript(garbled_text)
        self.assertIsInstance(sanitized, str)
        self.assertNotIn("?", sanitized)
        self.assertNotIn("#", sanitized)
        
        # Parser execution should be exception-free
        candidates = parse_dispatch_announcement(garbled_text, UNITS_VOCABULARY)
        self.assertIsInstance(candidates, list)

    def test_04_unknown_address_fallback_safety(self):
        """Verify unresolvable address falls through gracefully."""
        from cfr_dispatch.config import ADDRESS_SHAPEFILE_PATH, ZONES_SHAPEFILE_PATH
        if os.path.exists(ADDRESS_SHAPEFILE_PATH) and os.path.exists(ZONES_SHAPEFILE_PATH):
            validator = CoquitlamDataValidator(ADDRESS_SHAPEFILE_PATH, ZONES_SHAPEFILE_PATH)
            result = validator.local_geocode("9999 NonExistent Fake Street")
            # Should return None coordinates or flag verification without crashing
            self.assertTrue(result is None or result.get("lat") is None)

    def test_05_network_disconnect_resilience(self):
        """Verify network connectivity checker flags WAN outage."""
        with patch("requests.head", side_effect=Exception("Network Unreachable")):
            status = check_network_connectivity()
            self.assertEqual(status["status"], "OFFLINE")

if __name__ == "__main__":
    print("=" * 60)
    print("      CFR EVO FAULT INJECTION & RESILIENCE TEST SUITE")
    print("=" * 60)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFaultInjection)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(not result.wasSuccessful())
