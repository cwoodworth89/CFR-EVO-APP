# NOTE: For database schemas, migrations, and schema configs, see docs/supabase_setup.md
import logging
import requests

def post_to_supabase(payload: dict, url: str, key: str) -> bool:
    """Sends geocoded dispatch metadata to the Supabase Postgres REST endpoint."""
    if not url or not key:
        logging.warning("Supabase URL or Key not set. Skipping push.")
        return False
        
    endpoint = f"{url.rstrip('/')}/rest/v1/live_calls"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        logging.info(f"Posting dispatch payload to Supabase ({endpoint})...")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        if response.status_code == 400 and ("audio_url" in payload or "audio_duration" in payload):
            logging.warning("Supabase POST returned 400. Retrying without audio columns (please run migrations if you want to store audio details)...")
            fallback_payload = payload.copy()
            fallback_payload.pop("audio_url", None)
            fallback_payload.pop("audio_duration", None)
            response = requests.post(endpoint, headers=headers, json=fallback_payload, timeout=10)
        response.raise_for_status()
        logging.info("Successfully posted to Supabase.")
        return True
    except Exception as e:
        logging.error(f"Failed to post to Supabase: {e}", exc_info=True)
        return False

def update_supabase_record(dispatch_id: str, payload: dict, url: str, key: str) -> bool:
    """Updates an existing dispatch record in Supabase matched by dispatch_id via PostgREST PATCH."""
    if not url or not key:
        logging.warning("Supabase URL or Key not set. Skipping update.")
        return False
        
    endpoint = f"{url.rstrip('/')}/rest/v1/live_calls?dispatch_id=eq.{dispatch_id}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        logging.info(f"Updating dispatch ID {dispatch_id} in Supabase...")
        response = requests.patch(endpoint, headers=headers, json=payload, timeout=10)
        if response.status_code == 400 and ("audio_url" in payload or "audio_duration" in payload):
            logging.warning("Supabase PATCH returned 400. Retrying without audio columns...")
            fallback_payload = payload.copy()
            fallback_payload.pop("audio_url", None)
            fallback_payload.pop("audio_duration", None)
            response = requests.patch(endpoint, headers=headers, json=fallback_payload, timeout=10)
        response.raise_for_status()
        logging.info("Successfully updated Supabase record.")
        return True
    except Exception as e:
        logging.error(f"Failed to update Supabase record: {e}", exc_info=True)
        return False

def upload_to_supabase_storage(file_bytes: bytes, file_name: str, url: str, key: str) -> str | None:
    """Uploads binary file bytes to Supabase Storage bucket 'dispatch-audio' and returns its public URL."""
    if not url or not key:
        logging.warning("Supabase URL or Key not set. Skipping audio upload.")
        return None
        
    bucket = "dispatch-audio"
    endpoint = f"{url.rstrip('/')}/storage/v1/object/{bucket}/{file_name}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "audio/wav"
    }
    
    try:
        logging.info(f"Uploading audio file {file_name} to Supabase Storage ({endpoint})...")
        response = requests.post(endpoint, headers=headers, data=file_bytes, timeout=20)
        if response.status_code == 200:
            logging.info("Audio uploaded successfully.")
            # Construct and return the public URL
            public_url = f"{url.rstrip('/')}/storage/v1/object/public/{bucket}/{file_name}"
            return public_url
        else:
            logging.error(f"Failed to upload audio to Supabase Storage. Status: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Failed to upload audio to Supabase Storage: {e}", exc_info=True)
        return None
