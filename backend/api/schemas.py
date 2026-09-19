"""
Pydantic Schemas for CFR EVO API Gateway.
Defines request and response data models for auth, dispatches, parcels, streetview, road closures, and metrics.
"""
from datetime import date
from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class DispatchCreateSchema(BaseModel):
    dispatch_id: str
    incident_type: Optional[str] = "Unknown Incident"
    responding_units: Optional[List[str]] = []
    routing_metrics: Optional[List[Dict[str, Any]]] = []
    target: Optional[Dict[str, Any]] = {}
    raw_transcript: Optional[str] = None
    sanitized_transcript: Optional[str] = None
    verify_location: Optional[bool] = False
    # Marks a genuine pipeline test dispatch (CLAUDE.md 6.5). The pipeline has sent it at
    # the top level since the flag existed (cfr_dispatch/pipeline/payload_builder.py:496),
    # but there was no field here, so Pydantic dropped it silently and 0 of 700 stored rows
    # carried it -- no corpus figure could exclude a test call. There is no is_test column:
    # _fold_is_test() in routers/dispatches.py moves it into `target`.
    #
    # Default None, not False: with exclude_unset a request that sent nothing writes
    # nothing, so a row never acquires a fabricated False (CLAUDE.md 6.1).
    is_test: Optional[bool] = None
    origins: Optional[List[str]] = []
    audio_url: Optional[str] = None
    audio_duration: Optional[float] = None
    verified_transcript: Optional[str] = None
    verified_address: Optional[str] = None
    verified_incident: Optional[str] = None
    verified_units: Optional[List[str]] = None
    verified_map_grid: Optional[str] = None
    verified_talkgroup: Optional[str] = None
    verified_response_type: Optional[str] = None
    verified_x_street_1: Optional[str] = None
    verified_x_street_2: Optional[str] = None
    feedback_submitted: Optional[bool] = False


class EvaluationCreateSchema(BaseModel):
    """One backtest run's summary, written to public.evaluation_history."""
    model_version: str
    total_samples: int
    # Optional since 2026-09-05: only an STT run has these (tools/harness_common.py).
    wer: Optional[float] = None
    cer: Optional[float] = None
    perfect_percent: Optional[float] = None
    operational_percent: Optional[float] = None
    failed_percent: Optional[float] = None
    stage: Optional[str] = None
    git_hash: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    metrics: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class BulkModelUpdatedSchema(BaseModel):
    """Payload for the bulk training-dataset bookkeeping flag."""
    dispatch_ids: List[str]
    model_updated: bool = True


class DispatchUpdateSchema(BaseModel):
    incident_type: Optional[str] = None
    responding_units: Optional[List[str]] = None
    routing_metrics: Optional[List[Dict[str, Any]]] = None
    target: Optional[Dict[str, Any]] = None
    raw_transcript: Optional[str] = None
    sanitized_transcript: Optional[str] = None
    verify_location: Optional[bool] = None
    # See DispatchCreateSchema.is_test. Needed on the UPDATE side too because phase 2's
    # correction branch replaces `target` wholesale (pipeline/payload_builder.py:509,
    # phase2.py:527): without this the flag phase 1 wrote would be erased by the very
    # correction that follows it. Phase 2 already sends it (phase2.py:520, 557, 572).
    is_test: Optional[bool] = None
    origins: Optional[List[str]] = None
    audio_url: Optional[str] = None
    audio_duration: Optional[float] = None
    verified_transcript: Optional[str] = None
    verified_address: Optional[str] = None
    verified_incident: Optional[str] = None
    verified_units: Optional[List[str]] = None
    verified_map_grid: Optional[str] = None
    verified_talkgroup: Optional[str] = None
    verified_response_type: Optional[str] = None
    verified_x_street_1: Optional[str] = None
    verified_x_street_2: Optional[str] = None
    feedback_submitted: Optional[bool] = None
    quality_rating: Optional[str] = None
    model_updated: Optional[bool] = None
    review_notes: Optional[str] = None


class FeedbackSchema(BaseModel):
    verified_transcript: Optional[str] = None
    verified_address: Optional[str] = None
    verified_incident: Optional[str] = None
    verified_units: Optional[List[str]] = None
    verified_map_grid: Optional[str] = None
    verified_talkgroup: Optional[str] = None
    verified_response_type: Optional[str] = None
    verified_x_street_1: Optional[str] = None
    verified_x_street_2: Optional[str] = None
    quality_rating: Optional[str] = None
    review_notes: Optional[str] = None
    feedback_submitted: Optional[bool] = True


class StreetViewOverrideSchema(BaseModel):
    address: Optional[str] = None
    clean_address: Optional[str] = None
    front_lat: float
    front_lng: float
    heading: float = 0.0
    pitch: float = 5.0
    fov: float = 90.0   # degrees; the SDK's zoom 1 (#35a)
    pano_id: Optional[str] = None


class ParcelEntranceSchema(BaseModel):
    """Set (or clear, with lat/lng null) the operator-verified arrival point of one parcel (#49).

    `parcel_id` is public.parcels.id, the row's own key, and is what a caller should send:
    neither gis_id nor address identifies a row on its own. See _entrance_target() in
    routers/parcels.py for the measurement behind that.
    """
    parcel_id: Optional[int] = None
    address: Optional[str] = None
    gis_id: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    note: Optional[str] = None
    set_by: str


class ParcelCameraOverrideSchema(BaseModel):
    gis_id: Optional[str] = None
    address: Optional[str] = None
    clean_address: Optional[str] = None
    heading: float = 0.0
    pitch: float = 5.0
    fov: float = 90.0   # degrees
    # Where the camera stands. `view_lat`/`view_lng` is the name; `front_lat`/`front_lng`
    # is the older spelling of the same thing and is still accepted, but neither writes the
    # parcel's computed frontage any more (punch list #78, operator ruling 2026-09-11).
    view_lat: Optional[float] = None
    view_lng: Optional[float] = None
    front_lat: Optional[float] = None
    front_lng: Optional[float] = None
    pano_id: Optional[str] = None

    @property
    def camera_lat(self) -> Optional[float]:
        return self.view_lat if self.view_lat is not None else self.front_lat

    @property
    def camera_lng(self) -> Optional[float]:
        return self.view_lng if self.view_lng is not None else self.front_lng


