"""
Dispatch Management Endpoints for CFR EVO API Gateway.
Handles CRUD operations, real-time MQTT broadcasting, SSE streaming, and HITL feedback for emergency calls.
"""
import asyncio
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

try:
    from backend.api.database import get_db
    from backend.api.models import LiveCallModel
    from backend.api.schemas import DispatchCreateSchema, DispatchUpdateSchema, FeedbackSchema
    from backend.api.mqtt import publish_mqtt_event
except ModuleNotFoundError:
    from api.database import get_db
    from api.models import LiveCallModel
    from api.schemas import DispatchCreateSchema, DispatchUpdateSchema, FeedbackSchema
    from api.mqtt import publish_mqtt_event

router = APIRouter(prefix="/api/dispatches", tags=["dispatches"])


def serialize_call(call: LiveCallModel) -> dict:
    """Formats LiveCallModel SQLAlchemy model into a clean JSON-serializable dictionary."""
    metrics = getattr(call, "routing_metrics", None)
    if not metrics and isinstance(call.target, dict):
        metrics = call.target.get("routing_metrics", [])
    if not metrics:
        metrics = []

    return {
        "id": call.id,
        "dispatch_id": call.dispatch_id,
        "timestamp": call.timestamp.isoformat() if call.timestamp else None,
        "created_at": call.timestamp.isoformat() if call.timestamp else None,
        "incident_type": call.incident_type,
        "responding_units": call.responding_units or [],
        "routing_metrics": metrics,
        "target": call.target or {},
        "raw_transcript": call.raw_transcript,
        "sanitized_transcript": call.sanitized_transcript,
        "verify_location": call.verify_location,
        "origins": call.origins or [],
        "audio_url": call.audio_url,
        "audio_duration": float(call.audio_duration) if call.audio_duration is not None else None,
        "verified_transcript": call.verified_transcript,
        "verified_address": call.verified_address,
        "verified_incident": call.verified_incident,
        "verified_units": call.verified_units or [],
        "verified_map_grid": call.verified_map_grid,
        "verified_talkgroup": call.verified_talkgroup,
        "verified_response_type": call.verified_response_type,
        "verified_x_street_1": call.verified_x_street_1,
        "verified_x_street_2": call.verified_x_street_2,
        "feedback_submitted": call.feedback_submitted,
        "quality_rating": call.quality_rating,
        "model_updated": call.model_updated,
        "review_notes": call.review_notes
    }


@router.get("")
def get_dispatches(
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieves paginated dispatch records ordered by newest first."""
    calls = db.query(LiveCallModel).order_by(desc(LiveCallModel.timestamp)).offset(offset).limit(limit).all()
    return [serialize_call(c) for c in calls]


@router.post("")
def create_or_upsert_dispatch(payload: DispatchCreateSchema, db: Session = Depends(get_db)):
    """Creates a new dispatch record or updates an existing record by dispatch_id, broadcasting via MQTT."""
    existing = db.query(LiveCallModel).filter(LiveCallModel.dispatch_id == payload.dispatch_id).first()
    data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)

    if existing:
        for key, val in data.items():
            setattr(existing, key, val)
        db.commit()
        db.refresh(existing)
        serialized = serialize_call(existing)
        publish_mqtt_event("UPDATE", serialized)
        return serialized
    else:
        new_call = LiveCallModel(**data)
        db.add(new_call)
        db.commit()
        db.refresh(new_call)
        serialized = serialize_call(new_call)
        publish_mqtt_event("INSERT", serialized)
        return serialized



@router.get("/stats")
def get_dispatch_stats(db: Session = Depends(get_db)):
    """Returns operational dispatch counts and confidence statistics."""
    total_calls = db.query(LiveCallModel).count()
    verified_calls = db.query(LiveCallModel).filter(LiveCallModel.feedback_submitted == True).count()
    unverified_calls = total_calls - verified_calls
    # average_confidence was removed 2026-08-29 (punch-list #45) along with the
    # score itself. Nothing consumed it. Flagged-dispatch count replaces it: a
    # countable condition rather than an average of a number that conflated address
    # correctness with metadata completeness.
    flagged_calls = db.query(LiveCallModel).filter(
        LiveCallModel.target["review_flag_count"].as_integer() > 0
    ).count()

    return {
        "total_dispatches": total_calls,
        "verified_dispatches": verified_calls,
        "unverified_dispatches": unverified_calls,
        "flagged_dispatches": flagged_calls
    }


@router.get("/unverified")
def get_unverified_dispatches(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    """Returns dispatches requiring Human-in-the-Loop review and feedback."""
    calls = db.query(LiveCallModel).filter(
        (LiveCallModel.feedback_submitted == False) | (LiveCallModel.feedback_submitted.is_(None))
    ).order_by(desc(LiveCallModel.timestamp)).limit(limit).all()
    return [serialize_call(c) for c in calls]


@router.get("/stream")
async def stream_dispatches():
    """Server-Sent Events (SSE) live stream endpoint for kiosk fallback connectivity."""
    async def event_generator():
        while True:
            # Send periodic SSE keepalive heartbeat every 15s
            await asyncio.sleep(15)
            yield f"data: {json.dumps({'type': 'heartbeat', 'status': 'connected'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{dispatch_id}")
def get_dispatch_by_id(dispatch_id: str, db: Session = Depends(get_db)):
    """Retrieves a single dispatch record by database ID or string dispatch_id."""
    if dispatch_id.isdigit():
        call = db.query(LiveCallModel).filter(LiveCallModel.id == int(dispatch_id)).first()
    else:
        call = db.query(LiveCallModel).filter(LiveCallModel.dispatch_id == dispatch_id).first()

    if not call:
        raise HTTPException(status_code=404, detail="Dispatch record not found")

    return serialize_call(call)


@router.patch("/{dispatch_id}")
def update_dispatch(dispatch_id: str, payload: DispatchUpdateSchema, db: Session = Depends(get_db)):
    """Partially updates an existing dispatch record and broadcasts the change via MQTT."""
    if dispatch_id.isdigit():
        call = db.query(LiveCallModel).filter(LiveCallModel.id == int(dispatch_id)).first()
    else:
        call = db.query(LiveCallModel).filter(LiveCallModel.dispatch_id == dispatch_id).first()

    if not call:
        raise HTTPException(status_code=404, detail="Dispatch record not found")

    data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    for key, val in data.items():
        setattr(call, key, val)

    db.commit()
    db.refresh(call)
    serialized = serialize_call(call)
    publish_mqtt_event("UPDATE", serialized)
    return serialized


@router.put("/{dispatch_id}")
def put_dispatch(dispatch_id: str, payload: DispatchUpdateSchema, db: Session = Depends(get_db)):
    """Full update / replace alias for dispatch records."""
    return update_dispatch(dispatch_id=dispatch_id, payload=payload, db=db)


@router.delete("/{dispatch_id}")
def delete_dispatch(dispatch_id: str, db: Session = Depends(get_db)):
    """Deletes a dispatch record and broadcasts a DELETE event to MQTT listeners."""
    if dispatch_id.isdigit():
        call = db.query(LiveCallModel).filter(LiveCallModel.id == int(dispatch_id)).first()
    else:
        call = db.query(LiveCallModel).filter(LiveCallModel.dispatch_id == dispatch_id).first()

    if not call:
        raise HTTPException(status_code=404, detail="Dispatch record not found")

    serialized = serialize_call(call)
    db.delete(call)
    db.commit()
    publish_mqtt_event("DELETE", serialized)
    return {"status": "success", "deleted_id": dispatch_id}


@router.post("/{dispatch_id}/feedback")
def submit_dispatch_feedback(dispatch_id: str, payload: FeedbackSchema, db: Session = Depends(get_db)):
    """Submits Human-in-the-Loop verified corrections for a dispatch."""
    if dispatch_id.isdigit():
        call = db.query(LiveCallModel).filter(LiveCallModel.id == int(dispatch_id)).first()
    else:
        call = db.query(LiveCallModel).filter(LiveCallModel.dispatch_id == dispatch_id).first()

    if not call:
        raise HTTPException(status_code=404, detail="Dispatch record not found")

    update_data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    update_data["feedback_submitted"] = True

    for key, val in update_data.items():
        setattr(call, key, val)

    db.commit()
    db.refresh(call)
    serialized = serialize_call(call)
    publish_mqtt_event("UPDATE", serialized)
    return serialized

