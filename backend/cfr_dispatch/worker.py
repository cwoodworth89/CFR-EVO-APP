import os
import time
import logging
import multiprocessing
from collections import deque
from typing import Any, Dict

from cfr_dispatch.config.cloud import (
    WHISPER_MODEL
)
from cfr_dispatch.config.paths import SHAPES_DIR
from cfr_dispatch.stt import get_whisper_model
from cfr_dispatch.pipeline import process_phase_1_check, process_phase_2_finalize
from gis_service import CoquitlamDataValidator

class DispatchSessionManager:
    """
    Thread-safe / process-local session state manager for two-phase dispatch processing.
    Tracks preliminary Phase 1 trigger points and stores rolling execution profiles.
    """
    def __init__(self, max_history: int = 50, session_ttl_seconds: int = 600):
        self._triggered_phase_1_ids = set()
        self._phase_1_trigger_lengths = {}
        self._phase_1_candidates = {}
        self._session_timestamps = {}
        self._session_ttl_s = session_ttl_seconds
        self._recent_profiles = deque(maxlen=max_history)

    def _evict_stale_sessions(self):
        """Removes session entries that have exceeded TTL without Phase 2 finalization."""
        now = time.time()
        stale_ids = [
            sid for sid, ts in self._session_timestamps.items()
            if now - ts > self._session_ttl_s
        ]
        for sid in stale_ids:
            self.cleanup_session(sid)

    def is_phase_1_triggered(self, dispatch_id: str) -> bool:
        self._evict_stale_sessions()
        return dispatch_id in self._triggered_phase_1_ids

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
        self._triggered_phase_1_ids.add(dispatch_id)
        self._phase_1_trigger_lengths[dispatch_id] = buffer_len
        self._session_timestamps[dispatch_id] = time.time()
        self._phase_1_candidates[dispatch_id] = {
            "raw_transcript": raw_transcript,
            "transcript": transcript,
            "candidates": candidates,
            "units": units,
            "target": target
        }

    def get_phase_1_data(self, dispatch_id: str) -> dict | None:
        return self._phase_1_candidates.get(dispatch_id)

    def cleanup_session(self, dispatch_id: str):
        self._triggered_phase_1_ids.discard(dispatch_id)
        self._phase_1_trigger_lengths.pop(dispatch_id, None)
        self._phase_1_candidates.pop(dispatch_id, None)
        self._session_timestamps.pop(dispatch_id, None)

    def get_recent_profiles(self) -> list:
        return list(self._recent_profiles)

_cached_validator = None

def get_shared_validator() -> CoquitlamDataValidator | None:
    """Returns singleton CoquitlamDataValidator for geocoding and STT hotword indexing."""
    global _cached_validator
    if _cached_validator is None:
        try:
            address_shp = str(SHAPES_DIR / "Property_Information" / "Addresses.shp")
            zones_shp = str(SHAPES_DIR / "Emergency_Response_Zones" / "Emergency_Response_Zones.shp")
            logging.info("Initializing shared CoquitlamDataValidator...")
            _cached_validator = CoquitlamDataValidator(
                address_shp_path=address_shp,
                zones_shp_path=zones_shp
            )
        except Exception as e:
            logging.warning(f"Failed to load shared validator: {e}")
    return _cached_validator

def background_worker_loop(task_queue: multiprocessing.Queue):
    """
    Background worker loop executing in a dedicated multiprocessing Process.
    Loads GIS validator and Whisper int8 model once, then routes Phase 1 checks and Phase 2 finalizations.
    """
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
