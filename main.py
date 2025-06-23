# ==============================================================================
# cfr-dispatch-mapping
# DEFINITIVE SCRIPT V22.0 (Self-Validation Logic)
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
import wavio
import librosa
import googlemaps
import requests
import sounddevice as sd
import numpy as np
from google.cloud import speech
from word2number import w2n
from thefuzz import fuzz

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
ADDRESS_CONFIDENCE_THRESHOLD = 95

# --- DISPATCH VOCABULARIES (For Intelligent Parser) ---
# Not currently used in SIMPLE parsing mode, but kept for future use.
UNITS_VOCABULARY = [
    "Engine 1", "Engine 2", "Engine 3", "Engine 4", "Engine 5", "Engine 10", "Engine 11",
    "Rescue 1", "Rescue 2", "Ladder 1", "Ladder 2",
    "Car 1", "Car 2", "Car 3", "Car 4", "Car 5", "Car 6", "Car 7", "Car 8", "Car 9",
    "Medic 1", "Hazmat 3", "Tender 4", "Light Attack Vehicle 4",
    "Squad 1", "Squad 2", "Squad 3", "Squad 4",
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

# --- MODIFIED --- This function now extracts all plausible candidates for validation.
def parse_address_candidates(transcript: str) -> list[str]:
    """
    Finds all plausible address candidates in a transcript and returns them as a list.
    """
    street_types_pattern = r"Street|Avenue|Drive|Way|Road|Crescent|Boulevard|Place|Court"
    address_pattern = re.compile(
        fr"""
        (\d+|(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)[\s-]+)+)
        \s+
        ((?:(?! \s? {street_types_pattern} \b) [\w\s.'-])+?)
        \s+
        ({street_types_pattern})\b
        """, re.IGNORECASE | re.VERBOSE
    )

    matches = address_pattern.finditer(transcript)
    plausible_addresses = []
    
    for match in matches:
        number_part, street_name, street_type = match.groups()
        try:
            # Heuristic: Only consider matches with house numbers >= 100 as plausible candidates.
            # This is the key to filtering out false positives from unit numbers like "Engine 3".
            street_number_val = w2n.word_to_num(number_part)
            if street_number_val >= 100:
                final_street_name = " ".join(street_name.strip().split())
                formatted_address = f"{street_number_val} {final_street_name} {street_type.strip()}, Coquitlam, BC"
                plausible_addresses.append(formatted_address)
        except ValueError:
            continue
            
    logging.info(f"Found {len(plausible_addresses)} plausible address candidates: {plausible_addresses}")
    return plausible_addresses

def parse_intersection_from_transcript(transcript: str) -> str | None:
    street_types = r"Street|Avenue|Drive|Way|Road|Crescent|Boulevard|Place|Court"
    pattern = re.compile(fr"([A-Za-z\s.-]+?)\s+({street_types})\s+(?:and|at)\s+([A-Za-z\s.-]+?)\s+({street_types})", re.IGNORECASE)
    match = pattern.search(transcript)
    if match:
        s1_name, s1_type, s2_name, s2_type = match.groups()
        return f"{s1_name.strip()} {s1_type} and {s2_name.strip()} {s2_type}, Coquitlam, BC"
    return None

# ==============================================================================
# --- DATA PROCESSING & WORKER FUNCTIONS ---
# ==============================================================================
# --- MODIFIED --- This function now contains the full self-validation workflow.
def process_full_dispatch(buffer, gmaps_api_key, join_api_key):
    logging.info("Starting dispatch processing pipeline.")
    if not buffer:
        logging.warning("Buffer empty, nothing to process.")
        return

    full_dispatch_audio = np.concatenate(buffer)
    temp_filename = f"temp_dispatch_full.wav"
    wavio.write(temp_filename, full_dispatch_audio, AUDIO_SAMPLE_RATE, sampwidth=2)
    logging.info(f"Dispatch audio saved to '{temp_filename}'.")

    transcript = transcribe_audio_file(temp_filename)
    if not transcript:
        logging.error("Transcription failed. Ending processing for this event.")
        return
    logging.info(f"Full Transcript: '{transcript}'")

    # --- NEW SELF-VALIDATION WORKFLOW ---

    # 1. Primary parsing: Try to find address candidates
    location_candidates = parse_address_candidates(transcript)
    
    validated_address = None
    
    # 2. Self-Validation Logic: Check if candidates match each other
    if len(location_candidates) >= 2:
        score = fuzz.ratio(location_candidates[0], location_candidates[1])
        logging.info(f"Comparing first two address candidates. Similarity score: {score}%")
        if score > 95:
            logging.info("SUCCESS: Address self-validated by repetition in dispatch audio.")
            validated_address = location_candidates[0]

    if not validated_address and location_candidates:
        logging.info("No self-validation occurred. Proceeding with single best candidate.")
        validated_address = location_candidates[0]
    
    # 3. Fallback to Intersection Parsing
    if not validated_address:
        logging.info("No standard address candidates found. Checking for an intersection.")
        validated_address = parse_intersection_from_transcript(transcript)

    # 4. Proceed if we have any valid location string
    if validated_address:
        logging.info(f"Proceeding to geocode validated location: '{validated_address}'")
        location_data = geocode_address(validated_address, gmaps_api_key)

        if location_data:
            # This is our final "Best Practice" safety check against Google's data
            components = {comp['types'][0]: comp['short_name'] for comp in location_data.get('address_components', [])}
            g_street_number = components.get('street_number', '')
            g_route = components.get('route', '')
            g_locality = components.get('locality', '')
            g_province = components.get('administrative_area_level_1', '')
            rebuilt_google_address = f"{g_street_number} {g_route}, {g_locality}, {g_province}"

            street_type_map = {
                "street": "st", "avenue": "ave", "drive": "dr", "road": "rd", "way": "wy",
                "crescent": "cres", "boulevard": "blvd", "place": "pl", "court": "ct"
            }
            def normalize_string(text):
                text = text.lower()
                for full, abbr in street_type_map.items():
                    text = re.sub(r'\b' + re.escape(full) + r'\b', abbr, text)
                return text.replace('.', '').replace(',', '')

            normalized_location_string = normalize_string(validated_address)
            normalized_google_address = normalize_string(rebuilt_google_address)
            confidence_score = fuzz.token_set_ratio(normalized_location_string, normalized_google_address)
            
            logging.info("Final Google Confidence Check: Comparing normalized strings...")
            logging.info(f"    - Parsed: '{normalized_location_string}'")
            logging.info(f"    - Google: '{normalized_google_address}'")
            logging.info(f"Normalized Confidence Score: {confidence_score}%")

            if confidence_score >= ADDRESS_CONFIDENCE_THRESHOLD:
                logging.info("Confidence score is high. Proceeding with push notification.")
                launch_navigation_on_phone(location_data['geometry']['location'], validated_address, join_api_key)
            else:
                logging.critical(f"SAFETY WARNING: Final confidence score ({confidence_score}%) is below threshold. Push notification CANCELLED.")
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
        if not response or not response.results: return None
        full_transcript = " ".join(result.alternatives[0].transcript for result in response.results if result.alternatives).strip()
        return full_transcript if full_transcript else None
    except Exception as e:
        logging.error(f"Transcription API error: {e}", exc_info=True)
        return None

def geocode_address(address: str, gmaps_api_key: str) -> dict | None:
    gmaps = googlemaps.Client(key=gmaps_api_key)
    try:
        geocode_result = gmaps.geocode(address)
        if not geocode_result or geocode_result[0]["geometry"]["location_type"] == 'APPROXIMATE':
            logging.warning(f"Could not find a precise location for '{address}'")
            return None
        first_result = geocode_result[0]
        logging.info(f"Google Found: {first_result['formatted_address']}")
        return first_result
    except Exception as e:
        logging.error(f"Geocoding API error: {e}", exc_info=True)
        return None

def launch_navigation_on_phone(location_coords: dict, address_label: str, join_api_key: str):
    latitude = location_coords['lat']
    longitude = location_coords['lng']
    label = address_label
    text_payload = f"dispatch=:={latitude}|||{longitude}|||{label}"
    
    base_url = "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush"
    params = {'apikey': join_api_key, 'deviceId': 'group.phone', 'text': text_payload}
    
    logging.info(f"Preparing to send payload: {text_payload}")
    try:
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
                logging.info(f"Successfully opened audio stream. Listening to device ID #{stream.device}: '{device_info.get('name', 'Unknown')}'")
            except Exception as e:
                logging.warning(f"Could not query for audio device name, but stream is open: {e}")
            
            time.sleep(1.0)

            while True:
                logging.info("STATE: LISTENING_FOR_TONE")
                loudness_history = deque(maxlen=SUSTAINED_LOUDNESS_WINDOW)
                is_capturing_tone = False; analysis_buffer = []
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
                    
                    current_time = time.time()
                    if current_time - last_log_time >= 5.0:
                        logging.debug(f"Listening... RMS: {int(rms):<5} | Loud Chunks: {sum(loudness_history)}/{SUSTAINED_LOUDNESS_CHUNKS_REQUIRED}")
                        last_log_time = current_time
                    
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