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

local_api_url = os.environ.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")

def clean_old_dispatches(limit: int = 100):
    endpoint = f"{local_api_url}/api/dispatches?limit=500"
    try:
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        calls = response.json()
        print(f"Total dispatches in database: {len(calls)}")
    except Exception as e:
        print(f"Failed to fetch calls from local API: {e}")

if __name__ == "__main__":
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
