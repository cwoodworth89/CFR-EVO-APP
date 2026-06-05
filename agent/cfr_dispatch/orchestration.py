# cfr_dispatch/orchestration.py
# System orchestration, audio capture, and background process worker loops

import os
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
    STT_ENGINE,
    WHISPER_MODEL,
    INTEGRATION_PAYLOAD_OPTION,
    ENABLE_GOOGLE_MAPS_FALLBACK,
    ENABLE_NTFY_PUSH,
    ENABLE_JOIN_PUSH,
    AUDIO_SAMPLE_RATE,
    NOISE_AMPLITUDE_THRESHOLD,
    SUSTAINED_LOUDNESS_WINDOW,
    SUSTAINED_LOUDNESS_CHUNKS_REQUIRED,
    TONE_ANALYSIS_DURATION_SECONDS,
    MAX_DISPATCH_DURATION_S,
    END_OF_DISPATCH_SILENCE_S,
    END_OF_DISPATCH_RMS_THRESHOLD,
    POST_EVENT_RESET_SILENCE_S,
    DEVICE_ID,
    UNITS_VOCABULARY,
    ADDRESS_SHAPEFILE_PATH,
    ZONES_SHAPEFILE_PATH,
    ADAPTATION_RESOURCE_IDS,
    BOOST_MAPPING,
    GCP_PROJECT_ID,
    RECOGNIZER_RESOURCE_NAME
)
from cfr_dispatch.dsp import (
    get_rms,
    analyze_live_audio,
    get_best_match,
    filter_known_tones
)
from cfr_dispatch.parser import (
    sanitize_transcript,
    match_incident_type,
    parse_alarm_level,
    abbreviate_units,
    parse_dispatch_announcement,
    CALL_TYPES
)
from cfr_dispatch.gis import CoquitlamDataValidator
from cfr_dispatch.integration import (
    post_to_supabase,
    post_to_ntfy,
    launch_navigation_on_phone
)

# Global queue for background multiprocessing worker
dispatch_queue = multiprocessing.Queue()

def setup_logging():
    """Configures global debug logs and console streams."""
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

def transcribe_audio_file(file_path: str) -> str | None:
    """Transcribes audio using Google Cloud Speech-to-Text v2 with custom phrase adaptation."""
    try:
        from google.cloud import speech_v2
        client = speech_v2.SpeechClient()

        phrases_to_boost = []
        for resource_id in ADAPTATION_RESOURCE_IDS:
            base_id = next((key for key in BOOST_MAPPING if resource_id.startswith(key)), None)
            boost_value = BOOST_MAPPING.get(base_id, 10)
            
            full_resource_name = f"projects/{GCP_PROJECT_ID}/locations/global/customClasses/{resource_id}"
            phrases_to_boost.append({"value": f"${full_resource_name}", "boost": boost_value})

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

        with open(file_path, "rb") as audio_file:
            content = audio_file.read()
        
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

def transcribe_audio_file_local(file_path: str) -> str | None:
    """
    Transcribes audio locally using faster-whisper if available, falling back to
    standard openai-whisper as a secondary option.
    """
    try:
        from faster_whisper import WhisperModel
        logging.info(f"Loading local faster-whisper model '{WHISPER_MODEL}'...")
        model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        logging.info(f"Transcribing '{file_path}' using faster-whisper...")
        segments, info = model.transcribe(file_path, beam_size=5)
        text = " ".join([segment.text for segment in segments])
        return text.strip() or None
    except ImportError:
        try:
            import whisper
            logging.info(f"Loading local openai-whisper model '{WHISPER_MODEL}'...")
            model = whisper.load_model(WHISPER_MODEL)
            logging.info(f"Transcribing '{file_path}' using standard Whisper...")
            result = model.transcribe(file_path, language="en")
            return result.get("text", "").strip() or None
        except ImportError:
            logging.error("Neither faster-whisper nor openai-whisper is installed. Please run 'pip install faster-whisper' for local STT.")
            return None
    except Exception as e:
        logging.error(f"Local transcription error: {e}", exc_info=True)
        return None

def capture_full_dispatch(stream, blocksize, initial_buffer=None):
    """Captures continuous dispatch audio until END_OF_DISPATCH_SILENCE_S is reached."""
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

def process_full_dispatch(buffer, validator: CoquitlamDataValidator, tone_name: str, units_vocabulary: List[str]):
    """Processes a completed dispatch buffer: transcribes, geocodes, and posts integrations."""
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
        
        # 3. Transcribe Audio
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
                
        # Parse Incident Type and Alarm Level
        incident_type = match_incident_type(transcript, CALL_TYPES)
        alarm_level = parse_alarm_level(transcript)
        units_str = next((d.units for d in all_candidates if d.units), None)
        responding_units = abbreviate_units(units_str)

        # Check for specific placeholder phrase
        is_specific_placeholder = "contact dispatch" in transcript or "location information" in transcript
        
        if is_specific_placeholder:
            unique_addresses = ["Contact dispatch for location information"]
        
        if not unique_addresses:
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
                    
            # 6. Fallback (Anonymized Google maps fallback if enabled)
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
                
        # 8. Construct Payloads
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        target_payload = {
            "address": best_address,
            "lat": lat,
            "lng": lng,
            "rings": rings
        }
        
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
                
        if ENABLE_JOIN_PUSH:
            join_key = os.environ.get("JOIN_API_KEY")
            if join_key and lat and lng:
                launch_navigation_on_phone(target_payload, best_address, join_key)

    except Exception as e:
        logging.error(f"Error processing dispatch ID {dispatch_id}: {e}", exc_info=True)
    finally:
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
                logging.info(f"Cleaned up unique audio file '{temp_filename}'")
            except Exception as e:
                logging.warning(f"Could not delete unique audio file '{temp_filename}': {e}")

def background_worker_loop(task_queue: multiprocessing.Queue):
    """
    Background worker loop. Run in a separate Process.
    Initializes GIS validator once at startup and waits for dispatch capture events.
    """
    logging.info("Background Dispatch Worker process starting...")
    try:
        validator = CoquitlamDataValidator(ADDRESS_SHAPEFILE_PATH, ZONES_SHAPEFILE_PATH)
        logging.info("Background Dispatch Worker process initialized and ready.")
    except Exception as e:
        logging.critical(f"Failed to initialize validator in worker process: {e}", exc_info=True)
        return
        
    while True:
        try:
            task = task_queue.get()
            if task is None: # Poison pill
                break
            buffer, tone_name, units_vocab = task
            process_full_dispatch(buffer, validator, tone_name, units_vocab)
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
        logging.critical("FATAL ERROR: ENABLE_NTFY_PUSH is True but NTFY_TOPIC is not set.")
        return
        
    if ENABLE_JOIN_PUSH and not os.environ.get("JOIN_API_KEY"):
        logging.critical("FATAL ERROR: ENABLE_JOIN_PUSH is True but JOIN_API_KEY is not set.")
        return
    
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

                while True:
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
                                break
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

                # Dispatch Capture
                dispatch_buffer = capture_full_dispatch(stream, blocksize, initial_buffer=analysis_buffer)
                if dispatch_buffer:
                    logging.info("Queueing captured dispatch for background processor core...")
                    dispatch_queue.put((list(dispatch_buffer), matched_tone, UNITS_VOCABULARY))

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
