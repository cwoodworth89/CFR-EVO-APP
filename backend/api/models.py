from sqlalchemy import Column, Integer, BigInteger, String, Float, Boolean, Text, DateTime, JSON, ARRAY, Numeric, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY as PG_ARRAY
import uuid

try:
    from api.database import Base
except ModuleNotFoundError:
    from backend.api.database import Base

SafeJSON = JSON().with_variant(JSONB(), "postgresql")
SafeArray = JSON().with_variant(PG_ARRAY(String), "postgresql")
SafeUUID = String(36).with_variant(UUID(as_uuid=True), "postgresql")

class LiveCallModel(Base):
    __tablename__ = "live_calls"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    dispatch_id = Column(String, unique=True, index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    incident_type = Column(String, default="Unknown Incident", nullable=False)
    responding_units = Column(SafeArray, default=[], nullable=False)
    routing_metrics = Column(SafeJSON, default=[], nullable=True)
    target = Column(SafeJSON, default={}, nullable=False)
    
    raw_transcript = Column(Text, nullable=True)
    sanitized_transcript = Column(Text, nullable=True)
    confidence_score = Column(Numeric(5, 2), default=0.0)
    verify_location = Column(Boolean, default=False)
    origins = Column(SafeArray, default=[])
    
    audio_url = Column(Text, nullable=True)
    audio_duration = Column(Numeric(6, 2), nullable=True)
    
    verified_transcript = Column(Text, nullable=True)
    verified_address = Column(Text, nullable=True)
    verified_incident = Column(Text, nullable=True)
    verified_units = Column(SafeArray, nullable=True)
    feedback_submitted = Column(Boolean, default=False)
    quality_rating = Column(String, default="PENDING")
    model_updated = Column(Boolean, default=False)
    review_notes = Column(Text, nullable=True)



class EvaluationHistoryModel(Base):
    __tablename__ = "evaluation_history"
    __table_args__ = {'extend_existing': True}

    id = Column(SafeUUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    model_version = Column(String, nullable=False)
    total_samples = Column(Integer, nullable=False)
    wer = Column(Numeric(5, 2), nullable=False)
    cer = Column(Numeric(5, 2), nullable=False)
    perfect_percent = Column(Numeric(5, 2), nullable=False)
    operational_percent = Column(Numeric(5, 2), nullable=False)
    failed_percent = Column(Numeric(5, 2), nullable=False)


class DispatchUploadModel(Base):
    __tablename__ = "dispatch_uploads"
    __table_args__ = {'extend_existing': True}

    id = Column(SafeUUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    audio_url = Column(Text, nullable=False)
    verified_transcript = Column(Text, nullable=True)
    status = Column(String, default="pending", nullable=False)
    result = Column(SafeJSON, nullable=True)
    error_message = Column(Text, nullable=True)


class RoadClosureModel(Base):
    __tablename__ = "road_closures"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    closure_id = Column(String, unique=True, index=True, nullable=False)
    street_name = Column(String, nullable=False)
    source = Column(String, nullable=False)
    closure_type = Column(String, default="FULL_CLOSURE")
    emergency_access = Column(String, nullable=False)
    headline = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    geometry = Column(SafeJSON, nullable=False)
    coordinates = Column(SafeArray, nullable=False)
    zone_id = Column(String(16), index=True, nullable=True)
    affected_zones = Column(SafeArray, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class StreetViewOverrideModel(Base):
    __tablename__ = "streetview_overrides"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    clean_address = Column(String, unique=True, index=True, nullable=False)
    front_lat = Column(Float, nullable=False)
    front_lng = Column(Float, nullable=False)
    heading = Column(Float, default=0.0, nullable=False)
    pitch = Column(Float, default=5.0, nullable=False)
    fov = Column(Float, default=80.0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

