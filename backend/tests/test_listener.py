# NOTE: For audio listener thresholds, tone fingerprints, and microphone diagnostics, see:
#   - docs/hardware_specification.md
#   - docs/test_procedures.md
import sounddevice as sd
import numpy as np
import librosa
import time
import os
import sys

# Ensure working directory is the agent folder so relative paths resolve correctly
script_dir = os.path.dirname(os.path.abspath(__file__))
agent_dir = os.path.dirname(script_dir)
os.chdir(agent_dir)
if agent_dir not in sys.path:
    sys.path.append(agent_dir)

# ==============================================================================
# --- CONFIGURATION (Updated) ---
# ==============================================================================
SAMPLE_RATE = 22050

TONE_FINGERPRINTS = {
    "Chief Tone":  [429.69, 437.50, 445.31, 656.25, 664.06], # Source fingerprints, 16kHz
    "Engine Tone": [593.75, 601.56, 609.38, 1343.75, 1351.56],# Source fingerprints, 16kHz
    "Rescue Tone": [718.75, 726.56, 734.38, 890.62, 898.44]  # Source fingerprints, 16kHz
}

# --- SENSITIVITY AND TIMING ADJUSTMENTS ---
MATCH_THRESHOLD = 4
FREQUENCY_TOLERANCE_HZ = 15.0
SILENCE_THRESHOLD = 20.0 
SILENCE_DURATION_S = 4.0
FINAL_COOLDOWN_S = 1.0
# -------------------------------------------

# ==============================================================================
# --- REAL-TIME LISTENER (Unchanged Logic) ---
# ==============================================================================
def run_fingerprint_listener():
    print("--- Starting Real-Time Fingerprint Listener (Tuned) ---")
    print(f"Match Threshold: {MATCH_THRESHOLD}, Silence Duration: {SILENCE_DURATION_S}s")
    print("Press Ctrl+C to stop.")

    fft_freqs = librosa.fft_frequencies(sr=SAMPLE_RATE, n_fft=2048)
    blocksize = int(SAMPLE_RATE * 0.1)
    
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, blocksize=blocksize) as stream:
        while True:
            try:
                audio_chunk, _ = stream.read(blocksize)
                audio_chunk = audio_chunk.flatten()

                stft = np.abs(librosa.stft(audio_chunk, n_fft=2048))
                mean_freqs = np.mean(stft, axis=1)
                top_live_indices = np.argsort(mean_freqs)[-10:]
                top_live_freqs = fft_freqs[top_live_indices]
                
                for tone_name, fingerprint in TONE_FINGERPRINTS.items():
                    matches = sum(1 for f in fingerprint if np.any(np.abs(top_live_freqs - f) <= FREQUENCY_TOLERANCE_HZ))
                    
                    if matches >= MATCH_THRESHOLD:
                        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"\n[{current_time}] >>> TRIGGER DETECTED: Heard '{tone_name}' with {matches} matching frequencies. <<<")
                        print("--- Event in progress. Waiting for silence... ---")

                        silence_start_time = None
                        while True:
                            chunk, _ = stream.read(blocksize)
                            volume = np.linalg.norm(chunk) * 100
                            if volume < SILENCE_THRESHOLD:
                                if silence_start_time is None:
                                    silence_start_time = time.time()
                                else:
                                    if time.time() - silence_start_time >= SILENCE_DURATION_S:
                                        print("--- Silence confirmed. Event finished. ---")
                                        break
                            else:
                                silence_start_time = None
                        
                        # This is the corrected line
                        time.sleep(FINAL_COOLDOWN_S)
                        
                        print("--- Cooldown complete. Resuming listening... ---\n")
                        break
            except KeyboardInterrupt:
                print("\nListener stopped by user.")
                break
            except Exception as e:
                print(f"An error occurred: {e}")

if __name__ == "__main__":
    run_fingerprint_listener()