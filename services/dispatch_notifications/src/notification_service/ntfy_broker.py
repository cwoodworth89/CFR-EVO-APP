import json
import logging
import requests

def post_to_ntfy(payload: dict, topic: str, token: str = None) -> bool:
    """Posts dispatch data to a private Ntfy channel to wake up Android devices."""
    if not topic or topic.strip() == "" or "your-private-ntfy-topic" in topic:
        logging.info("Ntfy topic not configured or using default placeholder. Skipping push.")
        return False
        
    endpoint = f"https://ntfy.sh/{topic}"
    headers = {}
    if token and token.strip() != "" and "your-optional-ntfy-token" not in token:
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
            headers["Click"] = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            
        logging.info(f"Posting dispatch payload to ntfy.sh topic '{topic}'...")
        response = requests.post(endpoint, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        logging.info("Successfully posted to Ntfy.")
        return True
    except Exception as e:
        logging.warning(f"Failed to post to Ntfy: {e} (Please verify your NTFY_TOPIC and NTFY_TOKEN credentials.)")
        return False
