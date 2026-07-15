# NOTE: For hardware specs, Raspberry Pi setup, and audio capture interfaces, see docs/hardware_specification.md
import os

# Core hardware config
AUDIO_SAMPLE_RATE = 16000

def _parse_device_id():
    val = os.environ.get("AUDIO_DEVICE_ID")
    if val is None or val.strip() == "":
        return None
    val = val.strip()
    try:
        return int(val)
    except ValueError:
        if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
            val = val[1:-1]
        return val

DEVICE_ID = _parse_device_id()
