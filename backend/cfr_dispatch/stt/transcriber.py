import os
import threading
import logging
import numpy as np
from cfr_dispatch.config.runtime import WHISPER_MODEL
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
                # local_files_only=True -- CLAUDE.md s1 requires the whole stack to run
                # with no WAN. Verified against the installed faster_whisper 1.2.1 on the
                # kiosk 2026-08-31: the parameter defaults to False and WhisperModel hands
                # it straight to huggingface_hub.snapshot_download, so every cold start
                # called huggingface.co to check the model revision -- observed live in
                # journalctl at 18:35:09. The weights were already cached locally (142 MB
                # at ~/.cache/huggingface/hub/models--Systran--faster-whisper-base), so the
                # request bought nothing and put a WAN dependency on the boot path of an
                # offline dispatch system.
                #
                # With this set, an absent cache raises instead of quietly downloading.
                # That is the intended behaviour (s6.1): a new machine is seeded
                # deliberately, not over the network at first boot. See
                # docs/external_calls.md.
                try:
                    _whisper_model_singleton = WhisperModel(
                        WHISPER_MODEL,
                        device="cpu",
                        compute_type="int8",
                        local_files_only=True,
                    )
                except Exception as e:
                    raise RuntimeError(
                        f"Whisper model '{WHISPER_MODEL}' is not in the local Hugging Face "
                        f"cache, and this system does not download models at runtime "
                        f"(CLAUDE.md s1, offline-only). Seed it once from a networked "
                        f"machine -- for a bare size name the repo is "
                        f"'Systran/faster-whisper-{WHISPER_MODEL}' -- or copy the matching "
                        f"~/.cache/huggingface/hub/models--* directory from a working host. "
                        f"Underlying error: {e}"
                    ) from e
    return _whisper_model_singleton

def transcribe_audio_local(audio_data, model=None, validator=None) -> str | None:
    """
    Transcribes audio (NumPy array or file path) locally using a cached
    faster-whisper model with street/unit phrase biasing and Silero VAD filtering.
    """
    try:
        active_model = model or get_whisper_model()
        is_faster_whisper = hasattr(active_model, 'transcribe') and not hasattr(active_model, 'load_model')
        
        # Supply the loaded model's real max_length and tokenizer so the hotword budget
        # is MEASURED against what faster-whisper will actually keep, rather than guessed
        # from a term count. Overshooting is silent -- it cost every arterial in the city
        # its biasing (punch-list #18).
        _encoder = None
        _max_length = 448
        try:
            _max_length = int(getattr(active_model, 'max_length', 448))
            from faster_whisper.tokenizer import Tokenizer
            _tok = Tokenizer(active_model.hf_tokenizer, active_model.model.is_multilingual,
                             task='transcribe', language='en')
            _encoder = _tok.encode
        except Exception as e:
            logging.debug(f"STT hotword budget falling back to estimate: {e}")
        initial_prompt, hotwords_str = build_stt_bias_words(
            validator, UNITS_VOCABULARY, max_length=_max_length, encoder=_encoder)
        
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
