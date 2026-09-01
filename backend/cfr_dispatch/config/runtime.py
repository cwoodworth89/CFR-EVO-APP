# Runtime settings for the local stack.
#
# Formerly config/cloud.py. Nothing in this module was ever cloud-related: the
# project runs entirely offline (CLAUDE.md s1) and the only Google dependency in
# the system is the frontend's Street View key (VITE_GOOGLE_MAPS_API_KEY).
# STT_ENGINE lived here as a "google"/"whisper" selector; it was hardcoded to
# "whisper" and never branched on, so it has been removed rather than kept as a
# setting that reads as adjustable and is not.
#
# NOTE: For integration options, payload fields, database setup, and GIS properties, see:
#   - docs/dispatch_integration_options.md
#   - docs/gis_endpoints.md  (SUPERSEDED -- GIS now comes from PostGIS via the API)
import os

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")                                # Options: "tiny", "base", "small", or custom path
INTEGRATION_PAYLOAD_OPTION = 2                        # 1: Lightweight, 2: Full parcel rings
ENABLE_NTFY_PUSH = True
VERBOSITY_LEVEL = int(os.environ.get("VERBOSITY_LEVEL", "1"))  # 0: Muted, 1: Standard, 2: Verbose, 3: Trace
