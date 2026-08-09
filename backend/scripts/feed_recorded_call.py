# feed_recorded_call.py
# Helper script to feed a saved WAV file into the dispatch mapping pipeline.
# NOTE: For usage guides, expected test calls, and Procedure 4, see docs/test_procedures.md
#
# Usage:
#   python feed_recorded_call.py <path_to_wav_file> [tone_name]
#
# Example:
#   python feed_recorded_call.py test_dispatch.wav
#

import sys
import os

# Ensure working directory is the backend folder so relative data paths and imports resolve correctly
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
os.chdir(backend_dir)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)


import wavio
import numpy as np
import logging

import cfr_dispatch
from gis_service import CoquitlamDataValidator
from cfr_dispatch.orchestration import process_full_dispatch, setup_logging
from cfr_dispatch.worker import get_shared_validator
from cfr_dispatch.config.vocab import UNITS_VOCABULARY

def main():
    # Setup console logging
    setup_logging()
    
    if len(sys.argv) < 2:
        print("Usage: python feed_recorded_call.py <path_to_wav_file> [tone_name]")
        sys.exit(1)
        
    wav_path = sys.argv[1]
    tone_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(wav_path):
        print(f"Error: File not found: '{wav_path}'")
        sys.exit(1)
        
    print(f"Reading WAV file: '{wav_path}'...")
    try:
        wav = wavio.read(wav_path)
    except Exception as e:
        print(f"Error: Could not read WAV file: {e}")
        sys.exit(1)
        
    # Convert to float mono
    if wav.data.ndim > 1:
        print("Converting stereo to mono...")
        audio_float = wav.data.mean(axis=1).astype(np.float32)
    else:
        audio_float = wav.data.squeeze().astype(np.float32)

    # Normalize float range if int16
    max_val = np.max(np.abs(audio_float))
    if max_val > 1.0:
        audio_float = audio_float / 32768.0

    rate = wav.rate
    if rate != 16000:
        import librosa
        print(f"Resampling from {rate} Hz to 16000 Hz using librosa...")
        audio_float = librosa.resample(audio_float, orig_sr=rate, target_sr=16000)

    audio_data = (audio_float * 32767.0).astype(np.int16)
        
    print("Initializing Coquitlam Data Validator...")
    validator = get_shared_validator()
    
    print(f"Feeding audio array ({len(audio_data)} samples) into pipeline...")
    # Wrap in a list so np.concatenate works as expected inside process_full_dispatch
    process_full_dispatch([audio_data], validator, tone_name, UNITS_VOCABULARY)
    print("Finished feeding call to pipeline.")

if __name__ == "__main__":
    main()
