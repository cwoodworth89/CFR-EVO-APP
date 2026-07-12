# cfr_dispatch/orchestration.py
# System orchestration, audio capture, and background process worker loops

import os
import io
import re
import time
import uuid
import datetime
import logging
import wavio
import requests
import numpy as np
from typing import List, Optional
import sounddevice as sd
from collections import deque
import multiprocessing

# Local package imports
from cfr_dispatch.config import (
    DispatchData,
    STT_ENGINE,
    WHISPER_MODEL,
    INTEGRATION_PAYLOAD_OPTION,
    ENABLE_GOOGLE_MAPS_FALLBACK,
    ENABLE_NTFY_PUSH,
    AUDIO_SAMPLE_RATE,
    NOISE_AMPLITUDE_THRESHOLD,
    SUSTAINED_LOUDNESS_WINDOW,
    SUSTAINED_LOUDNESS_CHUNKS_REQUIRED,
    TONE_ANALYSIS_DURATION_SECONDS,
    MAX_DISPATCH_DURATION_S,
    END_OF_DISPATCH_SILENCE_S,
    END_OF_DISPATCH_RMS_THRESHOLD,
    POST_EVENT_RESET_SILENCE_S,
    PHASE_1_CHECK_INTERVAL_S,
    MIN_PHASE_1_DURATION_S,
    DEVICE_ID,
    UNITS_VOCABULARY,
    ADDRESS_SHAPEFILE_PATH,
    ZONES_SHAPEFILE_PATH,
    ADAPTATION_RESOURCE_IDS,
    BOOST_MAPPING,
    GCP_PROJECT_ID,
    RECOGNIZER_RESOURCE_NAME,
    ADDRESS_HOUSE_NUM_COLUMN,
    ADDRESS_STREET_NAME_COLUMN,
    ADDRESS_STREET_TYPE_COLUMN,
    ADDRESS_FULL_ADDR_COLUMN,
    STREET_NAME_CONFIDENCE_THRESHOLD,
    ZONES_MAP_NAME_COLUMN,
    VERBOSITY_LEVEL,
    NUM_PEAKS_TO_FIND,
    TONE_ZSCORE_THRESHOLD,
    GOLDEN_FINGERPRINTS,
    FREQUENCY_TOLERANCE_HZ,
    MATCH_THRESHOLD_PERCENT
)
from audio_service import (
    get_rms,
    analyze_live_audio,
    get_best_match,
    filter_known_tones,
    capture_full_dispatch
)
from cfr_dispatch.parser import (
    sanitize_transcript,
    match_incident_type,
    abbreviate_units,
    parse_dispatch_announcement,
    split_rounds,
    CALL_TYPES
)
from gis_service import CoquitlamDataValidator
from notification_service import (
    post_to_supabase,
    post_to_ntfy,
    update_supabase_record,
    upload_to_supabase_storage
)

# Global queue for background multiprocessing worker
dispatch_queue = multiprocessing.Queue()

def setup_logging():
    """Configures global debug logs and console streams using daily 0800 shift rotation."""
    import time
    import datetime
    from logging.handlers import TimedRotatingFileHandler
    
    # Configure logging formatters globally to use local time (Pacific Time)
    logging.Formatter.converter = time.localtime

    logger = logging.getLogger()
    
    # Map verbosity levels: 0 (MUTED), 1 (STANDARD), 2 (VERBOSE), 3 (TRACE)
    if VERBOSITY_LEVEL == 0:
        log_level = logging.ERROR
    elif VERBOSITY_LEVEL == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
        
    logger.setLevel(log_level)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    # Timed Rotating File Handler (rotates daily at 08:00, retains 10 backups)
    log_file = 'dispatch.log'
    file_handler = TimedRotatingFileHandler(
        log_file,
        when='D',
        interval=1,
        backupCount=10,
        atTime=datetime.time(8, 0, 0)
    )
    file_handler.setLevel(logging.DEBUG if VERBOSITY_LEVEL >= 2 else logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(threadName)s - %(funcName)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO if VERBOSITY_LEVEL >= 1 else logging.WARNING)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Silence verbose third-party loggers
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def transcribe_audio_bytes(content: bytes) -> str | None:
    """Transcribes raw WAV audio bytes using Google Cloud Speech-to-Text v2 with custom phrase adaptation."""
    try:
        from google.cloud import speech_v2
        client = speech_v2.SpeechClient()

        phrases_to_boost = []
        for resource_id in ADAPTATION_RESOURCE_IDS:
            base_id = next((key for key in BOOST_MAPPING if resource_id.startswith(key)), None)
            boost_value = BOOST_MAPPING.get(base_id, 10)
            
            full_resource_name = f"projects/{GCP_PROJECT_ID}/locations/global/customClasses/{resource_id}"
            phrases_to_boost.append({"value": f"${full_resource_name}", "boost": boost_value})

        # Inject system-wide structural biases and vocabulary into the recognizer
        system_phrases = [
            "Coquitlam",
            "respond emergency",
            "respond routine",
            "medical aid",
            "use talk group",
            "talk group",
            "map grid",
            "Combined Response Coquitlam"
        ]
        
        # Add units and unit patterns (e.g., "Engine 1" to "Engine 19")
        for unit in UNITS_VOCABULARY:
            system_phrases.append(unit)
            for num in range(1, 20):
                system_phrases.append(f"{unit} {num}")
                
        # Boost structural dispatch phrases at high priority
        for phrase in system_phrases:
            phrases_to_boost.append({"value": phrase, "boost": 20.0})

        inline_set = speech_v2.types.PhraseSet(phrases=phrases_to_boost)
        adaptation_phrase_set_dict = {"inline_phrase_set": inline_set}
        adaptation_config = speech_v2.SpeechAdaptation(
            phrase_sets=[adaptation_phrase_set_dict]
        )
        
        config = speech_v2.RecognitionConfig(
            auto_decoding_config={},
            language_codes=["en-CA"],
            model="long",
            features=speech_v2.RecognitionFeatures(
                enable_automatic_punctuation=True,
            ),
            adaptation=adaptation_config
        )
        
        request = speech_v2.types.RecognizeRequest(
            recognizer=RECOGNIZER_RESOURCE_NAME,
            config=config,
            content=content,
        )
        
        logging.info(f"Sending Google STT V2 transcription request...")
        response = client.recognize(request=request)

        if not response or not response.results:
            logging.warning("Google STT returned no results.")
            return None
        
        transcripts = [
            result.alternatives[0].transcript 
            for result in response.results 
            if result.alternatives
        ]
        return " ".join(transcripts).strip() or None

    except Exception as e:
        logging.error(f"Google STT API error: {e}", exc_info=True)
        return None

def transcribe_audio_file(file_path: str) -> str | None:
    """Transcribes audio file respecting STT_ENGINE configuration."""
    if STT_ENGINE == "whisper":
        return transcribe_audio_file_local(file_path)
    try:
        with open(file_path, "rb") as audio_file:
            content = audio_file.read()
        return transcribe_audio_bytes(content)
    except Exception as e:
        logging.error(f"Failed to read audio file: {e}", exc_info=True)
        return None

_cached_validator = None

def get_shared_validator():
    global _cached_validator
    if _cached_validator is None:
        try:
            from gis_service import CoquitlamDataValidator
            from cfr_dispatch.config import (
                ADDRESS_SHAPEFILE_PATH,
                ZONES_SHAPEFILE_PATH,
                ADDRESS_HOUSE_NUM_COLUMN,
                ADDRESS_STREET_NAME_COLUMN,
                ADDRESS_STREET_TYPE_COLUMN,
                ADDRESS_FULL_ADDR_COLUMN,
                ZONES_MAP_NAME_COLUMN,
                STREET_NAME_CONFIDENCE_THRESHOLD
            )
            logging.info("Initializing shared CoquitlamDataValidator for STT hotwords...")
            _cached_validator = CoquitlamDataValidator(
                ADDRESS_SHAPEFILE_PATH,
                ZONES_SHAPEFILE_PATH,
                house_num_col=ADDRESS_HOUSE_NUM_COLUMN,
                street_name_col=ADDRESS_STREET_NAME_COLUMN,
                street_type_col=ADDRESS_STREET_TYPE_COLUMN,
                full_addr_col=ADDRESS_FULL_ADDR_COLUMN,
                zone_map_name_col=ZONES_MAP_NAME_COLUMN,
                street_confidence_threshold=STREET_NAME_CONFIDENCE_THRESHOLD
            )
        except Exception as e:
            logging.warning(f"Failed to load shared validator for STT hotwords: {e}")
    return _cached_validator

def get_hitl_verified_streets() -> list[str]:
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            return []
            
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}"
        }
        # Query unique verified address fields where feedback_submitted is true
        endpoint = f"{supabase_url.rstrip('/')}/rest/v1/live_calls?select=verified_address&feedback_submitted=eq.true"
        response = requests.get(endpoint, headers=headers, timeout=5)
        response.raise_for_status()
        records = response.json()
        
        verified_streets = []
        for r in records:
            addr = r.get("verified_address")
            if addr:
                # Extract street name (remove leading house numbers and trailing city/province info)
                match = re.search(r'^\d+\s+(?P<street>.*)', addr.split(',')[0].strip())
                if match:
                    street = match.group('street').strip().title()
                    if street:
                        verified_streets.append(street)
        return list(set(verified_streets))
    except Exception as e:
        logging.warning(f"Failed to fetch HITL verified streets for STT hotwords: {e}")
        return []

def build_stt_bias_words(validator, units_vocabulary) -> tuple[str, str]:
    base_words = [
        "Coquitlam", "respond", "routine", "emergency", "Combined Response Coquitlam",
        "use talk group", "map grid", "medical aid", "overdose", "lift assist", 
        "structure fire", "alarm activated"
    ]
    # Core units (abbreviated list to optimize prompt length)
    units = ["Engine", "Rescue", "Ladder", "Medic", "Squad", "Battalion", "Quint"]
    
    # Fetch HITL verified streets to bias Whisper dynamically toward corrected addresses
    hitl_streets = get_hitl_verified_streets()
    
    streets = []
    if validator:
        try:
            if hasattr(validator, 'addresses_gdf') and validator.addresses_gdf is not None:
                col = validator.street_name_col
                # Extract only the top 15 most frequent street names to prevent prompt token limit crashes
                street_counts = validator.addresses_gdf[col].dropna().value_counts()
                top_streets = street_counts.head(15).index.tolist()
                streets = [str(s).title() for s in top_streets if len(str(s).strip()) > 1]
        except Exception as e:
            logging.warning(f"Failed to fetch unique streets for STT hotwords: {e}")
            
    # Combine terms, removing duplicates and capping to a strict limit of 35 terms (HITL streets prioritized)
    # This prevents the Whisper decoder from throwing a positional embedding RuntimeError (token count > 448)
    all_terms = list(dict.fromkeys(base_words + units + hitl_streets + streets))
    all_terms = all_terms[:35]
    
    hotwords_str = ", ".join(all_terms)
    initial_prompt_str = ", ".join(all_terms)
    return initial_prompt_str, hotwords_str

def transcribe_audio_local(audio_data, model=None, validator=None) -> str | None:
    """
    Transcribes audio (NumPy array or file path) locally using a pre-loaded/cached
    faster-whisper or openai-whisper model with street/unit phrase biasing.
    """
    try:
        if model is None:
            # On-demand fallback
            from faster_whisper import WhisperModel
            logging.info(f"Loading local faster-whisper model '{WHISPER_MODEL}' on demand...")
            model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")

        is_faster_whisper = hasattr(model, 'transcribe') and not hasattr(model, 'load_model')
        
        # Resolve validator dynamically if not supplied
        if validator is None:
            validator = get_shared_validator()
            
        initial_prompt, hotwords_str = build_stt_bias_words(validator, UNITS_VOCABULARY)
        
        if is_faster_whisper:
            logging.info("Transcribing using cached faster-whisper model with vocabulary boosting...")
            try:
                segments, info = model.transcribe(audio_data, beam_size=2, language="en", initial_prompt=initial_prompt, hotwords=hotwords_str)
            except TypeError:
                # Fallback if hotwords parameter is not supported by ctranslate2 version
                segments, info = model.transcribe(audio_data, beam_size=2, language="en", initial_prompt=initial_prompt)
            text = " ".join([segment.text for segment in segments])
            return text.strip() or None
        else:
            logging.info("Transcribing using cached standard Whisper model...")
            if isinstance(audio_data, str):
                import whisper
                audio_data = whisper.load_audio(audio_data)
            result = model.transcribe(audio_data, language="en", beam_size=2, initial_prompt=initial_prompt)
            return result.get("text", "").strip() or None
            
    except Exception as e:
        logging.error(f"Local transcription error: {e}", exc_info=True)
        return None

def transcribe_audio_file_local(file_path: str, model=None) -> str | None:
    """Transcribes local audio file path using Whisper (backwards compatibility)."""
    return transcribe_audio_local(file_path, model=model)


def google_geocode_fallback(address: str, api_key: str) -> tuple[dict | None, str | None]:
    """Helper to geocode address using Google Geocoding API as fallback."""
    if not api_key:
        return None, None
    try:
        import googlemaps
        gmaps = googlemaps.Client(key=api_key)
        search_query = f"{address}, Coquitlam, BC"
        geocode_result = gmaps.geocode(search_query)
        if not geocode_result:
            return None, None
        first_result = geocode_result[0]
        location_type = first_result["geometry"]["location_type"]
        good_location_types = ["ROOFTOP", "RANGE_INTERPOLATED", "GEOMETRIC_CENTER"]
        if location_type not in good_location_types:
             return None, None
        location_data = {
            "geometry": {
                "location": {
                    "lat": first_result["geometry"]["location"]["lat"],
                    "lng": first_result["geometry"]["location"]["lng"]
                }
            }
        }
        corrected_label = first_result.get("formatted_address")
        return location_data, corrected_label
    except Exception as e:
        logging.error(f"Google maps fallback geocoding error: {e}")
        return None, None


def process_and_post_payload(dispatch_id, raw_transcript, sanitized_transcript, all_candidates, validator, units_vocabulary, verify_location_override=None, audio_url=None, audio_duration=None, verified_transcript=None):
    """Common logic for geocoding, preparing DB payload, and posting to Supabase/NTFY."""
    try:
        unique_addresses = []
        for d in all_candidates:
            if d.address and d.address not in unique_addresses:
                unique_addresses.append(d.address)
            if d.intersection and d.intersection not in unique_addresses:
                unique_addresses.append(d.intersection)
                
        # Parse Incident Type
        incident_type = match_incident_type(sanitized_transcript, CALL_TYPES)
        units_str = next((d.units for d in all_candidates if d.units), None)
        responding_units = abbreviate_units(units_str)

        # Check for specific placeholder phrase
        is_specific_placeholder = "contact dispatch" in sanitized_transcript.lower() or "location information" in sanitized_transcript.lower()
        
        if is_specific_placeholder:
            unique_addresses = ["Contact dispatch for location information"]
        
        if not unique_addresses:
            if responding_units or incident_type != "Unknown Incident":
                logging.warning("No address or intersection parsed, but dispatch details found. Using 'Unknown Location' fallback.")
                unique_addresses = ["Unknown Location"]
            else:
                logging.warning("Could not parse any address or intersection from transcript, and no dispatch details found. Storing as fallback to allow manual review.")
                unique_addresses = ["Unknown Location"]
                verify_location_override = True
            
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
                    
            # 6. Fallback (Anonymized Google maps fallback if enabled)
            if not local_geocode_result and ENABLE_GOOGLE_MAPS_FALLBACK:
                gmaps_api_key = os.environ.get("GOOGLE_API_KEY")
                if gmaps_api_key:
                    for i, candidate_address in enumerate(unique_addresses):
                        logging.info(f"Attempting Google maps fallback for: '{candidate_address}'")
                        location_data, corrected_address_label = google_geocode_fallback(candidate_address, gmaps_api_key)
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
                logging.info(f"[Post-Check] Grid Check skipped for grids {parsed_grids} because location coordinates are null.")
                
        # 8. Construct Payloads
        # Use local time with timezone offset to align with local logs
        timestamp = datetime.datetime.now().astimezone().isoformat()
        
        map_grid = next((d.map_grid for d in all_candidates if d.map_grid), None)
        radio_channel = next((d.radio_channel for d in all_candidates if d.radio_channel), None)
        
        # Structured Confidence Index Calculation
        if best_address == "Contact dispatch for location information":
            confidence_score = 100.0
            verify_location = False
        else:
            base_confidence = confidence_score if confidence_score is not None else 0.0
            penalties = 0.0
            if lat is None or lng is None:
                penalties += 30.0
            if not responding_units or len(responding_units) == 0 or (len(responding_units) == 1 and responding_units[0] == "Unknown Unit"):
                penalties += 20.0
            if not map_grid or str(map_grid).strip() == "" or str(map_grid).lower() == "none":
                penalties += 15.0
            if not radio_channel or str(radio_channel).strip() == "" or str(radio_channel).lower() == "none":
                penalties += 15.0
            
            confidence_score = max(0.0, base_confidence - penalties)
            if confidence_score < 90.0:
                verify_location = True
                
        if verify_location_override is not None:
            verify_location = verify_location_override
            
        target_payload = {
            "address": best_address,
            "lat": lat,
            "lng": lng,
            "rings": rings,
            "map_grid": map_grid,
            "radio_channel": radio_channel
        }
        
        db_payload = {
            "dispatch_id": dispatch_id,
            "incident_type": incident_type,
            "responding_units": responding_units,
            "timestamp": timestamp,
            "raw_transcript": raw_transcript,
            "sanitized_transcript": sanitized_transcript,
            "confidence_score": confidence_score,
            "verify_location": verify_location
        }
        
        if audio_url is not None:
            db_payload["audio_url"] = audio_url
        if audio_duration is not None:
            db_payload["audio_duration"] = audio_duration
        if verified_transcript is not None:
            db_payload["verified_transcript"] = verified_transcript
        
        if INTEGRATION_PAYLOAD_OPTION == 1:
            db_payload["address"] = best_address
        else:
            db_payload["target"] = target_payload
            
        # 9. Send Integrations
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        if supabase_url and supabase_key:
            post_to_supabase(db_payload, supabase_url, supabase_key)
            
        if ENABLE_NTFY_PUSH:
            ntfy_topic = os.environ.get("NTFY_TOPIC")
            ntfy_token = os.environ.get("NTFY_TOKEN")
            if ntfy_topic:
                post_to_ntfy(db_payload, ntfy_topic, ntfy_token)
                
        return db_payload, responding_units

    except Exception as e:
        logging.error(f"Error in process_and_post_payload: {e}", exc_info=True)
        return None, []


def save_and_upload_audio(dispatch_id: str, buffer: list, tone_name: str) -> tuple[str | None, float]:
    """
    Concatenates recorded audio buffer chunks, saves a .wav file locally
    (to frontend/public/recordings/ and backend/audio_files/recordings/),
    uploads it to Supabase Storage, and returns the public audio URL (or local path)
    and audio duration in seconds.
    """
    try:
        import numpy as np
        import wavio
        import io
        import os
        
        # Combine chunks
        full_dispatch_audio = np.concatenate(buffer)
        
        # Calculate duration
        duration_seconds = round(len(full_dispatch_audio) / AUDIO_SAMPLE_RATE, 2)
        logging.info(f"Recorded audio duration: {duration_seconds}s")
        
        # Filter tones to create clean listening wav (same as what gets transcribed)
        filtered_audio = filter_known_tones(full_dispatch_audio, tone_name, AUDIO_SAMPLE_RATE, GOLDEN_FINGERPRINTS)
        
        # Convert to WAV bytes in memory
        wav_io = io.BytesIO()
        wavio.write(wav_io, filtered_audio, AUDIO_SAMPLE_RATE, sampwidth=2)
        audio_bytes = wav_io.getvalue()
        
        # 1. Save locally to frontend/public/recordings/ for local playback fallback
        local_url_path = f"/recordings/{dispatch_id}.wav"
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            local_dir = os.path.join(base_dir, "frontend", "public", "recordings")
            os.makedirs(local_dir, exist_ok=True)
            local_file_path = os.path.join(local_dir, f"{dispatch_id}.wav")
            logging.info(f"Saving audio locally to {local_file_path}...")
            with open(local_file_path, "wb") as f:
                f.write(audio_bytes)
        except Exception as e:
            logging.warning(f"Could not save audio locally to frontend/public/recordings: {e}")
            
        # Also save to backend/audio_files/recordings/ for records/debugging
        try:
            backend_rec_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio_files", "recordings")
            os.makedirs(backend_rec_dir, exist_ok=True)
            backend_file_path = os.path.join(backend_rec_dir, f"{dispatch_id}.wav")
            with open(backend_file_path, "wb") as f:
                f.write(audio_bytes)
        except Exception as e:
            logging.warning(f"Could not save audio locally to backend/audio_files/recordings: {e}")
            
        # 2. Upload to Supabase Storage
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        
        public_url = None
        if supabase_url and supabase_key:
            public_url = upload_to_supabase_storage(audio_bytes, f"{dispatch_id}.wav", supabase_url, supabase_key)
            
        # If upload succeeded, return the Supabase public URL. Otherwise, return the local fallback path.
        audio_url = public_url if public_url else local_url_path
        return audio_url, duration_seconds
        
    except Exception as e:
        logging.error(f"Error in save_and_upload_audio: {e}", exc_info=True)
        return None, 0.0

def process_full_dispatch(buffer, validator: CoquitlamDataValidator, tone_name: str, units_vocabulary: List[str], stt_model=None):
    """Processes a completed dispatch buffer: transcribes, geocodes, and posts integrations."""
    dispatch_id = f"DISP-{time.strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
    try:
        logging.info(f"--- STARTING DISPATCH PROCESSING (ID: {dispatch_id}) ---")
        if not buffer:
            logging.warning("Buffer empty, nothing to process.")
            return
            
        # 1. Combine and Filter Audio
        full_dispatch_audio = np.concatenate(buffer)
        filtered_audio = filter_known_tones(full_dispatch_audio, tone_name, AUDIO_SAMPLE_RATE, GOLDEN_FINGERPRINTS)
        
        # 2. Transcribe Audio (100% In-Memory)
        raw_transcript = None
        if STT_ENGINE == "google":
            wav_io = io.BytesIO()
            wavio.write(wav_io, filtered_audio, AUDIO_SAMPLE_RATE, sampwidth=2)
            audio_bytes = wav_io.getvalue()
            raw_transcript = transcribe_audio_bytes(audio_bytes)
        elif STT_ENGINE == "whisper":
            audio_float = filtered_audio.astype(np.float32) / 32768.0
            if len(audio_float.shape) > 1:
                audio_float = audio_float.squeeze()
            raw_transcript = transcribe_audio_local(audio_float, model=stt_model, validator=validator)
            
        if not raw_transcript:
            logging.warning("Transcription failed. Storing empty placeholder to allow manual review.")
            raw_transcript = "[Transcription Failed]"
            
        transcript = sanitize_transcript(raw_transcript)
        
        # 3. Parse announcements
        announcements = split_rounds(transcript, units_vocabulary)
        all_candidates = []
        for text in announcements:
            if len(text.split()) > 2:
                all_candidates.extend(parse_dispatch_announcement(text, units_vocabulary))
                
        # 4. Save and Upload Audio
        audio_url, audio_duration = save_and_upload_audio(dispatch_id, buffer, tone_name)
        
        # 5. Geocode and Post
        process_and_post_payload(dispatch_id, raw_transcript, transcript, all_candidates, validator, units_vocabulary,
                                 audio_url=audio_url, audio_duration=audio_duration)
    except Exception as e:
        logging.error(f"Error processing dispatch ID {dispatch_id}: {e}", exc_info=True)


def is_round_1_complete_check(dispatch_list: List[DispatchData], raw_transcript: str) -> bool:
    """Determines if the first round of the dispatch announcement is complete using map grid and unit repetition heuristics."""
    if not dispatch_list:
        return False
    
    # We need at least one candidate with a parsed address or intersection
    candidate = next((d for d in dispatch_list if d.address or d.intersection), None)
    if not candidate:
        return False
        
    # Check if we have units and call type
    has_units = candidate.units is not None and len(candidate.units) > 0
    has_call_type = candidate.call_type is not None and candidate.call_type != "Unknown Incident"
    
    if has_units and has_call_type:
        # Primary Trigger: "Map Grid < 200"
        has_grid_less_than_200 = False
        if candidate.map_grid:
            try:
                # Remove non-digits
                clean_grid = "".join(filter(str.isdigit, candidate.map_grid))
                if clean_grid:
                    grid_num = int(clean_grid)
                    if grid_num < 200:
                        has_grid_less_than_200 = True
            except ValueError:
                pass
        
        # Fallback check raw_transcript for "grid" and some digits
        if not has_grid_less_than_200:
            grid_matches = re.findall(r'\b(?:grid|grade)\s*(\d{1,3})\b', raw_transcript.lower())
            for gm in grid_matches:
                try:
                    if int(gm) < 200:
                        has_grid_less_than_200 = True
                        break
                except ValueError:
                    pass
                    
        # Secondary Trigger: Unit repetition (the exact same unit+number appears twice, e.g. "engine 2" ... "engine 2")
        has_unit_repetition = False
        unit_vocab_pattern = '|'.join(u.lower() for u in UNITS_VOCABULARY)
        unit_pairs = re.findall(rf'\b({unit_vocab_pattern})\s+(\d+)\b', raw_transcript.lower())
        if unit_pairs:
            from collections import Counter
            counts = Counter(unit_pairs)
            if any(count >= 2 for count in counts.values()):
                has_unit_repetition = True
                
        if has_grid_less_than_200 or has_unit_repetition:
            return True
            
    return False


def process_phase_1_check(task: dict, validator: CoquitlamDataValidator, stt_model, triggered_phase_1_ids: set, phase_1_trigger_lengths: dict, phase_1_candidates: dict):
    """Worker function to transcribe, parse, and trigger Phase 1 if complete."""
    dispatch_id = task["dispatch_id"]
    buffer = task["buffer"]
    tone_name = task["tone_name"]
    units_vocab = task["units_vocab"]
    
    if dispatch_id in triggered_phase_1_ids:
        return
        
    try:
        # 1. Combine and Filter Audio
        full_dispatch_audio = np.concatenate(buffer)
        filtered_audio = filter_known_tones(full_dispatch_audio, tone_name, AUDIO_SAMPLE_RATE, GOLDEN_FINGERPRINTS)
        
        # 2. Transcribe Audio (100% In-Memory)
        raw_transcript = None
        if STT_ENGINE == "google":
            wav_io = io.BytesIO()
            wavio.write(wav_io, filtered_audio, AUDIO_SAMPLE_RATE, sampwidth=2)
            audio_bytes = wav_io.getvalue()
            raw_transcript = transcribe_audio_bytes(audio_bytes)
        elif STT_ENGINE == "whisper":
            audio_float = filtered_audio.astype(np.float32) / 32768.0
            if len(audio_float.shape) > 1:
                audio_float = audio_float.squeeze()
            raw_transcript = transcribe_audio_local(audio_float, model=stt_model, validator=validator)
            
        if not raw_transcript:
            return
            
        transcript = sanitize_transcript(raw_transcript)
        
        # 3. Parse announcements
        announcements = split_rounds(transcript, units_vocab)
        all_candidates = []
        for text in announcements:
            if len(text.split()) > 2:
                all_candidates.extend(parse_dispatch_announcement(text, units_vocab))
                
        # 4. Check if complete
        if is_round_1_complete_check(all_candidates, transcript):
            logging.info(f"--- PHASE 1 SEMANTIC TRIGGER MET FOR DISPATCH {dispatch_id} ---")
            
            # Post Phase 1 payload to Supabase
            db_payload, responding_units = process_and_post_payload(
                dispatch_id, raw_transcript, transcript, all_candidates, validator, units_vocab, verify_location_override=False
            )
            
            if db_payload:
                # Success! Save state in worker memory
                triggered_phase_1_ids.add(dispatch_id)
                phase_1_trigger_lengths[dispatch_id] = len(buffer)
                phase_1_candidates[dispatch_id] = {
                    "raw_transcript": raw_transcript,
                    "transcript": transcript,
                    "candidates": all_candidates,
                    "units": responding_units,
                    "target": db_payload.get("target") or {"address": db_payload.get("address")}
                }
    except Exception as e:
        logging.error(f"Error in process_phase_1_check for ID {dispatch_id}: {e}", exc_info=True)


def process_phase_2_finalize(task: dict, validator: CoquitlamDataValidator, stt_model, triggered_phase_1_ids: set, phase_1_trigger_lengths: dict, phase_1_candidates: dict):
    """Worker function to process the completed dispatch audio, verify, and correct if necessary."""
    dispatch_id = task["dispatch_id"]
    buffer = task["buffer"]
    tone_name = task["tone_name"]
    units_vocab = task["units_vocab"]
    
    try:
        logging.info(f"--- STARTING PHASE 2 FINALIZE PROCESSING (ID: {dispatch_id}) ---")
        
        # Save and Upload Audio
        audio_url, audio_duration = save_and_upload_audio(dispatch_id, buffer, tone_name)
        
        # Retrieve Phase 1 trigger point
        p1_len = phase_1_trigger_lengths.get(dispatch_id, 0)
        p1_data = phase_1_candidates.get(dispatch_id)
        
        # If Phase 1 triggered, we slice and transcribe the second round only to bypass de-duplication
        if p1_data and p1_len > 0 and p1_len < len(buffer):
            logging.info(f"Phase 1 was triggered at block {p1_len}/{len(buffer)}. Slicing buffer for Round 2.")
            second_round_buffer = buffer[p1_len:]
        else:
            logging.info("Phase 1 was not triggered (or buffer invalid). Transcribing full audio as fallback.")
            second_round_buffer = buffer
            p1_data = None
            
        # 1. Combine and Filter Audio
        full_dispatch_audio = np.concatenate(second_round_buffer)
        filtered_audio = filter_known_tones(full_dispatch_audio, tone_name, AUDIO_SAMPLE_RATE, GOLDEN_FINGERPRINTS)
        
        # 2. Transcribe Audio (100% In-Memory)
        raw_transcript = None
        if STT_ENGINE == "google":
            wav_io = io.BytesIO()
            wavio.write(wav_io, filtered_audio, AUDIO_SAMPLE_RATE, sampwidth=2)
            audio_bytes = wav_io.getvalue()
            raw_transcript = transcribe_audio_bytes(audio_bytes)
        elif STT_ENGINE == "whisper":
            audio_float = filtered_audio.astype(np.float32) / 32768.0
            if len(audio_float.shape) > 1:
                audio_float = audio_float.squeeze()
            raw_transcript = transcribe_audio_local(audio_float, model=stt_model, validator=validator)
            
        if not raw_transcript:
            logging.warning("Phase 2 transcription failed. Storing empty placeholder to allow manual review.")
            raw_transcript = "[Transcription Failed]"
            
        transcript = sanitize_transcript(raw_transcript)
        logging.info(f"Phase 2 Sanitized Transcript: '{transcript}'")
        
        # 3. Parse announcements
        announcements = split_rounds(transcript, units_vocab)
        all_candidates = []
        for text in announcements:
            if len(text.split()) > 2:
                all_candidates.extend(parse_dispatch_announcement(text, units_vocab))
                
        # 4. Handle DB insertion/update
        if not p1_data:
            # Fallback: Phase 1 never triggered, so we just treat this as a standard single-phase run
            logging.info("Phase 1 fallback: Inserting new record in single-phase mode.")
            process_and_post_payload(dispatch_id, raw_transcript, transcript, all_candidates, validator, units_vocab,
                                     audio_url=audio_url, audio_duration=audio_duration)
        else:
            # Phase 1 did trigger! We compare Phase 2 with Phase 1 to verify or correct
            p1_candidate = next((d for d in p1_data["candidates"] if d.address or d.intersection), None)
            p2_candidate = next((d for d in all_candidates if d.address or d.intersection), None)
            
            p1_addr = (p1_candidate.address or p1_candidate.intersection or "").lower() if p1_candidate else ""
            p2_addr = (p2_candidate.address or p2_candidate.intersection or "").lower() if p2_candidate else ""
            
            # Combine Phase 1 and Phase 2 transcripts
            p1_raw = p1_data.get("raw_transcript") or p1_data.get("transcript") or ""
            p1_sanitized = p1_data.get("transcript") or ""
            
            full_raw = f"{p1_raw} {raw_transcript}".strip() if p1_raw else raw_transcript
            full_sanitized = f"{p1_sanitized} {transcript}".strip() if p1_sanitized else transcript
            
            # Compare addresses
            addresses_match = p1_addr == p2_addr and p1_addr != ""
            
            supabase_url = os.environ.get("SUPABASE_URL")
            supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
            
            if addresses_match:
                logging.info(f"Phase 2 verification: Address matches Phase 1 ('{p1_candidate.address or p1_candidate.intersection}'). Updating database record to verified.")
                # Update Supabase record status to verified (verify_location=False)
                if supabase_url and supabase_key:
                    update_payload = {
                        "verify_location": False,
                        "confidence_score": 100.0,  # Boost confidence to 100% since both rounds verified it
                        "audio_url": audio_url,
                        "audio_duration": audio_duration,
                        "raw_transcript": full_raw,
                        "sanitized_transcript": full_sanitized
                    }
                    update_supabase_record(dispatch_id, update_payload, supabase_url, supabase_key)
            else:
                logging.warning(f"Phase 2 verification MISMATCH: Phase 1 address was '{p1_addr}', Phase 2 is '{p2_addr}'.")
                
                # If Phase 2 geocoding succeeds and has a valid candidate, correct the record!
                if p2_candidate:
                    logging.info("Attempting geocoding for Phase 2 corrected address...")
                    unique_addresses = [p2_candidate.address or p2_candidate.intersection]
                    
                    # Run offline geocoding
                    res = validator.local_geocode(unique_addresses[0])
                    if res:
                        logging.info(f"Phase 2 geocoding corrected match SUCCEEDED: '{res['address']}' (Score: {res['confidence']}%)")
                        target_payload = {
                            "address": res["address"],
                            "lat": res["lat"],
                            "lng": res["lng"],
                            "rings": res["rings"]
                        }
                        
                        # Prepare update payload
                        update_payload = {
                            "verify_location": False,
                            "confidence_score": float(res["confidence"]),
                            "audio_url": audio_url,
                            "audio_duration": audio_duration,
                            "raw_transcript": full_raw,
                            "sanitized_transcript": full_sanitized
                        }
                        if INTEGRATION_PAYLOAD_OPTION == 1:
                            update_payload["address"] = res["address"]
                        else:
                            update_payload["target"] = target_payload
                            
                        # Update Supabase
                        if supabase_url and supabase_key:
                            update_supabase_record(dispatch_id, update_payload, supabase_url, supabase_key)
                            
                        # Send correction push notification
                        if ENABLE_NTFY_PUSH:
                            ntfy_topic = os.environ.get("NTFY_TOPIC")
                            ntfy_token = os.environ.get("NTFY_TOKEN")
                            if ntfy_topic:
                                corr_payload = {
                                    "dispatch_id": dispatch_id,
                                    "incident_type": match_incident_type(transcript, CALL_TYPES),
                                    "responding_units": abbreviate_units(p2_candidate.units),
                                    "lat": res["lat"],
                                    "lng": res["lng"],
                                    "target": target_payload
                                }
                                try:
                                    post_to_ntfy(
                                        corr_payload,
                                        ntfy_topic,
                                        ntfy_token,
                                        title=f"CORRECTION: Dispatch {dispatch_id}",
                                        tags="warning,rotating_light"
                                    )
                                except Exception as n_err:
                                    logging.error(f"Failed to post correction to Ntfy: {n_err}")
                    else:
                        # Geocoding failed for Phase 2 as well, keep Phase 1 but mark as verify_location=True
                        logging.warning("Phase 2 geocoding failed. Keeping Phase 1 data but flagging verify_location=True.")
                        if supabase_url and supabase_key:
                            update_payload = {
                                "verify_location": True,
                                "audio_url": audio_url,
                                "audio_duration": audio_duration,
                                "raw_transcript": full_raw,
                                "sanitized_transcript": full_sanitized
                            }
                            update_supabase_record(dispatch_id, update_payload, supabase_url, supabase_key)
                else:
                    # No Phase 2 candidate found (e.g. dispatcher override, noise, cutoff)
                    # Gracefully fallback: keep Phase 1 data, mark as verified=True
                    logging.info("No valid candidate in Phase 2. Keeping Phase 1 data as verified.")
                    if supabase_url and supabase_key:
                        update_payload = {
                            "verify_location": False,
                            "audio_url": audio_url,
                            "audio_duration": audio_duration,
                            "raw_transcript": full_raw,
                            "sanitized_transcript": full_sanitized
                        }
                        update_supabase_record(dispatch_id, update_payload, supabase_url, supabase_key)
                        
    except Exception as e:
        logging.error(f"Error in process_phase_2_finalize for ID {dispatch_id}: {e}", exc_info=True)
    finally:
        # Clean up memory state
        triggered_phase_1_ids.discard(dispatch_id)
        phase_1_trigger_lengths.pop(dispatch_id, None)
        phase_1_candidates.pop(dispatch_id, None)

def get_audio_duration(file_path: str) -> float:
    """Helper to retrieve audio duration in seconds using wavio, PyAV, or fallbacks."""
    try:
        if file_path.lower().endswith('.wav'):
            import wavio
            w = wavio.read(file_path)
            return round(w.data.shape[0] / w.rate, 2)
    except Exception:
        pass
    try:
        import av
        with av.open(file_path) as container:
            duration = float(container.duration) / av.time_base
            return round(duration, 2)
    except Exception:
        pass
    return 30.0

def poll_dispatch_uploads(validator, stt_model):
    """Polls Supabase for pending dispatch uploads, transcribes and parses, then saves the result."""
    import requests
    import json
    import os
    import tempfile
    
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        return
        
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/dispatch_uploads?status=eq.pending"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(endpoint, headers=headers, timeout=10)
        response.raise_for_status()
        pending_requests = response.json()
        
        for req in pending_requests:
            req_id = req.get("id")
            audio_url = req.get("audio_url")
            verified_transcript = req.get("verified_transcript")
            
            logging.info(f"Processing dispatch upload {req_id}...")
            
            # Update status to processing
            patch_endpoint = f"{supabase_url.rstrip('/')}/rest/v1/dispatch_uploads?id=eq.{req_id}"
            requests.patch(patch_endpoint, headers=headers, json={"status": "processing"}, timeout=10)
            
            try:
                # Download audio file
                download_url = audio_url
                if "/object/public/" in audio_url:
                    download_url = audio_url.replace("/object/public/", "/object/authenticated/")
                    
                logging.info(f"Downloading upload audio from: {download_url}")
                audio_headers = {
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}"
                }
                audio_response = requests.get(download_url, headers=audio_headers, timeout=20)
                audio_response.raise_for_status()
                audio_bytes = audio_response.content
                
                suffix = ".wav"
                if ".mp3" in audio_url.lower():
                    suffix = ".mp3"
                    
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                    temp_file.write(audio_bytes)
                    temp_path = temp_file.name
                    
                try:
                    # Get duration
                    audio_duration = get_audio_duration(temp_path)
                    
                    # Run speech to text
                    raw_transcript = None
                    if STT_ENGINE == "google":
                        raw_transcript = transcribe_audio_bytes(audio_bytes)
                    elif STT_ENGINE == "whisper":
                        is_faster_whisper = stt_model and hasattr(stt_model, 'transcribe') and not hasattr(stt_model, 'load_model')
                        if is_faster_whisper:
                            raw_transcript = transcribe_audio_local(temp_path, model=stt_model, validator=validator)
                        else:
                            try:
                                import whisper
                                audio_float = whisper.load_audio(temp_path)
                                raw_transcript = transcribe_audio_local(audio_float, model=stt_model, validator=validator)
                            except Exception as w_err:
                                logging.warning(f"Standard Whisper load failed (likely ffmpeg missing): {w_err}. Trying direct path...")
                                raw_transcript = transcribe_audio_local(temp_path, model=stt_model, validator=validator)
                            
                    if not raw_transcript:
                        raise ValueError("Speech-to-Text did not produce any transcript text.")
                        
                    transcript = sanitize_transcript(raw_transcript)
                    logging.info(f"Upload transcribed: '{transcript}'")
                    
                    # Parse incident rounds (split by map grid/unit repetitions)
                    announcements = split_rounds(transcript, UNITS_VOCABULARY)
                    all_candidates = []
                    for text in announcements:
                        if len(text.split()) > 2:
                            all_candidates.extend(parse_dispatch_announcement(text, UNITS_VOCABULARY))
                            
                    # Check for double rounds
                    second_round_recorded = False
                    second_round_matched = False
                    
                    if len(all_candidates) >= 2:
                        second_round_recorded = True
                        p1 = all_candidates[0]
                        p2 = all_candidates[1]
                        p1_addr = (p1.address or p1.intersection or "").lower()
                        p2_addr = (p2.address or p2.intersection or "").lower()
                        if p1_addr == p2_addr and p1_addr != "":
                            second_round_matched = True
                            
                    # Geocode and run pipeline to post to live_calls
                    dispatch_id = f"UPL-{time.strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
                    
                    db_payload, responding_units = process_and_post_payload(
                        dispatch_id=dispatch_id,
                        raw_transcript=raw_transcript,
                        sanitized_transcript=transcript,
                        all_candidates=all_candidates,
                        validator=validator,
                        units_vocabulary=UNITS_VOCABULARY,
                        verify_location_override=False,
                        audio_url=audio_url,
                        audio_duration=audio_duration,
                        verified_transcript=verified_transcript
                    )
                    
                    if not db_payload:
                        raise ValueError("No valid address or intersection details could be geocoded from the transcript.")
                        
                    # Calculate transcript similarity score if verified transcript is provided
                    accuracy = 100.0
                    if verified_transcript:
                        from thefuzz import fuzz
                        clean_stt = " ".join(transcript.lower().split())
                        clean_verified = " ".join(verified_transcript.lower().split())
                        accuracy = float(fuzz.ratio(clean_stt, clean_verified))
                        
                    # Gather coordinates and details
                    target_obj = db_payload.get("target") or {
                        "address": db_payload.get("address") or "Unknown Location",
                        "lat": None,
                        "lng": None,
                        "rings": []
                    }
                    
                    result_payload = {
                        "dispatch_id": dispatch_id,
                        "timestamp": db_payload.get("timestamp"),
                        "incident_type": db_payload.get("incident_type"),
                        "responding_units": db_payload.get("responding_units", []),
                        "target": target_obj,
                        "address": target_obj.get("address"),
                        "raw_transcript": raw_transcript,
                        "sanitized_transcript": transcript,
                        "confidence_score": db_payload.get("confidence_score", 0.0),
                        "verify_location": False,
                        "radio_channel": next((d.radio_channel for d in all_candidates if d.radio_channel), None),
                        "map_grid": next((d.map_grid for d in all_candidates if d.map_grid), None),
                        "second_round_recorded": second_round_recorded,
                        "second_round_matched": second_round_matched,
                        "verified_transcript": verified_transcript,
                        "transcript_accuracy": accuracy,
                        "audio_url": audio_url,
                        "audio_duration": audio_duration
                    }
                    
                    # Update status to completed
                    requests.patch(
                        patch_endpoint,
                        headers=headers,
                        json={
                            "status": "completed",
                            "result": result_payload
                        },
                        timeout=10
                    )
                    logging.info(f"Upload {req_id} completed. Posted Dispatch ID: {dispatch_id}")
                    
                finally:
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass
                            
            except Exception as e:
                logging.error(f"Error processing dispatch upload: {e}", exc_info=True)
                requests.patch(
                    patch_endpoint,
                    headers=headers,
                    json={
                        "status": "failed",
                        "error_message": str(e)
                    },
                    timeout=10
                )
    except Exception as e:
        logging.error(f"Failed to poll dispatch uploads: {e}")

def start_dispatch_upload_poller(validator, stt_model):
    """Starts the dispatch uploads polling loop in a daemon background thread."""
    import threading
    
    def poll_thread():
        logging.info("Starting dispatch uploads poller thread...")
        while True:
            try:
                poll_dispatch_uploads(validator, stt_model)
            except Exception as e:
                logging.error(f"Error in dispatch uploads poller thread: {e}")
            time.sleep(5.0)
            
    t = threading.Thread(target=poll_thread, name="DispatchUploadPoller", daemon=True)
    t.start()

def background_worker_loop(task_queue: multiprocessing.Queue):
    """
    Background worker loop. Run in a separate Process.
    Initializes GIS validator and loads/caches the speech-to-text models once at startup.
    """
    setup_logging()
    logging.info("Background Dispatch Worker process starting...")
    try:
        validator = CoquitlamDataValidator(
            ADDRESS_SHAPEFILE_PATH,
            ZONES_SHAPEFILE_PATH,
            house_num_col=ADDRESS_HOUSE_NUM_COLUMN,
            street_name_col=ADDRESS_STREET_NAME_COLUMN,
            street_type_col=ADDRESS_STREET_TYPE_COLUMN,
            full_addr_col=ADDRESS_FULL_ADDR_COLUMN,
            zone_map_name_col=ZONES_MAP_NAME_COLUMN,
            street_confidence_threshold=STREET_NAME_CONFIDENCE_THRESHOLD
        )
        logging.info("Background Dispatch Worker process initialized and ready.")
    except Exception as e:
        logging.critical(f"Failed to initialize validator in worker process: {e}", exc_info=True)
        return
        
    stt_model = None
    if STT_ENGINE == "whisper":
        try:
            device = "cpu"
            compute_type = "int8"
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                    compute_type = "float16"
            except ImportError:
                pass
            
            logging.info(f"Pre-loading local STT engine '{WHISPER_MODEL}' on {device} ({compute_type})...")
            try:
                from faster_whisper import WhisperModel
                stt_model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)
                logging.info("faster-whisper model pre-loaded successfully.")
            except ImportError:
                import whisper
                stt_model = whisper.load_model(WHISPER_MODEL, device=device)
                logging.info("standard whisper model pre-loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to pre-load Whisper model: {e}. Will load on demand.", exc_info=True)

    # Start dispatch uploads poller thread
    start_dispatch_upload_poller(validator, stt_model)

    triggered_phase_1_ids = set()
    phase_1_trigger_lengths = {}
    phase_1_candidates = {}

    while True:
        try:
            task = task_queue.get()
            if task is None: # Poison pill
                break
            if isinstance(task, dict):
                task_type = task.get("type")
                if task_type == "phase_1_check":
                    process_phase_1_check(
                        task, validator, stt_model,
                        triggered_phase_1_ids, phase_1_trigger_lengths, phase_1_candidates
                    )
                elif task_type == "phase_2_finalize":
                    process_phase_2_finalize(
                        task, validator, stt_model,
                        triggered_phase_1_ids, phase_1_trigger_lengths, phase_1_candidates
                    )
            else:
                # Backwards compatibility
                buffer, tone_name, units_vocab = task
                process_full_dispatch(buffer, validator, tone_name, units_vocab, stt_model)
        except Exception as e:
            logging.error(f"Error in background worker processing task: {e}", exc_info=True)

def run_dispatch_system():
    """Main program entrypoint. Initiates audio stream and tone triggers."""
    setup_logging()
    
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        logging.critical("FATAL ERROR: Missing required environment variables (SUPABASE_URL, SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY).")
        return
        
    if STT_ENGINE == "google" and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        logging.critical("FATAL ERROR: STT_ENGINE is set to 'google' but GOOGLE_APPLICATION_CREDENTIALS is not set.")
        return
        
    if ENABLE_NTFY_PUSH and not os.environ.get("NTFY_TOPIC"):
        logging.warning("ENABLE_NTFY_PUSH is True but NTFY_TOPIC is not set. Push notifications will be skipped.")
        

    
    # Spawn background processor process
    global dispatch_queue
    logging.info("Starting background worker process...")
    worker_process = multiprocessing.Process(target=background_worker_loop, args=(dispatch_queue,), daemon=True)
    worker_process.start()

    # Audio device query
    logging.info("Initializing Audio Input Stream Listener...")
    blocksize = 1024
    try:
        with sd.InputStream(samplerate=AUDIO_SAMPLE_RATE, channels=1, blocksize=blocksize, dtype='int16', device=DEVICE_ID) as stream:
            try:
                device_info = sd.query_devices(stream.device, 'input')
                logging.info(f"Successfully opened audio stream on: '{device_info.get('name', 'Unknown')}'")
            except Exception as e:
                logging.warning(f"Could not query audio device name: {e}")
            time.sleep(1.0)
            
            while True:
                logging.info("STATE: LISTENING_FOR_TONE")
                loudness_history = deque(maxlen=SUSTAINED_LOUDNESS_WINDOW)
                history_audio_buffer = deque(maxlen=SUSTAINED_LOUDNESS_WINDOW)
                is_capturing_tone, analysis_buffer, last_log_time, matched_tone = False, [], 0, None
                
                # Rolling history of quiet RMS values to compute adaptive baseline
                baseline_rms_history = deque(maxlen=50)
                baseline_rms_history.append(NOISE_AMPLITUDE_THRESHOLD / 2.5)

                while True:
                    if is_capturing_tone:
                        pcm, _ = stream.read(blocksize)
                        analysis_buffer.append(pcm)
                        if len(analysis_buffer) * blocksize >= TONE_ANALYSIS_DURATION_SECONDS * AUDIO_SAMPLE_RATE:
                            logging.info("Analyzing captured audio for a dispatch tone...")
                            full_sample_np = np.concatenate(analysis_buffer)
                            live_frequencies = analyze_live_audio(full_sample_np.tobytes(), AUDIO_SAMPLE_RATE, NUM_PEAKS_TO_FIND, TONE_ZSCORE_THRESHOLD)
                            matched_tone, score = get_best_match(live_frequencies, GOLDEN_FINGERPRINTS, FREQUENCY_TOLERANCE_HZ, MATCH_THRESHOLD_PERCENT)
                            if matched_tone:
                                logging.info(f"TONE CONFIRMED: '{matched_tone}' (Match: {score*100:.0f}%)")
                                break
                            else:
                                logging.info("Triggered sound was not a recognized tone, resetting.")
                                is_capturing_tone = False
                                # Reset baseline when false-trigger occurs to prevent bias
                                baseline_rms_history.clear()
                                baseline_rms_history.append(NOISE_AMPLITUDE_THRESHOLD / 2.5)
                                continue
                        else:
                            continue

                    pcm, _ = stream.read(blocksize)
                    history_audio_buffer.append(pcm)
                    rms = get_rms(pcm)
                    
                    # Update background quiet noise baseline if current RMS is not abnormally high
                    if rms < NOISE_AMPLITUDE_THRESHOLD * 1.5:
                        baseline_rms_history.append(rms)
                        
                    current_baseline = np.mean(baseline_rms_history) if baseline_rms_history else (NOISE_AMPLITUDE_THRESHOLD / 2.5)
                    # Adaptive threshold is at least the noise floor threshold, or 2.5x the rolling background noise baseline
                    current_threshold = max(NOISE_AMPLITUDE_THRESHOLD, current_baseline * 2.5)

                    current_time = time.time()
                    if VERBOSITY_LEVEL >= 3 and current_time - last_log_time >= 5.0:
                        logging.debug(f"Listening... RMS: {int(rms):<5} | Threshold: {int(current_threshold):<5} | Loud Chunks: {sum(loudness_history)}/{SUSTAINED_LOUDNESS_CHUNKS_REQUIRED}")
                        last_log_time = current_time

                    is_currently_loud = rms > current_threshold
                    loudness_history.append(is_currently_loud)
                    
                    if not is_capturing_tone and sum(loudness_history) >= SUSTAINED_LOUDNESS_CHUNKS_REQUIRED:
                        logging.info(f"Sustained loud sound detected! Capturing for {TONE_ANALYSIS_DURATION_SECONDS}s to analyze...")
                        is_capturing_tone = True
                        analysis_buffer = list(history_audio_buffer)
                        loudness_history.clear()

                # Dispatch Capture
                dispatch_id = f"DISP-{time.strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
                dispatch_buffer = capture_full_dispatch(
                    stream,
                    blocksize,
                    dispatch_queue,
                    dispatch_id,
                    matched_tone,
                    initial_buffer=analysis_buffer,
                    sample_rate=AUDIO_SAMPLE_RATE,
                    max_duration_s=MAX_DISPATCH_DURATION_S,
                    min_phase_1_duration_s=MIN_PHASE_1_DURATION_S,
                    phase_1_check_interval_s=PHASE_1_CHECK_INTERVAL_S,
                    end_of_dispatch_rms_threshold=END_OF_DISPATCH_RMS_THRESHOLD,
                    end_of_dispatch_silence_s=END_OF_DISPATCH_SILENCE_S,
                    units_vocabulary=UNITS_VOCABULARY
                )
                if dispatch_buffer:
                    logging.info(f"Queueing finalized dispatch ID {dispatch_id} for background processor core...")
                    dispatch_queue.put({
                        "type": "phase_2_finalize",
                        "dispatch_id": dispatch_id,
                        "buffer": list(dispatch_buffer),
                        "tone_name": matched_tone,
                        "units_vocab": UNITS_VOCABULARY
                    })

                logging.info(f"Waiting for {POST_EVENT_RESET_SILENCE_S}s of silence before resetting...")
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
        # Poison pill worker
        dispatch_queue.put(None)
        logging.info("System shut down.")
