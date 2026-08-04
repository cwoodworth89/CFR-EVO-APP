import os
import json
import logging
import requests

MQTT_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = "cfr/dispatches"

def publish_mqtt_dispatch(payload: dict, event_type: str = "INSERT") -> bool:
    """Publishes dispatch payload directly to Mosquitto MQTT broker for real-time station alerts."""
    try:
        import paho.mqtt.publish as publish
        
        msg_payload = json.dumps({
            "eventType": event_type,
            "new": payload
        }, default=str)
        
        logging.info(f"Publishing dispatch alert to MQTT broker {MQTT_HOST}:{MQTT_PORT} on topic '{MQTT_TOPIC}'...")
        publish.single(MQTT_TOPIC, msg_payload, hostname=MQTT_HOST, port=MQTT_PORT, qos=1)
        logging.info("Successfully published dispatch to local MQTT broker.")
        return True
    except Exception as e:
        logging.warning(f"Failed to publish to MQTT broker ({MQTT_HOST}:{MQTT_PORT}): {e}")
        return False

def post_to_ntfy(payload: dict, topic: str = None, token: str = None, title: str = None, priority: str = "5", tags: str = None) -> bool:
    """Posts dispatch data to local MQTT broker, and optionally ntfy.sh if configured."""
    # 1. Publish to local Mosquitto MQTT
    mqtt_success = publish_mqtt_dispatch(payload)

    # 2. Public ntfy.sh (optional legacy fallback)
    if not topic or topic.strip() == "" or "your-private-ntfy-topic" in topic:
        return mqtt_success
        
    endpoint = f"https://ntfy.sh/{topic}"
    headers = {}
    if token and token.strip() != "" and "your-optional-ntfy-token" not in token:
        headers["Authorization"] = f"Bearer {token}"
        
    try:
        if title:
            headers["Title"] = title
        else:
            headers["Title"] = f"Dispatch: {payload.get('incident_type', 'Structure Fire')}"
            
        headers["Priority"] = priority
        headers["Tags"] = tags or "fire_engine,rotating_light"
            
        import urllib.parse
        target = payload.get("target", {})
        address = payload.get("address") or target.get("address") or "Unknown Location"
        lat = payload.get("lat") or target.get("lat")
        lng = payload.get("lng") or target.get("lng")

        if address and address != "Unknown Location":
            query_str = address
            if "Coquitlam" not in query_str and "BC" not in query_str:
                query_str += ", Coquitlam, BC"
            encoded_query = urllib.parse.quote_plus(query_str)
            headers["Click"] = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
        elif lat and lng:
            headers["Click"] = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"

        units_list = payload.get("responding_units", [])
        units_str = ", ".join(units_list) if isinstance(units_list, list) and units_list else str(units_list)
        transcript = payload.get("verified_transcript") or payload.get("sanitized_transcript") or payload.get("raw_transcript") or "No transcript available"
        transcript_clean = transcript[:150] + "..." if len(transcript) > 150 else transcript

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
        lines.append(f"📝 Transcript: {transcript_clean}")
        
        logging.info(f"Posting formatted dispatch payload to ntfy.sh topic '{topic}'...")
        response = requests.post(endpoint, headers=headers, data="\n".join(lines).encode('utf-8'), timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logging.warning(f"Failed to post to Ntfy: {e}")
        return mqtt_success
