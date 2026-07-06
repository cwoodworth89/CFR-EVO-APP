# test_device.py
import sounddevice as sd
import numpy as np
import os

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
            
    # 3. Test the chosen device
    selected_device = devices[choice_idx]
    print(f"\nTesting Device {choice_idx}: {selected_device['name']}...")
    print("Recording for 5 seconds. Speak, play a sound, or play a dispatch tone now...")
    
    sample_rate = 16000
    try:
        audio_data = sd.rec(int(5.0 * sample_rate), samplerate=sample_rate, channels=1, dtype='int16', device=choice_idx)
        sd.wait()
        
        rms_val = get_rms(audio_data)
        max_val = np.max(np.abs(audio_data))
        
        print("\n--- Test Complete ---")
        print(f"RMS Level: {rms_val:.2f}")
        print(f"Max Peak:  {max_val}")
        
        if rms_val < 50:
            print("WARNING: RMS level is very low (~0). The line might be silent or muted.")
        elif rms_val > 1000:
            print("SUCCESS: Strong audio signal detected!")
        else:
            print("INFO: Moderate audio signal detected.")
            
    except Exception as e:
        print(f"ERROR: Failed to open or record from device: {e}")
        return
        
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
