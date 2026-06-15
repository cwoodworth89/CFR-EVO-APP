# NOTE: For audio device index discovery and volume meter checks, see:
#   - docs/hardware_specification.md
#   - docs/test_procedures.md
import sounddevice as sd
import numpy as np
import time

def list_audio_devices():
    """Lists all available audio devices and their properties."""
    print("--- Available Audio Devices ---")
    devices = sd.query_devices()
    input_devices = []
    for i, device in enumerate(devices):
        # We are only interested in devices that can be used as input
        if device['max_input_channels'] > 0:
            print(f"Input Device ID {i}: {device['name']}")
            input_devices.append(i)
    print("--------------------------------")
    return input_devices

def run_volume_meter(device_id=None):
    """
    Listens to a specific microphone and prints the live volume level.

    Args:
        device_id (int, optional): The ID of the microphone to use. 
                                   If None, the system default is used.
    """
    if device_id is not None:
        print(f"\n--- Starting Volume Meter on Device ID: {device_id} ---")
    else:
        print("\n--- Starting Volume Meter on System Default Input Device ---")
    
    print("This will display the volume level once per second.")
    print("Make some noise, stay quiet, and play the dispatch tones to see the difference.")
    print("Press Ctrl+C to stop.\n")

    def print_volume(indata, frames, time, status):
        """This function is called for each audio block."""
        volume_norm = np.linalg.norm(indata) * 10
        # We use \r (carriage return) and end='' to print on the same line
        print(f"Current Volume Level: {volume_norm:6.2f}", end='\r')

    try:
        # Create a non-blocking stream that calls the print_volume function
        with sd.InputStream(device=device_id, channels=1, callback=print_volume):
            while True:
                time.sleep(1) # Keep the script alive while the stream runs in the background
    except KeyboardInterrupt:
        print("\nVolume meter stopped by user.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("This could mean the selected Device ID is invalid.")


if __name__ == "__main__":
    # Step 1: List all devices so the user can see their options
    available_devices = list_audio_devices()

    # Step 2: Prompt the user to choose a device or use the default
    choice = input("Enter the Device ID of the microphone you want to test, or press Enter to use the system default: ")
    
    selected_device = None
    if choice.strip() and choice.isdigit() and int(choice) in available_devices:
        selected_device = int(choice)
    
    # Step 3: Run the volume meter on the chosen device
    run_volume_meter(device_id=selected_device)