import librosa
import numpy as np
import os

# ==============================================================================
# --- FINGERPRINTING LOGIC (Unchanged) ---
# ==============================================================================

def create_fingerprint(file_path):
    """
    Analyzes a clean audio source file and identifies its dominant frequencies.
    """
    print(f"\n--- Creating Golden Fingerprint for: {file_path} ---")
    try:
        y, sr = librosa.load(file_path, sr=16000)
        stft = np.abs(librosa.stft(y, n_fft=2048))
        mean_freqs = np.mean(stft, axis=1)
        
        num_top_freqs = 5 
        top_freq_indices = np.argsort(mean_freqs)[-num_top_freqs:]
        
        fft_freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
        dominant_freqs = fft_freqs[top_freq_indices]
        dominant_freqs.sort()

        print("\n--- Analysis Complete ---")
        print("This tone is composed of the following primary frequencies (in Hz):")
        for freq in dominant_freqs:
            print(f"  > {freq:.2f} Hz")
            
        # --- THIS IS THE NEW, FOOLPROOF OUTPUT LOGIC ---
        # 1. Create a list where each number is formatted as a string with 2 decimal places.
        formatted_freq_list = [f"{f:.2f}" for f in dominant_freqs]
        
        # 2. Join the elements of the list with a comma and a space.
        output_string = ", ".join(formatted_freq_list)
        
        # 3. Print the final, manually constructed string inside brackets.
        print("\n--- Copy this golden fingerprint into your main.py and test_listener.py ---")
        print(f"TONE_FINGERPRINT = [{output_string}]")
        # -----------------------------------------------
        
    except Exception as e:
        print(f"An error occurred: {e}")

# ==============================================================================
# --- MAIN EXECUTION (Interactive) ---
# ==============================================================================

if __name__ == "__main__":
    filename = input("Please enter the filename of the tone you want to fingerprint (e.g., source_tone_chief.wav): ")
    
    if os.path.exists(filename):
        create_fingerprint(filename)
    else:
        print(f"\nError: File '{filename}' not found.")
        print("Please make sure the audio file is in the same folder as the script and the name is spelled correctly.")