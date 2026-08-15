# NOTE: Local database and API dispatch persistence gateway
import os
import logging
import requests

LOCAL_API_URL = os.environ.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")

def save_dispatch_record(payload: dict, url: str = None, key: str = None) -> bool:
    """Posts dispatch payload to local FastAPI gateway (/api/dispatches)."""
    endpoint = f"{LOCAL_API_URL}/api/dispatches"
    try:
        logging.info(f"Posting dispatch payload to local API gateway ({endpoint})...")
        response = requests.post(endpoint, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Successfully posted dispatch to local API gateway.")
        return True
    except Exception as e:
        logging.error(f"Failed to post to local API gateway: {e}")
        return False

def update_dispatch_record(dispatch_id: str, payload: dict, url: str = None, key: str = None) -> bool:
    """Updates dispatch record in local FastAPI gateway."""
    endpoint = f"{LOCAL_API_URL}/api/dispatches/{dispatch_id}"
    try:
        logging.info(f"Updating dispatch ID {dispatch_id} in local API gateway...")
        response = requests.patch(endpoint, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Successfully updated local API record.")
        return True
    except Exception as e:
        logging.error(f"Failed to update local API record: {e}")
        return False

def save_audio_recording(file_bytes: bytes, file_name: str, url: str = None, key: str = None) -> str:
    """Saves audio file locally to recordings directory and returns relative URL route."""
    recordings_dir = os.environ.get("RECORDINGS_DIR")
    if not recordings_dir:
        # Step up 5 directory levels from dispatch_persistence.py to reach project root (CFR-EVO-APP)
        current = os.path.abspath(__file__)
        for _ in range(5):
            current = os.path.dirname(current)
        recordings_dir = os.path.join(current, "backend", "audio_files", "recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    local_path = os.path.join(recordings_dir, file_name)
    local_url = f"/api/audio/{file_name}"
    
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(dir=recordings_dir, delete=False, suffix=".tmp") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        os.replace(tmp_path, local_path)
        logging.info(f"Successfully saved audio file locally to {local_path}.")
    except Exception as e:
        logging.error(f"Failed to save audio file locally: {e}")

    return local_url

