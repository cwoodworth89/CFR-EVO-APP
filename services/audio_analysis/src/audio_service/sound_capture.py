import time
import logging
from audio_service.dsp_tone_spotter import get_rms

def capture_full_dispatch(
    stream, 
    blocksize: int, 
    dispatch_queue, 
    dispatch_id: str, 
    matched_tone: str, 
    initial_buffer=None,
    sample_rate: int = 16000,
    max_duration_s: float = 240.0,
    min_phase_1_duration_s: float = 20.0,
    phase_1_check_interval_s: float = 5.0,
    end_of_dispatch_rms_threshold: float = 30.0,
    end_of_dispatch_silence_s: float = 8.0,
    units_vocabulary = None
):
    """Captures continuous dispatch audio until END_OF_DISPATCH_SILENCE_S is reached, pushing Phase 1 checks periodically."""
    logging.info(f"STATE: CAPTURING DISPATCH (ID: {dispatch_id})")
    audio_buffer = initial_buffer if initial_buffer is not None else []
    max_chunks = int((sample_rate / blocksize) * max_duration_s)
    start_chunk = len(audio_buffer)
    silence_start_time = None
    last_check_time = time.time()
    
    for i in range(start_chunk, max_chunks):
        try:
            pcm, _ = stream.read(blocksize)
            audio_buffer.append(pcm)
            
            # Periodic Phase 1 Check trigger
            current_time = time.time()
            duration_s = (len(audio_buffer) * blocksize) / sample_rate
            if duration_s >= min_phase_1_duration_s and (current_time - last_check_time >= phase_1_check_interval_s):
                last_check_time = current_time
                logging.debug(f"Queueing intermediate audio buffer for Phase 1 check ({len(audio_buffer)} blocks, {duration_s:.1f}s)...")
                dispatch_queue.put({
                    "type": "phase_1_check",
                    "dispatch_id": dispatch_id,
                    "buffer": list(audio_buffer),
                    "tone_name": matched_tone,
                    "units_vocab": units_vocabulary or []
                })

            volume = get_rms(pcm)
            if volume < end_of_dispatch_rms_threshold:
                if silence_start_time is None:
                    silence_start_time = time.time()
                elif time.time() - silence_start_time >= end_of_dispatch_silence_s:
                    logging.info(f"END OF DISPATCH DETECTED by {end_of_dispatch_silence_s}s of silence.")
                    return audio_buffer
            else:
                silence_start_time = None
        except Exception as e:
            logging.error(f"Audio stream read error: {e}", exc_info=True)
            break
            
    logging.info(f"MAX DURATION ({max_duration_s}s) REACHED.")
    return audio_buffer
