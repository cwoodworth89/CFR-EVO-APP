import os
import json
import logging
import requests
import urllib.parse

NTFY_SERVER_URL = os.environ.get("NTFY_SERVER_URL", "http://localhost:8080").rstrip("/")
if NTFY_SERVER_URL.startswith("https://"):
    NTFY_SERVER_URL = NTFY_SERVER_URL.replace("https://", "http://", 1)

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "cfr-dispatches")
API_BASE_URL = os.environ.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")
if API_BASE_URL.startswith("https://"):
    API_BASE_URL = API_BASE_URL.replace("https://", "http://", 1)


def post_to_ntfy(payload: dict, topic: str = None, token: str = None, title: str = None, priority: str = "5", tags: str = None, is_test: bool = None) -> bool:
    """Posts dispatch alert to local Ntfy push notification server on a single static admin topic."""
    if is_test is None:
        is_test = bool(payload.get("is_test", False))

    target = payload.get("target", {})
    address = payload.get("address") or target.get("address") or "Unknown Location"
    lat = payload.get("lat") or target.get("lat")
    lng = payload.get("lng") or target.get("lng")
    incident_type = payload.get("incident_type", "Emergency Call")

    if is_test:
        if not title:
            title = f"🚨 *TEST* DISPATCH: {incident_type}"
        elif "*TEST*" not in title:
            title = f"*TEST* {title}"
        if not tags:
            tags = "test,warning,fire_engine,rotating_light"
    else:
        if not title:
            title = f"🚨 DISPATCH: {incident_type}"
        if not tags:
            tags = "fire_engine,rotating_light,warning"

    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tags
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

    lines = []
    if is_test:
        lines.append("⚠️ *** THIS IS A SYSTEM TEST - NOT A REAL EMERGENCY *** ⚠️\n")
    lines.append(f"📍 Location: {'*TEST* ' if is_test else ''}{address}")
    lines.append(f"🚒 Units: {units_str}")
    if map_grid:
        lines.append(f"🗺️ Map Grid: {map_grid}")
    if radio_channel:
        lines.append(f"📻 Radio Channel: {radio_channel}")
    lines.append(f"📝 Transcript: {transcript_clean}")
    if is_test:
        lines.append("\n⚠️ *** THIS IS A SYSTEM TEST - NOT A REAL EMERGENCY *** ⚠️")
    
    message_body = "\n".join(lines).encode('utf-8')
    target_topic = topic or NTFY_TOPIC
    endpoint = f"{NTFY_SERVER_URL}/{target_topic}"

    safe_headers = {}
    for k, v in headers.items():
        if isinstance(v, str):
            safe_headers[k] = v.encode("utf-8").decode("latin-1")
        else:
            safe_headers[k] = str(v)

    if token:
        safe_headers["Authorization"] = f"Bearer {token}"

    try:
        logging.info(f"Posting dispatch notification to local Ntfy ({endpoint})...")
        res = requests.post(endpoint, headers=safe_headers, data=message_body, timeout=5)
        return res.status_code == 200
    except Exception as e:
        logging.warning(f"Could not post Ntfy alert to {endpoint}: {e}")
        return False


NTFY_ERROR_TOPIC = os.environ.get("NTFY_ERROR_TOPIC", "dev-errors")


def notify_pipeline_error(dispatch_id: str, stage: str, error: BaseException,
                          topic: str = None, token: str = None) -> bool:
    """Pushes a pipeline exception to the maintainer's Ntfy topic.

    Why this exists
    ---------------
    On 2026-08-31 two UnboundLocalErrors in `process_phase_2_finalize` had been
    aborting Phase 2 after the audio was written but before the record was updated.
    Fifteen dispatches lost their audio player. The error was in
    `journalctl -u cfr-agent` from the first occurrence, naming the dispatch and the
    variable, and went unread for two days -- punch-list #59.

    Punch-list #26 restored that logging in August. Nothing watches it. This is the
    watching.

    Deliberately separate from `chief-master`
    ----------------------------------------
    `chief-master` goes to chiefs and crews. A stack trace is not a dispatch, and putting
    one there trains people to swipe past both. `dev-errors` is the maintainer's topic and
    nobody operational subscribes to it.

    Never raises
    ------------
    A failing notifier must not add a second exception to the one being reported. Every
    path returns a bool, and the caller is inside an `except` already.
    """
    try:
        target_topic = topic or NTFY_ERROR_TOPIC
        url = f"{NTFY_SERVER_URL}/{target_topic}"
        headers = {
            "Title": f"⚠️ Pipeline error: {stage}",
            "Priority": "4",
            "Tags": "rotating_light,bug",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = (
            f"{type(error).__name__}: {error}\n\n"
            f"Dispatch: {dispatch_id or 'unknown'}\n"
            f"Stage:    {stage}\n\n"
            f"journalctl -u cfr-agent --since today | grep {dispatch_id or 'ERROR'}"
        )
        res = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=5)
        return res.status_code == 200
    except Exception as e:
        # Log and swallow. The original error is what matters.
        logging.warning(f"Could not send pipeline error alert to Ntfy: {e}")
        return False


def notify_it_alert(audit: dict, ntfy_topic: str = None, ntfy_token: str = None) -> bool:
    """Sends IT infrastructure health alert to administrative Ntfy channel."""
    target_topic = ntfy_topic or NTFY_TOPIC
    url = f"{NTFY_SERVER_URL}/{target_topic}"
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
