# ==============================================================================
# cfr-dispatch-mapping
# DEFINITIVE SCRIPT V21.0 (Best Practice Confidence Check)
# ==============================================================================

# --- Core Python Libraries ---
import os
import re
import time
import struct
import threading
import logging
from collections import deque

# --- Installed Libraries ---
# NOTE: fuzzywuzzy is required for the address confidence check.
import wavio
import librosa
import googlemaps
import requests
import sounddevice as sd
import numpy as np
from google.cloud import speech
from word2number import w2n
from thefuzz import fuzz, process as fuzzy_process
import Levenshtein

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================
# --- FEATURE FLAGS ---
USE_INTELLIGENT_PARSER = False

# --- API & PATHS ---
AUDIO_SAMPLE_RATE = 16000

# --- AUDIO TRIGGER SETTINGS ---
DEVICE_ID = 2
NOISE_AMPLITUDE_THRESHOLD = 500
SUSTAINED_LOUDNESS_WINDOW = 5
SUSTAINED_LOUDNESS_CHUNKS_REQUIRED = 4
TONE_ANALYSIS_DURATION_SECONDS = 3.5
MATCH_THRESHOLD_PERCENT = 0.7
FREQUENCY_TOLERANCE_HZ = 10
NUM_PEAKS_TO_FIND = 20

# --- GOLDEN FINGERPRINTS ---
GOLDEN_FINGERPRINTS = {
    "Chief Tone":  [429.69, 437.50, 445.31, 656.25, 664.06],
    "Engine Tone": [593.75, 601.56, 609.38, 1343.75, 1351.56],
    "Rescue Tone": [718.75, 726.56, 734.38, 890.62, 898.44]
}

# --- GENERAL TIMING ---
MAX_DISPATCH_DURATION_S = 75
END_OF_DISPATCH_SILENCE_S = 3.0
END_OF_DISPATCH_RMS_THRESHOLD = 300
POST_EVENT_RESET_SILENCE_S = 3.0

# --- SAFETY CHECKS ---
ADDRESS_CONFIDENCE_THRESHOLD = 95 # We can raise this now that the check is more accurate

# --- DISPATCH VOCABULARIES (For Intelligent Parser) ---
UNITS_VOCABULARY = [
    "Engine 1", "Engine 2", "Engine 3", "Engine 4", "Engine 5", "Engine 10", "Engine 11",
    "Rescue 1", "Rescue 2", "Ladder 1", "Ladder 2",
    "Car 1", "Car 2", "Car 3", "Car 4", "Car 5", "Car 6", "Car 7", "Car 8", "Car 9",
    "Medic 1", "Hazmat 3", "Tender 4", "Light Attack Vehicle 4",
    "Squad 1", "Squad 2", "Squad 3", "Squad 4",
]
TALKGROUPS_VOCABULARY = [
    "5 Coquitlam", "6 Coquitlam", "7 Coquitlam", "8 Coquitlam", "9 Coquitlam",
    "Combined Response Coquitlam", "Combined Response Port Mann"
]
CALL_TYPES_VOCABULARY = [
    "Structure Fire", "Medical Aid", "Alarms Activated", "Motor Vehicle Incident", "Assist",
]

# ==============================================================================
# --- LOGGING SETUP ---
# ==============================================================================
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    if logger.hasHandlers():
        logger.handlers.clear()
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
# --- HELPER FUNCTIONS & ALL PARSERS ---
# ==============================================================================
def get_rms(data: np.ndarray) -> float:
    return np.sqrt(np.mean(data.astype(np.float32)**2)) if data.size > 0 else 0

def analyze_live_audio(data: bytes, num_peaks=NUM_PEAKS_TO_FIND) -> set:
    audio_array = np.frombuffer(data, dtype=np.int16)
    if len(audio_array) == 0: return set()
    fft_data = np.fft.rfft(audio_array)
    fft_freqs = np.fft.rfftfreq(len(audio_array), 1.0 / AUDIO_SAMPLE_RATE)
    fft_magnitude = np.abs(fft_data)
    try:
        peak_indices = np.argpartition(fft_magnitude, -num_peaks)[-num_peaks:]
        found_freqs = set(int(f) for f in fft_freqs[peak_indices])
        logging.debug(f"Found peak frequencies: {found_freqs}")
        return found_freqs
    except (ValueError, IndexError):
        return set()

def get_best_match(live_frequencies: set) -> tuple | tuple[None, None]:
    best_match_tone = None; best_match_score = -1
    for tone_name, golden_freqs in GOLDEN_FINGERPRINTS.items():
        matches_found = sum(1 for gf in golden_freqs if any(abs(lf - gf) <= FREQUENCY_TOLERANCE_HZ for lf in live_frequencies))
        score = matches_found / len(golden_freqs) if golden_freqs else 0
        if score > best_match_score:
            best_match_score = score
            best_match_tone = tone_name
    if best_match_score >= MATCH_THRESHOLD_PERCENT:
        return best_match_tone, best_match_score
    return None, None

# --- MODIFIED ---
# This is the fully upgraded address parser
# --- MODIFIED ---
# This function now intelligently selects the BEST match instead of just the first one.
def parse_address_from_transcript(transcript: str) -> str | None:
    """
    Finds a standard address, handling both digit/word numbers and avoiding over-matching.
    It now evaluates all potential matches and selects the most plausible one.
    """
    street_types_pattern = r"Street|Avenue|Drive|Way|Road|Crescent|Boulevard|Place|Court"

    address_pattern = re.compile(
        fr"""
        (
            \d+
            |
            (?:
                (?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)
                [\s-]+
            )+
        )
        \s+
        (
            (?:(?! \s? {street_types_pattern} \b) [\w\s.'-])+?
        )
        \s+
        (
            {street_types_pattern}
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE
    )

    matches = list(address_pattern.finditer(transcript))
    logging.debug(f"Found {len(matches)} potential address matches: {[m.groups() for m in matches]}")
    if not matches:
        return None

    # --- NEW: Best Match Selection Logic ---
    best_match = None
    highest_score = -1

    for match in matches:
        number_part_str, street_name, street_type = match.groups()
        score = 0
        try:
            # Heuristic: A higher, more "address-like" number gets a higher score.
            # We add a large bonus for numbers >= 100 to strongly prefer them over unit numbers.
            street_number_val = w2n.word_to_num(number_part_str)
            score = street_number_val + (10000 if street_number_val >= 100 else 0)
        except ValueError:
            score = 0 # Cannot parse number, score is 0.
        
        logging.debug(f"Evaluating potential match: {match.groups()} with score {score}")

        if score > highest_score:
            highest_score = score
            best_match = match
    
    if not best_match:
        logging.warning("Could not determine a best address match from candidates.")
        return None
    # --- END: Best Match Selection Logic ---

    logging.debug(f"Selected best address match: {best_match.groups()}")
    number_part, street_name, street_type = best_match.groups()
    
    # Proceed with the proven conversion and formatting logic from the best match
    street_number = str(w2n.word_to_num(number_part))
    final_street_name = " ".join(street_name.strip().split()) # Consolidate whitespace
    
    return f"{street_number} {final_street_name} {street_type.strip()}, Coquitlam, BC"

def parse_intersection_from_transcript(transcript: str) -> str | None:
    street_types = r"Street|Avenue|Drive|Way|Road|Crescent|Boulevard|Place|Court"
    pattern = re.compile(fr"([A-Za-z\s.-]+?)\s+({street_types})\s+(?:and|at)\s+([A-Za-z\s.-]+?)\s+({street_types})", re.IGNORECASE)
    match = pattern.search(transcript)
    logging.debug(f"Intersection regex match: {match}")
    if match:
        s1_name, s1_type, s2_name, s2_type = match.groups()
        return f"{s1_name.strip()} {s1_type} and {s2_name.strip()} {s2_type}, Coquitlam, BC"
    return None

def correct_text_with_vocabulary(text: str, vocabulary: list, score_cutoff=80) -> str | None:
    if not text or not vocabulary: return None
    best_match, score = fuzzy_process.extractOne(text, vocabulary)
    logging.debug(f"Fuzzy match for '{text}': Best is '{best_match}' with score {score}")
    return best_match if score >= score_cutoff else None

def parse_full_dispatch_syntax(transcript: str) -> dict | None:
    pattern = re.compile(r"""
        ^.*? (?P<units>[\w\s,]+?)\s+ Respond\s+(?P<response_type>\w+),\s+ (?P<call_type>.*?),\s+
        (?P<address>.*?),\s+ (?P<cross_roads>.*?),\s+ Use\s+Talk\s+Group\s+(?P<talkgroup>.*?),\s* .*?
        Map\s+Grid\s+(?P<map_grid>[\w\s]+?)(?=\s|$)
    """, re.VERBOSE | re.IGNORECASE)
    match = pattern.search(transcript)
    if not match: return None
    return {key: value.strip() for key, value in match.groupdict().items()}

# ==============================================================================
# --- DATA PROCESSING & WORKER FUNCTIONS ---
# ==============================================================================
def process_full_dispatch(buffer, gmaps_api_key, join_api_key):
    logging.info("Starting dispatch processing pipeline.")
    if not buffer:
        logging.warning("Buffer empty, nothing to process.")
        return

    full_dispatch_audio = np.concatenate(buffer)
    if full_dispatch_audio.ndim == 1:
        full_dispatch_audio = full_dispatch_audio.reshape(-1, 1)
    temp_filename = f"temp_dispatch_full.wav"
    wavio.write(temp_filename, full_dispatch_audio, AUDIO_SAMPLE_RATE, sampwidth=2)
    logging.info(f"Dispatch audio saved to '{temp_filename}'.")

    transcript = transcribe_audio_file(temp_filename)
    if not transcript:
        logging.error("Transcription failed. Ending processing for this event.")
        return
    logging.info(f"Full Transcript: '{transcript}'")

    if USE_INTELLIGENT_PARSER:
        logging.info("Using INTELLIGENT parsing mode.")
        parsed_data = parse_full_dispatch_syntax(transcript)
        if not parsed_data:
            logging.error("Could not parse dispatch syntax.")
            return

        final_units = ", ".join(filter(None, [correct_text_with_vocabulary(u.strip(), UNITS_VOCABULARY) for u in parsed_data.get('units', '').split(',')]))
        final_talkgroup = correct_text_with_vocabulary(parsed_data.get('talkgroup'), TALKGROUPS_VOCABULARY)
        try: final_map_grid = str(w2n.word_to_num(parsed_data.get('map_grid')))
        except (ValueError, TypeError): final_map_grid = parsed_data.get('map_grid')
        location_string = parsed_data.get('address')
        logging.info(f"--- Dispatch Details (Corrected) ---\nUnits: {final_units}\nCall Type: {parsed_data.get('call_type')}\nAddress: {location_string}\nMap Grid: {final_map_grid}\nTalkgroup: {final_talkgroup}")

    else:
        logging.info("Using SIMPLE parsing mode.")
        location_string = parse_address_from_transcript(transcript)
        if not location_string:
            logging.info("No standard address found. Checking for an intersection.")
            location_string = parse_intersection_from_transcript(transcript)

    # --- MODIFIED ---
    # This block contains the new "Best Practice" confidence check logic.
    if location_string:
        logging.info(f"Found Location to process: {location_string}")
        location_data = geocode_address(location_string, gmaps_api_key)
        
        if location_data:
            # 1. Rebuild a clean address from Google's components
            components = {comp['types'][0]: comp['short_name'] for comp in location_data.get('address_components', [])}
            g_street_number = components.get('street_number', '')
            g_route = components.get('route', '')
            g_locality = components.get('locality', '')
            g_province = components.get('administrative_area_level_1', '')
            
            rebuilt_google_address = f"{g_street_number} {g_route}, {g_locality}, {g_province}"

            # 2. Normalize street types in BOTH strings
            street_type_map = {
                "street": "st", "avenue": "ave", "drive": "dr", "road": "rd", "way": "wy",
                "crescent": "cres", "boulevard": "blvd", "place": "pl", "court": "ct"
            }
            
            def normalize_string(text):
                text = text.lower()
                for full, abbr in street_type_map.items():
                    text = re.sub(r'\b' + re.escape(full) + r'\b', abbr, text)
                return text.replace('.', '').replace(',', '')

            normalized_location_string = normalize_string(location_string)
            normalized_google_address = normalize_string(rebuilt_google_address)

            # 3. Perform the confidence check on the fully normalized strings
            confidence_score = fuzz.token_set_ratio(normalized_location_string, normalized_google_address)
            
            logging.info("Confidence Check: Comparing normalized strings...")
            logging.info(f"    - Parsed: '{normalized_location_string}'")
            logging.info(f"    - Google: '{normalized_google_address}'")
            logging.info(f"Normalized Confidence Score: {confidence_score}%")

            # 4. Proceed with the high-confidence result
            if confidence_score >= ADDRESS_CONFIDENCE_THRESHOLD:
                logging.info("Confidence score is high. Proceeding with push notification.")
                launch_navigation_on_phone(location_data['geometry']['location'], location_string, join_api_key)
            else:
                logging.critical(f"SAFETY WARNING: Geocoding confidence score ({confidence_score}%) is below threshold. Push notification CANCELLED.")
    else:
        logging.warning("No address or intersection could be parsed from the transcript.")
    logging.info("Dispatch processing complete.")


def transcribe_audio_file(file_path: str) -> str | None:
    try:
        client = speech.SpeechClient()
        with open(file_path, "rb") as audio_file: content = audio_file.read()
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, sample_rate_hertz=AUDIO_SAMPLE_RATE, language_code="en-CA", enable_automatic_punctuation=True)
        response = client.recognize(config=config, audio=audio)
        logging.debug(f"Google Speech API raw response: {response}")
        if not response or not response.results: return None
        full_transcript = " ".join(result.alternatives[0].transcript for result in response.results if result.alternatives).strip()
        return full_transcript if full_transcript else None
    except Exception as e:
        logging.error(f"Transcription API error: {e}", exc_info=True)
        return None

# --- MODIFIED ---
# This function now returns the full, rich result from the Google API.
def geocode_address(address: str, gmaps_api_key: str) -> dict | None:
    gmaps = googlemaps.Client(key=gmaps_api_key)
    try:
        geocode_result = gmaps.geocode(address)
        if not geocode_result or geocode_result[0]["geometry"]["location_type"] == 'APPROXIMATE':
            logging.warning(f"Could not find a precise location for '{address}'")
            return None
        
        first_result = geocode_result[0]
        logging.info(f"Found location: {first_result['formatted_address']}")
        # Return the entire result object, which contains components and geometry
        return first_result

    except Exception as e:
        logging.error(f"Geocoding API error: {e}", exc_info=True)
        return None

# --- MODIFIED ---
# This function is updated to accept the new `location_coords` object.
def launch_navigation_on_phone(location_coords: dict, address_label: str, join_api_key: str):
    """Builds a simple, multi-part payload that is easy for Tasker to split."""
    latitude = location_coords['lat']
    longitude = location_coords['lng']
    label = address_label
    text_payload = f"dispatch=:={latitude}|||{longitude}|||{label}"
    
    base_url = "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush"
    params = {'apikey': join_api_key, 'deviceId': 'group.phone', 'text': text_payload}
    
    logging.info(f"Preparing to send payload: {text_payload}")
    try:
        logging.info("Sending navigation request to Join API...")
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        logging.info("Join message sent successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Join API error: {e}", exc_info=True)

def capture_full_dispatch(stream, blocksize, initial_buffer=None):
    logging.info("STATE: CAPTURING DISPATCH")
    audio_buffer = initial_buffer if initial_buffer is not None else []
    max_chunks = int((AUDIO_SAMPLE_RATE / blocksize) * MAX_DISPATCH_DURATION_S)
    start_chunk = len(audio_buffer)
    silence_start_time = None
    for i in range(start_chunk, max_chunks):
        try:
            pcm = stream.read(blocksize)[0]
            audio_buffer.append(pcm)
            volume = get_rms(pcm)
            if volume < END_OF_DISPATCH_RMS_THRESHOLD:
                if silence_start_time is None:
                    silence_start_time = time.time()
                elif time.time() - silence_start_time >= END_OF_DISPATCH_SILENCE_S:
                    logging.info(f"END OF DISPATCH DETECTED by {END_OF_DISPATCH_SILENCE_S}s of silence.")
                    return audio_buffer
            else:
                silence_start_time = None
        except Exception as e:
            logging.error(f"Audio stream read error: {e}", exc_info=True)
            break
    logging.info(f"MAX DURATION ({MAX_DISPATCH_DURATION_S}s) REACHED.")
    return audio_buffer

# ==============================================================================
# --- MAIN APPLICATION ---
# ==============================================================================
def run_dispatch_system():
    gmaps_api_key = os.environ.get("GOOGLE_API_KEY")
    join_api_key = os.environ.get("JOIN_API_KEY")
    if not all([gmaps_api_key, join_api_key, os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")]):
        logging.critical("FATAL ERROR: Environment variables not set.")
        return

    logging.info("--- CFR Dispatch Mapping System: ONLINE ---")
    blocksize = 1024
    try:
        with sd.InputStream(samplerate=AUDIO_SAMPLE_RATE, channels=1, blocksize=blocksize, dtype='int16', device=DEVICE_ID) as stream:
            try:
                device_info = sd.query_devices(stream.device, 'input')
                device_name = device_info.get('name', 'Unknown Device')
                logging.info(f"Successfully opened audio stream. Listening to device ID #{stream.device}: '{device_name}'")
            except Exception as e:
                logging.warning(f"Could not query for audio device name, but stream is open: {e}")

            time.sleep(1.0)

            while True:
                logging.info("STATE: LISTENING_FOR_TONE")
                loudness_history = deque(maxlen=SUSTAINED_LOUDNESS_WINDOW)
                is_capturing_tone = False; analysis_buffer = []

                # --- NEW --- Add a variable to track the last log time
                last_log_time = 0

                while True:
                    if is_capturing_tone:
                        analysis_buffer.append(stream.read(blocksize)[0])
                        if time.time() >= capture_end_time:
                            logging.info("Analyzing captured audio for a tone...")
                            full_sample_np = np.concatenate(analysis_buffer)
                            live_frequencies = analyze_live_audio(full_sample_np.tobytes())
                            matched_tone, score = get_best_match(live_frequencies)
                            if matched_tone:
                                logging.info(f"TONE CONFIRMED: '{matched_tone}' (Match: {score*100:.0f}%)")
                                break
                            else:
                                logging.info("Triggered sound was not a recognized tone, resetting.")
                                is_capturing_tone = False
                                continue
                        else: continue
                    
                    pcm = stream.read(blocksize)[0]
                    rms = get_rms(pcm)

                    # --- MODIFIED --- This block replaces the old logging line
                    # Only log the status every 5 seconds to keep the logs clean.
                    current_time = time.time()
                    if current_time - last_log_time >= 5.0:
                        logging.debug(f"Listening... RMS: {int(rms):<5} | Loud Chunks: {sum(loudness_history)}/{SUSTAINED_LOUDNESS_CHUNKS_REQUIRED}")
                        last_log_time = current_time
                    # --- END MODIFICATION ---

                    is_currently_loud = rms > NOISE_AMPLITUDE_THRESHOLD
                    loudness_history.append(is_currently_loud)
                    if sum(loudness_history) >= SUSTAINED_LOUDNESS_CHUNKS_REQUIRED:
                        logging.info(f"Sustained sound detected! Capturing for {TONE_ANALYSIS_DURATION_SECONDS}s to analyze...")
                        is_capturing_tone = True
                        analysis_buffer = []
                        capture_end_time = time.time() + TONE_ANALYSIS_DURATION_SECONDS
                        loudness_history.clear()

                dispatch_buffer = capture_full_dispatch(stream, blocksize, initial_buffer=analysis_buffer)
                if dispatch_buffer:
                    worker = threading.Thread(target=process_full_dispatch, args=(list(dispatch_buffer), gmaps_api_key, join_api_key))
                    worker.start()

                logging.info(f"Event processing handed to worker. Waiting for {POST_EVENT_RESET_SILENCE_S}s of silence before resetting...")
                silence_chunks_needed = int((AUDIO_SAMPLE_RATE / blocksize) * POST_EVENT_RESET_SILENCE_S)
                consecutive_silent_chunks = 0
                while consecutive_silent_chunks < silence_chunks_needed:
                    pcm = stream.read(blocksize)[0]
                    if get_rms(pcm) < NOISE_AMPLITUDE_THRESHOLD:
                        consecutive_silent_chunks += 1
                    else:
                        consecutive_silent_chunks = 0
                logging.info("Silence detected. Resetting system.")
    except KeyboardInterrupt:
        logging.info("Listener stopped by user.")
    except Exception as e:
        logging.critical(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        logging.info("System shut down.")

if __name__ == "__main__":
    setup_logging()
    run_dispatch_system()