# NOTE: For integration options, payload fields, database setup, and GIS properties, see:
#   - docs/dispatch_integration_options.md
#   - docs/supabase_setup.md
#   - docs/gis_endpoints.md
import os
from cfr_dispatch.config.paths import SHAPES_DIR

# Integration settings
STT_ENGINE = os.environ.get("STT_ENGINE", "whisper")  # Options: "google", "whisper"
WHISPER_MODEL = "base"                                # Options: "tiny", "base", "small"
INTEGRATION_PAYLOAD_OPTION = 2                        # 1: Lightweight, 2: Full parcel rings
ENABLE_GOOGLE_MAPS_FALLBACK = False
ENABLE_NTFY_PUSH = True
USE_INTELLIGENT_PARSER = True
VERBOSITY_LEVEL = int(os.environ.get("VERBOSITY_LEVEL", "1"))  # 0: Muted, 1: Standard, 2: Verbose, 3: Trace

# local GIS paths
ADDRESS_SHAPEFILE_PATH = str(SHAPES_DIR / "Property_Information" / "Addresses.shp")
ZONES_SHAPEFILE_PATH = str(SHAPES_DIR / "Emergency_Response_Zones" / "Emergency_Response_Zones.shp")

# local GIS columns
ADDRESS_FULL_ADDR_COLUMN = 'ADDRESS'
ADDRESS_HOUSE_NUM_COLUMN = 'HOUSE'
ADDRESS_STREET_NAME_COLUMN = 'STREET'
ADDRESS_STREET_TYPE_COLUMN = 'STREETTYPE'
ZONES_MAP_NAME_COLUMN = 'MAP_NAME'

# GIS match thresholds
ADDRESS_CONFIDENCE_THRESHOLD = 95
STREET_NAME_CONFIDENCE_THRESHOLD = 80

# GCP Speech Adaptation Configuration
GCP_PROJECT_ID = 'cfr-dispatch-mapping'
RECOGNIZER_RESOURCE_NAME = f"projects/{GCP_PROJECT_ID}/locations/global/recognizers/_"
STREET_NAMES_BASE_ID = "coquitlam-street-names"
MAP_GRIDS_ID = "map-grid-numbers"
UNITS_ID = "cfr-units"
CALL_TYPES_ID = "cfr-call-types"
CHANNELS_ID = "cfr-radio-channels"
KEYWORDS_ID = "cfr-keywords"
NUM_STREET_CHUNKS = 2

ADAPTATION_RESOURCE_IDS = [f"{STREET_NAMES_BASE_ID}-{i+1}" for i in range(NUM_STREET_CHUNKS)] + [
    MAP_GRIDS_ID, UNITS_ID, CALL_TYPES_ID, CHANNELS_ID, KEYWORDS_ID
]

BOOST_MAPPING = {
    STREET_NAMES_BASE_ID: 20,
    MAP_GRIDS_ID: 20,
    CALL_TYPES_ID: 18,
    UNITS_ID: 17,
    CHANNELS_ID: 14,
    KEYWORDS_ID: 18
}
