#!/usr/bin/env python3

import pyaudio
import numpy as np
import time
import keyboard
from collections import deque, Counter
import sys

# --- Configuration & Constants ---

# -- Audio Settings
CHUNK = 2048
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000 # Required kHz for Porcupine and Google API native

# ==============================================================================
# === CRITICAL TUNING PARAMETERS FOR VALIDATION ================================
# ==============================================================================
MATCH_THRESHOLD_PERCENT = 0.7
TONE_ANALYSIS_DURATION_SECONDS = 3.5
NOISE_AMPLITUDE_THRESHOLD = 500
SUSTAINED_LOUDNESS_WINDOW = 5
SUSTAINED_LOUDNESS_CHUNKS_REQUIRED = 4
FREQUENCY_TOLERANCE_HZ = 10
NUM_PEAKS_TO_FIND = 20

# ==============================================================================
# === GOLDEN FINGERPRINTS (Paste your longer, source-generated fingerprints here)
# ==============================================================================
GOLDEN_FINGERPRINTS = {
    "Chief Tone":  [437.50, 656.25],
    "Engine Tone": [601.56, 1351.56],
    "Rescue Tone": [726.56, 890.62, 2179.69]
}

# --- Global State Variables ---
session_stats = {
    "confirmed_positives": {name: 0 for name in GOLDEN_FINGERPRINTS},
    "false_positives": {name: 0 for name in GOLDEN_FINGERPRINTS},
    "missed_tones": {name: 0 for name in GOLDEN_FINGERPRINTS},
}
is_paused = False

# --- Core Audio and Analysis Functions ---

def get_rms(data):
    audio_array = np.frombuffer(data, dtype=np.int16)
    return np.sqrt(np.mean(audio_array.astype(float)**2)) if len(audio_array) > 0 else 0

def analyze_live_audio(data, num_peaks=NUM_PEAKS_TO_FIND):
    audio_array = np.frombuffer(data, dtype=np.int16)
    if len(audio_array) == 0: return set()
    fft_data = np.fft.rfft(audio_array)
    fft_freq = np.fft.rfftfreq(len(audio_array), 1.0 / RATE)
    fft_magnitude = np.abs(fft_data)
    try:
        peak_indices = np.argpartition(fft_magnitude, -num_peaks)[-num_peaks:]
        return set(int(f) for f in fft_freq[peak_indices])
    except (ValueError, IndexError):
        return set()

def get_best_match(live_frequencies):
    best_match_tone = None
    best_match_score = -1
    best_match_details = ""
    for tone_name, golden_freqs in GOLDEN_FINGERPRINTS.items():
        matches_found = 0
        total_golden_freqs = len(golden_freqs)
        for golden_f in golden_freqs:
            for live_f in live_frequencies:
                if abs(live_f - golden_f) <= FREQUENCY_TOLERANCE_HZ:
                    matches_found += 1
                    break
        score = matches_found / total_golden_freqs if total_golden_freqs > 0 else 0
        if score > best_match_score:
            best_match_score = score
            best_match_tone = tone_name
            best_match_details = f"({matches_found}/{total_golden_freqs} matched)"
    if best_match_score >= MATCH_THRESHOLD_PERCENT:
        return best_match_tone, best_match_details
    else:
        return None, None

def select_audio_device(p):
    print("--- Please Select an Audio Input Device ---")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info.get('maxInputChannels') > 0:
            print(f"  Device ID {i} - {info.get('name')}")
    while True:
        try:
            choice = int(input("Enter the Device ID for CABLE Output (or other source): "))
            # Basic validation
            if p.get_device_info_by_index(choice).get('maxInputChannels') > 0:
                print(f"Selected device {choice}.\n")
                return choice
            else:
                 print("Invalid ID. That device has no input channels.")
        except (ValueError, IndexError):
            print("Invalid input. Please enter a valid device ID number.")

def handle_missed_tone():
    global is_paused
    if is_paused: return
    is_paused = True
    print("\n\n--- MISSED TONE REPORT ---")
    tone_names = list(GOLDEN_FINGERPRINTS.keys())
    for i, name in enumerate(tone_names): print(f"  {i+1}: {name}")
    try:
        choice = int(input(f"Which tone did I miss? (1-{len(tone_names)}): "))
        choice_index = choice - 1
        if 0 <= choice_index < len(tone_names):
            selected_tone = tone_names[choice_index]
            session_stats["missed_tones"][selected_tone] += 1
            print(f"✅ Missed tone logged for '{selected_tone}'. Thank you!")
        else:
            print("❌ Invalid selection.")
    except (ValueError, IndexError):
        print("❌ Invalid input.")
    finally:
        print("Resuming listening...\n")
        is_paused = False

def finalize_session():
    print("\n\n" + "="*60)
    print("    ✅ VALIDATION SESSION COMPLETE! ✅")
    print("="*60)
    print(f"Tuning Parameters Used:")
    print(f"  - Match Threshold: {MATCH_THRESHOLD_PERCENT * 100:.0f}%")
    print(f"  - Frequency Tolerance: ±{FREQUENCY_TOLERANCE_HZ} Hz")
    print("\n--- Performance Report ---")
    for tone_name in GOLDEN_FINGERPRINTS.keys():
        confirmed = session_stats['confirmed_positives'][tone_name]
        missed = session_stats['missed_tones'][tone_name]
        false = session_stats['false_positives'][tone_name]
        print(f"\n'{tone_name}':")
        print(f"  - Correct Detections: {confirmed}")
        print(f"  - False Detections:   {false}")
        print(f"  - Missed Detections:    {missed}")
    print("\n" + "="*60)
    print("Consider adjusting MATCH_THRESHOLD_PERCENT or FREQUENCY_TOLERANCE_HZ.")

def main():
    global is_paused
    p = pyaudio.PyAudio()
    device_index = select_audio_device(p)
    stream = None
    
    loudness_history = deque(maxlen=SUSTAINED_LOUDNESS_WINDOW)
    analysis_buffer = []
    is_capturing = False
    capture_end_time = 0

    try:
        keyboard.add_hotkey('m', handle_missed_tone, suppress=True)
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                        input_device_index=device_index, frames_per_buffer=CHUNK)

        print("--- Golden Fingerprint Validator ---")
        print("Purpose: Test your golden fingerprints against live audio and tune the matching sensitivity.")
        print("\nStarting now...")

        while True:
            if is_paused:
                time.sleep(0.1)
                continue

            data = stream.read(CHUNK, exception_on_overflow=False)
            
            if is_capturing:
                analysis_buffer.append(data)
                if time.time() >= capture_end_time:
                    is_paused = True
                    full_sample = b''.join(analysis_buffer)
                    live_frequencies = analyze_live_audio(full_sample)
                    matched_tone, match_details = get_best_match(live_frequencies)

                    if matched_tone:
                        print(f"\n>>> MATCH FOUND: '{matched_tone}' {match_details}. Is this correct? (y/n): ", end="")
                        sys.stdout.flush()
                        answer = input().lower().strip()
                        if answer == 'y':
                            session_stats["confirmed_positives"][matched_tone] += 1
                            print("✅ Correct match logged.")
                        else:
                            session_stats["false_positives"][matched_tone] += 1
                            print("❌ False positive logged.")
                    else:
                        print("\n--- Triggered but no match found. Likely a non-tone sound. ---")

                    is_capturing = False
                    is_paused = False
                    print("Resuming listening...\n")
                continue

            rms = get_rms(data)
            is_currently_loud = rms > NOISE_AMPLITUDE_THRESHOLD
            loudness_history.append(is_currently_loud)
            is_sustained_loud = sum(loudness_history) >= SUSTAINED_LOUDNESS_CHUNKS_REQUIRED

            print(f"Listening... RMS: {int(rms):<5} | Loud Chunks: {sum(loudness_history)}/{SUSTAINED_LOUDNESS_CHUNKS_REQUIRED}", end='\r')

            if is_sustained_loud:
                print(f"\nSustained sound detected! Capturing for {TONE_ANALYSIS_DURATION_SECONDS}s...")
                is_capturing = True
                analysis_buffer = [] # *** BUG FIX: Initialize a clean, empty buffer ***
                capture_end_time = time.time() + TONE_ANALYSIS_DURATION_SECONDS
                loudness_history.clear()

    except KeyboardInterrupt:
        print("\nUser interrupted. Finalizing session...")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        if stream and stream.is_active(): stream.stop_stream()
        if stream: stream.close()
        p.terminate()
        keyboard.remove_hotkey('m')
        finalize_session()

if __name__ == '__main__':
    main()