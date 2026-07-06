import json
import logging
import requests

def post_to_ntfy(payload: dict, topic: str, token: str = None, title: str = None, priority: str = "5", tags: str = None) -> bool:
    """Posts dispatch data to a private Ntfy channel to wake up Android devices."""
    if not topic or topic.strip() == "" or "your-private-ntfy-topic" in topic:
        logging.info("Ntfy topic not configured or using default placeholder. Skipping push.")
        return False
        
    endpoint = f"https://ntfy.sh/{topic}"
    headers = {}
    if token and token.strip() != "" and "your-optional-ntfy-token" not in token:
        headers["Authorization"] = f"Bearer {token}"
        
    try:
        # Determine Title
        if title:
            headers["Title"] = title
        else:
            headers["Title"] = f"Dispatch: {payload.get('incident_type', 'Structure Fire')}"
            
        headers["Priority"] = priority
        
        # Determine Tags
        if tags:
            headers["Tags"] = tags
        else:
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
            
        # Format a clean, human-readable body message instead of raw JSON
        address = payload.get("address")
        if not address:
            target = payload.get("target", {})
            address = target.get("address")
        if not address:
            address = "Unknown Location"

        units_list = payload.get("responding_units", [])
        if isinstance(units_list, list):
            units_str = ", ".join(units_list) if units_list else "None assigned"
        else:
            units_str = str(units_list)

        transcript = payload.get("verified_transcript") or payload.get("sanitized_transcript") or payload.get("raw_transcript") or ""
        
        # Fallback if no transcript is present (e.g. for simple correction events)
        if not transcript:
            is_correction = title and "CORRECTION" in title
            if is_correction:
                transcript = "Location/units updated in Phase 2 processing."
            else:
                transcript = "No transcript available"

        if transcript.startswith("[") and transcript.endswith("]"):
            transcript_clean = transcript
        else:
            transcript_clean = transcript[:150] + "..." if len(transcript) > 150 else transcript

        duration = payload.get("audio_duration")
        duration_str = f" ({duration:.1f}s)" if duration else ""
        
        map_grid = payload.get("map_grid") or target.get("map_grid")
        radio_channel = payload.get("radio_channel") or target.get("radio_channel")

        lines = [
            f"📍 Address: {address}",
            f"🚒 Units: {units_str}"
        ]
        if map_grid:
            lines.append(f"🗺️ Map Grid: {map_grid}")
        if radio_channel:
            lines.append(f"📻 Channel: {radio_channel}")
            
        lines.append(f"📝 Transcript: {transcript_clean}{duration_str}")
        
        message_body = "\n".join(lines)
            
        logging.info(f"Posting formatted dispatch payload to ntfy.sh topic '{topic}'...")
        response = requests.post(endpoint, headers=headers, data=message_body.encode('utf-8'), timeout=10)
        response.raise_for_status()
        logging.info("Successfully posted to Ntfy.")
        return True
    except Exception as e:
        logging.warning(f"Failed to post to Ntfy: {e} (Please verify your NTFY_TOPIC and NTFY_TOKEN credentials.)")
        return False
