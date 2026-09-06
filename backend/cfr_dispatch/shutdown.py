"""Graceful stop: finish the capture in progress before the agent exits (punch-list #70).

`systemctl restart cfr-agent` sends SIGTERM to every process in the unit's control group at
once: the listener and the worker. Until 2026-09-05 neither handled it. The listener died
mid-capture and the worker died mid-phase-2, so a restart 50 seconds into a structure-fire
broadcast (DISP-2026-33D8C2, 11:42 PDT) left no recording, no address and a partial payload on
the kiosk.

Now:
  * the main process turns SIGTERM into a flag (`stop_requested`); the listener returns at the
    next quiet moment, or after the capture in progress has ended and been queued;
  * the worker ignores SIGTERM and exits on the poison pill, so systemd's signal cannot cut
    phase 2 short;
  * on the way out the orchestrator sends the pill and waits for the worker to drain
    (`drain_and_stop`) before the daemon child would be killed with the parent.

The unit needs `TimeoutStopSec` long enough for all of that: a capture runs at most 75 s
(`MAX_DISPATCH_DURATION_S`) and phase 2 took 6 s on 2026-09-05, so 150 s. The default of
90 s is what the kiosk had; `setup_kiosk.sh` carries the new value.
"""
import logging
import signal
import threading

_stop = threading.Event()

# Phase 2 on a 75 s recording took 6 s on 2026-09-05 (DISP-2026-3E1426: queued 11:32:15,
# finalised 11:32:20). Ten times that covers a slow STT pass without holding a restart hostage.
WORKER_DRAIN_TIMEOUT_S = 60


def _on_sigterm(signum, frame):
    if not _stop.is_set():
        logging.info("SIGTERM received: finishing any capture in progress, then exiting.")
    _stop.set()


def install_sigterm_handler() -> None:
    """Main process only. SIGINT keeps raising KeyboardInterrupt, as before."""
    signal.signal(signal.SIGTERM, _on_sigterm)


def ignore_sigterm_in_worker() -> None:
    """Worker process. systemd signals the whole control group; the worker must live long
    enough to finish the phase 2 it is on, and it exits on the poison pill instead."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)


def stop_requested() -> bool:
    return _stop.is_set()


def reset_for_tests() -> None:
    _stop.clear()


def drain_and_stop(supervisor, dispatch_queue, timeout_s: float = WORKER_DRAIN_TIMEOUT_S) -> bool:
    """Stop the supervisor from respawning, send the pill, wait for the worker to finish.

    Returns True when the worker exited in time. Order matters: the supervisor's stop flag
    first, or its watch thread sees the worker exit on the pill and starts another one.
    """
    supervisor.stop()
    dispatch_queue.put(None)
    worker = getattr(supervisor, "process", None)
    if worker is None or not worker.is_alive():
        return True
    worker.join(timeout=timeout_s)
    if worker.is_alive():
        logging.warning("Worker still busy after %ss; exiting anyway. Phase 2 for the last "
                        "capture may be lost.", timeout_s)
        return False
    logging.info("Worker drained and exited.")
    return True
