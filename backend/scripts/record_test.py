# backend/scripts/record_test.py
import os
import sys
import time
import numpy as np
import sounddevice as sd
import wavio

def get_rms(audio_array):
    if len(audio_array) == 0:
        return 0.0
    return np.sqrt(np.mean(audio_array.astype(float)**2))

def load_env_device_id():
    # Simple parser for .env
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
    print("        AUDIO RECORDING DIAGNOSTIC TEST          ")
    print("==================================================")
    
    # 1. Determine Device ID
    env_device_id = load_env_device_id()
    if len(sys.argv) > 1:
        try:
            device_id = int(sys.argv[1])
            print(f"Using command-line override Device ID: {device_id}")
        except ValueError:
            print(f"Invalid argument. Defaulting to .env or system default.")
            device_id = env_device_id
    else:
        device_id = env_device_id

    if device_id is None:
        print("AUDIO_DEVICE_ID not found in .env. Using system default device.")
    else:
        print(f"Targeting Device ID: {device_id}")

    # 2. Setup audio capture
    sample_rate = 16000
    blocksize = 1024
    duration_seconds = 15
    
    print(f"\nPreparing to record {duration_seconds} seconds of audio...")
    print("This will record everything it hears to 'test_capture.wav'.")
    print("Please play dispatch tones, scanner noise, or make sounds during this time.")
    print("==================================================")
    
    for count in range(3, 0, -1):
        print(f"Starting in {count}...", end="\r")
        sys.stdout.flush()
        time.sleep(1)
        
    print("RECORDING STARTED... Speak or play audio now!         ")
    print("--------------------------------------------------")

    audio_blocks = []
    rms_values = []
    
    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, blocksize=blocksize, dtype='int16', device=device_id) as stream:
            total_blocks = int((sample_rate / blocksize) * duration_seconds)
            for b in range(total_blocks):
                pcm, overflowed = stream.read(blocksize)
                audio_blocks.append(pcm)
                rms_val = get_rms(pcm)
                rms_values.append(rms_val)
                
                # Draw a simple live indicator
                progress = int((b / total_blocks) * 100)
                bar = "#" * int(min(rms_val / 200, 20))
                print(f"  Progress: {progress:>2}% | Current RMS: {rms_val:<8.1f} | [{bar:<20}]", end="\r")
                sys.stdout.flush()
                
    except KeyboardInterrupt:
        print("\nRecording cancelled early by user.")
    except Exception as e:
        print(f"\nERROR opening or reading from audio device: {e}")
        print("Make sure the Device ID exists and is not currently in use by another program.")
        sys.exit(1)
        
    print("\n--------------------------------------------------")
    print("RECORDING FINISHED.")
    
    if not audio_blocks:
        print("No audio data captured.")
        sys.exit(1)
        
    # Concatenate and save to WAV
    full_audio = np.concatenate(audio_blocks)
    output_filename = "test_capture.wav"
    wavio.write(output_filename, full_audio, sample_rate, sampwidth=2)
    
    # Calculate stats
    min_rms = np.min(rms_values)
    max_rms = np.max(rms_values)
    avg_rms = np.mean(rms_values)
    std_rms = np.std(rms_values)
    max_peak = np.max(np.abs(full_audio))
    
    print("\nAudio Capture Analysis Summary:")
    print(f"  - Output File:         {os.path.abspath(output_filename)}")
    print(f"  - Saved Sample Count:  {len(full_audio)}")
    print(f"  - Peak Amplitude Seen: {max_peak} (Max 32767 for 16-bit)")
    print(f"  - Average RMS Level:   {avg_rms:.1f}")
    print(f"  - Max RMS Level:       {max_rms:.1f}")
    print(f"  - Min RMS Level:       {min_rms:.1f}")
    print(f"  - RMS Std Deviation:   {std_rms:.1f}")
    print("--------------------------------------------------")
    
    if max_peak < 10:
        print("⚠️ WARNING: The audio captured contains almost zero signal (absolute silence).")
        print("   This typically indicates that the line is muted, volume is set to 0, or the hardware connection is disconnected.")
    elif max_rms < 100:
        print("⚠️ WARNING: The average audio level is extremely quiet.")
        print("   Make sure the hardware volume dial on the source or sound card input gain is turned up.")
        print("   If this is tapped from a speaker wire, make sure the speaker itself is playing sound.")
    else:
        print("✅ SUCCESS: Sound card has registered non-silent audio data.")
        print("   To hear if the audio contains the correct dispatch page or scanner static, copy this file to a computer with speakers and play it:")
        print(f"   e.g. scp user@<ip>:{os.path.abspath(output_filename)} .")

if __name__ == "__main__":
    main()
