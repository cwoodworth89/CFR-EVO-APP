import os
import json
import logging
import hashlib
import requests
import urllib.parse
from datetime import datetime, timezone

NTFY_SERVER_URL = os.environ.get("NTFY_SERVER_URL", "http://localhost:8080").rstrip("/")
if NTFY_SERVER_URL.startswith("https://"):
    NTFY_SERVER_URL = NTFY_SERVER_URL.replace("https://", "http://", 1)

NTFY_TOPIC_SECRET = os.environ.get("NTFY_TOPIC_SECRET", "AUTO_MONTHLY")
NTFY_MASTER_SALT = os.environ.get("NTFY_MASTER_SALT", "cfr_master_salt_2026")
CHIEF_MASTER_TOPIC = os.environ.get("CHIEF_MASTER_TOPIC", "chief-master")

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
    """Posts dispatch alert to local/remote Ntfy push notification topics with audio attachments."""
    # 1. Format Ntfy notification payload
    target = payload.get("target", {})
    address = payload.get("address") or target.get("address") or "Unknown Location"
    lat = payload.get("lat") or target.get("lat")
    lng = payload.get("lng") or target.get("lng")

    headers = {
        "Title": title or f"🚨 DISPATCH: {payload.get('incident_type', 'Emergency Call')}",
        "Priority": priority,
        "Tags": tags or "fire_engine,rotating_light,warning"
    }

    raw_audio = payload.get("audio_url")
    audio_full_url = None
    if raw_audio:
        if raw_audio.startswith("http://") or raw_audio.startswith("https://"):
            audio_full_url = raw_audio.replace("https://", "http://", 1)
        else:
            audio_full_url = f"{API_BASE_URL}{'' if raw_audio.startswith('/') else '/'}{raw_audio}"
            audio_full_url = audio_full_url.replace("https://", "http://", 1)
            
        headers["Attach"] = audio_full_url

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

    target_topics = [CHIEF_MASTER_TOPIC]
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
        endpoints = [f"{NTFY_SERVER_URL}/{t}"]
        if not NTFY_SERVER_URL.startswith("https://ntfy.sh"):
            endpoints.append(f"https://ntfy.sh/{t}")

        safe_headers = {}
        for k, v in headers.items():
            if isinstance(v, str):
                safe_headers[k] = v.encode("utf-8").decode("latin-1")
            else:
                safe_headers[k] = str(v)

        body_bytes = message_body.encode("utf-8") if isinstance(message_body, str) else message_body

        for endpoint in endpoints:
            try:
                logging.info(f"Posting dispatch notification to Ntfy endpoint ({endpoint})...")
                res = requests.post(endpoint, headers=safe_headers, data=body_bytes, timeout=8)
                if res.status_code == 200:
                    ntfy_success = True
            except Exception as e:
                logging.warning(f"Could not post Ntfy alert to topic '{t}' at {endpoint}: {e}")

    return ntfy_success

def notify_it_alert(audit: dict, ntfy_topic: str = None, ntfy_token: str = None) -> bool:
    """Sends IT infrastructure health alert to administrative Ntfy channel."""
    topic = ntfy_topic or os.environ.get("NTFY_TOPIC", CHIEF_MASTER_TOPIC)
    url = f"{NTFY_SERVER_URL}/{topic}"
    headers = {
        "Title": f"⚠️ CFR EVO IT Health Alert: {audit.get('status', 'Warning')}",
        "Priority": "4",
        "Tags": "warning,computer"
    }
    if ntfy_token:
        headers["Authorization"] = f"Bearer {ntfy_token}"
    body = json.dumps(audit, indent=2)
    try:
        res = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=5)
        return res.status_code == 200
    except Exception as e:
        logging.warning(f"Could not send IT alert to Ntfy: {e}")
        return False
