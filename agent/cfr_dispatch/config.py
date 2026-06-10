# cfr_dispatch/config.py
# Configuration thresholds, constants, and paths for CFR Dispatch Mapping

import os
from dataclasses import dataclass
from typing import Optional

# -- Integration Settings --
STT_ENGINE = os.environ.get("STT_ENGINE", "google")  # Options: "google", "whisper"
WHISPER_MODEL = "medium"                # Options: "tiny", "base", "small", "medium"
INTEGRATION_PAYLOAD_OPTION = 2        # 1: Lightweight address, 2: Fully geocoded parcel rings
ENABLE_GOOGLE_MAPS_FALLBACK = False   # Keep offline-first by disabling fallback
ENABLE_NTFY_PUSH = True               # Free Tasker push notifications
# -- Audio Settings --
USE_INTELLIGENT_PARSER = True
AUDIO_SAMPLE_RATE = 16000
# Default audio hardware device ID (checks environment or defaults to system default None)
DEVICE_ID = int(os.environ.get("AUDIO_DEVICE_ID")) if os.environ.get("AUDIO_DEVICE_ID") is not None else None
NOISE_AMPLITUDE_THRESHOLD = 3000
NOISE_AMPLITUDE_THRESHOLD_MIN = 1500  # Keep a record of the original minimum threshold
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
MATCH_THRESHOLD_PERCENT = 0.85
FREQUENCY_TOLERANCE_HZ = 10
NUM_PEAKS_TO_FIND = 20
GOLDEN_FINGERPRINTS = {
    "Chief Tone":  [437.50, 656.25],
    "Engine Tone": [601.56, 1351.56],
    "Rescue Tone": [726.56, 890.62, 2179.69]
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

import re

# Helper function to load vocabulary files relative to this package
def load_vocabulary_file(filename: str) -> list[str]:
    package_dir = os.path.dirname(os.path.abspath(__file__))
    agent_dir = os.path.dirname(package_dir)
    filepath = os.path.join(agent_dir, "data", "vocabulary", filename)
    items = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    items.append(line)
    return items

# Dynamic Vocabulary Loading
UNITS_VOCAB_RAW = load_vocabulary_file("units_vocabulary.txt")
RESPONSE_TYPES = load_vocabulary_file("response_types.txt")
RADIO_CHANNELS = load_vocabulary_file("radio_channels.txt")
MAP_GRIDS = load_vocabulary_file("map_grid_numbers.txt")
CALL_TYPES = sorted(load_vocabulary_file("call_types.txt"), key=len, reverse=True)

# Extract base unit types dynamically from units_vocabulary.txt (e.g. "Engine 1" -> "Engine")
_types_set = set()
for _unit in UNITS_VOCAB_RAW:
    _match = re.match(r'^([a-zA-Z\s]+?)\s*\d*$', _unit)
    if _match:
        _types_set.add(_match.group(1).strip())
UNITS_VOCABULARY = sorted(list(_types_set)) if _types_set else [
    "Car", "Engine", "Hazmat", "Hazmat Tender", "Ladder", "Light Attack Vehicle", "Medic", "Quint", "Rescue", "Squad", "Tender"
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
