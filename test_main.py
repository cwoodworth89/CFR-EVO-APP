# ==============================================================================
# cfr-dispatch-mapping
# DEFINITIVE SCRIPT V37.0 (FINALIZED ADAPTATION & SANITIZATION)
# ==============================================================================

# --- Core Python Libraries ---
import os
import re
import time
import threading
import logging
import uuid
import datetime
import json
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple

# --- Installed Libraries ---
import wavio
import googlemaps
import requests
import sounddevice as sd
import numpy as np
from scipy import signal
from google.cloud import speech_v2
from thefuzz import fuzz
from word2number import w2n
import geopandas as gpd
from shapely.geometry import Point
import regex as re

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================
# -- Integration Settings --
STT_ENGINE = "whisper"                # Options: "google", "whisper"
WHISPER_MODEL = "base"                # Options: "tiny", "base", "small"
INTEGRATION_PAYLOAD_OPTION = 2        # 1: Lightweight address, 2: Fully geocoded parcel rings
ENABLE_GOOGLE_MAPS_FALLBACK = False   # Keep offline-first by disabling fallback
ENABLE_NTFY_PUSH = True               # Free Tasker push notifications
ENABLE_JOIN_PUSH = False              # Legacy push notifications

# -- Audio Settings --
USE_INTELLIGENT_PARSER = True; AUDIO_SAMPLE_RATE = 16000; DEVICE_ID = 2
NOISE_AMPLITUDE_THRESHOLD = 1500; SUSTAINED_LOUDNESS_WINDOW = 5
SUSTAINED_LOUDNESS_CHUNKS_REQUIRED = 5; TONE_ANALYSIS_DURATION_SECONDS = 3.5
MAX_DISPATCH_DURATION_S = 59; END_OF_DISPATCH_SILENCE_S = 3.0
END_OF_DISPATCH_RMS_THRESHOLD = 450; POST_EVENT_RESET_SILENCE_S = 3.0

# -- Tone Fingerprints & Matching --
MATCH_THRESHOLD_PERCENT = 0.65; FREQUENCY_TOLERANCE_HZ = 10; NUM_PEAKS_TO_FIND = 20
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
# -- Vocabularies & Parsing --
# This is the CANONICAL list of official unit names. It's our source of truth.
# In main.py, in the --- CONFIGURATION --- section

# -- Vocabularies & Parsing --
# This is the CANONICAL list of official unit types. It's our source of truth
# for parsing, derived from the specific apparatus data.
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

# This is a list used ONLY to help the address parser. It contains all official
# units PLUS any common speech-to-text misspellings (e.g., "Quint" -> "Queens").
UNIT_PARSING_IGNORE_LIST = UNITS_VOCABULARY + [
    "Queens" # Add other phonetic misspellings here as you discover them
]

INVALID_NEXT_WORDS = r'respond|alarm|activated|crew|group'

# --- SPEECH ADAPTATION CONFIG ---
GCP_PROJECT_ID = 'cfr-dispatch-mapping'
RECOGNIZER_RESOURCE_NAME = f"projects/{GCP_PROJECT_ID}/locations/global/recognizers/_"

# -- Define all our Custom Class IDs --
STREET_NAMES_BASE_ID = "coquitlam-street-names"
MAP_GRIDS_ID = "map-grid-numbers"
UNITS_ID = "cfr-units"
CALL_TYPES_ID = "cfr-call-types"
CHANNELS_ID = "cfr-radio-channels"
KEYWORDS_ID = "cfr-keywords"
NUM_STREET_CHUNKS = 2

# -- Generate the full list of resource IDs to use --
ADAPTATION_RESOURCE_IDS = [f"{STREET_NAMES_BASE_ID}-{i+1}" for i in range(NUM_STREET_CHUNKS)] + [
    MAP_GRIDS_ID, UNITS_ID, CALL_TYPES_ID, CHANNELS_ID, KEYWORDS_ID
]

# -- Adaptation Boost Configuration --
# This dictionary controls how strongly we bias the speech-to-text engine
# towards recognizing phrases from our custom vocabulary lists.
#
# RANGE: The boost value is a positive floating point number. The API enforces a
#        hard maximum limit of 20.0. A value of 0 provides no boost.
#
# HOW IT WORKS: A value of 20 means the phrases in that class are about 20 times
# more likely to be chosen than a generic word that sounds similar. The effect is
# relative; a class with a boost of 20 is still more preferred than a class with
# a boost of 15.
#
# RECOMMENDED STARTING VALUES (scaled to the 0-20 range):
# - Critical, must-be-correct info (Addresses): 18-20
# - High-priority info (Call Types, Units): 15-18
# - Medium-priority info (Channels, Keywords): 10-15
BOOST_MAPPING = {
    STREET_NAMES_BASE_ID: 20,   # Max boost for critical address info
    MAP_GRIDS_ID: 20,           # Max boost for critical address info
    CALL_TYPES_ID: 18,          # High priority
    UNITS_ID: 17,               # High priority
    CHANNELS_ID: 14,            # Medium priority
    KEYWORDS_ID: 18             # Lower priority, but still boosted
}

# ==============================================================================
# --- DATA STRUCTURES & LOGGING ---
# ==============================================================================
@dataclass
class DispatchData:
    raw_text: str; units: Optional[str] = None; response_type: Optional[str] = None; call_type: Optional[str] = None; address: Optional[str] = None; intersection: Optional[str] = None; radio_channel: Optional[str] = None; map_grid: Optional[str] = None

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    if logger.hasHandlers(): logger.handlers.clear()
    file_handler = logging.FileHandler('dispatch.log', mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(threadName)s - %(funcName)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

# ==============================================================================
# --- COQUITLAM DATA VALIDATOR CLASS ---
# ==============================================================================
class CoquitlamDataValidator:
    def __init__(self, address_shp_path, zones_shp_path):
        self.addresses_gdf, self.zones_gdf, self.zones_crs = None, None, None
        self.zones_sindex = None
        self._load_data(address_shp_path, zones_shp_path)
    def _load_data(self, address_shp_path, zones_shp_path):
        try:
            logging.info(f"Loading Coquitlam address data from: {address_shp_path} (using pyogrio engine)")
            self.addresses_gdf = gpd.read_file(address_shp_path, engine="pyogrio")
            self.addresses_gdf[ADDRESS_HOUSE_NUM_COLUMN] = self.addresses_gdf[ADDRESS_HOUSE_NUM_COLUMN].astype(str).str.strip()
            self.addresses_gdf[ADDRESS_STREET_NAME_COLUMN] = self.addresses_gdf[ADDRESS_STREET_NAME_COLUMN].astype(str).str.strip()
            self.addresses_gdf[ADDRESS_STREET_TYPE_COLUMN] = self.addresses_gdf[ADDRESS_STREET_TYPE_COLUMN].astype(str).str.strip()
            logging.info(f"Successfully loaded and indexed {len(self.addresses_gdf)} Coquitlam addresses.")
        except Exception as e: logging.error(f"FATAL: Could not load or process Coquitlam address Shapefile. Error: {e}"); self.addresses_gdf = None
        try:
            logging.info(f"Loading Coquitlam emergency zones from: {zones_shp_path} (using pyogrio engine)")
            self.zones_gdf = gpd.read_file(zones_shp_path, engine="pyogrio")
            self.zones_crs = self.zones_gdf.crs
            logging.info("Building spatial index for emergency zones...")
            self.zones_sindex = self.zones_gdf.sindex
            logging.info(f"Successfully loaded {len(self.zones_gdf)} Coquitlam emergency zones.")
        except Exception as e: logging.error(f"FATAL: Could not load Coquitlam emergency zones Shapefile. Error: {e}"); self.zones_gdf = None
    def validate_address_exists(self, parsed_address: str) -> tuple[int, str | None]:
        if self.addresses_gdf is None or not parsed_address: return 0, None
        if " and " in parsed_address.lower() and not re.match(r'^\d+', parsed_address): return 100, parsed_address
        match = re.search(r'^(?P<number>\d+)\s+(?P<street>.*)', parsed_address.split(',')[0].strip())
        if not match: return 0, None
        parsed_num, parsed_street = match.group('number'), match.group('street').upper()
        possible_matches = self.addresses_gdf[self.addresses_gdf[ADDRESS_HOUSE_NUM_COLUMN] == parsed_num]
        if possible_matches.empty: return 0, None
        best_score, best_match_full_address = 0, None
        for _, row in possible_matches.iterrows():
            db_full_street = f"{row[ADDRESS_STREET_NAME_COLUMN]} {row[ADDRESS_STREET_TYPE_COLUMN]}".upper()
            score = fuzz.token_set_ratio(parsed_street, db_full_street.strip())
            if score > best_score: best_score, best_match_full_address = score, row[ADDRESS_FULL_ADDR_COLUMN]
        logging.debug(f"Surgical validation for '{parsed_address}': Best street name match score = {best_score}%")
        if best_score >= STREET_NAME_CONFIDENCE_THRESHOLD: return best_score, best_match_full_address
        return best_score, None
    def local_geocode(self, parsed_address: str) -> dict | None:
        if self.addresses_gdf is None or not parsed_address: return None
        if " and " in parsed_address.lower() and not re.match(r'^\d+', parsed_address):
            return None
        match = re.search(r'^(?P<number>\d+)\s+(?P<street>.*)', parsed_address.split(',')[0].strip())
        if not match: return None
        parsed_num, parsed_street_raw = match.group('number'), match.group('street').strip()
        
        # Normalize parsed street type to match database abbreviations
        words = parsed_street_raw.split()
        if len(words) >= 1:
            street_type_raw = words[-1]
            street_name_raw = " ".join(words[:-1])
            
            type_mapping = {
                "crescent": "cres", "highway": "hwy", "street": "st",
                "avenue": "ave", "court": "crt", "place": "pl",
                "drive": "dr", "boulevard": "blvd", "lane": "ln", "road": "rd"
            }
            norm_type = type_mapping.get(street_type_raw.lower(), street_type_raw).upper()
            parsed_street = f"{street_name_raw} {norm_type}".upper().strip()
        else:
            parsed_street = parsed_street_raw.upper().strip()
            
        possible_matches = self.addresses_gdf[self.addresses_gdf[ADDRESS_HOUSE_NUM_COLUMN] == parsed_num]
        if possible_matches.empty: return None
        best_score, best_row = 0, None
        for _, row in possible_matches.iterrows():
            db_full_street = f"{row[ADDRESS_STREET_NAME_COLUMN]} {row[ADDRESS_STREET_TYPE_COLUMN]}".upper().strip()
            score = fuzz.token_set_ratio(parsed_street, db_full_street)
            if score > best_score:
                best_score = score
                best_row = row
        if best_score >= STREET_NAME_CONFIDENCE_THRESHOLD and best_row is not None:
            try:
                geom_gdf = gpd.GeoDataFrame([best_row], crs=self.addresses_gdf.crs)
                geom_gdf_wgs84 = geom_gdf.to_crs("EPSG:4326")
                matched_geom = geom_gdf_wgs84.geometry.iloc[0]
                centroid = matched_geom.centroid
                
                rings = []
                def extract_rings(geometry) -> list:
                    r = []
                    if geometry.geom_type == 'Polygon':
                        exterior = [[coord[0], coord[1]] for coord in geometry.exterior.coords]
                        r.append(exterior)
                        for interior in geometry.interiors:
                            r.append([[coord[0], coord[1]] for coord in interior.coords])
                    elif geometry.geom_type == 'MultiPolygon':
                        for polygon in geometry.geoms:
                            r.extend(extract_rings(polygon))
                    return r
                
                rings = extract_rings(matched_geom)
                return {
                    "address": best_row[ADDRESS_FULL_ADDR_COLUMN],
                    "lat": centroid.y,
                    "lng": centroid.x,
                    "rings": rings,
                    "confidence": best_score
                }
            except Exception as e:
                logging.error(f"Error transforming coordinates for local geocode: {e}", exc_info=True)
                return None
        return None
    def validate_point_in_grid(self, lat: float, lon: float, grid_id: str) -> bool:
        if self.zones_gdf is None or self.zones_sindex is None or not grid_id: return False
        try:
            point = Point(lon, lat)
            point_gdf = gpd.GeoDataFrame([{'geometry': point}], crs="EPSG:4326").to_crs(self.zones_crs)
            point_geom = point_gdf.geometry.iloc[0]
            possible_matches_idx = list(self.zones_sindex.intersection(point_geom.bounds))
            possible_matches = self.zones_gdf.iloc[possible_matches_idx]
            target_zone = possible_matches[possible_matches[ZONES_MAP_NAME_COLUMN] == grid_id]
            if target_zone.empty: return False
            return target_zone.geometry.contains(point_geom).any()
        except Exception as e: logging.error(f"Point-in-grid validation error: {e}", exc_info=True); return False

# ==============================================================================
# --- HELPER FUNCTIONS & PARSERS ---
# ==============================================================================
def get_rms(data: np.ndarray) -> float:
    return np.sqrt(np.mean(data.astype(np.float32)**2)) if data.size > 0 else 0

def sanitize_transcript(text: str) -> str:
    """
    Cleans a transcript by:
    1. Converting it to lowercase.
    2. Replacing number words (one, two) with digits (1, 2) for consistency.
    3. Removing all punctuation except spaces.
    4. Normalizing whitespace to single spaces.
    """
    text = text.lower()

    number_words = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
        'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
        'eighteen': '18', 'nineteen': '19', 'twenty': '20'
    }

    # Use regex with word boundaries (\b) to replace whole words only
    pattern = r'\b(' + '|'.join(number_words.keys()) + r')\b'
    text = re.sub(pattern, lambda m: number_words[m.group(0)], text)

    # Remove all remaining non-alphanumeric characters (except spaces)
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    # Normalize multiple spaces down to a single space
    return ' '.join(text.split())

def load_call_types(filepath="call_types.txt") -> list:
    call_types = []
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        call_types.append(line)
            logging.info(f"Loaded {len(call_types)} call types from '{filepath}'")
        except Exception as e:
            logging.error(f"Error loading call types from '{filepath}': {e}")
    else:
        logging.warning(f"'{filepath}' not found. Fuzzy incident type matching will be limited.")
    # Sort by length descending so longer/more specific phrases match first
    return sorted(call_types, key=len, reverse=True)

CALL_TYPES = load_call_types()


def match_incident_type(transcript: str, call_types: list) -> str:
    # 1. Look for exact substring matches (case-insensitive)
    for ct in call_types:
        if ct.lower() in transcript:
            return ct
            
    # 2. Look for best fuzzy match
    best_match = None
    best_score = 0
    for ct in call_types:
        score = fuzz.token_set_ratio(ct.lower(), transcript)
        if score > best_score:
            best_score = score
            best_match = ct
            
    if best_score >= 80:
        return best_match
        
    return "Unknown Incident"

def parse_alarm_level(transcript: str) -> int:
    # Search for keywords
    if "first alarm" in transcript or "1st alarm" in transcript or "alarm level 1" in transcript:
        return 1
    if "second alarm" in transcript or "2nd alarm" in transcript or "alarm level 2" in transcript:
        return 2
    if "third alarm" in transcript or "3rd alarm" in transcript or "alarm level 3" in transcript:
        return 3
    # Look for generic "alarm level X"
    match = re.search(r'alarm\s+level\s+(\d+)', transcript)
    if match:
        return int(match.group(1))
    return 1

def abbreviate_units(units_str: str) -> list:
    if not units_str:
        return []
    # Map unit types to letters
    mapping = {
        "engine": "E",
        "ladder": "L",
        "rescue": "R",
        "car": "C",
        "squad": "S",
        "medic": "M",
        "quint": "Q",
        "tender": "T",
        "hazmat": "H",
        "light attack vehicle": "LAV"
    }
    found_units = []
    # Find all matches of word followed by digits/hyphens
    matches = re.findall(r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat|light attack vehicle)\s+([\w\d-]+)\b', units_str.lower())
    for unit_type, unit_num in matches:
        abbr = mapping.get(unit_type, unit_type.capitalize())
        found_units.append(f"{abbr}{unit_num.upper()}")
    return found_units

def post_to_supabase(payload: dict, url: str, key: str) -> bool:
    if not url or not key:
        logging.warning("Supabase URL or Key not set. Skipping push.")
        return False
    
    endpoint = f"{url.rstrip('/')}/rest/v1/live_calls"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        logging.info(f"Posting dispatch payload to Supabase ({endpoint})...")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Successfully posted to Supabase.")
        return True
    except Exception as e:
        logging.error(f"Failed to post to Supabase: {e}", exc_info=True)
        return False

def post_to_ntfy(payload: dict, topic: str, token: str = None) -> bool:
    if not topic:
        logging.warning("Ntfy topic not set. Skipping push.")
        return False
        
    endpoint = f"https://ntfy.sh/{topic}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    try:
        # Custom Ntfy notification parameters for high-priority Tasker wake-up
        headers["Title"] = f"Dispatch: {payload.get('incident_type', 'Structure Fire')}"
        headers["Priority"] = "5"
        headers["Tags"] = "fire_engine,rotating_light"
        
        # Pull coordinates to enable native click-to-navigate action
        lat = payload.get("lat")
        lng = payload.get("lng")
        if not lat or not lng:
            target = payload.get("target", {})
            lat = target.get("lat")
            lng = target.get("lng")
            
        if lat and lng:
            headers["Click"] = f"google.navigation:q={lat},{lng}"
            
        logging.info(f"Posting dispatch payload to ntfy.sh topic '{topic}'...")
        response = requests.post(endpoint, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        logging.info("Successfully posted to Ntfy.")
        return True
    except Exception as e:
        logging.error(f"Failed to post to Ntfy: {e}", exc_info=True)
        return False

def transcribe_audio_file_local(file_path: str) -> str | None:
    try:
        import whisper
        logging.info("Loading local Whisper model...")
        model = whisper.load_model(WHISPER_MODEL)
        logging.info(f"Transcribing '{file_path}' using local Whisper...")
        result = model.transcribe(file_path, language="en")
        return result.get("text", "").strip() or None
    except ImportError:
        logging.error("openai-whisper library not installed. Please run 'pip install openai-whisper' to use local transcription.")
        return None
    except Exception as e:
        logging.error(f"Local transcription error: {e}", exc_info=True)
        return None

def analyze_live_audio(data: bytes, num_peaks=NUM_PEAKS_TO_FIND) -> set:
    audio_array = np.frombuffer(data, dtype=np.int16)
    if len(audio_array) == 0: return set()
    cutoff_hz=300.0; nyquist_freq=0.5*AUDIO_SAMPLE_RATE; normal_cutoff=cutoff_hz/nyquist_freq
    b, a = signal.butter(5, normal_cutoff, btype='high', analog=False)
    filtered_signal = signal.lfilter(b, a, audio_array)
    fft_data = np.fft.rfft(filtered_signal); fft_freqs = np.fft.rfftfreq(len(filtered_signal), 1.0/AUDIO_SAMPLE_RATE)
    fft_magnitude = np.abs(fft_data)
    try:
        peak_indices = np.argpartition(fft_magnitude, -num_peaks)[-num_peaks:]
        return set(int(f) for f in fft_freqs[peak_indices])
    except (ValueError, IndexError): return set()

def get_best_match(live_frequencies: set) -> tuple | tuple[None, None]:
    best_match_tone, best_match_score = None, -1
    for tone_name, golden_freqs in GOLDEN_FINGERPRINTS.items():
        matches_found = sum(1 for gf in golden_freqs if any(abs(lf - gf) <= FREQUENCY_TOLERANCE_HZ for lf in live_frequencies))
        score = matches_found / len(golden_freqs) if golden_freqs else 0
        if score > best_match_score: best_match_score, best_match_tone = score, tone_name
    if best_match_score >= MATCH_THRESHOLD_PERCENT: return best_match_tone, best_match_score
    return None, None

def filter_known_tones(audio_data: np.ndarray, tone_name: str, sample_rate: int) -> np.ndarray:
    if not tone_name or tone_name not in GOLDEN_FINGERPRINTS: return audio_data
    tone_frequencies = GOLDEN_FINGERPRINTS[tone_name]
    logging.info(f"Applying notch filters for '{tone_name}' at freqs: {tone_frequencies}")
    filtered_audio = audio_data.copy()
    for freq in tone_frequencies:
        b, a = signal.iirnotch(freq, 50.0, fs=sample_rate)
        filtered_audio = signal.lfilter(b, a, filtered_audio)
    return filtered_audio.astype(np.int16)

def normalize_street_suffix(text: str) -> str:
    type_mapping = {
        "crescent": "Cres", "cres": "Cres",
        "highway": "Hwy", "hwy": "Hwy",
        "street": "St", "st": "St",
        "avenue": "Ave", "ave": "Ave",
        "court": "Crt", "crt": "Crt",
        "place": "Pl", "pl": "Pl",
        "drive": "Dr", "dr": "Dr",
        "boulevard": "Blvd", "blvd": "Blvd",
        "lane": "Ln", "ln": "Ln",
        "road": "Rd", "rd": "Rd"
    }
    words = text.split()
    if not words:
        return text
    last_word = words[-1].lower()
    if last_word in type_mapping:
        words[-1] = type_mapping[last_word]
    else:
        words[-1] = words[-1].capitalize()
        
    for i in range(len(words) - 1):
        words[i] = words[i].capitalize()
    return " ".join(words)

def clean_location_text(text: str, call_types: list, units_vocab: list) -> str:
    """
    Cleans a parsed location string (address or intersection) by recursively stripping
    leading prepositions, incident types, units, and action/dispatch keywords.
    """
    text = ' '.join(text.split()).strip()
    if not text:
        return ""
    
    prepositions = {"at", "near", "on", "for", "in", "to", "and"}
    action_words = {"respond", "routine", "emergency", "alarm", "activated", "level", "map", "grid"}
    
    call_type_phrases = []
    if call_types:
        for ct in call_types:
            ct_clean = re.sub(r'[^a-z0-9\s]', '', ct.lower()).strip()
            if ct_clean:
                call_type_phrases.append(ct_clean)
            
    incident_words = {"fire", "medical", "rescue", "accident", "crash", "leak", "assist", "arrest", "mvi"}
    
    unit_words = set(u.lower() for u in units_vocab) if units_vocab else set()
    unit_words.update({"engine", "ladder", "squad", "medic", "rescue", "tender", "hazmat", "quint", "car", "command"})

    changed = True
    while changed:
        changed = False
        lower_text = text.lower()
        words = lower_text.split()
        if not words:
            break
            
        first_word = words[0]
        if first_word in prepositions or first_word in action_words or first_word in unit_words:
            text = text[len(first_word):].strip()
            changed = True
            continue
            
        if first_word.isdigit():
            if len(words) > 1 and (words[1] in action_words or words[1] in prepositions or words[1] in unit_words):
                text = text[len(first_word):].strip()
                changed = True
                continue
        
        for phrase in sorted(call_type_phrases, key=len, reverse=True):
            if lower_text.startswith(phrase):
                phrase_len = len(phrase)
                if phrase_len == len(text) or text[phrase_len].isspace():
                    text = text[phrase_len:].strip()
                    changed = True
                    break
        if changed:
            continue
            
        if first_word in incident_words:
            text = text[len(first_word):].strip()
            changed = True
            continue

    return text

def parse_dispatch_announcement(announcement_text: str, units_vocab: list) -> List[DispatchData]:
    text = announcement_text.strip()
    street_types = r"street|avenue|drive|way|road|crescent|boulevard|place|court|highway|lane"
    
    unit_lookbehind = '|'.join(UNIT_PARSING_IGNORE_LIST)
    
    # --- STABLE REGEX ---
    # Matches house numbers consisting of digits, spaces, or hyphens (avoiding arbitrary words)
    address_pattern = re.compile(
        fr"(?<!\b(?:{unit_lookbehind})s?\s\d+\s)" 
        fr"(?P<number_phrase>(?:\d+[\s-]*)+)\s+" 
        fr"(?P<street_name>(?:[a-zA-Z'-]+\s+){{0,4}}?)"
        fr"(?P<street_type>{street_types})"
        fr"(?! \s* (?:{INVALID_NEXT_WORDS}))",
        re.IGNORECASE | re.VERBOSE
    )
    
    address_matches = list(address_pattern.finditer(text))
    intersection_pattern = re.compile(fr"((?:[\w'-]+\s+){{0,4}}?(?:{street_types}))\s+and\s+((?:[\w'-]+\s+){{0,4}}?(?:{street_types}))", re.IGNORECASE)
    intersection_match = intersection_pattern.search(text)
    
    found_dispatches = []
    if address_matches:
        for match in address_matches:
            # --- TWO-STAGE NUMBER PARSING ---
            number_phrase = match.group('number_phrase').strip()
            cleaned_number = None
            
            # Stage 1: Try to convert using the intelligent word_to_num library
            try:
                # This handles complex cases like "one twenty" or "nine-ninety"
                cleaned_number = str(w2n.word_to_num(number_phrase))
                logging.debug(f"Successfully parsed number phrase '{number_phrase}' with word2number -> {cleaned_number}")
            except ValueError:
                # Stage 2: If word_to_num fails, fall back to just joining the digits
                # This handles the digit-by-digit case like "1 2 0"
                digits_only = "".join(filter(str.isdigit, number_phrase))
                if digits_only:
                    cleaned_number = digits_only
                    logging.debug(f"word2number failed for '{number_phrase}', fell back to digit joining -> {cleaned_number}")

            if not cleaned_number:
                logging.warning(f"Could not parse a valid number from phrase: '{number_phrase}'. Skipping candidate.")
                continue

            raw_street = f"{match.group('street_name').strip()} {match.group('street_type')}"
            cleaned_street = clean_location_text(raw_street, CALL_TYPES, units_vocab)
            normalized_street = normalize_street_suffix(cleaned_street)
            
            if normalized_street:
                address_str = f"{cleaned_number} {normalized_street}"
                found_dispatches.append(DispatchData(raw_text=text, address=address_str))
    
    if not found_dispatches and intersection_match:
        leg1 = clean_location_text(intersection_match.group(1), CALL_TYPES, units_vocab)
        leg2 = clean_location_text(intersection_match.group(2), CALL_TYPES, units_vocab)
        normalized_leg1 = normalize_street_suffix(leg1)
        normalized_leg2 = normalize_street_suffix(leg2)
        if normalized_leg1 and normalized_leg2:
            intersection_str = f"{normalized_leg1} and {normalized_leg2}"
            found_dispatches.append(DispatchData(raw_text=text, intersection=intersection_str))
    
    if not found_dispatches: 
        return []


    # The rest of the function is unchanged
    units_pattern = re.compile(r'^(?P<units>(?:(?:' + '|'.join(units_vocab) + r')\s+[\w\d-]+[,\s]*)+)', re.IGNORECASE)
    response_pattern = re.compile(r'\brespond\s*(?P<type>routine|emergency)\b', re.IGNORECASE)
    map_grid_pattern = re.compile(r'\b(?:map grid|math grade|math grid)\s*(\d{1,3})\b', re.IGNORECASE)
    final_grid_pattern = re.compile(r'coquitlam\s*(\d{1,3})\b', re.IGNORECASE)
    
    units_str = (units_pattern.search(text).group('units').strip() if units_pattern.search(text) else None)
    response_str = (response_pattern.search(text).group('type').strip() if response_pattern.search(text) else None)
    
    parsed_grids = map_grid_pattern.findall(text)
    final_grid_matches = final_grid_pattern.findall(text)
    if final_grid_matches: 
        parsed_grids.extend(final_grid_matches)
    grid_str = parsed_grids[0] if parsed_grids else None
    
    for dispatch in found_dispatches:
        dispatch.units, dispatch.response_type, dispatch.map_grid = units_str, response_str, grid_str
        
    return found_dispatches

def transcribe_audio_file(file_path: str) -> str | None:
    """Transcribes audio using Speech-to-Text v2 with a globally configured adaptation model."""
    try:
        client = speech_v2.SpeechClient()

        # Build the list of phrases to boost based on the global BOOST_MAPPING
        phrases_to_boost = []
        for resource_id in ADAPTATION_RESOURCE_IDS:
            # Find the base ID (e.g., "cfr-units") to look up its boost value
            base_id = next((key for key in BOOST_MAPPING if resource_id.startswith(key)), None)
            boost_value = BOOST_MAPPING.get(base_id, 10) # Default to 10 if a mapping isn't found
            
            full_resource_name = f"projects/{GCP_PROJECT_ID}/locations/global/customClasses/{resource_id}"
            phrases_to_boost.append({"value": f"${full_resource_name}", "boost": boost_value})

        # Construct the adaptation object using the required dictionary format
        inline_set = speech_v2.types.PhraseSet(phrases=phrases_to_boost)
        adaptation_phrase_set_dict = {"inline_phrase_set": inline_set}
        adaptation_config = speech_v2.SpeechAdaptation(
            phrase_sets=[adaptation_phrase_set_dict]
        )
        
        # Configure the recognition request
        config = speech_v2.RecognitionConfig(
            auto_decoding_config={},
            language_codes=["en-CA"],
            model="long",
            features=speech_v2.RecognitionFeatures(
                enable_automatic_punctuation=True,
            ),
            adaptation=adaptation_config
        )

        with open(file_path, "rb") as audio_file:
            content = audio_file.read()
        
        request = speech_v2.types.RecognizeRequest(
            recognizer=RECOGNIZER_RESOURCE_NAME,
            config=config,
            content=content,
        )
        
        logging.info(f"Sending V2 transcription request with boosted phrases: {phrases_to_boost}")
        response = client.recognize(request=request)

        if not response or not response.results:
            logging.warning("Transcription returned no results.")
            return None
        
        # Safely join transcripts, only from results that have alternatives
        transcripts = [
            result.alternatives[0].transcript 
            for result in response.results 
            if result.alternatives
        ]
        
        return " ".join(transcripts).strip() or None

    except Exception as e:
        logging.error(f"Transcription API error: {e}", exc_info=True)
        return None

def geocode_address(address: str, gmaps_api_key: str) -> Tuple[dict | None, str | None]:
    gmaps = googlemaps.Client(key=gmaps_api_key)
    try:
        full_query_address = f"{address}, Coquitlam, BC"
        geocode_result = gmaps.geocode(full_query_address)
        if not geocode_result: logging.warning(f"Could not find a location for '{full_query_address}'"); return None, None
        first_result = geocode_result[0]
        formatted_address = first_result.get('formatted_address')
        logging.info(f"Google Found: {formatted_address}")
        is_numbered_query = re.match(r'^\d+', address)
        has_street_number = any(comp['types'][0] == 'street_number' for comp in first_result.get('address_components', []))
        if is_numbered_query and not has_street_number:
            logging.warning(f"IMPRECISE RESULT: Query for '{address}' returned a result without a street number. Rejecting.")
            return None, None
        return first_result, formatted_address
    except Exception as e: logging.error(f"Geocoding API error: {e}", exc_info=True); return None, None

def launch_navigation_on_phone(location_coords: dict, address_label: str, join_api_key: str):
    latitude, longitude = location_coords['lat'], location_coords['lng']
    label = address_label.split(',')[0]
    text_payload = f"dispatch=:={latitude}|||{longitude}|||{label}"
    base_url = "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush"
    params = {'apikey': join_api_key, 'deviceId': 'group.phone', 'text': text_payload}
    logging.info(f"Preparing to send payload: {text_payload}")
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        logging.info("Join message sent successfully.")
    except requests.exceptions.RequestException as e: logging.error(f"Join API error: {e}", exc_info=True)

def capture_full_dispatch(stream, blocksize, initial_buffer=None):
    logging.info("STATE: CAPTURING DISPATCH")
    audio_buffer = initial_buffer if initial_buffer is not None else []
    max_chunks = int((AUDIO_SAMPLE_RATE / blocksize) * MAX_DISPATCH_DURATION_S)
    start_chunk = len(audio_buffer)
    silence_start_time = None
    for i in range(start_chunk, max_chunks):
        try:
            pcm, _ = stream.read(blocksize)
            audio_buffer.append(pcm)
            volume = get_rms(pcm)
            if volume < END_OF_DISPATCH_RMS_THRESHOLD:
                if silence_start_time is None: silence_start_time = time.time()
                elif time.time() - silence_start_time >= END_OF_DISPATCH_SILENCE_S:
                    logging.info(f"END OF DISPATCH DETECTED by {END_OF_DISPATCH_SILENCE_S}s of silence."); return audio_buffer
            else: silence_start_time = None
        except Exception as e: logging.error(f"Audio stream read error: {e}", exc_info=True); break
    logging.info(f"MAX DURATION ({MAX_DISPATCH_DURATION_S}s) REACHED."); return audio_buffer

def process_full_dispatch(buffer, validator: CoquitlamDataValidator, tone_name: str, units_vocabulary: list):
    dispatch_id = f"DISP-{time.strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
    temp_filename = f"temp_dispatch_{dispatch_id}.wav"
    
    try:
        logging.info(f"--- STARTING DISPATCH PROCESSING (ID: {dispatch_id}) ---")
        if not buffer:
            logging.warning("Buffer empty, nothing to process.")
            return
            
        # 1. Combine and Filter Audio
        full_dispatch_audio = np.concatenate(buffer)
        filtered_audio = filter_known_tones(full_dispatch_audio, tone_name, AUDIO_SAMPLE_RATE)
        
        # 2. Write to Unique Temp File
        wavio.write(temp_filename, filtered_audio, AUDIO_SAMPLE_RATE, sampwidth=2)
        logging.info(f"Dispatch audio saved to unique file '{temp_filename}'.")
        
        # 3. Transcribe Audio (Google vs local Whisper)
        raw_transcript = None
        if STT_ENGINE == "google":
            raw_transcript = transcribe_audio_file(temp_filename)
        elif STT_ENGINE == "whisper":
            raw_transcript = transcribe_audio_file_local(temp_filename)
            
        if not raw_transcript:
            logging.error("Transcription failed.")
            return
            
        logging.info(f"Original Transcript: '{raw_transcript}'")
        transcript = sanitize_transcript(raw_transcript)
        logging.info(f"Sanitized Transcript: '{transcript}'")
        
        # 4. Parse announcements
        announcements = re.split(r'\bcoquitlam\b', transcript, flags=re.IGNORECASE)
        all_candidates = []
        for text in announcements:
            if len(text.split()) > 2:
                all_candidates.extend(parse_dispatch_announcement(text, units_vocabulary))
                
        unique_addresses = []
        for d in all_candidates:
            if d.address and d.address not in unique_addresses:
                unique_addresses.append(d.address)
            if d.intersection and d.intersection not in unique_addresses:
                unique_addresses.append(d.intersection)
                
        # Parse Call Type (Incident Type) and Alarm Level early so we can verify if a dispatch actually occurred
        incident_type = match_incident_type(transcript, CALL_TYPES)
        alarm_level = parse_alarm_level(transcript)
        units_str = next((d.units for d in all_candidates if d.units), None)
        responding_units = abbreviate_units(units_str)

        # Check for specific placeholder phrase in transcript
        is_specific_placeholder = "contact dispatch" in transcript or "location information" in transcript
        
        if is_specific_placeholder:
            unique_addresses = ["Contact dispatch for location information"]
        
        if not unique_addresses:
            # Check if this was a valid call (e.g. units were dispatched)
            if responding_units or incident_type != "Unknown Incident":
                logging.warning("No address or intersection parsed, but dispatch details found. Using 'Unknown Location' fallback.")
                unique_addresses = ["Unknown Location"]
            else:
                logging.error("Could not parse any address or intersection from transcript, and no dispatch details found. Aborting.")
                return
            
        # 5. Geocode Local-First (100% Offline)
        local_geocode_result = None
        verify_location = False
        confidence_score = 0.0
        
        first_candidate = unique_addresses[0] if unique_addresses else "Unknown Location"
        
        if first_candidate == "Contact dispatch for location information":
            local_geocode_result = {
                "address": first_candidate,
                "lat": None,
                "lng": None,
                "rings": []
            }
            confidence_score = 100.0
            verify_location = False
        elif first_candidate == "Unknown Location":
            local_geocode_result = {
                "address": first_candidate,
                "lat": None,
                "lng": None,
                "rings": []
            }
            confidence_score = 0.0
            verify_location = True
        else:
            for i, candidate_address in enumerate(unique_addresses):
                logging.info(f"Attempting Local Geocode for Candidate #{i+1}: '{candidate_address}'")
                res = validator.local_geocode(candidate_address)
                if res:
                    logging.info(f"[Local GIS Check] Match SUCCEEDED: '{res['address']}' (Score: {res['confidence']}%)")
                    local_geocode_result = {
                        "address": res["address"],
                        "lat": res["lat"],
                        "lng": res["lng"],
                        "rings": res["rings"]
                    }
                    confidence_score = float(res["confidence"])
                    verify_location = False
                    break
                else:
                    logging.warning(f"[Local GIS Check] Match FAILED for candidate '{candidate_address}'.")
                    
            # 6. Fallback (Anonymized Google maps fallback for unknown addresses/intersections if enabled)
            if not local_geocode_result and ENABLE_GOOGLE_MAPS_FALLBACK:
                gmaps_api_key = os.environ.get("GOOGLE_API_KEY")
                if gmaps_api_key:
                    for i, candidate_address in enumerate(unique_addresses):
                        logging.info(f"Attempting Google maps fallback for: '{candidate_address}'")
                        location_data, corrected_address_label = geocode_address(candidate_address, gmaps_api_key)
                        if location_data:
                            lat = location_data['geometry']['location']['lat']
                            lng = location_data['geometry']['location']['lng']
                            local_geocode_result = {
                                "address": corrected_address_label or candidate_address,
                                "lat": lat,
                                "lng": lng,
                                "rings": []
                            }
                            confidence_score = 75.0
                            verify_location = False
                            break
            
            # 6b. Offline Fallback for Intersections or Unresolvable addresses
            if not local_geocode_result:
                logging.warning(f"Geocoding failed for '{first_candidate}'. Sending address string to Supabase with null coordinates.")
                local_geocode_result = {
                    "address": first_candidate,
                    "lat": None,
                    "lng": None,
                    "rings": []
                }
                confidence_score = 0.0
                verify_location = True
            
        # 7. Extract incident details and build metadata
        best_address = local_geocode_result["address"]
        lat = local_geocode_result["lat"]
        lng = local_geocode_result["lng"]
        rings = local_geocode_result["rings"]
        
        # Post-check validation: Point in grid
        parsed_grids = list(set(d.map_grid for d in all_candidates if d.map_grid and d.map_grid.isdigit()))
        if parsed_grids:
            if lat is not None and lng is not None:
                is_in_any_grid = any(validator.validate_point_in_grid(lat, lng, grid) for grid in parsed_grids)
                if is_in_any_grid:
                    logging.info(f"[Post-Check] Grid Check PASSED for grids: {parsed_grids}")
                else:
                    logging.warning(f"[Post-Check] GRID MISMATCH: Location is NOT inside grids {parsed_grids}")
            else:
                logging.info(f"[Post-Check] Grid Check skipped for grids {parsed_grids} because location coordinates are null (intersection or missing address).")
                
        # 8. Construct Payloads (Option 1 & Option 2)
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        # Sub-object target for Option 2
        target_payload = {
            "address": best_address,
            "lat": lat,
            "lng": lng,
            "rings": rings
        }
        
        # Base database row
        db_payload = {
            "dispatch_id": dispatch_id,
            "incident_type": incident_type,
            "alarm_level": alarm_level,
            "responding_units": responding_units,
            "timestamp": timestamp,
            "raw_transcript": transcript,
            "confidence_score": confidence_score,
            "verify_location": verify_location
        }
        
        if INTEGRATION_PAYLOAD_OPTION == 1:
            db_payload["address"] = best_address
        else: # Option 2
            db_payload["target"] = target_payload

            
        # 9. Send Integrations (Supabase, Ntfy, Join)
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        if supabase_url and supabase_key:
            post_to_supabase(db_payload, supabase_url, supabase_key)
            
        if ENABLE_NTFY_PUSH:
            ntfy_topic = os.environ.get("NTFY_TOPIC")
            ntfy_token = os.environ.get("NTFY_TOKEN")
            if ntfy_topic:
                post_to_ntfy(db_payload, ntfy_topic, ntfy_token)
                
        if ENABLE_JOIN_PUSH:
            join_api_key = os.environ.get("JOIN_API_KEY")
            if join_api_key:
                launch_navigation_on_phone({"lat": lat, "lng": lng}, best_address, join_api_key)
                
        logging.info("--- Dispatch processing complete ---")
        
    except Exception as e:
        logging.critical(f"FATAL ERROR in worker thread: {e}", exc_info=True)
        
    finally:
        # Cleanup temporary audio file to prevent resource leaks
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
                logging.info(f"Cleaned up unique audio file '{temp_filename}'")
            except Exception as e:
                logging.warning(f"Could not delete unique audio file '{temp_filename}': {e}")

def run_dispatch_system():
    # Load call types at startup
    global CALL_TYPES
    CALL_TYPES = load_call_types()
    
    # Check required environment variables based on integration choices
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        logging.critical("FATAL ERROR: Missing required environment variables (SUPABASE_URL, SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY).")
        return
        
    if STT_ENGINE == "google" and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        logging.critical("FATAL ERROR: STT_ENGINE is set to 'google' but GOOGLE_APPLICATION_CREDENTIALS is not set.")
        return
        
    if ENABLE_NTFY_PUSH and not os.environ.get("NTFY_TOPIC"):
        logging.critical("FATAL ERROR: ENABLE_NTFY_PUSH is True but NTFY_TOPIC is not set.")
        return
        
    if ENABLE_JOIN_PUSH and not os.environ.get("JOIN_API_KEY"):
        logging.critical("FATAL ERROR: ENABLE_JOIN_PUSH is True but JOIN_API_KEY is not set.")
        return
    
    logging.info("Initializing Coquitlam Data Validator...")
    validator = CoquitlamDataValidator(ADDRESS_SHAPEFILE_PATH, ZONES_SHAPEFILE_PATH)
    logging.info("--- CFR Dispatch Mapping System: ONLINE (OFFLINE-FIRST) ---")
    
    blocksize = 1024
    try:
        with sd.InputStream(samplerate=AUDIO_SAMPLE_RATE, channels=1, blocksize=blocksize, dtype='int16', device=DEVICE_ID) as stream:
            try:
                device_info = sd.query_devices(stream.device, 'input')
                logging.info(f"Successfully opened audio stream on: '{device_info.get('name', 'Unknown')}'")
            except Exception as e: logging.warning(f"Could not query audio device name: {e}")
            time.sleep(1.0) # Allow stream to stabilize
            
            while True:
                logging.info("STATE: LISTENING_FOR_TONE")
                loudness_history = deque(maxlen=SUSTAINED_LOUDNESS_WINDOW)
                history_audio_buffer = deque(maxlen=SUSTAINED_LOUDNESS_WINDOW)
                is_capturing_tone, analysis_buffer, last_log_time, matched_tone = False, [], 0, None

                while True: # Inner loop for tone detection
                    if is_capturing_tone:
                        pcm, _ = stream.read(blocksize)
                        analysis_buffer.append(pcm)
                        if len(analysis_buffer) * blocksize >= TONE_ANALYSIS_DURATION_SECONDS * AUDIO_SAMPLE_RATE:
                            logging.info("Analyzing captured audio for a dispatch tone...")
                            full_sample_np = np.concatenate(analysis_buffer)
                            live_frequencies = analyze_live_audio(full_sample_np.tobytes())
                            matched_tone, score = get_best_match(live_frequencies)
                            if matched_tone:
                                logging.info(f"TONE CONFIRMED: '{matched_tone}' (Match: {score*100:.0f}%)")
                                break # Exit inner loop to start dispatch capture
                            else:
                                logging.info("Triggered sound was not a recognized tone, resetting.")
                                is_capturing_tone = False
                                continue
                        else:
                            continue

                    pcm, _ = stream.read(blocksize)
                    history_audio_buffer.append(pcm)
                    rms = get_rms(pcm)
                    current_time = time.time()
                    if current_time - last_log_time >= 5.0:
                        logging.debug(f"Listening... RMS: {int(rms):<5} | Loud Chunks: {sum(loudness_history)}/{SUSTAINED_LOUDNESS_CHUNKS_REQUIRED}")
                        last_log_time = current_time

                    is_currently_loud = rms > NOISE_AMPLITUDE_THRESHOLD
                    loudness_history.append(is_currently_loud)
                    
                    if not is_capturing_tone and sum(loudness_history) >= SUSTAINED_LOUDNESS_CHUNKS_REQUIRED:
                        logging.info(f"Sustained loud sound detected! Capturing for {TONE_ANALYSIS_DURATION_SECONDS}s to analyze...")
                        is_capturing_tone = True
                        analysis_buffer = list(history_audio_buffer)
                        loudness_history.clear()

                # --- Dispatch Capture and Processing ---
                dispatch_buffer = capture_full_dispatch(stream, blocksize, initial_buffer=analysis_buffer)
                if dispatch_buffer:
                    worker = threading.Thread(
                        target=process_full_dispatch, 
                        args=(list(dispatch_buffer), validator, matched_tone, UNITS_VOCABULARY), 
                        name="DispatchWorker"
                    )
                    worker.start()

                logging.info(f"Event processing handed to worker. Waiting for {POST_EVENT_RESET_SILENCE_S}s of silence before resetting...")
                silence_chunks_needed = int((AUDIO_SAMPLE_RATE / blocksize) * POST_EVENT_RESET_SILENCE_S)
                consecutive_silent_chunks = 0
                while consecutive_silent_chunks < silence_chunks_needed:
                    pcm, _ = stream.read(blocksize)
                    if get_rms(pcm) < NOISE_AMPLITUDE_THRESHOLD:
                        consecutive_silent_chunks += 1
                    else:
                        consecutive_silent_chunks = 0
                
                logging.info("Silence detected. Resetting system.")

    except KeyboardInterrupt:
        logging.info("Listener stopped by user.")
    except Exception as e:
        logging.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
    finally:
        logging.info("System shut down.")

if __name__ == "__main__":
    setup_logging()
    run_dispatch_system()