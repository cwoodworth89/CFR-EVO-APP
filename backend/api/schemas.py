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
    fov: float = 80.0


class ParcelCameraOverrideSchema(BaseModel):
    gis_id: Optional[str] = None
    address: Optional[str] = None
    clean_address: Optional[str] = None
    heading: float = 0.0
    pitch: float = 5.0
    fov: float = 80.0
    front_lat: Optional[float] = None
    front_lng: Optional[float] = None


