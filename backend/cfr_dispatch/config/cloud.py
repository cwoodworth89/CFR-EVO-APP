# NOTE: For integration options, payload fields, database setup, and GIS properties, see:
#   - docs/dispatch_integration_options.md
#   - docs/gis_endpoints.md  (SUPERSEDED -- GIS now comes from PostGIS via the API)
import os

# Integration settings
STT_ENGINE = "whisper"                                    # Locked offline model: "whisper"

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")                                # Options: "tiny", "base", "small", or custom path
INTEGRATION_PAYLOAD_OPTION = 2                        # 1: Lightweight, 2: Full parcel rings
ENABLE_NTFY_PUSH = True
VERBOSITY_LEVEL = int(os.environ.get("VERBOSITY_LEVEL", "1"))  # 0: Muted, 1: Standard, 2: Verbose, 3: Trace
