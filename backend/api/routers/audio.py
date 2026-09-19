"""
Audio Streaming, Upload, and RF Listener Status Endpoints for CFR EVO API Gateway.
Provides atomic WAV recording ingestion, streaming fallback, and radio listener heartbeat telemetry.
"""
import os
import json
import time
import logging
import tempfile
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["audio"])

RECORDINGS_DIR = os.environ.get(
    "RECORDINGS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "audio_files", "recordings")
)
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# The listener's heartbeat file, written by backend/cfr_dispatch/audio_listener.py
# (LISTENER_STATUS_FILE there). The host's ./backend/data is bind-mounted to
# /app/backend/data (docker-compose.yml, api service), so both ends reach the same file.
LISTENER_STATUS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "listener_status.json"
)

# The age at which a heartbeat stops meaning "alive". Unchanged from the value this endpoint
# has applied since the heartbeat was added; what is new is that a capture in progress now
# keeps the heartbeat fresh instead of running the clock out.
#
# Paired with LISTENER_HEARTBEAT_INTERVAL_S = 5.0 in backend/cfr_dispatch/config/runtime.py,
# the interval the listener writes at: six writes fit inside this window, so five must be
# missed in a row before a live listener reads as dead. backend/tests/test_listener_heartbeat.py
# fails if that ratio drops below 6, whichever side moves.
LISTENER_STALE_AFTER_S = 30.0

# The listener's own two states, written into the heartbeat
# (audio_listener.py LISTENER_STATE_IDLE / LISTENER_STATE_CAPTURING). The third is this
# endpoint's: a stopped process cannot write its own death, so only the age of the file says it.
LISTENER_STATE_CAPTURING = "capturing"
LISTENER_STATE_IDLE = "idle"
LISTENER_STATE_UNRESPONSIVE = "unresponsive"

# CLAUDE.md s6.1: a device the capture never resolved is an explicit unknown, not a name.
DEVICE_UNKNOWN = "--"


@router.post("/api/audio/upload")
async def upload_audio(file: UploadFile = File(...), filename: Optional[str] = None):
    """Atomically writes an uploaded audio recording to the local kiosk disk."""
    save_name = filename or file.filename
    if not save_name:
        save_name = f"dispatch_{int(time.time())}.wav"
    if not save_name.endswith(".wav"):
        save_name += ".wav"

    target_path = os.path.join(RECORDINGS_DIR, save_name)
    content = await file.read()

    # Atomic write to prevent concurrent reads of partially uploaded audio files
    with tempfile.NamedTemporaryFile(dir=RECORDINGS_DIR, delete=False, suffix=".tmp") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    os.replace(tmp_path, target_path)

    return {
        "status": "success",
        "filename": save_name,
        "audio_url": f"/api/audio/{save_name}"
    }


@router.get("/api/audio/{filename}")
def get_audio_file(filename: str):
    """Streams a dispatch WAV audio file with media-type headers."""
    clean_name = os.path.basename(filename)
    target_path = os.path.join(RECORDINGS_DIR, clean_name)
    if not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail="Audio recording not found")
    return FileResponse(target_path, media_type="audio/wav")


def _device_label(data: dict) -> str:
    """The resolved device name, or '--' when the capture resolved none (CLAUDE.md s6.1)."""
    name = data.get("device")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return DEVICE_UNKNOWN


def _unresponsive(message: str, age_seconds: Optional[float] = None,
                  last_heartbeat: Optional[str] = None) -> dict:
    """No usable heartbeat. `status` stays 'offline' for the console's existing reader."""
    return {
        "status": "offline",
        "listener_state": LISTENER_STATE_UNRESPONSIVE,
        "message": message,
        # A listener that is not reporting has no device. The last one it named is a fact
        # about a process that may be gone, and would read as current.
        "device": DEVICE_UNKNOWN,
        "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
        "last_heartbeat": last_heartbeat
    }


@router.get("/api/listener/status")
def get_listener_status():
    """Checks the operational status and heartbeat of the background RF audio listener process.

    Three states, in `listener_state`:

      capturing     -- alive, and a broadcast is being recorded right now. A restart here
                       loses the call and its audio (2026-09-05, punch-list #70).
      idle          -- alive and waiting for tones.
      unresponsive  -- no heartbeat, or one older than LISTENER_STALE_AFTER_S.

    `status` ('online' / 'offline') is unchanged and still covers the first two, because the
    console reads it directly (frontend/src/components/DispatchReview.jsx:157).
    """
    status_file = LISTENER_STATUS_FILE
    if not os.path.exists(status_file) or os.path.getsize(status_file) == 0:
        return _unresponsive("RF Listener process inactive (No heartbeat detected)")
    try:
        with open(status_file, "r") as f:
            data = json.load(f)
        last_hb_str = data.get("last_heartbeat")
        if not last_hb_str:
            return _unresponsive("RF Listener status unknown (heartbeat carries no timestamp)")
        last_hb_dt = datetime.fromisoformat(last_hb_str)
        age_seconds = (datetime.now(timezone.utc) - last_hb_dt).total_seconds()
    except Exception:
        return _unresponsive("RF Listener status temporarily unavailable")

    if age_seconds > LISTENER_STALE_AFTER_S:
        return _unresponsive(
            f"RF Listener unresponsive (Heartbeat {round(age_seconds)}s ago)",
            age_seconds=age_seconds,
            last_heartbeat=last_hb_str
        )

    # Fresh heartbeat. A heartbeat written before this field existed has no `state`; it is
    # reported as idle, never as capturing -- a capture this endpoint cannot see is not one
    # it may claim.
    capturing = data.get("state") == LISTENER_STATE_CAPTURING
    response = {
        "status": "online",
        "listener_state": LISTENER_STATE_CAPTURING if capturing else LISTENER_STATE_IDLE,
        "message": "RF Audio Listener Active",
        "device": _device_label(data),
        "stt_engine": data.get("stt_engine"),
        "age_seconds": round(age_seconds, 1),
        "last_heartbeat": last_hb_str
    }
    if not capturing:
        return response

    dispatch_id = data.get("dispatch_id")
    capture_age = None
    started = data.get("capture_started")
    if started:
        try:
            capture_age = round((datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds(), 1)
        except Exception:
            # An unparsable start time is an unknown age, not a zero (CLAUDE.md s6.1).
            capture_age = None
    response["dispatch_id"] = dispatch_id
    response["capture_started"] = started
    response["capture_age_seconds"] = capture_age
    age_text = f" for {round(capture_age)}s" if capture_age is not None else ""
    response["message"] = (
        f"RF Listener capturing {dispatch_id or 'a dispatch'}{age_text} "
        "-- a restart now loses the call"
    )
    return response
