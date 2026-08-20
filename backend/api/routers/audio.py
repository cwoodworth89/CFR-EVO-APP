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


@router.get("/api/listener/status")
def get_listener_status():
    """Checks the operational status and heartbeat of the background RF audio listener process."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    status_file = os.path.join(base_dir, "data", "listener_status.json")
    if not os.path.exists(status_file) or os.path.getsize(status_file) == 0:
        return {
            "status": "offline",
            "message": "RF Listener process inactive (No heartbeat detected)",
            "last_heartbeat": None
        }
    try:
        with open(status_file, "r") as f:
            data = json.load(f)
        last_hb_str = data.get("last_heartbeat")
        if last_hb_str:
            last_hb_dt = datetime.fromisoformat(last_hb_str)
            age_seconds = (datetime.now(timezone.utc) - last_hb_dt).total_seconds()
            if age_seconds <= 30:
                return {
                    "status": "online",
                    "message": "RF Audio Listener Active",
                    "device": data.get("device"),
                    "stt_engine": data.get("stt_engine"),
                    "age_seconds": round(age_seconds, 1),
                    "last_heartbeat": last_hb_str
                }
            else:
                return {
                    "status": "offline",
                    "message": f"RF Listener unresponsive (Heartbeat {round(age_seconds)}s ago)",
                    "age_seconds": round(age_seconds, 1),
                    "last_heartbeat": last_hb_str
                }
    except Exception:
        return {"status": "offline", "message": "RF Listener status temporarily unavailable", "last_heartbeat": None}
    return {"status": "offline", "message": "RF Listener status unknown", "last_heartbeat": None}
