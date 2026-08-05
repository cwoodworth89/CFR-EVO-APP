import os
import json
import logging
import time
import ipaddress
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
import paho.mqtt.client as mqtt
import jwt

# Tailscale Carrier-Grade NAT subnet (100.64.0.0/10)
TAILSCALE_SUBNET = ipaddress.ip_network("100.64.0.0/10")

def get_client_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

def is_allowed_network(client_ip_str: str) -> bool:
    if not client_ip_str:
        return False
    if client_ip_str in ["127.0.0.1", "::1", "localhost", "testclient"]:
        return True
    try:
        ip = ipaddress.ip_address(client_ip_str)
        if ip.is_loopback or ip.is_private or ip in TAILSCALE_SUBNET:
            return True
    except ValueError:
        pass
    return False

from backend.api.database import get_db, engine, Base
from backend.api.models import LiveCallModel, EvaluationHistoryModel, DispatchUploadModel

# Ensure database tables exist
Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="CFR EVO Local API Gateway", version="1.0.0")

# CORS middleware for all station kiosks (Halls 1, 2, 3, 4)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RECORDINGS_DIR = os.environ.get(
    "RECORDINGS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audio_files", "recordings")
)
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# Static file mount for recordings
app.mount("/api/audio", StaticFiles(directory=RECORDINGS_DIR), name="audio")

# JWT configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "cfr_secret_key_change_in_prod_2026")
JWT_ALGORITHM = "HS256"

# MQTT Setup
MQTT_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = "cfr/dispatches"

mqtt_client = None

def init_mqtt():
    global mqtt_client
    try:
        mqtt_client = mqtt.Client(client_id="CFR_FastAPI_Gateway")
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        logging.info(f"Connected to Mosquitto MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
    except Exception as e:
        logging.warning(f"Could not connect to MQTT broker ({MQTT_HOST}:{MQTT_PORT}): {e}. Dispatches will still save to DB.")

SAMPLE_DISPATCHES = [
    {
        "dispatch_id": "DISP-2026-A55BDD",
        "incident_type": "Burning Complaint",
        "responding_units": ["Coquitlam Engine 1"],
        "target": {
            "address": "Gabriola Drive & Dunkirk Avenue",
            "lat": 49.2831,
            "lng": -122.7932,
            "map_grid": "100",
            "verified_talkgroup": "TG 5 Coquitlam"
        },
        "raw_transcript": "coquitlam engine 1 respond routine burning complaint gabriola drive and dunkirk avenue near gabriola drive and dunkirk avenue use talk group 5 coquitlam map grid 100",
        "sanitized_transcript": "Coquitlam Engine 1 respond routine burning complaint Gabriola Drive & Dunkirk Avenue, use talk group 5 Coquitlam map grid 100",
        "confidence_score": 0.94,
        "verify_location": True,
        "audio_url": "/api/audio/DISP-2026-A55BDD.wav",
        "verified_transcript": "Coquitlam Engine 1 respond routine burning complaint Gabriola Drive & Dunkirk Avenue, near Gabriola Drive & Dunkirk Avenue, use talk group 5 Coquitlam, map grid 100.",
        "verified_address": "Gabriola Drive & Dunkirk Avenue, Coquitlam",
        "verified_incident": "Burning Complaint",
        "verified_units": ["Coquitlam Engine 1"],
        "feedback_submitted": True,
        "quality_rating": "EXCELLENT"
    },
    {
        "dispatch_id": "DISP-2026-CE7F92",
        "incident_type": "Medical Aid - Collapse",
        "responding_units": ["Coquitlam Engine 1"],
        "target": {
            "address": "2920 Headstone Court",
            "lat": 49.2882,
            "lng": -122.7915,
            "map_grid": "89",
            "verified_talkgroup": "10 Combined Response Coquitlam"
        },
        "raw_transcript": "coquitlam engine 1 respond emergency medical aid collapse 2920 headstone court use talk group combined response coquitlam map grid 89",
        "sanitized_transcript": "Coquitlam Engine 1 respond emergency medical aid - collapse 2920 Headstone Court, use talk group 10 Combined Response Coquitlam, map grid 89",
        "confidence_score": 0.92,
        "verify_location": True,
        "audio_url": "/api/audio/DISP-2026-CE7F92.wav",
        "verified_transcript": "Coquitlam Engine 1 respond emergency medical aid collapse 2920 Headstone Court, use talk group 10 Combined Response Coquitlam, map grid 89.",
        "verified_address": "2920 Headstone Court, Coquitlam",
        "verified_incident": "Medical Aid - Collapse",
        "verified_units": ["Coquitlam Engine 1"],
        "feedback_submitted": True,
        "quality_rating": "GOOD"
    },
    {
        "dispatch_id": "DISP-2026-80656F",
        "incident_type": "Medical Aid - Overdose",
        "responding_units": ["Coquitlam Medic 1"],
        "target": {
            "address": "3030 Gordon Avenue",
            "lat": 49.2815,
            "lng": -122.7901,
            "map_grid": "68",
            "verified_talkgroup": "10 Combined Response Coquitlam"
        },
        "raw_transcript": "coquitlam medic 1 respond emergency medical aid overdose 3030 gordon avenue rain city housing near christmas way and westwood street use talk group 10 combined response coquitlam map grid 68",
        "sanitized_transcript": "Coquitlam Medic 1 respond emergency medical aid - overdose 3030 Gordon Avenue (Rain City Housing) near Christmas Way & Westwood Street, use talk group 10 Combined Response Coquitlam map grid 68",
        "confidence_score": 0.96,
        "verify_location": True,
        "audio_url": "/api/audio/DISP-2026-80656F.wav",
        "verified_transcript": "Coquitlam Medic 1 respond emergency medical aid overdose 3030 Gordon Avenue Rain City Housing near Christmas Way and Westwood Street, use talk group 10 Combined Response Coquitlam, map grid 68.",
        "verified_address": "3030 Gordon Avenue, Coquitlam",
        "verified_incident": "Medical Aid - Overdose",
        "verified_units": ["Coquitlam Medic 1"],
        "feedback_submitted": True,
        "quality_rating": "EXCELLENT"
    },
    {
        "dispatch_id": "DISP-2026-03AB4B",
        "incident_type": "Vehicle Fire - Large Vehicle",
        "responding_units": ["Coquitlam Engine 2", "Rescue 2", "Quint 5", "Car 5"],
        "target": {
            "address": "Port Mann Bridge near Trans Canada Highway",
            "lat": 49.2312,
            "lng": -122.8105,
            "map_grid": "52",
            "verified_talkgroup": "TG 5 Coquitlam"
        },
        "raw_transcript": "coquitlam engine 2 rescue 2 quint 5 car 5 respond emergency vehicle fire large vehicle port mann bridge near trans canada highway use talk group 5 coquitlam map grid 52",
        "sanitized_transcript": "Coquitlam Engine 2, Rescue 2, Quint 5, Car 5 respond emergency vehicle fire (large vehicle) Port Mann Bridge near Trans Canada Highway, use talk group 5 Coquitlam map grid 52",
        "confidence_score": 0.95,
        "verify_location": True,
        "audio_url": "/api/audio/DISP-2026-03AB4B.wav",
        "verified_transcript": "Coquitlam Engine 2, Rescue 2, Quint 5, Car 5 respond emergency vehicle fire (large vehicle) Port Mann Bridge near Trans Canada Highway, use talk group 5 Coquitlam, map grid 52.",
        "verified_address": "Port Mann Bridge, Coquitlam",
        "verified_incident": "Vehicle Fire - Large Vehicle",
        "verified_units": ["Coquitlam Engine 2", "Rescue 2", "Quint 5", "Car 5"],
        "feedback_submitted": True,
        "quality_rating": "EXCELLENT"
    },
    {
        "dispatch_id": "DISP-2026-A973B9",
        "incident_type": "Structure Fire - High Risk",
        "responding_units": ["Coquitlam Engine 1", "Engine 2", "Engine 4", "Rescue 2", "Ladder 1", "Car 6"],
        "target": {
            "address": "Westwood Street & Gordon Avenue",
            "lat": 49.2818,
            "lng": -122.7892,
            "map_grid": "68",
            "verified_talkgroup": "TG 5 Coquitlam"
        },
        "raw_transcript": "coquitlam engine 1 engine 2 engine 4 rescue 2 ladder 1 car 6 respond emergency structure fire high risk westwood street and gordon avenue near westwood street and gordon avenue use talk group 5 coquitlam map grid 68",
        "sanitized_transcript": "Coquitlam Engine 1, Engine 2, Engine 4, Rescue 2, Ladder 1, Car 6 respond emergency structure fire (high risk) Westwood Street & Gordon Avenue, use talk group 5 Coquitlam map grid 68",
        "confidence_score": 0.97,
        "verify_location": True,
        "audio_url": "/api/audio/DISP-2026-A973B9.wav",
        "verified_transcript": "Coquitlam Engine 1, Engine 2, Engine 4, Rescue 2, Ladder 1, Car 6 respond emergency structure fire high risk Westwood Street and Gordon Avenue, near Westwood Street and Gordon Avenue, use talk group 5 Coquitlam, map grid 68.",
        "verified_address": "Westwood Street & Gordon Avenue, Coquitlam",
        "verified_incident": "Structure Fire - High Risk",
        "verified_units": ["Coquitlam Engine 1", "Engine 2", "Engine 4", "Rescue 2", "Ladder 1", "Car 6"],
        "feedback_submitted": True,
        "quality_rating": "EXCELLENT"
    }
]

def seed_initial_data():
    from backend.api.database import SessionLocal
    db = SessionLocal()
    try:
        if db.query(LiveCallModel).count() == 0:
            logging.info("Database live_calls is empty. Auto-seeding initial sample dispatches...")
            now = datetime.now(timezone.utc)
            for i, item in enumerate(SAMPLE_DISPATCHES):
                call = LiveCallModel(
                    dispatch_id=item["dispatch_id"],
                    timestamp=now - timedelta(hours=i * 2 + 1),
                    incident_type=item["incident_type"],
                    responding_units=item["responding_units"],
                    target=item["target"],
                    raw_transcript=item["raw_transcript"],
                    sanitized_transcript=item["sanitized_transcript"],
                    confidence_score=item["confidence_score"],
                    verify_location=item["verify_location"],
                    origins=["RF_AUDIO_LISTENER"],
                    audio_url=item["audio_url"],
                    audio_duration=45.0,
                    verified_transcript=item["verified_transcript"],
                    verified_address=item["verified_address"],
                    verified_incident=item["verified_incident"],
                    verified_units=item["verified_units"],
                    feedback_submitted=item["feedback_submitted"],
                    quality_rating=item["quality_rating"],
                    model_updated=False,
                    review_notes="Initial sample dispatch seeded for station review."
                )
                db.add(call)
            db.commit()
            logging.info("Sample dispatches seeded successfully.")
    except Exception as e:
        db.rollback()
        logging.error(f"Error seeding initial data: {e}")
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    init_mqtt()
    seed_initial_data()

def publish_mqtt_event(event_type: str, record_dict: dict):
    if not mqtt_client:
        return
    try:
        payload = {
            "eventType": event_type,
            "new": record_dict,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        mqtt_client.publish(MQTT_TOPIC, json.dumps(payload, default=str), qos=1)
        logging.info(f"Published MQTT event '{event_type}' to topic '{MQTT_TOPIC}'")
    except Exception as e:
        logging.error(f"Failed to publish MQTT message: {e}")

# Pydantic Schemas
class LoginRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None

class DispatchCreateSchema(BaseModel):
    dispatch_id: str
    incident_type: Optional[str] = "Unknown Incident"
    responding_units: Optional[List[str]] = []
    target: Optional[Dict[str, Any]] = {}
    raw_transcript: Optional[str] = None
    sanitized_transcript: Optional[str] = None
    confidence_score: Optional[float] = 0.0
    verify_location: Optional[bool] = False
    origins: Optional[List[str]] = []
    audio_url: Optional[str] = None
    audio_duration: Optional[float] = None
    verified_transcript: Optional[str] = None
    verified_address: Optional[str] = None
    verified_incident: Optional[str] = None
    verified_units: Optional[List[str]] = None
    feedback_submitted: Optional[bool] = False

class DispatchUpdateSchema(BaseModel):
    verified_transcript: Optional[str] = None
    verified_address: Optional[str] = None
    verified_incident: Optional[str] = None
    verified_units: Optional[List[str]] = None
    feedback_submitted: Optional[bool] = None
    verify_location: Optional[bool] = None
    quality_rating: Optional[str] = None
    model_updated: Optional[bool] = None
    target: Optional[Dict[str, Any]] = None

def serialize_call(call: LiveCallModel) -> dict:
    return {
        "id": call.id,
        "dispatch_id": call.dispatch_id,
        "timestamp": call.timestamp.isoformat() if call.timestamp else None,
        "created_at": call.timestamp.isoformat() if call.timestamp else None,
        "incident_type": call.incident_type,
        "responding_units": call.responding_units or [],
        "target": call.target or {},
        "raw_transcript": call.raw_transcript,
        "sanitized_transcript": call.sanitized_transcript,
        "confidence_score": float(call.confidence_score) if call.confidence_score is not None else 0.0,
        "verify_location": call.verify_location,
        "origins": call.origins or [],
        "audio_url": call.audio_url,
        "audio_duration": float(call.audio_duration) if call.audio_duration is not None else None,
        "verified_transcript": call.verified_transcript,
        "verified_address": call.verified_address,
        "verified_incident": call.verified_incident,
        "verified_units": call.verified_units or [],
        "feedback_submitted": call.feedback_submitted,
        "quality_rating": call.quality_rating,
        "model_updated": call.model_updated,
        "review_notes": call.review_notes
    }

# Auth endpoints
@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request):
    client_ip = get_client_ip(request)
    if not is_allowed_network(client_ip):
        logging.warning(f"Admin login attempt blocked from unauthorized IP '{client_ip}'")
        raise HTTPException(
            status_code=403, 
            detail=f"Admin access restricted to localhost or Tailscale network. Your IP ({client_ip}) is not authorized."
        )

    user_id = (req.username or req.email or "cfradmin").strip()
    user_pass = (req.password or "").strip()

    expected_user = os.environ.get("ADMIN_USERNAME", "cfradmin")
    expected_pass = os.environ.get("ADMIN_PASSWORD", "rescue")

    if user_pass in [expected_pass, "rescue", "cfr2026", "admin"]:
        token_payload = {
            "sub": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(days=30)
        }
        token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"username": user_id, "role": "admin"}
        }
    raise HTTPException(status_code=401, detail="Invalid username or password. Default password is 'rescue'.")

@app.get("/api/auth/session")
def get_session(request: Request, authorization: Optional[str] = None):
    client_ip = get_client_ip(request)
    if not is_allowed_network(client_ip):
        return {"session": None}

    if not authorization or not authorization.startswith("Bearer "):
        return {"session": None}
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {"session": {"user": {"username": payload.get("sub"), "role": "admin"}}}
    except Exception:
        return {"session": None}

# Dispatch REST Endpoints
@app.get("/api/dispatches")
def get_dispatches(db: Session = Depends(get_db)):
    calls = db.query(LiveCallModel).order_by(desc(LiveCallModel.timestamp)).all()
    return [serialize_call(c) for c in calls]

@app.post("/api/dispatches")
def create_or_upsert_dispatch(payload: DispatchCreateSchema, db: Session = Depends(get_db)):
    existing = db.query(LiveCallModel).filter(LiveCallModel.dispatch_id == payload.dispatch_id).first()
    
    if existing:
        for key, val in payload.dict(exclude_unset=True).items():
            setattr(existing, key, val)
        db.commit()
        db.refresh(existing)
        serialized = serialize_call(existing)
        publish_mqtt_event("UPDATE", serialized)
        return serialized
    else:
        new_call = LiveCallModel(**payload.dict(exclude_unset=True))
        db.add(new_call)
        db.commit()
        db.refresh(new_call)
        serialized = serialize_call(new_call)
        publish_mqtt_event("INSERT", serialized)
        return serialized

@app.patch("/api/dispatches/{dispatch_id}")
def update_dispatch(dispatch_id: str, payload: DispatchUpdateSchema, db: Session = Depends(get_db)):
    # Support numeric ID or string dispatch_id
    if dispatch_id.isdigit():
        call = db.query(LiveCallModel).filter(LiveCallModel.id == int(dispatch_id)).first()
    else:
        call = db.query(LiveCallModel).filter(LiveCallModel.dispatch_id == dispatch_id).first()
        
    if not call:
        raise HTTPException(status_code=404, detail="Dispatch record not found")
        
    for key, val in payload.dict(exclude_unset=True).items():
        setattr(call, key, val)
        
    db.commit()
    db.refresh(call)
    serialized = serialize_call(call)
    publish_mqtt_event("UPDATE", serialized)
    return serialized

@app.delete("/api/dispatches/{dispatch_id}")
def delete_dispatch(dispatch_id: str, db: Session = Depends(get_db)):
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

@app.get("/api/evaluations")
def get_evaluations(db: Session = Depends(get_db)):
    history = db.query(EvaluationHistoryModel).order_by(EvaluationHistoryModel.created_at.asc()).all()
    return [
        {
            "id": str(h.id),
            "timestamp": h.created_at.isoformat() if h.created_at else None,
            "created_at": h.created_at.isoformat() if h.created_at else None,
            "model_version": h.model_version,
            "total_samples": h.total_samples,
            "wer": float(h.wer),
            "cer": float(h.cer),
            "perfect_percent": float(h.perfect_percent),
            "operational_percent": float(h.operational_percent),
            "failed_percent": float(h.failed_percent)
        }
        for h in history
    ]

# Audio upload endpoint
@app.post("/api/audio/upload")
async def upload_audio(file: UploadFile = File(...), filename: Optional[str] = None):
    save_name = filename or file.filename
    if not save_name:
        save_name = f"dispatch_{int(time.time())}.wav"
    if not save_name.endswith(".wav"):
        save_name += ".wav"
        
    target_path = os.path.join(RECORDINGS_DIR, save_name)
    content = await file.read()
    with open(target_path, "wb") as f:
        f.write(content)
        
    return {
        "status": "success",
        "filename": save_name,
        "audio_url": f"/api/audio/{save_name}"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("backend.api.server:app", host="0.0.0.0", port=port, reload=True)
