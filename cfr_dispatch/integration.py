# cfr_dispatch/integration.py
# Integration API clients for Supabase, Ntfy, and Join

import json
import logging
import requests
from typing import Tuple

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
        response.raise_for_status()
        logging.info("Successfully posted to Supabase.")
        return True
    except Exception as e:
        logging.error(f"Failed to post to Supabase: {e}", exc_info=True)
        return False

def post_to_ntfy(payload: dict, topic: str, token: str = None) -> bool:
    """Posts dispatch data to a private Ntfy channel to wake up Android devices."""
    if not topic:
        logging.warning("Ntfy topic not set. Skipping push.")
        return False
        
    endpoint = f"https://ntfy.sh/{topic}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    try:
        headers["Title"] = f"Dispatch: {payload.get('incident_type', 'Structure Fire')}"
        headers["Priority"] = "5"
        headers["Tags"] = "fire_engine,rotating_light"
        
        # Parse coordinates for direct tap-to-navigate action
        lat = payload.get("lat")
        lng = payload.get("lng")
        if not lat or not lng:
            target = payload.get("target", {})
            lat = target.get("lat")
            lng = target.get("lng")
            
        if lat and lng:
            headers["Click"] = f"google.navigation:q={lat},{lng}"
            
        logging.info(f"Posting dispatch payload to ntfy.sh topic '{topic}'...")
        response = requests.post(endpoint, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        logging.info("Successfully posted to Ntfy.")
        return True
    except Exception as e:
        logging.error(f"Failed to post to Ntfy: {e}", exc_info=True)
        return False

def launch_navigation_on_phone(location_coords: dict, address_label: str, join_api_key: str):
    """Triggers Android Join push API to open maps (legacy fallback)."""
    if not join_api_key or not location_coords:
        return
    latitude, longitude = location_coords['lat'], location_coords['lng']
    label = address_label.split(',')[0]
    text_payload = f"dispatch=:={latitude}|||{longitude}|||{label}"
    base_url = "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush"
    params = {'apikey': join_api_key, 'deviceId': 'group.phone', 'text': text_payload}
    
    logging.info(f"Preparing to send Join payload: {text_payload}")
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        logging.info("Join message sent successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Join API error: {e}", exc_info=True)
