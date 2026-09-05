import os
import time
import logging
import multiprocessing
from collections import deque
from typing import Any, Dict

from cfr_dispatch.config.runtime import (
    WHISPER_MODEL
)
from cfr_dispatch.stt import get_whisper_model
from cfr_dispatch.pipeline import process_phase_1_check, process_phase_2_finalize
from gis_service import CoquitlamDataValidator
from cfr_dispatch.logging_setup import setup_logging
from cfr_dispatch.session_store import PostgresSessionStore

class DispatchSessionManager:
    """Two-phase dispatch session state.

    Phase 1 state is persisted in PostgreSQL (`public.dispatch_sessions`) rather than held
    in this process. It used to be a plain dict, so a worker crash lost every in-flight
    dispatch's phase 1 context -- and phase 2, finding nothing, took the "Phase 1 was
    skipped" branch and published a second INSERT instead of an UPDATE, putting a duplicate
    on the kiosk (punch-list #25, #29).

    The public interface is unchanged, so phase 1 and phase 2 call it exactly as before.

    Execution profiles stay in memory deliberately: they are rolling metrics for this
    process, not dispatch state, and nothing reads them after a restart.
    """

    def __init__(self, max_history: int = 50, session_ttl_seconds: int = 600):
        self._store = PostgresSessionStore(ttl_seconds=session_ttl_seconds)
        self._recent_profiles = deque(maxlen=max_history)

    def _evict_stale_sessions(self):
        self._store.evict_stale()

    def is_phase_1_triggered(self, dispatch_id: str) -> bool:
        self._evict_stale_sessions()
        return self._store.is_triggered(dispatch_id)

    def record_phase_1_success(
        self,
        dispatch_id: str,
        buffer_len: int,
        raw_transcript: str,
        transcript: str,
        candidates: list,
        units: list,
        target: dict
    ):
        self._evict_stale_sessions()
        self._store.record_phase_1(
            dispatch_id=dispatch_id,
            buffer_len=buffer_len,
            raw_transcript=raw_transcript,
            transcript=transcript,
            candidates=candidates,
            units=units,
            target=target,
        )

    def get_phase_1_data(self, dispatch_id: str) -> dict | None:
        return self._store.get_phase_1(dispatch_id)

    def cleanup_session(self, dispatch_id: str):
        self._store.cleanup(dispatch_id)

_cached_validator = None

def get_shared_validator() -> CoquitlamDataValidator | None:
    global _cached_validator
    if _cached_validator is None:
        try:
            db_url = os.environ.get(
                'DATABASE_URL',
                'postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch'
            )
            logging.info('Initializing CoquitlamDataValidator (PostgreSQL)...')
            _cached_validator = CoquitlamDataValidator(database_url=db_url)
        except Exception as e:
            logging.warning(f'Failed to load shared validator: {e}')
    return _cached_validator

def background_worker_loop(task_queue: multiprocessing.Queue):
    """
    Background worker loop executing in a dedicated multiprocessing Process.
    Loads GIS validator and Whisper int8 model once, then routes Phase 1 checks and Phase 2 finalizations.
    """
    # Configure logging IN this process. It is not inherited: Python 3.14 changed the
    # default multiprocessing start method on Linux from fork to forkserver, and a
    # forkserver child starts with the default root logger at WARNING. Without this every
    # logging.info in the two-phase pipeline is discarded -- no MQTT publish lines, no
    # [METRICS] TTA timings, no geocoder resolution notes -- which left the system
    # undiagnosable from its logs for anything that did not raise a warning (punch-list #26).
    #
    # A separate file from the orchestrator on purpose: a TimedRotatingFileHandler is not
    # safe to share across processes, which would race on the rotation rename.
    setup_logging(log_file='dispatch-worker.log')

    logging.info("Background Dispatch Worker process starting...")
    validator = get_shared_validator()
    stt_model = get_whisper_model()
    session_manager = DispatchSessionManager()
    logging.info("Background Dispatch Worker process initialized and ready.")

    while True:
        try:
            task = task_queue.get()
            if task is None:  # Poison pill
                logging.info("Worker received shutdown signal. Exiting.")
                break
            if isinstance(task, dict):
                task_type = task.get("type")
                if task_type == "phase_1_check":
                    process_phase_1_check(task, validator, stt_model, session_manager)
                elif task_type == "phase_2_finalize":
                    process_phase_2_finalize(task, validator, stt_model, session_manager)
        except Exception as e:
            logging.error(f"Error in background worker loop: {e}", exc_info=True)
