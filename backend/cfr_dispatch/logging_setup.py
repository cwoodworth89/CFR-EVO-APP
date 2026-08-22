"""Logging configuration, shared by the orchestrator and the background worker.

WHY THIS IS ITS OWN MODULE
--------------------------
The dispatch pipeline runs in a `multiprocessing.Process` spawned from
`orchestration.run_dispatch_system`. `setup_logging()` used to live in that module and was
called once, before the spawn, on the assumption that the child would inherit the
configuration.

On Python 3.14 it does not. The default multiprocessing start method on Linux changed from
`fork` to **`forkserver`** (verified on the kiosk: `multiprocessing.get_start_method()`
returns `forkserver` under Python 3.14.4). A forkserver child does not inherit the parent's
logging configuration -- it starts with the default root logger at WARNING writing to
stderr.

The effect was that **every `logging.info` in the entire two-phase pipeline was silently
discarded**: no `Published … to Mosquitto` lines, no `[METRICS] Phase 1 TTA` timings, no
geocoder resolution notes. Only WARNING and above survived, in the default `WARNING:root:`
format, which is what gave the mismatch away in the journal. The system was not diagnosable
from its logs for anything that did not raise a warning. Punch-list #26.

The fix is to configure logging *inside* each process rather than relying on inheritance,
which is correct under any start method.
"""
import time
import logging
import datetime
from logging.handlers import TimedRotatingFileHandler

from cfr_dispatch.config.cloud import VERBOSITY_LEVEL


def _level_for_verbosity() -> int:
    if VERBOSITY_LEVEL == 0:
        return logging.ERROR
    if VERBOSITY_LEVEL == 1:
        return logging.INFO
    return logging.DEBUG


def setup_logging(log_file: str = 'dispatch.log'):
    """Configure the root logger: a daily 08:00-rotating file, plus stderr.

    `log_file` is per-process on purpose. A `TimedRotatingFileHandler` is not safe to share
    between processes -- both would hold the same path open and race on the rename at
    rotation, which can lose or truncate a day's log. The worker therefore writes its own
    file, and both processes stream to stderr, which systemd captures into the unit journal.
    """
    logging.Formatter.converter = time.localtime
    logger = logging.getLogger()
    logger.setLevel(_level_for_verbosity())

    if logger.hasHandlers():
        logger.handlers.clear()

    file_handler = TimedRotatingFileHandler(
        log_file,
        when='D',
        interval=1,
        backupCount=10,
        atTime=datetime.time(8, 0, 0)
    )
    file_handler.setLevel(logging.DEBUG if VERBOSITY_LEVEL >= 2 else logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s'))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO if VERBOSITY_LEVEL >= 1 else logging.WARNING)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s'))
    logger.addHandler(console_handler)

    # Silence verbose third-party loggers
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
