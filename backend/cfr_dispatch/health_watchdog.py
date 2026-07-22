# backend/cfr_dispatch/health_watchdog.py
# Automated IT Health Watchdog & System Diagnostics Monitor

import os
import sys
import time
import shutil
import logging
import requests
import numpy as np

# Ensure backend root is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from cfr_dispatch.config.hardware import resolve_audio_device, AUDIO_SAMPLE_RATE

def check_disk_space(path: str = ".") -> Dict[str, Any]:
    """Checks available disk space in GB and percentage."""
    try:
        total, used, free = shutil.disk_usage(path)
        free_gb = free / (1024 ** 3)
        total_gb = total / (1024 ** 3)
        free_pct = (free / total) * 100
        return {
            "status": "OK" if free_pct > 10.0 else "WARNING",
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "free_pct": round(free_pct, 1)
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def check_network_connectivity(target_url: str = "https://1.1.1.1") -> Dict[str, Any]:
    """Checks WAN / LAN connectivity via HTTP HEAD request."""
    try:
        start = time.time()
        res = requests.head(target_url, timeout=3)
        latency_ms = (time.time() - start) * 1000
        return {
            "status": "OK" if res.status_code < 400 else "WARNING",
            "latency_ms": round(latency_ms, 1),
            "status_code": res.status_code
        }
    except Exception as e:
        return {"status": "OFFLINE", "error": str(e), "latency_ms": None}

def check_audio_interface() -> Dict[str, Any]:
    """Tests audio soundcard availability and verifies non-zero RMS signal."""
    dev_idx, dev_name = resolve_audio_device()
    if dev_idx is None:
        return {
            "status": "ERROR",
            "device_name": dev_name,
            "error": "No valid audio input device found"
        }

    try:
        import sounddevice as sd
        # Sample 0.5 seconds of audio to test stream capture
        duration = 0.5
        samples = int(duration * AUDIO_SAMPLE_RATE)
        recording = sd.rec(samples, samplerate=AUDIO_SAMPLE_RATE, channels=1, dtype='int16', device=dev_idx)
        sd.wait()
        
        rms = float(np.sqrt(np.mean(np.square(recording.astype(np.float32)))))
        return {
            "status": "OK" if rms >= 0.0 else "WARNING",
            "device_idx": dev_idx,
            "device_name": dev_name,
            "rms_level": round(rms, 2)
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "device_idx": dev_idx,
            "device_name": dev_name,
            "error": str(e)
        }

def run_full_health_audit() -> Dict[str, Any]:
    """Runs a complete IT health audit across hardware, storage, and network vectors."""
    audit = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "audio": check_audio_interface(),
        "disk": check_disk_space(),
        "network": check_network_connectivity()
    }
    
    # Overall status determination
    statuses = [audit["audio"]["status"], audit["disk"]["status"], audit["network"]["status"]]
    if "ERROR" in statuses or "OFFLINE" in statuses:
        audit["overall_status"] = "UNHEALTHY"
    elif "WARNING" in statuses:
        audit["overall_status"] = "DEGRADED"
    else:
        audit["overall_status"] = "HEALTHY"
        
    return audit

def send_it_alert_if_unhealthy(audit: Dict[str, Any], ntfy_topic: str = None, ntfy_token: str = None):
    """Sends an automated IT notification if health checks fail."""
    if audit["overall_status"] == "HEALTHY":
        return

    topic = ntfy_topic or os.environ.get("NTFY_TOPIC", "cfr-dispatch-alerts")
    url = f"https://ntfy.sh/{topic}"
    
    title = f"⚠️ IT HEALTH ALERT: Kiosk {audit['overall_status']}"
    body = (
        f"Kiosk System Status: {audit['overall_status']}\n"
        f"🎙️ Audio Interface: {audit['audio']['status']} ({audit['audio'].get('device_name', 'N/A')})\n"
        f"💾 Disk Space: {audit['disk']['status']} ({audit['disk'].get('free_gb', 0)} GB free)\n"
        f"🌐 Network WAN: {audit['network']['status']} ({audit['network'].get('latency_ms', 'N/A')} ms)"
    )
    
    try:
        headers = {"Title": title, "Tags": "warning,computer"}
        if ntfy_token:
            headers["Authorization"] = f"Bearer {ntfy_token}"
        requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=5)
        logging.info("Automated IT Health Alert posted successfully.")
    except Exception as e:
        logging.error(f"Failed to post IT health alert: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("           CFR EVO AUTOMATED IT HEALTH WATCHDOG AUDIT")
    print("=" * 60)
    res = run_full_health_audit()
    print(f"Overall System Status: {res['overall_status']}")
    print(f"  [AUDIO] Audio Interface: {res['audio']}")
    print(f"  [DISK]  Storage Space:   {res['disk']}")
    print(f"  [NET]   Network WAN:     {res['network']}")
    print("=" * 60)
