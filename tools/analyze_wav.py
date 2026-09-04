# analyze_wav.py
# A simple helper script to analyze the frequencies in a WAV file.

import wavio
import numpy as np

# --- CONFIGURATION ---
# The sample rate should match our main script.
AUDIO_SAMPLE_RATE = 16000
# The number of top frequencies to find.
NUM_PEAKS_TO_FIND = 20


def analyze_audio_file(filepath: str) -> list[int] | None:
    """
    Reads a WAV file, performs a frequency analysis, and returns the top frequencies.
    """
    try:
        # Read the WAV file using wavio
        wav = wavio.read(filepath)
    except Exception as e:
        print(f"Error: Could not read or process the WAV file '{filepath}'.")
        print(f"Details: {e}")
        return None

    # Check if the audio is stereo and convert to mono if necessary
    if wav.data.ndim > 1:
        # Average the channels to get a mono signal
        audio_array = wav.data.mean(axis=1).astype(np.int16)
    else:
        audio_array = wav.data.astype(np.int16)

    if len(audio_array) == 0:
        print("Error: Audio file is empty.")
        return None

    # Perform the FFT (Fast Fourier Transform) analysis
    fft_data = np.fft.rfft(audio_array)
    fft_freqs = np.fft.rfftfreq(len(audio_array), 1.0 / AUDIO_SAMPLE_RATE)
    fft_magnitude = np.abs(fft_data)

    try:
        # Find the indices of the top N peaks in the magnitude
        peak_indices = np.argpartition(fft_magnitude, -NUM_PEAKS_TO_FIND)[-NUM_PEAKS_TO_FIND:]
        # Get the corresponding frequencies for those peaks
        found_freqs = set(int(f) for f in fft_freqs[peak_indices])
        return sorted(list(found_freqs))
    except (ValueError, IndexError):
        print("Error: Could not find peaks in the audio data.")
        return None


if __name__ == "__main__":
    # -------------------------------------------------------------------
    # --- IMPORTANT: Change this to the name of your WAV file. ---
    FILENAME_TO_ANALYZE = "audio_files/ahs_driver_room_recs/isolated_tones/rescue_tone_2.wav"
    # -------------------------------------------------------------------

    print(f"Analyzing frequencies for: {FILENAME_TO_ANALYZE}")
    
    frequencies = analyze_audio_file(FILENAME_TO_ANALYZE)
    
    if frequencies:
        print("\n--- Detected Frequencies (sorted) ---")
        print(frequencies)
        print("\nCompare this list to your GOLDEN_FINGERPRINTS in main.py")