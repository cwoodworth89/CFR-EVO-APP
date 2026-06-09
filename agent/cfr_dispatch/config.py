# cfr_dispatch/config.py
# Configuration thresholds, constants, and paths for CFR Dispatch Mapping

import os
from dataclasses import dataclass
from typing import Optional

# -- Integration Settings --
STT_ENGINE = os.environ.get("STT_ENGINE", "whisper")  # Options: "google", "whisper"
WHISPER_MODEL = "base"                # Options: "tiny", "base", "small"
INTEGRATION_PAYLOAD_OPTION = 2        # 1: Lightweight address, 2: Fully geocoded parcel rings
ENABLE_GOOGLE_MAPS_FALLBACK = False   # Keep offline-first by disabling fallback
ENABLE_NTFY_PUSH = True               # Free Tasker push notifications
# -- Audio Settings --
USE_INTELLIGENT_PARSER = True
AUDIO_SAMPLE_RATE = 16000
# Default audio hardware device ID (checks environment or defaults to system default None)
DEVICE_ID = int(os.environ.get("AUDIO_DEVICE_ID")) if os.environ.get("AUDIO_DEVICE_ID") is not None else None
NOISE_AMPLITUDE_THRESHOLD = 1500
SUSTAINED_LOUDNESS_WINDOW = 5
SUSTAINED_LOUDNESS_CHUNKS_REQUIRED = 5
TONE_ANALYSIS_DURATION_SECONDS = 3.5
MAX_DISPATCH_DURATION_S = 59
END_OF_DISPATCH_SILENCE_S = 3.0
END_OF_DISPATCH_RMS_THRESHOLD = 450
POST_EVENT_RESET_SILENCE_S = 3.0
PHASE_1_CHECK_INTERVAL_S = 3.0
MIN_PHASE_1_DURATION_S = 10.0

# -- Tone Fingerprints & Matching --
MATCH_THRESHOLD_PERCENT = 0.65
FREQUENCY_TOLERANCE_HZ = 10
NUM_PEAKS_TO_FIND = 20
GOLDEN_FINGERPRINTS = {
    "Chief Tone":  [429.69, 437.50, 445.31, 656.25, 664.06],
    "Engine Tone": [593.75, 601.56, 1343.75, 1351.56],
    "Rescue Tone": [718.75, 726.56, 734.38]
}

# -- Geodata & Validation --
ADDRESS_CONFIDENCE_THRESHOLD = 95
ADDRESS_SHAPEFILE_PATH = 'data/Property_Information/Addresses.shp'
ZONES_SHAPEFILE_PATH = 'data/Emergency_Response_Zones/Emergency_Response_Zones.shp'
ADDRESS_FULL_ADDR_COLUMN = 'ADDRESS'
ADDRESS_HOUSE_NUM_COLUMN = 'HOUSE'
ADDRESS_STREET_NAME_COLUMN = 'STREET'
ADDRESS_STREET_TYPE_COLUMN = 'STREETTYPE'
ZONES_MAP_NAME_COLUMN = 'MAP_NAME'
STREET_NAME_CONFIDENCE_THRESHOLD = 80

# -- Vocabularies & Parsing --
UNITS_VOCABULARY = [
    "Car",
    "Engine",
    "Hazmat",
    "Hazmat Tender",
    "Ladder",
    "Light Attack Vehicle",
    "Medic",
    "Quint",
    "Rescue",
    "Squad",
    "Tender"
]

UNIT_PARSING_IGNORE_LIST = UNITS_VOCABULARY + [
    "Queens" # Phonetic misspelling help for address parser
]

INVALID_NEXT_WORDS = r'respond|alarm|activated|crew|group'

# --- SPEECH ADAPTATION CONFIG (GCP Specific) ---
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

@dataclass
class DispatchData:
    raw_text: str
    units: Optional[str] = None
    response_type: Optional[str] = None
    call_type: Optional[str] = None
    address: Optional[str] = None
    intersection: Optional[str] = None
    radio_channel: Optional[str] = None
    map_grid: Optional[str] = None
