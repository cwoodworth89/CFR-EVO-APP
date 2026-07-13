# backend/scripts/clean_old_dispatches.py
import os
import sys
import requests
import json
from datetime import datetime

# Add parent directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import cfr_dispatch

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    print("Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set.")
    sys.exit(1)

headers = {
    "apikey": supabase_key,
    "Authorization": f"Bearer {supabase_key}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# Date cutoff: 2026-06-20 19:50:41
# Let's search with an ISO string representation.
cutoff_ts = "2026-06-20T19:50:41.999-07:00"

def get_old_calls():
    # Query live_calls table where timestamp is less than or equal to cutoff
    url = f"{supabase_url.rstrip('/')}/rest/v1/live_calls?timestamp=lte.{cutoff_ts}&order=timestamp.asc"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch calls: {e}")
        return []

def delete_supabase_storage_files(audio_urls):
    if not audio_urls:
        return
    
    print("\nDeleting audio files from Supabase Storage...")
    for url in audio_urls:
        if not url:
            continue
        try:
            # Parse bucket and path from URL: 
            # Example: https://nzdvjmwuzqrrdvjocyki.supabase.co/storage/v1/object/public/recordings/DISP-2026-XXXXXX.wav
            # Storage delete endpoint: /storage/v1/object/recordings/DISP-2026-XXXXXX.wav
            if "/storage/v1/object/public/" in url:
                path_part = url.split("/storage/v1/object/public/")[-1]
                bucket = path_part.split("/")[0]
                filepath = "/".join(path_part.split("/")[1:])
                
                delete_url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket}"
                delete_payload = {"prefixes": [filepath]}
                
                res = requests.delete(delete_url, headers=headers, json=delete_payload)
                if res.status_code in [200, 204]:
                    print(f"  Successfully deleted storage object: {path_part}")
                else:
                    print(f"  Failed to delete storage object {path_part}: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"  Error deleting storage file '{url}': {e}")

def delete_old_calls():
    # Perform DELETE on live_calls table
    url = f"{supabase_url.rstrip('/')}/rest/v1/live_calls?timestamp=lte.{cutoff_ts}"
    try:
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        deleted = response.json()
        print(f"\nSuccessfully deleted {len(deleted)} database records.")
        return deleted
    except Exception as e:
        print(f"Failed to delete database records: {e}")
        return []

if __name__ == "__main__":
    print(f"Supabase Target URL: {supabase_url}")
    print(f"Cutoff Timestamp: {cutoff_ts}\n")
    
    print("Fetching old dispatches...")
    calls = get_old_calls()
    
    if not calls:
        print("No dispatches found at or older than 2026-06-20 19:50:41.")
        sys.exit(0)
        
    print(f"Found {len(calls)} old dispatches:")
    print("--------------------------------------------------")
    audio_urls_to_delete = []
    for c in calls:
        print(f"ID: {c.get('dispatch_id')} | TS: {c.get('timestamp')} | Address: {c.get('address') or c.get('target', {}).get('address')}")
        audio_url = c.get("audio_url")
        if audio_url:
            audio_urls_to_delete.append(audio_url)
            
    print("--------------------------------------------------")
    
    # Run the deletions
    delete_supabase_storage_files(audio_urls_to_delete)
    delete_old_calls()
    print("\nCleanup completed.")
