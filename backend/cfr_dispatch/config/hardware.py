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
DEVICE_ID = _parse_device_id()

def resolve_audio_device(setting=None) -> tuple[int | None, str]:
    """
    Dynamically resolves audio input device index and device name.
    Delegates to domain audio_service.
    """
    if setting is None:
        setting = DEVICE_ID
    try:
        from audio_service import resolve_audio_device as _service_resolve
        return _service_resolve(setting)
    except Exception as e:
        return None, f"Audio Service Resolution Failed ({e})"


