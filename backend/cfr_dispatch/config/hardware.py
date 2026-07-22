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
    Supports integer indexes, string substring matches (e.g., 'USB Audio CODEC'),
    and falls back to system default input device.
    """
    if setting is None:
        setting = DEVICE_ID

    try:
        import sounddevice as sd
        devices = sd.query_devices()
    except Exception as e:
        return None, f"SoundDevice Query Failed ({e})"

    # If setting is an integer index
    if isinstance(setting, int):
        if 0 <= setting < len(devices):
            dev = devices[setting]
            if dev.get('max_input_channels', 0) > 0:
                return setting, dev.get('name', f'Device {setting}')
        # Fall through if integer index invalid/has no inputs

    # If setting is a string substring
    if isinstance(setting, str) and setting.strip():
        search_term = setting.strip().lower()
        for idx, dev in enumerate(devices):
            if dev.get('max_input_channels', 0) > 0 and search_term in dev.get('name', '').lower():
                return idx, dev.get('name')

    # Fallback to system default input device
    try:
        import sounddevice as sd
        default_idx = sd.default.device[0]
        if default_idx is not None and 0 <= default_idx < len(devices):
            return default_idx, devices[default_idx].get('name', f'Default ({default_idx})')
    except Exception:
        pass

    return None, "Default Input Device"

