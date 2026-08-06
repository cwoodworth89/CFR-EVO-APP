# cfr_dispatch/orchestration.py
# System orchestration, audio capture, and background process worker loops

import os
import io
import re
import time
import uuid
import datetime
import json
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
    resolve_audio_device,
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
    get_all_matches,
    filter_known_tones,
    capture_full_dispatch
)
from cfr_dispatch.parser import (
    sanitize_transcript,
    match_incident_type,
    abbreviate_units,
    parse_dispatch_announcement,
    split_rounds,
    reconstruct_template_transcript,
    merge_units,
    CALL_TYPES
)
from cfr_dispatch.offline_sync import start_offline_sync_poller, queue_offline_dispatch
from gis_service import CoquitlamDataValidator
from notification_service import (
    save_dispatch_record,
    post_to_ntfy,
    update_dispatch_record,
    save_audio_recording,
    post_to_supabase,
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

def clean_address_string(addr: str) -> str:
    if not addr:
        return addr
    addr = re.sub(r',\s*[A-Z]\d[A-Z]\s*\d[A-Z]\d', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r',\s*(BC|British Columbia)\b.*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r',\s*Canada\b.*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r',\s*Coquitlam\b.*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r',\s*Port Coquitlam\b.*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r',\s*Port Moody\b.*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\s*\(\s*Street\s+Centroid\s*\)', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bStreet\s+Centroid\b', '', addr, flags=re.IGNORECASE)
    return addr.strip()

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

_cached_hitl_streets = []
_last_hitl_fetch_time = 0.0

def get_hitl_verified_streets() -> list[str]:
    """
    Fetches the most frequently misheard street names that required HITL correction.
    Cached in memory for 10 minutes to prevent blocking network requests during transcription.
    """
    global _cached_hitl_streets, _last_hitl_fetch_time
    now = time.time()
    if _cached_hitl_streets and (now - _last_hitl_fetch_time < 600.0):
        return _cached_hitl_streets

    try:
        local_api_url = os.environ.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")
        endpoint = f"{local_api_url}/api/dispatches?limit=200"
        response = requests.get(endpoint, timeout=3)
        response.raise_for_status()
        records = response.json()
        
        from collections import defaultdict
        tally = defaultdict(int)
        
        for r in records:
            if not r.get("feedback_submitted"):
                continue
            verified_addr = r.get("verified_address")
            system_addr = r.get("address") or (r.get("target", {}).get("address") if r.get("target") else None)

                
            if not verified_addr:
                continue
                
            def clean_street(addr_str):
                if not addr_str:
                    return ""
                match = re.search(r'^\d+\s+(?P<street>.*)', addr_str.split(',')[0].strip())
                if match:
                    return match.group('street').strip().title()
                return addr_str.strip().title()
                
            v_street = clean_street(verified_addr)
            sys_street = clean_street(system_addr)
            
            if v_street and sys_street and v_street != sys_street:
                tally[v_street] += 1
                
        sorted_streets = sorted(tally.keys(), key=lambda s: tally[s], reverse=True)
        _cached_hitl_streets = sorted_streets
        _last_hitl_fetch_time = now
        return sorted_streets
    except Exception as e:
        logging.warning(f"Failed to fetch HITL verified streets for STT hotwords: {e}")
        return _cached_hitl_streets

def build_stt_bias_words(validator, units_vocabulary=None) -> tuple[str, str]:
    base_words = [
        "Coquitlam", "respond", "routine", "emergency", "Combined Response Coquitlam",
        "use talk group", "map grid", "medical aid", "overdose", "lift assist", 
        "structure fire", "alarm activated"
    ]
    if units_vocabulary and isinstance(units_vocabulary, (list, set)):
        base_words.extend([str(u).title() for u in units_vocabulary])
    
    # Fetch HITL verified streets to bias Whisper dynamically toward corrected addresses
    hitl_streets = get_hitl_verified_streets()
    
    streets = []
    if validator:
        try:
            if hasattr(validator, 'addresses_gdf') and validator.addresses_gdf is not None:
                col = validator.street_name_col
                street_counts = validator.addresses_gdf[col].dropna().value_counts()
                top_streets = street_counts.head(30).index.tolist()
                streets = [str(s).title() for s in top_streets if len(str(s).strip()) > 1]
        except Exception as e:
            logging.warning(f"Failed to fetch unique streets for STT hotwords: {e}")
            
    all_terms = list(dict.fromkeys(base_words + hitl_streets + streets))
    all_terms = all_terms[:45]
    
    hotwords_str = ", ".join(all_terms)
    initial_prompt_str = ", ".join(all_terms)
    return initial_prompt_str, hotwords_str

def transcribe_audio_local(audio_data, model=None, validator=None) -> str | None:
    """
    Transcribes audio (NumPy array or file path) locally using a pre-loaded/cached
    faster-whisper model with street/unit phrase biasing and VAD filtering.
    """
    try:
        if model is None:
            from faster_whisper import WhisperModel
            logging.info(f"Loading local faster-whisper model '{WHISPER_MODEL}' on demand...")
            model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")

        is_faster_whisper = hasattr(model, 'transcribe') and not hasattr(model, 'load_model')
        
        if validator is None:
            validator = get_shared_validator()
            
        initial_prompt, hotwords_str = build_stt_bias_words(validator, UNITS_VOCABULARY)
        
        if is_faster_whisper:
            logging.info("Transcribing using cached faster-whisper model with vocabulary boosting and VAD...")
            try:
                segments, info = model.transcribe(
                    audio_data, 
                    beam_size=2, 
                    language="en", 
                    initial_prompt=initial_prompt, 
                    hotwords=hotwords_str,
                    vad_filter=True,
                    condition_on_previous_text=False
                )
            except TypeError:
                segments, info = model.transcribe(
                    audio_data, 
                    beam_size=2, 
                    language="en", 
                    initial_prompt=initial_prompt,
                    vad_filter=True,
                    condition_on_previous_text=False
                )
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


def process_and_post_payload(dispatch_id, raw_transcript, sanitized_transcript, all_candidates, validator, units_vocabulary, verify_location_override=None, audio_url=None, audio_duration=None, verified_transcript=None, tone_name=None):
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
        best_address = clean_address_string(local_geocode_result["address"])
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
        if (not map_grid or str(map_grid).lower() == "none") and lat is not None and lng is not None:
            spatial_grid = validator.get_map_grid_for_point(lat, lng)
            if spatial_grid:
                map_grid = spatial_grid
                logging.info(f"Spatial fallback: Map grid auto-populated from emergency response zones -> '{map_grid}'")

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
            
        subaddress = next((d.subaddress for d in all_candidates if d.subaddress), None)
        target_payload = {
            "address": best_address,
            "lat": lat,
            "lng": lng,
            "rings": rings,
            "map_grid": map_grid,
            "radio_channel": radio_channel
        }
        if subaddress:
            target_payload["subaddress"] = subaddress
        if tone_name:
            if isinstance(tone_name, list):
                target_payload["captured_tones"] = tone_name
                target_payload["tone_name"] = ", ".join(tone_name)
            else:
                target_payload["tone_name"] = tone_name
                target_payload["captured_tones"] = [t.strip() for t in tone_name.split(",") if t.strip()]
        if all_candidates and all_candidates[0].intersection:
            target_payload["intersection"] = all_candidates[0].intersection
        
        # Post-Transcription Template Reconstruction
        reconstructed_transcript = sanitized_transcript
        if all_candidates and not is_specific_placeholder and best_address != "Unknown Location":
            try:
                candidate_copy = DispatchData(
                    raw_text=all_candidates[0].raw_text,
                    units=units_str,
                    response_type=all_candidates[0].response_type or "routine",
                    call_type=incident_type,
                    address=best_address,
                    intersection=all_candidates[0].intersection,
                    radio_channel=radio_channel,
                    map_grid=map_grid,
                    subaddress=subaddress
                )
                reconstructed_transcript = reconstruct_template_transcript(candidate_copy)
                logging.info(f"Reconstructed template transcript: '{reconstructed_transcript}'")
            except Exception as r_err:
                logging.warning(f"Failed to reconstruct template transcript: {r_err}")

        db_payload = {
            "dispatch_id": dispatch_id,
            "incident_type": incident_type,
            "responding_units": responding_units,
            "timestamp": timestamp,
            "raw_transcript": raw_transcript,
            "sanitized_transcript": reconstructed_transcript,
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
            success = post_to_supabase(db_payload, supabase_url, supabase_key)
            if not success:
                local_wav_path = None
                try:
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    local_wav_path = os.path.join(base_dir, "frontend", "public", "recordings", f"{dispatch_id}.wav")
                except Exception:
                    pass
                queue_offline_dispatch(dispatch_id, "insert", db_payload, local_wav_path)
            
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
            
        # Use local HTTP API gateway audio path for offline station reliability
        local_api_audio_url = f"/api/audio/{dispatch_id}.wav"
        
        # Optional: Upload to Supabase Storage if configured (background backup)
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        if supabase_url and supabase_key:
            try:
                upload_to_supabase_storage(audio_bytes, f"{dispatch_id}.wav", supabase_url, supabase_key)
            except Exception as e:
                logging.warning(f"Supabase storage upload fallback skipped: {e}")
            
        return local_api_audio_url, duration_seconds
        
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
                dispatch_id, raw_transcript, transcript, all_candidates, validator, units_vocab, verify_location_override=False, tone_name=tone_name
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
        
        # 1. Combine and Filter Full Audio (do not slice mid-audio to preserve complete context)
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
                                     audio_url=audio_url, audio_duration=audio_duration, tone_name=tone_name)
        else:
            # Phase 1 did trigger! We compare Phase 2 with Phase 1 to verify or correct
            p1_candidate = next((d for d in p1_data["candidates"] if d.address or d.intersection), None)
            p2_candidate = next((d for d in all_candidates if d.address or d.intersection), None)
            
            p1_addr = (p1_candidate.address or p1_candidate.intersection or "").lower() if p1_candidate else ""
            p2_addr = (p2_candidate.address or p2_candidate.intersection or "").lower() if p2_candidate else ""
            
            full_raw = raw_transcript
            full_sanitized = transcript
            
            # Compare addresses
            addresses_match = p1_addr == p2_addr and p1_addr != ""
            
            supabase_url = os.environ.get("SUPABASE_URL")
            supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
            
            p1_target = p1_data.get("target") or {} if p1_data else {}
            
            if addresses_match:
                logging.info(f"Phase 2 verification: Address matches Phase 1 ('{p1_candidate.address or p1_candidate.intersection}'). Updating database record to verified.")
                
                # Parse units, grid, channel, incident type from Phase 2 (merge with Phase 1 units to prevent dropping units)
                p1_units = p1_candidate.units if p1_candidate else None
                p2_units = p2_candidate.units if p2_candidate else None
                p2_units_str = merge_units(p1_units, p2_units) if (p1_units or p2_units) else None
                p2_responding_units = abbreviate_units(p2_units_str) if p2_units_str else []
                p2_grid = next((d.map_grid for d in all_candidates if d.map_grid), (p1_candidate.map_grid if p1_candidate else None))
                if (not p2_grid or str(p2_grid).lower() == "none") and p1_target and p1_target.get("lat") is not None and p1_target.get("lng") is not None:
                    p2_grid = validator.get_map_grid_for_point(p1_target["lat"], p1_target["lng"])
                p2_channel = next((d.radio_channel for d in all_candidates if d.radio_channel), (p1_candidate.radio_channel if p1_candidate else None))
                p2_incident_type = match_incident_type(full_sanitized, CALL_TYPES)
                
                # Reconstruct template
                reconstructed_transcript = full_sanitized
                best_p2_candidate = p2_candidate or p1_candidate
                if best_p2_candidate:
                    try:
                        candidate_copy = DispatchData(
                            raw_text=best_p2_candidate.raw_text,
                            units=p2_units_str,
                            response_type=best_p2_candidate.response_type or "routine",
                            call_type=p2_incident_type,
                            address=clean_address_string(p1_target.get("address")) or (p1_candidate.address if p1_candidate else best_p2_candidate.address),
                            intersection=best_p2_candidate.intersection,
                            radio_channel=p2_channel,
                            map_grid=p2_grid,
                            subaddress=best_p2_candidate.subaddress or p1_target.get("subaddress")
                        )
                        reconstructed_transcript = reconstruct_template_transcript(candidate_copy)
                        logging.info(f"Phase 2 reconstructed template transcript (match): '{reconstructed_transcript}'")
                    except Exception as r_err:
                        logging.warning(f"Failed to reconstruct Phase 2 template transcript: {r_err}")
                
                p1_address = p1_target.get("address") or (p1_candidate.address or p1_candidate.intersection if p1_candidate else "")
                
                target_payload = {
                    "address": p1_address,
                    "lat": p1_target.get("lat"),
                    "lng": p1_target.get("lng"),
                    "rings": p1_target.get("rings") or [],
                    "map_grid": p2_grid,
                    "radio_channel": p2_channel
                }
                if p1_target.get("subaddress"):
                    target_payload["subaddress"] = p1_target.get("subaddress")
                if p1_target.get("tone_name"):
                    target_payload["tone_name"] = p1_target.get("tone_name")
                if p1_target.get("intersection"):
                    target_payload["intersection"] = p1_target.get("intersection")
                elif best_p2_candidate.intersection:
                    target_payload["intersection"] = best_p2_candidate.intersection
                
                # Update Supabase record status to verified (verify_location=False)
                if supabase_url and supabase_key:
                    update_payload = {
                        "verify_location": False,
                        "confidence_score": 100.0,  # Boost confidence to 100% since both rounds verified it
                        "audio_url": audio_url,
                        "audio_duration": audio_duration,
                        "raw_transcript": full_raw,
                        "sanitized_transcript": reconstructed_transcript,
                        "incident_type": p2_incident_type,
                        "responding_units": p2_responding_units
                    }
                    if INTEGRATION_PAYLOAD_OPTION == 1:
                        update_payload["address"] = p1_address
                    else:
                        update_payload["target"] = target_payload
                        
                    success = update_supabase_record(dispatch_id, update_payload, supabase_url, supabase_key)
                    if not success:
                        local_wav_path = None
                        try:
                            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            local_wav_path = os.path.join(base_dir, "frontend", "public", "recordings", f"{dispatch_id}.wav")
                        except Exception:
                            pass
                        queue_offline_dispatch(dispatch_id, "update", update_payload, local_wav_path)
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
                        
                        p1_units = p1_candidate.units if p1_candidate else None
                        p2_units = p2_candidate.units if p2_candidate else None
                        p2_units_str = merge_units(p1_units, p2_units) if (p1_units or p2_units) else None
                        p2_responding_units = abbreviate_units(p2_units_str) if p2_units_str else []
                        p2_grid = next((d.map_grid for d in all_candidates if d.map_grid), (p1_candidate.map_grid if p1_candidate else None))
                        if (not p2_grid or str(p2_grid).lower() == "none") and res and res.get("lat") is not None and res.get("lng") is not None:
                            p2_grid = validator.get_map_grid_for_point(res["lat"], res["lng"])
                        p2_channel = next((d.radio_channel for d in all_candidates if d.radio_channel), (p1_candidate.radio_channel if p1_candidate else None))
                        p2_incident_type = match_incident_type(full_sanitized, CALL_TYPES)
                        
                        # Reconstruct template
                        reconstructed_transcript = full_sanitized
                        best_p2_candidate = p2_candidate or p1_candidate
                        if best_p2_candidate:
                            try:
                                candidate_copy = DispatchData(
                                    raw_text=best_p2_candidate.raw_text,
                                    units=p2_units_str,
                                    response_type=best_p2_candidate.response_type or "routine",
                                    call_type=p2_incident_type,
                                    address=clean_address_string(res["address"]),
                                    intersection=best_p2_candidate.intersection,
                                    radio_channel=p2_channel,
                                    map_grid=p2_grid,
                                    subaddress=best_p2_candidate.subaddress or p1_target.get("subaddress")
                                )
                                reconstructed_transcript = reconstruct_template_transcript(candidate_copy)
                                logging.info(f"Phase 2 reconstructed template transcript (corrected): '{reconstructed_transcript}'")
                            except Exception as r_err:
                                logging.warning(f"Failed to reconstruct Phase 2 template transcript: {r_err}")
                        
                        target_payload = {
                            "address": res["address"],
                            "lat": res["lat"],
                            "lng": res["lng"],
                            "rings": res["rings"],
                            "map_grid": p2_grid,
                            "radio_channel": p2_channel
                        }
                        if p1_target.get("subaddress"):
                            target_payload["subaddress"] = p1_target.get("subaddress")
                        elif best_p2_candidate and best_p2_candidate.subaddress:
                            target_payload["subaddress"] = best_p2_candidate.subaddress
                            
                        if p1_target.get("tone_name"):
                            target_payload["tone_name"] = p1_target.get("tone_name")
                            
                        if best_p2_candidate and best_p2_candidate.intersection:
                            target_payload["intersection"] = best_p2_candidate.intersection
                        elif p1_target.get("intersection"):
                            target_payload["intersection"] = p1_target.get("intersection")
                        
                        # Prepare update payload
                        update_payload = {
                            "verify_location": False,
                            "confidence_score": float(res["confidence"]),
                            "audio_url": audio_url,
                            "audio_duration": audio_duration,
                            "raw_transcript": full_raw,
                            "sanitized_transcript": reconstructed_transcript,
                            "incident_type": p2_incident_type,
                            "responding_units": p2_responding_units
                        }
                        if INTEGRATION_PAYLOAD_OPTION == 1:
                            update_payload["address"] = res["address"]
                        else:
                            update_payload["target"] = target_payload
                            
                        # Update Local Database API (and optional Supabase cloud backup)
                        success = update_dispatch_record(dispatch_id, update_payload, supabase_url, supabase_key)
                        if not success:
                            local_wav_path = None
                            try:
                                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                                local_wav_path = os.path.join(base_dir, "frontend", "public", "recordings", f"{dispatch_id}.wav")
                            except Exception:
                                pass
                            queue_offline_dispatch(dispatch_id, "update", update_payload, local_wav_path)
                            
                        # Send correction push notification
                        if ENABLE_NTFY_PUSH:
                            ntfy_topic = os.environ.get("NTFY_TOPIC")
                            ntfy_token = os.environ.get("NTFY_TOKEN")
                            if ntfy_topic:
                                corr_payload = {
                                    "dispatch_id": dispatch_id,
                                    "incident_type": p2_incident_type,
                                    "responding_units": p2_responding_units,
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
                        # Geocoding failed for Phase 2 as well, keep Phase 1 data but flag verify_location=True
                        logging.warning("Phase 2 geocoding failed. Keeping Phase 1 data but flagging verify_location=True.")
                        
                        p1_units = p1_candidate.units if p1_candidate else None
                        p2_units = p2_candidate.units if p2_candidate else None
                        p2_units_str = merge_units(p1_units, p2_units) if (p1_units or p2_units) else None
                        p2_responding_units = abbreviate_units(p2_units_str) if p2_units_str else []
                        p2_grid = next((d.map_grid for d in all_candidates if d.map_grid), (p1_candidate.map_grid if p1_candidate else None))
                        p2_channel = next((d.radio_channel for d in all_candidates if d.radio_channel), (p1_candidate.radio_channel if p1_candidate else None))
                        p2_incident_type = match_incident_type(full_sanitized, CALL_TYPES)
                        
                        # Reconstruct template
                        reconstructed_transcript = full_sanitized
                        best_p2_candidate = p2_candidate or p1_candidate
                        if best_p2_candidate:
                            try:
                                candidate_copy = DispatchData(
                                    raw_text=best_p2_candidate.raw_text,
                                    units=p2_units_str,
                                    response_type=best_p2_candidate.response_type or "routine",
                                    call_type=p2_incident_type,
                                    address=clean_address_string(p1_target.get("address")) or (p1_candidate.address if p1_candidate else best_p2_candidate.address),
                                    intersection=best_p2_candidate.intersection,
                                    radio_channel=p2_channel,
                                    map_grid=p2_grid,
                                    subaddress=best_p2_candidate.subaddress or p1_target.get("subaddress")
                                )
                                reconstructed_transcript = reconstruct_template_transcript(candidate_copy)
                                logging.info(f"Phase 2 reconstructed template transcript (failed geocode): '{reconstructed_transcript}'")
                            except Exception as r_err:
                                logging.warning(f"Failed to reconstruct Phase 2 template transcript: {r_err}")
                                
                        update_payload = {
                            "verify_location": True,
                            "audio_url": audio_url,
                            "audio_duration": audio_duration,
                            "raw_transcript": full_raw,
                            "sanitized_transcript": reconstructed_transcript,
                            "incident_type": p2_incident_type,
                            "responding_units": p2_responding_units
                        }
                        update_dispatch_record(dispatch_id, update_payload, supabase_url, supabase_key)
                else:
                    # No Phase 2 candidate found (e.g. dispatcher override, noise, cutoff)
                    # Gracefully fallback: keep Phase 1 data, mark as verified=True
                    logging.info("No valid candidate in Phase 2. Keeping Phase 1 data as verified.")
                    
                    p2_units_str = p1_candidate.units if p1_candidate else None
                    p2_responding_units = abbreviate_units(p2_units_str) if p2_units_str else []
                    p2_grid = p1_candidate.map_grid if p1_candidate else None
                    p2_channel = p1_candidate.radio_channel if p1_candidate else None
                    p2_incident_type = match_incident_type(full_sanitized, CALL_TYPES)
                    
                    # Reconstruct template
                    reconstructed_transcript = full_sanitized
                    if p1_candidate:
                        try:
                            candidate_copy = DispatchData(
                                raw_text=p1_candidate.raw_text,
                                units=p2_units_str,
                                response_type=p1_candidate.response_type or "routine",
                                call_type=p2_incident_type,
                                address=clean_address_string(p1_target.get("address")) or p1_candidate.address,
                                intersection=p1_candidate.intersection,
                                radio_channel=p2_channel,
                                map_grid=p2_grid,
                                subaddress=p1_candidate.subaddress or p1_target.get("subaddress")
                            )
                            reconstructed_transcript = reconstruct_template_transcript(candidate_copy)
                            logging.info(f"Phase 2 reconstructed template transcript (no candidate): '{reconstructed_transcript}'")
                        except Exception as r_err:
                            logging.warning(f"Failed to reconstruct Phase 2 template transcript: {r_err}")
                            
                    update_payload = {
                        "verify_location": False,
                        "audio_url": audio_url,
                        "audio_duration": audio_duration,
                        "raw_transcript": full_raw,
                        "sanitized_transcript": reconstructed_transcript,
                        "incident_type": p2_incident_type,
                        "responding_units": p2_responding_units
                    }
                    update_dispatch_record(dispatch_id, update_payload, supabase_url, supabase_key)

                        
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
                try:
                    stt_model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)
                except Exception as model_err:
                    logging.warning(f"Could not load specified model '{WHISPER_MODEL}': {model_err}. Falling back to standard 'base' faster-whisper model...")
                    stt_model = WhisperModel("base", device=device, compute_type=compute_type)
                logging.info("faster-whisper model pre-loaded successfully.")
            except ImportError:
                import whisper
                stt_model = whisper.load_model(WHISPER_MODEL if not os.path.isdir(WHISPER_MODEL) else "base", device=device)
                logging.info("standard whisper model pre-loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to pre-load Whisper model: {e}. Will load on demand.", exc_info=True)


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

def update_listener_heartbeat():
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        status_dir = os.path.join(base_dir, "data")
        os.makedirs(status_dir, exist_ok=True)
        status_file = os.path.join(status_dir, "listener_status.json")
        tmp_file = os.path.join(status_dir, "listener_status.json.tmp")
        payload = {
            "status": "online",
            "device": DEVICE_ID,
            "stt_engine": STT_ENGINE,
            "last_heartbeat": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "pid": os.getpid()
        }
        with open(tmp_file, "w") as f:
            json.dump(payload, f)
        os.replace(tmp_file, status_file)
    except Exception as e:
        logging.warning(f"Could not update listener heartbeat: {e}")

def log_tone_spectral_history(dispatch_id, matched_tones, live_frequencies, is_pa_page=False):
    """Logs timestamp, dispatch_id, matched tone names, and top 5 peak frequencies (Hz) for training dataset."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        log_file = os.path.join(data_dir, "tone_spectral_history.json")
        
        freq_list = sorted(list(live_frequencies)) if live_frequencies else []
        top_5_freqs = [round(f, 2) for f in freq_list[:5]]
        
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "dispatch_id": dispatch_id or f"TRIGGER-{int(time.time())}",
            "matched_tones": matched_tones if isinstance(matched_tones, list) else [matched_tones],
            "top_5_frequencies_hz": top_5_freqs,
            "all_detected_frequencies_hz": [round(f, 2) for f in freq_list],
            "is_pa_page": is_pa_page
        }
        
        history = []
        if os.path.exists(log_file):
            try:
                with open(log_file, "r") as f:
                    history = json.load(f)
            except Exception:
                history = []
        history.append(entry)
        if len(history) > 1000:
            history = history[-1000:]
            
        with open(log_file, "w") as f:
            json.dump(history, f, indent=2)
        logging.info(f"[Spectral History] Saved tone fingerprint: Tones={matched_tones} | Top Freqs={top_5_freqs} Hz")
    except Exception as e:
        logging.warning(f"Could not write spectral history log: {e}")

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
    dev_idx, dev_name = resolve_audio_device(DEVICE_ID)
    logging.info(f"Targeting Audio Input Interface: [{dev_idx}] '{dev_name}'")
    try:
        with sd.InputStream(samplerate=AUDIO_SAMPLE_RATE, channels=1, blocksize=blocksize, dtype='int16', device=dev_idx) as stream:
            try:
                device_info = sd.query_devices(stream.device, 'input')
                logging.info(f"Successfully opened audio stream on: '{device_info.get('name', 'Unknown')}'")
            except Exception as e:
                logging.warning(f"Could not query audio device name: {e}")
            time.sleep(1.0)
            
            last_hb_time = 0
            pa_cooldown_until = 0
            while True:
                logging.info("STATE: LISTENING_FOR_TONE")
                loudness_history = deque(maxlen=SUSTAINED_LOUDNESS_WINDOW)
                history_audio_buffer = deque(maxlen=SUSTAINED_LOUDNESS_WINDOW)
                is_capturing_tone, analysis_buffer, last_log_time, matched_tone = False, [], 0, None
                
                # Rolling history of quiet RMS values to compute adaptive baseline
                baseline_rms_history = deque(maxlen=50)
                baseline_rms_history.append(NOISE_AMPLITUDE_THRESHOLD / 2.5)

                while True:
                    current_time = time.time()
                    if current_time - last_hb_time >= 5.0:
                        update_listener_heartbeat()
                        last_hb_time = current_time
                    if is_capturing_tone:
                        pcm, _ = stream.read(blocksize)
                        analysis_buffer.append(pcm)
                        if len(analysis_buffer) * blocksize >= TONE_ANALYSIS_DURATION_SECONDS * AUDIO_SAMPLE_RATE:
                            logging.info("Analyzing captured audio for a dispatch tone...")
                            full_sample_np = np.concatenate(analysis_buffer)
                            live_frequencies = analyze_live_audio(full_sample_np.tobytes(), AUDIO_SAMPLE_RATE, NUM_PEAKS_TO_FIND, TONE_ZSCORE_THRESHOLD)
                            all_matches = get_all_matches(live_frequencies, GOLDEN_FINGERPRINTS, FREQUENCY_TOLERANCE_HZ, MATCH_THRESHOLD_PERCENT)
                            pa_matches = [m for m in all_matches if m[0] == "PA Tone"]
                            apparatus_matches = [m for m in all_matches if m[0] in ("Chief Tone", "Engine Tone", "Rescue Tone")]

                            if pa_matches and not apparatus_matches:
                                logging.info("TONE DETECTED: 'PA Tone' (station paging page). Disregarding and resetting listener.")
                                log_tone_spectral_history(None, ["PA Tone"], live_frequencies, is_pa_page=True)
                                is_capturing_tone = False
                                baseline_rms_history.clear()
                                baseline_rms_history.append(NOISE_AMPLITUDE_THRESHOLD / 2.5)
                                continue
                            elif apparatus_matches:
                                matched_tone_list = [m[0] for m in apparatus_matches]
                                matched_tone = ", ".join(matched_tone_list)
                                scores_str = ", ".join([f"{m[0]}: {m[1]*100:.0f}%" for m in apparatus_matches])
                                logging.info(f"TONES CONFIRMED: '{matched_tone}' ({scores_str})")
                                log_tone_spectral_history(None, matched_tone_list, live_frequencies, is_pa_page=False)
                                break
                            else:
                                logging.info("Triggered sound was not a recognized apparatus tone, resetting.")
                                is_capturing_tone = False
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

                # Reset immediately to ensure back-to-back dispatches are not missed.
                # (The end of the current dispatch was already determined by silence in capture_full_dispatch).
                logging.info("Resetting listener to LISTENING_FOR_TONE.")

    except KeyboardInterrupt:
        logging.info("Listener stopped by user.")
    except Exception as e:
        logging.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
    finally:
        # Poison pill worker
        dispatch_queue.put(None)
        logging.info("System shut down.")
