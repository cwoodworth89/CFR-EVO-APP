import os
import json
import logging
import requests
import urllib.parse

MQTT_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = "cfr/dispatches"

NTFY_SERVER_URL = os.environ.get("NTFY_SERVER_URL", "http://localhost:8080").rstrip("/")

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

def format_unit_topic(unit_str: str) -> str:
    """Normalizes unit code (e.g. 'E1' -> 'engine-1', 'L1' -> 'ladder-1', 'R1' -> 'rescue-1', 'C1' -> 'chief-1')."""
    clean = unit_str.strip().lower().replace(" ", "")
    if clean.startswith("e") or "engine" in clean:
        num = "".join(filter(str.isdigit, clean)) or "1"
        return f"engine-{num}"
    if clean.startswith("l") or "ladder" in clean:
        num = "".join(filter(str.isdigit, clean)) or "1"
        return f"ladder-{num}"
    if clean.startswith("r") or "rescue" in clean or "medic" in clean:
        num = "".join(filter(str.isdigit, clean)) or "1"
        return f"rescue-{num}"
    if clean.startswith("c") or "car" in clean or "chief" in clean:
        num = "".join(filter(str.isdigit, clean)) or "1"
        return f"chief-{num}"
    return f"unit-{clean}"

def post_to_ntfy(payload: dict, topic: str = None, token: str = None, title: str = None, priority: str = "5", tags: str = None) -> bool:
    """Posts dispatch data to local Mosquitto MQTT AND local/remote Ntfy topics (all-dispatches + unit-specific)."""
    # 1. Publish to local Mosquitto MQTT (for Station Kiosks)
    mqtt_success = publish_mqtt_dispatch(payload)

    # 2. Format Ntfy notification payload
    target = payload.get("target", {})
    address = payload.get("address") or target.get("address") or "Unknown Location"
    lat = payload.get("lat") or target.get("lat")
    lng = payload.get("lng") or target.get("lng")

    headers = {
        "Title": title or f"🚨 DISPATCH: {payload.get('incident_type', 'Emergency Call')}",
        "Priority": priority,
        "Tags": tags or "fire_engine,rotating_light,warning"
    }

    if address and address != "Unknown Location":
        query_str = address
        if "Coquitlam" not in query_str and "BC" not in query_str:
            query_str += ", Coquitlam, BC"
        encoded_query = urllib.parse.quote_plus(query_str)
        headers["Click"] = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
    elif lat and lng:
        headers["Click"] = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"

    units_list = payload.get("responding_units", [])
    units_str = ", ".join(units_list) if isinstance(units_list, list) and units_list else str(units_list or "None assigned")
    transcript = payload.get("verified_transcript") or payload.get("sanitized_transcript") or payload.get("raw_transcript") or "No transcript available"
    transcript_clean = transcript[:150] + "..." if len(transcript) > 150 else transcript

    map_grid = payload.get("map_grid") or target.get("map_grid")
    radio_channel = payload.get("radio_channel") or target.get("radio_channel")

    lines = [
        f"📍 Location: {address}",
        f"🚒 Units: {units_str}"
    ]
    if map_grid:
        lines.append(f"🗺️ Map Grid: {map_grid}")
    if radio_channel:
        lines.append(f"📻 Radio Channel: {radio_channel}")
    lines.append(f"📝 Transcript: {transcript_clean}")
    
    message_body = "\n".join(lines).encode('utf-8')

    # Determine Ntfy target topics (General topic + Unit specific topics)
    target_topics = ["cfr-dispatches"]
    if topic:
        target_topics.append(topic)

    if isinstance(units_list, list):
        for unit in units_list:
            unit_topic = format_unit_topic(unit)
            if unit_topic not in target_topics:
                target_topics.append(unit_topic)

    ntfy_success = False
    for t in set(target_topics):
        endpoint = f"{NTFY_SERVER_URL}/{t}"
        try:
            logging.info(f"Posting dispatch notification to Ntfy endpoint ({endpoint})...")
            res = requests.post(endpoint, headers=headers, data=message_body, timeout=8)
            if res.status_code == 200:
                ntfy_success = True
        except Exception as e:
            logging.warning(f"Could not post Ntfy alert to topic '{t}' at {endpoint}: {e}")

    return mqtt_success or ntfy_success
