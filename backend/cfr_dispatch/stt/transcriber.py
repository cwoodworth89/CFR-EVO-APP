import os
import threading
import logging
import numpy as np
from cfr_dispatch.config.cloud import WHISPER_MODEL
from cfr_dispatch.config.vocab import UNITS_VOCABULARY
from cfr_dispatch.stt.bias_prompt import build_stt_bias_words

_whisper_model_singleton = None
_whisper_lock = threading.Lock()

def get_whisper_model():
    """Returns singleton faster-whisper CTranslate2 int8 model."""
    global _whisper_model_singleton
    if _whisper_model_singleton is None:
        with _whisper_lock:
            if _whisper_model_singleton is None:
                from faster_whisper import WhisperModel
                logging.info(f"Loading local faster-whisper model '{WHISPER_MODEL}' (device=cpu, compute_type=int8)...")
                _whisper_model_singleton = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _whisper_model_singleton

def transcribe_audio_local(audio_data, model=None, validator=None) -> str | None:
    """
    Transcribes audio (NumPy array or file path) locally using a cached
    faster-whisper model with street/unit phrase biasing and Silero VAD filtering.
    """
    try:
        active_model = model or get_whisper_model()
        is_faster_whisper = hasattr(active_model, 'transcribe') and not hasattr(active_model, 'load_model')
        
        initial_prompt, hotwords_str = build_stt_bias_words(validator, UNITS_VOCABULARY)
        
        # Ensure float32 normalized between -1.0 and 1.0 for numpy arrays
        if isinstance(audio_data, np.ndarray) and audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32) / 32768.0
            if len(audio_data.shape) > 1:
                audio_data = audio_data.squeeze()

        with _whisper_lock:
            if is_faster_whisper:
                logging.debug("Transcribing using cached faster-whisper model with vocabulary boosting and VAD...")
                try:
                    segments, info = active_model.transcribe(
                        audio_data, 
                        beam_size=2, 
                        language="en", 
                        initial_prompt=initial_prompt, 
                        hotwords=hotwords_str,
                        vad_filter=True,
                        condition_on_previous_text=False
                    )
                except TypeError:
                    segments, info = active_model.transcribe(
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
                if isinstance(audio_data, str):
                    import whisper
                    audio_data = whisper.load_audio(audio_data)
                result = active_model.transcribe(audio_data, language="en", beam_size=2, initial_prompt=initial_prompt)
                return result.get("text", "").strip() or None
            
    except Exception as e:
        logging.error(f"Local Whisper transcription error: {e}", exc_info=True)
        return None

def transcribe_audio_file_local(file_path: str, model=None, validator=None) -> str | None:
    """Transcribes local audio file path using Whisper."""
    return transcribe_audio_local(file_path, model=model, validator=validator)
