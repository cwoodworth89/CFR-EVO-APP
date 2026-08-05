import os
import json
import logging
import hashlib
import requests
import urllib.parse
from datetime import datetime, timezone

MQTT_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = "cfr/dispatches"

NTFY_SERVER_URL = os.environ.get("NTFY_SERVER_URL", "http://localhost:8080").rstrip("/")
if NTFY_SERVER_URL.startswith("https://"):
    NTFY_SERVER_URL = NTFY_SERVER_URL.replace("https://", "http://", 1)

NTFY_TOPIC_SECRET = os.environ.get("NTFY_TOPIC_SECRET", "AUTO_MONTHLY")
NTFY_MASTER_SALT = os.environ.get("NTFY_MASTER_SALT", "cfr_master_salt_2026")
CHIEF_MASTER_TOPIC = os.environ.get("CHIEF_MASTER_TOPIC", "chief-master")  # Permanent, non-expiring master feed for Chiefs/Admin

API_BASE_URL = os.environ.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")
if API_BASE_URL.startswith("https://"):
    API_BASE_URL = API_BASE_URL.replace("https://", "http://", 1)

def get_monthly_secret(dt: datetime = None) -> str:
    """Computes a deterministic 6-char monthly secret salt from year+month and master salt."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    date_str = dt.strftime("%Y-%m")
    raw = f"{NTFY_MASTER_SALT}-{date_str}"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
    month_code = dt.strftime("%b%Y").lower()  # e.g. aug2026
    return f"{month_code}-{digest}"

def get_active_secrets() -> list[str]:
    """Returns list of active topic secrets (current month + previous month during 3-day grace period)."""
    if not NTFY_TOPIC_SECRET:
        return [""]
    if NTFY_TOPIC_SECRET != "AUTO_MONTHLY":
        return [NTFY_TOPIC_SECRET]

    now = datetime.now(timezone.utc)
    current_secret = get_monthly_secret(now)
    secrets = [current_secret]

    # First 3 days of the month: include previous month secret as grace period
    if now.day <= 3:
        year = now.year
        month = now.month - 1
        if month == 0:
            month = 12
            year -= 1
        prev_dt = datetime(year, month, 1, tzinfo=timezone.utc)
        prev_secret = get_monthly_secret(prev_dt)
        secrets.append(prev_secret)

    return secrets

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

def format_unit_topics(unit_str: str) -> list[str]:
    """Normalizes unit code (e.g. 'E1' -> 'engine-1') and appends active monthly secret tokens."""
    clean = unit_str.strip().lower().replace(" ", "")
    base = f"unit-{clean}"
    if clean.startswith("e") or "engine" in clean:
        num = "".join(filter(str.isdigit, clean)) or "1"
        base = f"engine-{num}"
    elif clean.startswith("l") or "ladder" in clean:
        num = "".join(filter(str.isdigit, clean)) or "1"
        base = f"ladder-{num}"
    elif clean.startswith("r") or "rescue" in clean or "medic" in clean:
        num = "".join(filter(str.isdigit, clean)) or "1"
        base = f"rescue-{num}"
    elif clean.startswith("c") or "car" in clean or "chief" in clean:
        num = "".join(filter(str.isdigit, clean)) or "1"
        base = f"chief-{num}"

    secrets = get_active_secrets()
    return [f"{base}-{s}" if s else base for s in secrets]

def post_to_ntfy(payload: dict, topic: str = None, token: str = None, title: str = None, priority: str = "5", tags: str = None) -> bool:
    """Posts dispatch data to local Mosquitto MQTT AND local/remote Ntfy topics with audio attachments & master feed."""
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

    # Resolve audio stream URL if present (force http:// for unencrypted local Ntfy broker)
    raw_audio = payload.get("audio_url")
    audio_full_url = None
    if raw_audio:
        if raw_audio.startswith("http://") or raw_audio.startswith("https://"):
            audio_full_url = raw_audio.replace("https://", "http://", 1)
        else:
            audio_full_url = f"{API_BASE_URL}{'' if raw_audio.startswith('/') else '/'}{raw_audio}"
            audio_full_url = audio_full_url.replace("https://", "http://", 1)
            
        headers["Attach"] = audio_full_url

    # Resolve Google Maps click URL
    click_url = None
    if address and address != "Unknown Location":
        query_str = address
        if "Coquitlam" not in query_str and "BC" not in query_str:
            query_str += ", Coquitlam, BC"
        encoded_query = urllib.parse.quote_plus(query_str)
        click_url = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
    elif lat and lng:
        click_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"

    if click_url:
        headers["Click"] = click_url

    # Format Tap-to-Listen and Open Map Lock-screen Action Buttons
    actions = []
    if audio_full_url:
        actions.append(f"view, 🎧 Listen to Call Audio, {audio_full_url}")
    if click_url:
        actions.append(f"view, 🗺️ Open Map Navigation, {click_url}")
        
    if actions:
        headers["Actions"] = "; ".join(actions)

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

    # Generate target topics:
    # A) Permanent Chief/Admin Master Feed (no expiry)
    target_topics = [CHIEF_MASTER_TOPIC]

    # B) Active monthly secret topics for general station & apparatus feeds
    secrets = get_active_secrets()
    for s in secrets:
        target_topics.append(f"cfr-dispatches-{s}" if s else "cfr-dispatches")
        if topic:
            target_topics.append(f"{topic}-{s}" if s else topic)

    if isinstance(units_list, list):
        for unit in units_list:
            unit_topics = format_unit_topics(unit)
            target_topics.extend(unit_topics)

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
