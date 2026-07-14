import os
import json
import logging
import time
from typing import Dict, Any

from notification_service import (
    post_to_supabase,
    update_supabase_record,
    upload_to_supabase_storage
)

# Relative directory for storing offline queue JSON files
QUEUE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "offline_queue")

def ensure_queue_dir():
    try:
        os.makedirs(QUEUE_DIR, exist_ok=True)
    except Exception as e:
        logging.error(f"Failed to create offline queue directory {QUEUE_DIR}: {e}")

def queue_offline_dispatch(dispatch_id: str, action: str, payload: dict, local_wav_path: str = None):
    """
    Saves a failed Supabase request (insert/update) to a local JSON file in the offline queue.
    """
    ensure_queue_dir()
    queue_file = os.path.join(QUEUE_DIR, f"{dispatch_id}_{action}_{int(time.time())}.json")
    
    queue_data = {
        "dispatch_id": dispatch_id,
        "action": action,
        "payload": payload,
        "local_wav_path": local_wav_path,
        "queued_at": time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    try:
        logging.info(f"Queueing offline dispatch [ID: {dispatch_id}, Action: {action}] to {queue_file}...")
        with open(queue_file, "w") as f:
            json.dump(queue_data, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Failed to write offline dispatch to queue file {queue_file}: {e}", exc_info=True)
        return False

def sync_offline_queue(supabase_url: str, supabase_key: str):
    """
    Scans the offline queue directory and attempts to flush all pending items to Supabase.
    """
    if not supabase_url or not supabase_key:
        return
        
    ensure_queue_dir()
    
    try:
        files = [f for f in os.listdir(QUEUE_DIR) if f.endswith(".json")]
        if not files:
            return
        files.sort()  # Sort chronologically
    except Exception as e:
        logging.error(f"Failed to list offline queue files: {e}")
        return

    logging.info(f"Offline sync: Found {len(files)} pending dispatches in queue.")
    
    for file_name in files:
        file_path = os.path.join(QUEUE_DIR, file_name)
        if not os.path.exists(file_path):
            continue
            
        try:
            with open(file_path, "r") as f:
                item = json.load(f)
        except Exception as e:
            logging.error(f"Failed to read queue file {file_name}: {e}. Removing corrupt file.")
            try:
                os.remove(file_path)
            except Exception:
                pass
            continue
            
        dispatch_id = item.get("dispatch_id")
        action = item.get("action")
        payload = item.get("payload", {})
        local_wav_path = item.get("local_wav_path")
        
        # 1. Try to upload audio if it is still a local path
        audio_url = payload.get("audio_url")
        if audio_url and audio_url.startswith("/recordings/") and local_wav_path:
            if os.path.exists(local_wav_path):
                try:
                    logging.info(f"Offline sync: Attempting to upload cached audio for {dispatch_id}...")
                    with open(local_wav_path, "rb") as audio_file:
                        audio_bytes = audio_file.read()
                    
                    public_url = upload_to_supabase_storage(audio_bytes, f"{dispatch_id}.wav", supabase_url, supabase_key)
                    if public_url:
                        logging.info(f"Offline sync: Audio uploaded successfully for {dispatch_id}. URL: {public_url}")
                        payload["audio_url"] = public_url
                        item["payload"] = payload
                        try:
                            with open(file_path, "w") as wf:
                                json.dump(item, wf, indent=2)
                        except Exception:
                            pass
                except Exception as upload_err:
                    logging.error(f"Offline sync: Failed to upload audio for {dispatch_id}: {upload_err}")
            else:
                logging.warning(f"Offline sync: Local WAV path {local_wav_path} does not exist for {dispatch_id}.")

        # 2. Perform DB operation
        success = False
        try:
            if action == "insert":
                success = post_to_supabase(payload, supabase_url, supabase_key)
            elif action == "update":
                success = update_supabase_record(dispatch_id, payload, supabase_url, supabase_key)
        except Exception as db_err:
            logging.error(f"Offline sync error during DB {action} for {dispatch_id}: {db_err}")
            
        if success:
            logging.info(f"Offline sync: Successfully synced {dispatch_id} ({action}). Removing queue file.")
            try:
                os.remove(file_path)
            except Exception as rm_err:
                logging.error(f"Failed to remove sync queue file {file_path}: {rm_err}")
        else:
            logging.warning(f"Offline sync: Sync failed for {dispatch_id} ({action}). Retrying on next cycle.")
            # Break early if sync fails, assuming network is still down to avoid spamming connection attempts
            break

def start_offline_sync_poller(supabase_url: str, supabase_key: str, interval_seconds: int = 60):
    """
    Starts a daemon background thread that periodically checks and flushes the offline queue.
    """
    import threading
    
    def sync_thread():
        logging.info("Starting offline queue sync poller thread...")
        while True:
            try:
                sync_offline_queue(supabase_url, supabase_key)
            except Exception as e:
                logging.error(f"Error in offline sync thread: {e}")
            time.sleep(interval_seconds)
            
    t = threading.Thread(target=sync_thread, name="OfflineSyncPoller", daemon=True)
    t.start()
