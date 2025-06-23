import sounddevice as sd
import pvporcupine
import os
import time

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================
ACCESS_KEY = os.environ.get("PICOVOICE_ACCESS_KEY")

# --- THIS IS THE CORRECTED FILENAME ---
KEYWORD_FILE_PATH = "map_grid_wakeword.ppn" 
# ------------------------------------

COOLDOWN_SECONDS = 2

# ... (The rest of the test script is unchanged) ...
def run_keyword_test():
    if not ACCESS_KEY or not os.path.exists(KEYWORD_FILE_PATH):
        print("Error: Missing Picovoice AccessKey or keyword file.")
        print("Please check your environment variables and that the KEYWORD_FILE_PATH is correct.")
        return
        
    porcupine = None
    try:
        porcupine = pvporcupine.create(
            access_key=ACCESS_KEY,
            keyword_paths=[KEYWORD_FILE_PATH]
        )
        
        print("--- Starting Keyword Spotter Test ---")
        print(f"Listening for the keyword 'Map Grid'...")
        print(f"Porcupine Sample Rate: {porcupine.sample_rate}")
        print("Say 'Map Grid' into your microphone. Press Ctrl+C to stop.")

        with sd.InputStream(
            samplerate=porcupine.sample_rate,
            channels=1,
            blocksize=porcupine.frame_length,
            dtype='int16'
        ) as stream:
            while True:
                pcm_chunk, _ = stream.read(porcupine.frame_length)
                result = porcupine.process(pcm_chunk.flatten())

                if result >= 0:
                    print(f"\n[{time.strftime('%H:%M:%S')}] >>> KEYWORD DETECTED: 'Map Grid' <<<")
                    print(f"--- Cooling down for {COOLDOWN_SECONDS} seconds... ---")
                    time.sleep(COOLDOWN_SECONDS)
                    print("--- Resuming listening... ---")
    except KeyboardInterrupt:
        print("\nListener stopped by user.")
    finally:
        if porcupine is not None:
            porcupine.delete()

if __name__ == "__main__":
    run_keyword_test()