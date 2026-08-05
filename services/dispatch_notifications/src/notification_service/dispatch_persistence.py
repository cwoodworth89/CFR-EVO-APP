# NOTE: Local database and API dispatch persistence gateway
import os
import logging
import requests

LOCAL_API_URL = os.environ.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")
ENABLE_SUPABASE_BACKUP = os.environ.get("ENABLE_SUPABASE_BACKUP", "false").lower() == "true"

def save_dispatch_record(payload: dict, url: str = None, key: str = None) -> bool:
    """Posts dispatch payload to local FastAPI gateway (/api/dispatches) and optional cloud backup."""
    endpoint = f"{LOCAL_API_URL}/api/dispatches"
    local_success = False
    try:
        logging.info(f"Posting dispatch payload to local API gateway ({endpoint})...")
        response = requests.post(endpoint, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Successfully posted dispatch to local API gateway.")
        local_success = True
    except Exception as e:
        logging.error(f"Failed to post to local API gateway: {e}")

    # If cloud Supabase backup is disabled, return local status
    if not ENABLE_SUPABASE_BACKUP:
        return local_success

    # Optional Cloud Supabase Backup Push
    url = url or os.environ.get("SUPABASE_URL", "")
    key = key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))

    if not url or not key:
        return local_success
        
    cloud_endpoint = f"{url.rstrip('/')}/rest/v1/live_calls"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        logging.info(f"Posting backup dispatch payload to Supabase cloud ({cloud_endpoint})...")
        response = requests.post(cloud_endpoint, headers=headers, json=payload, timeout=10)
        if response.status_code == 400 and ("audio_url" in payload or "audio_duration" in payload):
            fallback_payload = payload.copy()
            fallback_payload.pop("audio_url", None)
            fallback_payload.pop("audio_duration", None)
            response = requests.post(cloud_endpoint, headers=headers, json=fallback_payload, timeout=10)
        if response.status_code == 409:
            logging.info("Supabase POST returned 409 Conflict. Record already exists in cloud backup.")
            return True
        response.raise_for_status()
        logging.info("Successfully posted to Supabase cloud backup.")
        return True
    except Exception as e:
        logging.warning(f"Failed cloud Supabase backup push: {e}. Local push status: {local_success}")
        return local_success

def update_dispatch_record(dispatch_id: str, payload: dict, url: str = None, key: str = None) -> bool:
    """Updates dispatch record in local FastAPI gateway and optional cloud backup."""
    endpoint = f"{LOCAL_API_URL}/api/dispatches/{dispatch_id}"
    local_success = False
    try:
        logging.info(f"Updating dispatch ID {dispatch_id} in local API gateway...")
        response = requests.patch(endpoint, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Successfully updated local API record.")
        local_success = True
    except Exception as e:
        logging.error(f"Failed to update local API record: {e}")

    if not ENABLE_SUPABASE_BACKUP:
        return local_success

    url = url or os.environ.get("SUPABASE_URL", "")
    key = key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))

    if not url or not key:
        return local_success
        
    cloud_endpoint = f"{url.rstrip('/')}/rest/v1/live_calls?dispatch_id=eq.{dispatch_id}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        response = requests.patch(cloud_endpoint, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Successfully updated Supabase cloud record.")
        return True
    except Exception as e:
        logging.warning(f"Failed cloud Supabase update: {e}")
        return local_success

def save_audio_recording(file_bytes: bytes, file_name: str, url: str = None, key: str = None) -> str:
    """Saves audio file locally to recordings directory and returns relative URL route."""
    recordings_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "backend", "audio_files", "recordings"
    )
    os.makedirs(recordings_dir, exist_ok=True)
    local_path = os.path.join(recordings_dir, file_name)
    local_url = f"/api/audio/{file_name}"
    
    try:
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        logging.info(f"Successfully saved audio file locally to {local_path}.")
    except Exception as e:
        logging.error(f"Failed to save audio file locally: {e}")

    if not ENABLE_SUPABASE_BACKUP:
        return local_url

    url = url or os.environ.get("SUPABASE_URL", "")
    key = key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))

    if not url or not key:
        return local_url
        
    bucket = "dispatch-audio"
    cloud_endpoint = f"{url.rstrip('/')}/storage/v1/object/{bucket}/{file_name}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "audio/wav"
    }
    
    try:
        response = requests.post(cloud_endpoint, headers=headers, data=file_bytes, timeout=20)
        if response.status_code == 200:
            return f"{url.rstrip('/')}/storage/v1/object/public/{bucket}/{file_name}"
    except Exception as e:
        logging.warning(f"Failed to upload audio to Supabase cloud storage: {e}")
        
    return local_url

# Backward Compatibility Aliases
post_to_supabase = save_dispatch_record
update_supabase_record = update_dispatch_record
upload_to_supabase_storage = save_audio_recording
