"""Keeps the background dispatch worker alive, and says so loudly when it cannot.

WHY
---
The pipeline worker was started once and never looked at again:

    worker_process = multiprocessing.Process(target=background_worker_loop, ...)
    worker_process.start()

That was the only reference to it. It was never checked with `is_alive()`, never restarted,
and emitted no health signal, so **a worker crash was permanent and silent**. The audio
listener carried on detecting tones and capturing dispatches that nothing would ever
process, persist or broadcast.

Before the queue fix it was worse: a dead worker stopped draining the bounded queue, and
the blocking `put()` then stalled the listener entirely. That path is closed (punch-list
#28), so a dead worker now degrades rather than deadlocks — but it still means no dispatch
reaches the crew. Punch-list #27.

CRASH LOOPS
-----------
Restarting forever is not obviously better than stopping. If the worker dies repeatedly on
the same poisoned task, an endless restart loop buries the cause in noise and looks like
progress. So restarts are counted within a rolling window: past the ceiling the supervisor
**stops restarting and keeps saying so**, which is the honest failure — a human has to look.

The ceiling is deliberately generous. Losing dispatch processing is worse than a few extra
restarts, so the loop guard is there to catch a genuinely poisoned worker, not to be
conservative about recovery.
"""
import time
import logging
import threading
import multiprocessing

# How often to check. The worker reloads Whisper and the GIS validator on start, which
# takes a few seconds, so polling faster than this would just catch it mid-boot.
HEALTH_CHECK_INTERVAL_S = 15

# Restart ceiling within the rolling window. Chosen so an ordinary one-off crash always
# recovers, while a worker dying on every task stops after roughly a minute of trying
# rather than restarting indefinitely.
MAX_RESTARTS = 5
RESTART_WINDOW_S = 600


class WorkerSupervisor:
    """Restarts the dispatch worker if it dies, up to a ceiling."""

    def __init__(self, target, args, name="Background Dispatch Worker"):
        self._target = target
        self._args = args
        self._name = name
        self._process = None
        self._restart_times = []
        self._stop = threading.Event()
        self._thread = None
        self.gave_up = False

    # ------------------------------------------------------------------ lifecycle

    def start(self):
        """Start the worker and the supervising thread."""
        self._process = self._spawn()
        self._thread = threading.Thread(target=self._watch, daemon=True,
                                        name="worker-supervisor")
        self._thread.start()
        return self._process

    def stop(self):
        self._stop.set()

    @property
    def process(self):
        return self._process

    # ------------------------------------------------------------------ internals

    def _spawn(self):
        p = multiprocessing.Process(target=self._target, args=self._args, daemon=True)
        p.start()
        logging.info("%s started (pid %s).", self._name, p.pid)
        return p

    def _within_window(self):
        cutoff = time.time() - RESTART_WINDOW_S
        self._restart_times = [t for t in self._restart_times if t > cutoff]
        return len(self._restart_times)

    def _watch(self):
        while not self._stop.is_set():
            self._stop.wait(HEALTH_CHECK_INTERVAL_S)
            if self._stop.is_set():
                return
            if self._process is not None and self._process.is_alive():
                continue

            exitcode = self._process.exitcode if self._process else None

            if self.gave_up:
                # Keep saying it. A silent dead worker is what this module exists to
                # prevent, and going quiet after giving up would recreate exactly that.
                logging.critical(
                    "%s is DEAD and the supervisor has stopped restarting it. Dispatches "
                    "are being captured but NOT processed, persisted or broadcast. "
                    "Manual intervention required.", self._name)
                continue

            recent = self._within_window()
            if recent >= MAX_RESTARTS:
                self.gave_up = True
                logging.critical(
                    "%s died (exitcode %s) and has now been restarted %d times in %d "
                    "seconds. Refusing to restart again -- this looks like a crash loop, "
                    "and restarting forever would bury the cause. Dispatches are being "
                    "captured but NOT processed. Manual intervention required.",
                    self._name, exitcode, recent, RESTART_WINDOW_S)
                continue

            logging.critical(
                "%s died (exitcode %s). Restarting -- restart %d of %d allowed in %d "
                "seconds. Any dispatch it was mid-way through is lost.",
                self._name, exitcode, recent + 1, MAX_RESTARTS, RESTART_WINDOW_S)
            self._restart_times.append(time.time())
            try:
                self._process = self._spawn()
            except Exception as e:
                logging.critical("Failed to restart %s: %s", self._name, e, exc_info=True)
