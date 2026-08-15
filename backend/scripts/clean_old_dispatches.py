# backend/scripts/clean_old_dispatches.py
# Deletes old dispatch records from the local PostgreSQL database via the FastAPI endpoint.
import os
import sys
import requests
from datetime import datetime

# Add parent directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

local_api_url = os.environ.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")

def clean_old_dispatches(limit: int = 500):
    """Fetch and display old dispatches for review. Deletion requires manual confirmation."""
    endpoint = f"{local_api_url}/api/dispatches?limit={limit}"
    try:
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        calls = response.json()
        print(f"Total dispatches in database: {len(calls)}")
    except Exception as e:
        print(f"Failed to fetch calls from local API: {e}")
        return

    if not calls:
        print("No dispatches found.")
        return

    print(f"Found {len(calls)} dispatches:")
    print("--------------------------------------------------")
    for c in calls:
        print(f"ID: {c.get('dispatch_id')} | TS: {c.get('timestamp')} | Address: {c.get('address') or c.get('target', {}).get('address')}")
    print("--------------------------------------------------")

    # TODO: Implement local audio file deletion and dispatch record cleanup
    # via DELETE /api/dispatches/{id} endpoint (not yet implemented)
    print("\nNote: Automated deletion not yet implemented for local storage.")
    print("Use the FastAPI admin endpoint or direct SQL to remove old records.")

if __name__ == "__main__":
    clean_old_dispatches()
