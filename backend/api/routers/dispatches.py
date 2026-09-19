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
    from backend.api.schemas import (DispatchCreateSchema, DispatchUpdateSchema, FeedbackSchema,
                                     BulkModelUpdatedSchema)
    from backend.api.mqtt import publish_mqtt_event
except ModuleNotFoundError:
    from api.database import get_db
    from api.models import LiveCallModel
    from api.schemas import (DispatchCreateSchema, DispatchUpdateSchema, FeedbackSchema,
                             BulkModelUpdatedSchema)
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


# The `target` keys a list row carries in summary mode: what the review table, its filters and
# its open-flag count read (frontend ReviewTable.jsx, DispatchReview.jsx filteredCalls,
# utils/reviewFlags.js, review/reviewFormat.js getCallTones). Everything else in `target` --
# rings, candidates, segment, routing_metrics, notes -- comes with the full record, fetched from
# GET /api/dispatches/{id} when a row is selected.
SUMMARY_TARGET_KEYS = ("address", "map_coords_accurate", "tone_name", "review_flags",
                       "review_flag_count", "is_test")


def serialize_call_summary(call: LiveCallModel) -> dict:
    """A list row for the review table: the full record's shape, lighter.

    Operator 2026-09-18: the review dashboard took tens of seconds to load. Measured over the
    operator's link the full list was 2.4 MB for 693 rows (target 781 kB, routing_metrics
    320 kB, three transcripts 454 kB in the database). Summary mode drops routing_metrics, the
    sanitized and verified transcripts, origins, created_at (a copy of timestamp), audio_url and
    audio_duration, and every `target` key the table does not read.
    raw_transcript stays: the review search matches it. `summary: True` marks the row so the
    client never saves a review from it -- the save writes `target` back, and a partial target
    would overwrite the stored one.
    """
    target = call.target if isinstance(call.target, dict) else {}
    row = {
        "summary": True,
        "id": call.id,
        "dispatch_id": call.dispatch_id,
        "timestamp": call.timestamp.isoformat() if call.timestamp else None,
        "incident_type": call.incident_type,
        "responding_units": call.responding_units or [],
        "target": {k: target[k] for k in SUMMARY_TARGET_KEYS if k in target},
        "feedback_submitted": call.feedback_submitted,
    }
    # Optional fields are sent only when they hold something: a missing key reads as null to
    # every reader of a list row (`call.x ?? call.target?.x`, `x && x.length`), and across 693
    # rows the key names of empty fields were a third of the summary's weight.
    optional = {
        "raw_transcript": call.raw_transcript,
        "verified_address": call.verified_address,
        "verified_incident": call.verified_incident,
        "verified_units": call.verified_units or None,
        "verified_map_grid": call.verified_map_grid,
        "verified_talkgroup": call.verified_talkgroup,
        "verified_response_type": call.verified_response_type,
        "verified_x_street_1": call.verified_x_street_1,
        "verified_x_street_2": call.verified_x_street_2,
        "quality_rating": call.quality_rating,
        "model_updated": call.model_updated,
    }
    row.update({k: v for k, v in optional.items() if v not in (None, "", [])})
    return row


@router.get("")
def get_dispatches(
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    summary: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Retrieves paginated dispatch records ordered by newest first.

    `summary=true` returns list rows (serialize_call_summary) for the review table; the default
    response is the full record, unchanged for every other caller.
    """
    calls = db.query(LiveCallModel).order_by(desc(LiveCallModel.timestamp)).offset(offset).limit(limit).all()
    serialize = serialize_call_summary if summary else serialize_call
    return [serialize(c) for c in calls]


def _settle_is_test(data: dict, existing: Optional[LiveCallModel] = None) -> None:
    """Settle `target.is_test` for this write: fold in a top-level flag, and never let a
    `target` replacement silently drop one already stored.

    `is_test` marks a genuine pipeline test dispatch (CLAUDE.md 6.5). It lands in `target`
    rather than in a column of its own because every reader already looks there:
    SUMMARY_TARGET_KEYS above names it, so a summary list row carries it, and
    frontend/src/utils/dispatchModel.js:122 reads `record.is_test ?? target.is_test`. Both
    served shapes therefore carry it with no change to either serialiser and no migration.

    Carrying forward is the half that matters, and it is not belt-and-braces. Phase 2 sends
    four different UPDATE shapes, and the one on the COMMON path -- phase 1 and phase 2
    agreeing on the address, pipeline/phase2.py:387 -- replaces `target` wholesale and names
    no `is_test` at all. Its replacement is a spread of the phase-1 target held in the
    worker's memory (phase2.py:313, worker.py:65), which never carried the flag: the fold
    happens here, at the API, so the producer's own copy cannot know about it. Without the
    carry-forward, the flag written at create is erased by the routine phase-2 update on
    every test dispatch that geocodes cleanly.

    Preserving rather than requiring each writer to resend is deliberate. `is_test` is fixed
    when the call is captured; nothing downstream re-decides whether a broadcast was a test.
    An UPDATE replaces the geocoding answer, so it has no authority over the call's identity,
    and a rule that every writer must remember to resend has already failed once here -- at
    three sites out of four. Precedence: an explicit top-level flag wins, then an `is_test`
    the incoming `target` carries, then the stored value.

    Absent still means absent. When nobody names it and nothing is stored, `target` is left
    alone, so a row never acquires a fabricated False (CLAUDE.md 6.1). An explicit null says
    "unknown", which does not clear a value already measured.
    """
    flag = data.pop("is_test", None)   # popped either way: there is no is_test column to set
    incoming = data.get("target")
    replacing = isinstance(incoming, dict)
    stored = existing.target if existing is not None and isinstance(existing.target, dict) else {}

    if flag is None:
        if not replacing or "is_test" in incoming:
            # Nothing to do: either no `target` is being replaced, so the stored flag is
            # untouched, or the replacement already carries its own answer.
            return
        if "is_test" not in stored or stored["is_test"] is None:
            return
        flag = stored["is_test"]   # carry it across the replacement
    elif not replacing and bool(stored.get("is_test")) == bool(flag) and "is_test" in stored:
        # Already stored, and this write replaces no target: rewriting it would turn a
        # narrow PATCH into a full `target` write for nothing.
        return

    # A new dict, not a mutation -- SQLAlchemy does not track in-place changes to a JSON
    # column, so mutating `existing.target` would be silently lost.
    target = dict(incoming) if replacing else dict(stored)
    target["is_test"] = bool(flag)
    data["target"] = target


@router.post("")
def create_or_upsert_dispatch(payload: DispatchCreateSchema, db: Session = Depends(get_db)):
    """Creates a new dispatch record or updates an existing record by dispatch_id, broadcasting via MQTT."""
    existing = db.query(LiveCallModel).filter(LiveCallModel.dispatch_id == payload.dispatch_id).first()
    data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    _settle_is_test(data, existing)

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
    _settle_is_test(data, call)
    for key, val in data.items():
        setattr(call, key, val)

    db.commit()
    db.refresh(call)
    serialized = serialize_call(call)
    publish_mqtt_event("UPDATE", serialized)
    return serialized


@router.post("/model-updated")
def mark_model_updated(payload: BulkModelUpdatedSchema, db: Session = Depends(get_db)):
    """Bulk-sets model_updated on the given dispatch_ids in one transaction, without MQTT.

    `model_updated` is training-dataset bookkeeping: it records that a call's audio and
    verified transcript were pulled into the Whisper training cache. Nothing on the kiosk
    display reads it.

    It gets its own endpoint because update_dispatch() ends in publish_mqtt_event("UPDATE"),
    and extract_training_data.py set this flag with one PATCH per record -- so a single
    extraction run fired ~470 UPDATE events at the apparatus bay display, one React state
    update each, plus an update flash on whichever call happened to be on screen. A
    bookkeeping write should not reach the kiosk as a dispatch change.
    """
    if not payload.dispatch_ids:
        return {"status": "success", "updated": 0, "not_found": []}

    matched = db.query(LiveCallModel).filter(
        LiveCallModel.dispatch_id.in_(payload.dispatch_ids)
    ).all()

    for call in matched:
        call.model_updated = payload.model_updated
    db.commit()

    found = {c.dispatch_id for c in matched}
    missing = [d for d in payload.dispatch_ids if d not in found]
    if missing:
        logging.warning(
            f"mark_model_updated: {len(missing)} dispatch_id(s) not found, e.g. {missing[:5]}"
        )
    return {"status": "success", "updated": len(matched), "not_found": missing}


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

