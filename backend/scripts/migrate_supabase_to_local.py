import os
import json
import logging
import requests
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from sqlalchemy.orm import Session
from backend.api.database import SessionLocal, engine, Base
from backend.api.models import LiveCallModel, EvaluationHistoryModel, DispatchUploadModel

import sys
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from cfr_dispatch.parser import split_rounds
from cfr_dispatch.config import UNITS_VOCABULARY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Ensure database tables exist locally
Base.metadata.create_all(bind=engine)

RECORDINGS_DIR = Path(__file__).resolve().parent.parent / "audio_files" / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL", os.environ.get("VITE_SUPABASE_URL", ""))
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_ANON_KEY", os.environ.get("VITE_SUPABASE_ANON_KEY", "")))

def fetch_supabase_table(table_name: str) -> List[Dict[str, Any]]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        logging.warning("Supabase URL or Key not set. Skipping cloud query.")
        return []
        
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table_name}?select=*"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    try:
        logging.info(f"Fetching table '{table_name}' from Supabase...")
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        data = res.json()
        logging.info(f"Retrieved {len(data)} rows from Supabase table '{table_name}'.")
        return data
    except Exception as e:
        logging.error(f"Failed to fetch table '{table_name}' from Supabase: {e}")
        return []

def sync_audio_files(live_calls: List[Dict[str, Any]]):
    logging.info("Checking local audio recordings in backend/audio_files/recordings...")
    
    for call in live_calls:
        dispatch_id = call.get("dispatch_id")
        audio_url = call.get("audio_url")
        
        if not dispatch_id:
            continue
            
        local_wav_name = f"{dispatch_id}.wav"
        local_path = RECORDINGS_DIR / local_wav_name
        
        if local_path.exists() and local_path.stat().st_size > 0:
            logging.info(f"Audio file for {dispatch_id} exists locally ({local_wav_name}). Skipping download.")
            continue
            
        # Download from Supabase if missing locally
        if audio_url and ("http://" in audio_url or "https://" in audio_url):
            try:
                logging.info(f"Downloading missing audio for {dispatch_id} from {audio_url}...")
                res = requests.get(audio_url, timeout=20)
                if res.status_code == 200 and len(res.content) > 0:
                    with open(local_path, "wb") as f:
                        f.write(res.content)
                    logging.info(f"Successfully saved {local_wav_name} ({len(res.content)} bytes).")
                else:
                    logging.warning(f"Audio download for {dispatch_id} returned status {res.status_code}.")
            except Exception as e:
                logging.error(f"Failed to download audio for {dispatch_id}: {e}")

def migrate_live_calls(db: Session, calls: List[Dict[str, Any]]):
    logging.info(f"Migrating {len(calls)} live_calls to local PostgreSQL...")
    migrated_count = 0
    
    for call_data in calls:
        dispatch_id = call_data.get("dispatch_id")
        if not dispatch_id:
            continue
            
        existing = db.query(LiveCallModel).filter(LiveCallModel.dispatch_id == dispatch_id).first()
        
        # Format audio_url to relative path
        relative_audio = f"/api/audio/{dispatch_id}.wav" if (RECORDINGS_DIR / f"{dispatch_id}.wav").exists() else call_data.get("audio_url")
        
        raw_ts = call_data.get("timestamp") or call_data.get("created_at")
        ts_val = None
        if raw_ts:
            try:
                ts_val = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
            except Exception:
                ts_val = raw_ts

        raw_sanitized = call_data.get("sanitized_transcript") or call_data.get("raw_transcript") or ""
        if raw_sanitized:
            rounds = split_rounds(raw_sanitized, UNITS_VOCABULARY)
            sanitized_clean = rounds[0].strip() if rounds else raw_sanitized
        else:
            sanitized_clean = ""

        fields = {
            "dispatch_id": dispatch_id,
            "incident_type": call_data.get("incident_type") or "Unknown Incident",
            "responding_units": call_data.get("responding_units") or [],
            "target": call_data.get("target") or {},
            "raw_transcript": call_data.get("raw_transcript"),
            "sanitized_transcript": sanitized_clean,
            "confidence_score": call_data.get("confidence_score") or 0.0,
            "verify_location": call_data.get("verify_location") or False,
            "origins": call_data.get("origins") or [],
            "audio_url": relative_audio,
            "audio_duration": call_data.get("audio_duration"),
            "verified_transcript": call_data.get("verified_transcript"),
            "verified_address": call_data.get("verified_address"),
            "verified_incident": call_data.get("verified_incident"),
            "verified_units": call_data.get("verified_units") or [],
            "feedback_submitted": call_data.get("feedback_submitted") or False,
            "quality_rating": call_data.get("quality_rating") or "PENDING",
            "model_updated": call_data.get("model_updated") or False,
            "review_notes": call_data.get("review_notes") or call_data.get("target", {}).get("review_notes")
        }
        if ts_val:
            fields["timestamp"] = ts_val
        
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            new_record = LiveCallModel(**fields)
            db.add(new_record)
            
        migrated_count += 1
        
    db.commit()
    logging.info(f"Successfully migrated/upserted {migrated_count} live_calls into local PostgreSQL.")

import uuid

def migrate_evaluations(db: Session, evals: List[Dict[str, Any]]):
    logging.info(f"Migrating {len(evals)} evaluation_history records...")
    count = 0
    for e in evals:
        eval_id_raw = e.get("id")
        if not eval_id_raw:
            continue
            
        try:
            eval_id = uuid.UUID(str(eval_id_raw)) if isinstance(eval_id_raw, str) else eval_id_raw
        except Exception as err:
            logging.warning(f"Invalid UUID '{eval_id_raw}': {err}")
            continue

        existing = db.query(EvaluationHistoryModel).filter(EvaluationHistoryModel.id == eval_id).first()
        fields = {
            "id": eval_id,
            "model_version": e.get("model_version", "unknown"),
            "total_samples": e.get("total_samples", 0),
            "wer": e.get("wer", 0.0),
            "cer": e.get("cer", 0.0),
            "perfect_percent": e.get("perfect_percent", 0.0),
            "operational_percent": e.get("operational_percent", 0.0),
            "failed_percent": e.get("failed_percent", 0.0)
        }
        if not existing:
            db.add(EvaluationHistoryModel(**fields))
            count += 1
    db.commit()
    logging.info(f"Successfully inserted {count} evaluation_history records.")

def main():
    db = SessionLocal()
    try:
        calls = fetch_supabase_table("live_calls")
        if calls:
            sync_audio_files(calls)
            migrate_live_calls(db, calls)
            
        evals = fetch_supabase_table("evaluation_history")
        if evals:
            migrate_evaluations(db, evals)
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
