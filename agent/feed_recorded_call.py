# feed_recorded_call.py
# Helper script to feed a saved WAV file into the dispatch mapping pipeline.
#
# Usage:
#   python feed_recorded_call.py <path_to_wav_file> [tone_name]
#
# Example:
#   python feed_recorded_call.py test_dispatch.wav
#

import sys
import os
import wavio
import numpy as np
import logging

# Ensure main directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cfr_dispatch.gis import CoquitlamDataValidator
from cfr_dispatch.orchestration import process_full_dispatch, setup_logging
from cfr_dispatch.config import (
    UNITS_VOCABULARY,
    ADDRESS_SHAPEFILE_PATH,
    ZONES_SHAPEFILE_PATH
)

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
        
    # Convert to mono if stereo
    if wav.data.ndim > 1:
        print("Converting stereo to mono...")
        audio_data = wav.data.mean(axis=1)
    else:
        audio_data = wav.data.squeeze()
        
    rate = wav.rate
    if rate != 16000:
        from scipy import signal
        print(f"Resampling from {rate} Hz to 16000 Hz...")
        num_samples = int(len(audio_data) * 16000 / rate)
        audio_data = signal.resample(audio_data, num_samples)
        
    audio_data = audio_data.astype(np.int16)
        
    print("Initializing Coquitlam Data Validator...")
    validator = CoquitlamDataValidator(ADDRESS_SHAPEFILE_PATH, ZONES_SHAPEFILE_PATH)
    
    print(f"Feeding audio array ({len(audio_data)} samples) into pipeline...")
    # Wrap in a list so np.concatenate works as expected inside process_full_dispatch
    process_full_dispatch([audio_data], validator, tone_name, UNITS_VOCABULARY)
    print("Finished feeding call to pipeline.")

if __name__ == "__main__":
    main()
