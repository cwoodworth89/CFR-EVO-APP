"""The listener heartbeat: fresh through a capture, and three honest states out of the endpoint.

Why this exists. `capture_full_dispatch` held control for the whole broadcast and wrote no
heartbeat, so `GET /api/listener/status` reported "RF Listener unresponsive" partway into every
live capture -- the wrong signal at exactly the moment a restart is being decided. Measured on
the kiosk, 2026-09-19, from `journalctl -u cfr-agent`: of the last 13 captures, 12 ran longer
than the 30 s staleness threshold (25.8 s to 58.2 s, mean 43.8 s).

No audio hardware and no database. A fake clock advanced by a fake PortAudio stream stands in
for the 75 s the real capture takes, so the simulated capture is longer than the threshold
without the test taking that long.
"""
import json
import os
import queue
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

_BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_WORKSPACE = os.path.join(_BACKEND, "..")
sys.path.insert(0, os.path.abspath(_BACKEND))
sys.path.insert(0, os.path.abspath(os.path.join(_WORKSPACE, "services", "audio_analysis", "src")))

from audio_service import sound_capture  # noqa: E402
from api.routers import audio as audio_router  # noqa: E402
from cfr_dispatch.config.runtime import LISTENER_HEARTBEAT_INTERVAL_S  # noqa: E402

# The kiosk's MAX_DISPATCH_DURATION_S (backend/cfr_dispatch/config/dsp.py:11). Real captures
# measured 2026-09-19 ran 25.8-58.2 s; this is the cap they run against.
KIOSK_MAX_CAPTURE_S = 75.0
BLOCKSIZE = 1024
SAMPLE_RATE = 16000


class FakeClock:
    """A clock that only moves when audio is read, the way capture time actually passes."""

    def __init__(self, start: float = 1_700_000_000.0):
        self.now = start

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeStream:
    """One PortAudio block per read. Loud enough that the silence detector never fires."""

    def __init__(self, clock: FakeClock, amplitude: int = 2000):
        self.clock = clock
        self.reads = 0
        self.block = np.full(BLOCKSIZE, amplitude, dtype=np.int16)

    def read(self, blocksize):
        self.reads += 1
        self.clock.advance(blocksize / SAMPLE_RATE)
        return self.block, None


def _run_capture(heartbeat_cb, clock, max_duration_s=KIOSK_MAX_CAPTURE_S):
    stream = FakeStream(clock)
    started_at = clock.now
    with patch.object(sound_capture, "time", clock):
        sound_capture.capture_full_dispatch(
            stream,
            BLOCKSIZE,
            queue.Queue(maxsize=10),
            "DISP-2026-TEST01",
            "Engine Tone",
            initial_buffer=[],
            sample_rate=SAMPLE_RATE,
            max_duration_s=max_duration_s,
            # Phase 1 enqueues are not what these tests are about; held off so the only
            # periodic work in the loop is the heartbeat.
            min_phase_1_duration_s=10 ** 9,
            phase_1_check_interval_s=10 ** 9,
            end_of_dispatch_rms_threshold=30.0,
            end_of_dispatch_silence_s=3.0,
            heartbeat_cb=heartbeat_cb,
            heartbeat_interval_s=LISTENER_HEARTBEAT_INTERVAL_S,
        )
    return started_at, clock.now


class TestHeartbeatDuringCapture(unittest.TestCase):

    def test_capture_longer_than_the_threshold_keeps_the_heartbeat_fresh(self):
        clock = FakeClock()
        beats = []
        started_at, ended_at = _run_capture(lambda: beats.append(clock.now), clock)

        # The premise: this capture is longer than the age at which the endpoint gives up.
        self.assertGreater(ended_at - started_at, audio_router.LISTENER_STALE_AFTER_S)

        self.assertTrue(beats, "no heartbeat was written during the capture")
        # Every gap, including the two ends, stays inside the threshold -- so there is no
        # moment during the capture at which the endpoint would report unresponsive.
        marks = [started_at] + beats + [ended_at]
        gaps = [b - a for a, b in zip(marks, marks[1:])]
        self.assertLess(max(gaps), audio_router.LISTENER_STALE_AFTER_S,
                        f"heartbeat went stale mid-capture; gaps={gaps}")

    def test_a_failing_heartbeat_never_ends_a_capture(self):
        """Telemetry must not cost the call: the loop's own `except` would break out."""
        clock = FakeClock()

        def _explode():
            raise OSError("read-only filesystem")

        started_at, ended_at = _run_capture(_explode, clock, max_duration_s=40.0)
        self.assertAlmostEqual(ended_at - started_at, 40.0, delta=0.1)

    def test_no_callback_still_captures(self):
        """heartbeat_cb defaults to None; the sibling service stays usable without it."""
        clock = FakeClock()
        started_at, ended_at = _run_capture(None, clock, max_duration_s=40.0)
        self.assertAlmostEqual(ended_at - started_at, 40.0, delta=0.1)


class TestListenerStatusEndpoint(unittest.TestCase):
    """The three states, and the device field both ways."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.status_file = os.path.join(self._tmp.name, "listener_status.json")

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, payload):
        with open(self.status_file, "w") as f:
            json.dump(payload, f)

    def _status(self, path=None):
        with patch.object(audio_router, "LISTENER_STATUS_FILE", path or self.status_file):
            return audio_router.get_listener_status()

    @staticmethod
    def _now_iso(offset_s=0.0):
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(seconds=offset_s)).isoformat()

    def test_state_capturing(self):
        self._write({
            "status": "online", "state": "capturing",
            "dispatch_id": "DISP-2026-E9E7EC",
            "capture_started": self._now_iso(40.0),
            "device": "USB Audio CODEC", "stt_engine": "whisper",
            "last_heartbeat": self._now_iso(1.0), "pid": 475759
        })
        res = self._status()
        self.assertEqual(res["listener_state"], "capturing")
        # A capture is alive: the console's existing reader must not see this as offline.
        self.assertEqual(res["status"], "online")
        self.assertEqual(res["dispatch_id"], "DISP-2026-E9E7EC")
        self.assertAlmostEqual(res["capture_age_seconds"], 40.0, delta=2.0)
        self.assertIn("restart", res["message"])

    def test_state_idle_alive(self):
        self._write({
            "status": "online", "state": "idle", "dispatch_id": None,
            "capture_started": None, "device": "USB Audio CODEC",
            "stt_engine": "whisper", "last_heartbeat": self._now_iso(2.0), "pid": 1
        })
        res = self._status()
        self.assertEqual(res["listener_state"], "idle")
        self.assertEqual(res["status"], "online")
        self.assertNotIn("dispatch_id", res)

    def test_state_unresponsive_when_the_heartbeat_is_stale(self):
        self._write({
            "status": "online", "state": "idle", "device": "USB Audio CODEC",
            "stt_engine": "whisper", "last_heartbeat": self._now_iso(120.0), "pid": 1
        })
        res = self._status()
        self.assertEqual(res["listener_state"], "unresponsive")
        self.assertEqual(res["status"], "offline")
        self.assertGreater(res["age_seconds"], audio_router.LISTENER_STALE_AFTER_S)

    def test_state_unresponsive_when_there_is_no_heartbeat_file(self):
        res = self._status(path=os.path.join(self._tmp.name, "does_not_exist.json"))
        self.assertEqual(res["listener_state"], "unresponsive")
        self.assertEqual(res["status"], "offline")
        self.assertIsNone(res["last_heartbeat"])

    def test_a_heartbeat_without_a_state_field_is_idle_never_capturing(self):
        """A file written by an older agent build. Never claim a capture we cannot see."""
        self._write({
            "status": "online", "device": "USB Audio CODEC",
            "stt_engine": "whisper", "last_heartbeat": self._now_iso(2.0), "pid": 1
        })
        res = self._status()
        self.assertEqual(res["listener_state"], "idle")

    def test_device_reports_the_resolved_name(self):
        self._write({
            "status": "online", "state": "idle", "device": "USB Audio CODEC",
            "stt_engine": "whisper", "last_heartbeat": self._now_iso(1.0), "pid": 1
        })
        self.assertEqual(self._status()["device"], "USB Audio CODEC")

    def test_device_is_a_dash_when_none_was_resolved(self):
        """CLAUDE.md s6.1: null, empty, missing and non-string all render as the unknown."""
        for value in (None, "", "   ", 5):
            with self.subTest(device=value):
                self._write({
                    "status": "online", "state": "idle", "device": value,
                    "stt_engine": "whisper", "last_heartbeat": self._now_iso(1.0), "pid": 1
                })
                self.assertEqual(self._status()["device"], "--")

        self._write({
            "status": "online", "state": "idle",
            "stt_engine": "whisper", "last_heartbeat": self._now_iso(1.0), "pid": 1
        })
        self.assertEqual(self._status()["device"], "--")

    def test_device_is_a_dash_when_the_listener_is_unresponsive(self):
        """A process that is not reporting has no current device, only a last-known one."""
        self._write({
            "status": "online", "state": "idle", "device": "USB Audio CODEC",
            "stt_engine": "whisper", "last_heartbeat": self._now_iso(120.0), "pid": 1
        })
        self.assertEqual(self._status()["device"], "--")


class TestWriterAndReaderAgree(unittest.TestCase):
    """What the listener writes is what the endpoint reads back. Two files, one contract."""

    def test_writer_payload_drives_the_endpoint_states(self):
        from cfr_dispatch import audio_listener

        with tempfile.TemporaryDirectory() as tmp:
            status_file = os.path.join(tmp, "listener_status.json")
            with patch.object(audio_listener, "LISTENER_STATUS_FILE", status_file), \
                 patch.object(audio_router, "LISTENER_STATUS_FILE", status_file):

                audio_listener.update_listener_heartbeat(
                    state=audio_listener.LISTENER_STATE_CAPTURING,
                    device_name="USB Audio CODEC",
                    dispatch_id="DISP-2026-E9E7EC",
                    capture_started="2026-09-19T08:12:39.728000+00:00",
                )
                res = audio_router.get_listener_status()
                self.assertEqual(res["listener_state"], "capturing")
                self.assertEqual(res["status"], "online")
                self.assertEqual(res["dispatch_id"], "DISP-2026-E9E7EC")
                self.assertEqual(res["device"], "USB Audio CODEC")

                audio_listener.update_listener_heartbeat(
                    state=audio_listener.LISTENER_STATE_IDLE, device_name=None)
                res = audio_router.get_listener_status()
                self.assertEqual(res["listener_state"], "idle")
                self.assertEqual(res["status"], "online")
                # An unresolved device: never the AUDIO_DEVICE_ID setting dressed as a name.
                self.assertEqual(res["device"], "--")

    def test_the_write_interval_stays_well_inside_the_staleness_threshold(self):
        """The two constants live in different containers; this is what catches them drifting.

        Six writes inside the window means five must be missed in a row before a live
        listener reads as dead.
        """
        self.assertGreaterEqual(
            audio_router.LISTENER_STALE_AFTER_S / LISTENER_HEARTBEAT_INTERVAL_S, 6.0,
            "the listener's heartbeat interval is no longer well inside the endpoint's "
            "staleness threshold: see backend/cfr_dispatch/config/runtime.py and "
            "backend/api/routers/audio.py"
        )


if __name__ == "__main__":
    unittest.main()
