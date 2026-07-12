# backend/scripts/live_monitor.py
import os
import sys
import time
import numpy as np
import sounddevice as sd

def get_rms(audio_array):
    if len(audio_array) == 0:
        return 0.0
    return np.sqrt(np.mean(audio_array.astype(float)**2))

def load_env_device_id():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("AUDIO_DEVICE_ID="):
                    try:
                        return int(line.split("=")[1].strip())
                    except ValueError:
                        pass
    return None

def main():
    print("==================================================")
    print("        LIVE AUDIO LEVEL & CALIBRATION METER      ")
    print("==================================================")
    
    env_device_id = load_env_device_id()
    if len(sys.argv) > 1:
        try:
            device_id = int(sys.argv[1])
            print(f"Using command-line override Device ID: {device_id}")
        except ValueError:
            print(f"Invalid argument. Defaulting to .env or default.")
            device_id = env_device_id
    else:
        device_id = env_device_id

    if device_id is None:
        print("AUDIO_DEVICE_ID not found in .env. Using system default device.")
    else:
        print(f"Targeting Device ID: {device_id}")

    sample_rate = 16000
    blocksize = 1024
    
    print("\nPress Ctrl+C to exit and print a session summary.")
    print("==================================================")
    print(" Current RMS | Max RMS Seen | Max Peak | Signal Level Bar")
    print("--------------------------------------------------")

    max_rms_seen = 0.0
    max_peak_seen = 0
    rms_history = []
    
    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, blocksize=blocksize, dtype='int16', device=device_id) as stream:
            while True:
                pcm, overflowed = stream.read(blocksize)
                rms_val = get_rms(pcm)
                max_val = int(np.max(np.abs(pcm)))
                
                rms_history.append(rms_val)
                # Keep rolling history capped to 1000 samples for memory sanity
                if len(rms_history) > 1000:
                    rms_history.pop(0)
                    
                if rms_val > max_rms_seen:
                    max_rms_seen = rms_val
                if max_val > max_peak_seen:
                    max_peak_seen = max_val
                
                # Format level bar (each '#' represents 150 RMS units)
                bar_len = min(int(rms_val / 150), 30)
                bar = "#" * bar_len
                
                # Print stats on a single line
                print(f"  {rms_val:<10.1f} | {max_rms_seen:<12.1f} | {max_val:<8} | [{bar:<30}]", end="\r")
                sys.stdout.flush()
                
    except KeyboardInterrupt:
        print("\n==================================================")
        print("Live monitor stopped by user.")
        if rms_history:
            avg_rms = np.mean(rms_history)
            std_rms = np.std(rms_history)
            print(f"Session Summary:")
            print(f"  - Average RMS Level (last 1000 blocks): {avg_rms:.1f}")
            print(f"  - RMS Standard Deviation:                {std_rms:.1f}")
            print(f"  - Maximum RMS Level Captured:           {max_rms_seen:.1f}")
            print(f"  - Maximum Peak Value Captured:          {max_peak_seen} (Max 32767)")
            print("==================================================")
            
            # Print helpful threshold suggestions
            print("\nThreshold Configuration Suggestions:")
            if max_rms_seen > 150:
                suggested_threshold = int(max_rms_seen * 0.75)
                print(f"  * Your audio peaked at {max_rms_seen:.1f} RMS.")
                print(f"  * Recommended NOISE_AMPLITUDE_THRESHOLD: {max(150, suggested_threshold)}")
            else:
                print("  * Audio did not exceed 150 RMS. Try turning up physical line volume.")
    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    main()
