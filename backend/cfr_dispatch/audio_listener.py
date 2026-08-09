import os
import time
import json
import uuid
import datetime
import logging
from collections import deque
import numpy as np
import sounddevice as sd

from cfr_dispatch.config.dsp import (
    NOISE_AMPLITUDE_THRESHOLD,
    SUSTAINED_LOUDNESS_WINDOW,
    SUSTAINED_LOUDNESS_CHUNKS_REQUIRED,
    TONE_ANALYSIS_DURATION_SECONDS,
    NUM_PEAKS_TO_FIND,
    TONE_ZSCORE_THRESHOLD,
    GOLDEN_FINGERPRINTS,
    FREQUENCY_TOLERANCE_HZ,
    MATCH_THRESHOLD_PERCENT,
    MAX_DISPATCH_DURATION_S,
    MIN_PHASE_1_DURATION_S,
    PHASE_1_CHECK_INTERVAL_S,
    END_OF_DISPATCH_RMS_THRESHOLD,
    END_OF_DISPATCH_SILENCE_S
)
from cfr_dispatch.config.hardware import DEVICE_ID, AUDIO_SAMPLE_RATE
from cfr_dispatch.config.cloud import STT_ENGINE, VERBOSITY_LEVEL
from cfr_dispatch.config.vocab import UNITS_VOCABULARY
from audio_service import (
    get_rms,
    analyze_live_audio,
    get_all_matches,
    capture_full_dispatch,
    resolve_audio_device
)

def update_listener_heartbeat():
    """Writes heartbeat timestamp and process metadata to data/listener_status.json."""
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

def log_tone_spectral_history(dispatch_id: str, matched_tones: list | str, live_frequencies: list, is_pa_page: bool = False):
    """Logs timestamp, matched tones, and top peak frequencies for spectral dataset tracking."""
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

def run_audio_listener_loop(dispatch_queue):
    """Continuous PortAudio input stream listener and DSP tone trigger loop."""
    blocksize = 1024
    dev_idx, dev_name = resolve_audio_device(DEVICE_ID)
    logging.info(f"Targeting Audio Input Interface: [{dev_idx}] '{dev_name}'")

    with sd.InputStream(samplerate=AUDIO_SAMPLE_RATE, channels=1, blocksize=blocksize, dtype='int16', device=dev_idx) as stream:
        try:
            device_info = sd.query_devices(stream.device, 'input')
            logging.info(f"Successfully opened audio stream on: '{device_info.get('name', 'Unknown')}'")
        except Exception as e:
            logging.warning(f"Could not query audio device name: {e}")
        time.sleep(1.0)
        
        last_hb_time = 0
        while True:
            logging.debug("STATE: LISTENING_FOR_TONE")
            loudness_history = deque(maxlen=SUSTAINED_LOUDNESS_WINDOW)
            history_audio_buffer = deque(maxlen=SUSTAINED_LOUDNESS_WINDOW)
            is_capturing_tone, analysis_buffer, last_log_time, matched_tone = False, [], 0, None
            
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
                        logging.info("Analyzing captured audio for dispatch tones...")
                        full_sample_np = np.concatenate(analysis_buffer)
                        live_frequencies = analyze_live_audio(full_sample_np.tobytes(), AUDIO_SAMPLE_RATE, NUM_PEAKS_TO_FIND, TONE_ZSCORE_THRESHOLD)
                        all_matches = get_all_matches(live_frequencies, GOLDEN_FINGERPRINTS, FREQUENCY_TOLERANCE_HZ, MATCH_THRESHOLD_PERCENT)
                        pa_matches = [m for m in all_matches if m[0] == "PA Tone"]
                        apparatus_matches = [m for m in all_matches if m[0] in ("Chief Tone", "Engine Tone", "Rescue Tone")]

                        if pa_matches and not apparatus_matches:
                            logging.info("TONE DETECTED: 'PA Tone' (station paging). Disregarding and resetting listener.")
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
                            logging.info("Triggered sound was not a recognized apparatus tone. Resetting.")
                            is_capturing_tone = False
                            baseline_rms_history.clear()
                            baseline_rms_history.append(NOISE_AMPLITUDE_THRESHOLD / 2.5)
                            continue
                    else:
                        continue

                pcm, _ = stream.read(blocksize)
                history_audio_buffer.append(pcm)
                rms = get_rms(pcm)
                
                if rms < NOISE_AMPLITUDE_THRESHOLD * 1.5:
                    baseline_rms_history.append(rms)
                    
                current_baseline = np.mean(baseline_rms_history) if baseline_rms_history else (NOISE_AMPLITUDE_THRESHOLD / 2.5)
                current_threshold = max(NOISE_AMPLITUDE_THRESHOLD, current_baseline * 2.5)

                current_time = time.time()
                if VERBOSITY_LEVEL >= 3 and current_time - last_log_time >= 5.0:
                    logging.debug(f"Listening... RMS: {int(rms):<5} | Threshold: {int(current_threshold):<5} | Loud: {sum(loudness_history)}/{SUSTAINED_LOUDNESS_CHUNKS_REQUIRED}")
                    last_log_time = current_time

                is_currently_loud = rms > current_threshold
                loudness_history.append(is_currently_loud)
                
                if not is_capturing_tone and sum(loudness_history) >= SUSTAINED_LOUDNESS_CHUNKS_REQUIRED:
                    logging.info(f"Sustained loud sound detected! Capturing for {TONE_ANALYSIS_DURATION_SECONDS}s to analyze tones...")
                    is_capturing_tone = True
                    analysis_buffer = list(history_audio_buffer)
                    loudness_history.clear()

            # Dispatch Audio Stream Capture
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
                logging.info(f"[{dispatch_id}] Queueing finalized dispatch for background processing...")
                dispatch_queue.put({
                    "type": "phase_2_finalize",
                    "dispatch_id": dispatch_id,
                    "buffer": list(dispatch_buffer),
                    "tone_name": matched_tone,
                    "units_vocab": UNITS_VOCABULARY
                })

            logging.debug("Resetting listener to LISTENING_FOR_TONE.")
