"""Graceful stop (punch-list #70): SIGTERM becomes a flag, the worker ignores it, the drain waits.

Pure: no audio, no database. The listener loop itself needs PortAudio and is exercised on the
kiosk; what is pinned here is the contract the loop, the worker and the orchestrator rely on.
"""
import os
import signal
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cfr_dispatch import shutdown  # noqa: E402


class FakeWorker:
    def __init__(self, alive_after_join=False):
        self.alive = True
        self.alive_after_join = alive_after_join
        self.joined_with = None

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.joined_with = timeout
        self.alive = self.alive_after_join


class FakeSupervisor:
    def __init__(self, worker):
        self.process = worker
        self.calls = []

    def stop(self):
        self.calls.append("stop")


class FakeQueue:
    def __init__(self, log):
        self.log = log

    def put(self, item):
        self.log.append(("put", item))


def setup_function(_):
    shutdown.reset_for_tests()


def test_sigterm_sets_the_flag_and_nothing_else():
    shutdown.install_sigterm_handler()
    assert not shutdown.stop_requested()
    signal.raise_signal(signal.SIGTERM)
    assert shutdown.stop_requested()


def test_worker_ignores_sigterm():
    shutdown.ignore_sigterm_in_worker()
    assert signal.getsignal(signal.SIGTERM) is signal.SIG_IGN


def test_drain_stops_the_supervisor_before_the_pill_and_waits_for_the_worker():
    worker = FakeWorker()
    sup = FakeSupervisor(worker)
    log = []
    sup.calls = log  # share one log so the order is visible
    q = FakeQueue(log)
    assert shutdown.drain_and_stop(sup, q, timeout_s=7) is True
    assert log == ["stop", ("put", None)]      # supervisor first, or it respawns the worker
    assert worker.joined_with == 7


def test_drain_gives_up_after_the_timeout_and_says_so(caplog):
    worker = FakeWorker(alive_after_join=True)
    sup = FakeSupervisor(worker)
    q = FakeQueue([])
    with caplog.at_level("WARNING"):
        assert shutdown.drain_and_stop(sup, q, timeout_s=1) is False
    assert "still busy" in caplog.text


def test_drain_timeout_covers_a_full_capture_and_its_phase_2():
    # 75 s capture cap is the listener's, not this module's; the drain only waits for phase 2.
    assert shutdown.WORKER_DRAIN_TIMEOUT_S >= 30
