# test_device.py
import sounddevice as sd
import numpy as np
import os
import sys

def get_rms(audio_array):
    return np.sqrt(np.mean(audio_array.astype(float)**2)) if len(audio_array) > 0 else 0

def main():
    print("==================================================")
    print("      AUDIO DEVICE IDENTIFICATION & TESTER        ")
    print("==================================================")
    
    # 1. List all input devices
    devices = sd.query_devices()
    input_devices = []
    print("Available Input Devices:")
    for idx, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            try:
                api_name = sd.query_hostapis(d['hostapi'])['name']
            except Exception:
                api_name = "Unknown API"
            print(f"  Device ID {idx:<2}: {d['name']} ({api_name}) | Max In Channels: {d['max_input_channels']}")
            input_devices.append(idx)
            
    if not input_devices:
        print("ERROR: No input devices found on this system!")
        return
        
    print("==================================================")
    # 2. Prompt user to select a device
    while True:
        try:
            choice = input("Select a Device ID to test: ").strip()
            if not choice:
                continue
            choice_idx = int(choice)
            if choice_idx in input_devices:
                break
            else:
                print(f"Invalid selection. Please choose an index from the list above.")
        except ValueError:
            print("Invalid input. Please enter a valid number.")
            
    # 3. Test the chosen device in real-time
    selected_device = devices[choice_idx]
    sample_rate = 16000
    blocksize = 1024
    
    print(f"\nTesting Device {choice_idx}: {selected_device['name']}...")
    print("Press Ctrl+C to stop the real-time RMS level meter.")
    print("==================================================")
    print("  Current RMS |  Max RMS Seen |  Max Peak  |  Signal Bar")
    print("--------------------------------------------------")
    
    max_rms_seen = 0.0
    max_peak_seen = 0
    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, blocksize=blocksize, dtype='int16', device=choice_idx) as stream:
            while True:
                pcm, overflowed = stream.read(blocksize)
                rms_val = get_rms(pcm)
                max_val = int(np.max(np.abs(pcm)))
                if rms_val > max_rms_seen:
                    max_rms_seen = rms_val
                if max_val > max_peak_seen:
                    max_peak_seen = max_val
                
                # Format level bar
                bar = "#" * int(min(rms_val / 200, 20))
                print(f"  {rms_val:<11.1f} |  {max_rms_seen:<12.1f} |  {max_val:<10} |  [{bar:<20}]", end="\r")
                sys.stdout.flush()
                
    except KeyboardInterrupt:
        print("\n==================================================")
        print("Meter stopped by user.")
        print(f"Session Summary:")
        print(f"  - Maximum RMS Level:  {max_rms_seen:.1f}")
        print(f"  - Maximum Peak Value: {max_peak_seen}")
        
    # 4. Prompt to save to .env
    save_choice = input(f"\nDo you want to save Device ID {choice_idx} to backend/.env? (y/n): ").strip().lower()
    if save_choice == 'y':
        env_path = ".env"
        # Read current lines
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
        # Find if AUDIO_DEVICE_ID exists, update or append
        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("AUDIO_DEVICE_ID="):
                new_lines.append(f"AUDIO_DEVICE_ID={choice_idx}\n")
                updated = True
            else:
                new_lines.append(line)
                
        if not updated:
            new_lines.append(f"\n# Audio Device Config\nAUDIO_DEVICE_ID={choice_idx}\n")
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        print(f"SUCCESS: Saved AUDIO_DEVICE_ID={choice_idx} to backend/.env!")
        print("\nYou can now run the listener in the foreground of this terminal by running:")
        print("  python main.py")
    else:
        print("Cancelled. Device ID was not saved.")

if __name__ == "__main__":
    main()
