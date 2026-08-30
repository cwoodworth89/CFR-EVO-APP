import time
from dataclasses import dataclass, field
from typing import Any

class PipelineTimer:
    """Context manager to measure and report elapsed time for pipeline operations."""
    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_time = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000.0

    @property
    def elapsed_s(self) -> float:
        return self.elapsed_ms / 1000.0

@dataclass
class Phase1Result:
    """Structured result from a Phase 1 preliminary check."""
    dispatch_id: str
    raw_transcript: str
    sanitized_transcript: str
    incident_type: str
    responding_units: list[str]
    address: str
    lat: float | None
    lng: float | None
    # Count of named review flags. Replaced confidence_score 2026-08-29
    # (punch-list #45); the flag names themselves live in db_payload.
    review_flag_count: int = 0
    is_triggered: bool = False
    db_payload: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)

@dataclass
class Phase2Result:
    """Structured result from a Phase 2 finalized call processing & verification."""
    dispatch_id: str
    is_match: bool
    was_corrected: bool
    final_address: str
    lat: float | None
    lng: float | None
    # Count of named review flags. Replaced confidence_score 2026-08-29
    # (punch-list #45); the flag names themselves live in db_payload.
    review_flag_count: int = 0
    audio_url: str | None = None
    audio_duration: float = 0.0
    db_payload: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
