import os

# Core hardware config
AUDIO_SAMPLE_RATE = 16000

# Default audio hardware device ID from environment
DEVICE_ID = int(os.environ.get("AUDIO_DEVICE_ID")) if os.environ.get("AUDIO_DEVICE_ID") is not None else None
