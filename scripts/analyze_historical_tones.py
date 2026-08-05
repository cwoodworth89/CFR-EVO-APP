import os
import sys
import glob
import json
import wavio
import numpy as np
import requests
from collections import Counter

# Add backend directory to sys.path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, backend_dir)
services_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "services", "audio_analysis", "src")
sys.path.insert(0, services_dir)

from audio_service.dsp_tone_spotter import analyze_live_audio, get_all_matches
from cfr_dispatch.config.dsp import GOLDEN_FINGERPRINTS, FREQUENCY_TOLERANCE_HZ, MATCH_THRESHOLD_PERCENT

recordings_dir = os.path.join(backend_dir, "audio_files", "recordings")
wav_files = glob.glob(os.path.join(recordings_dir, "*.wav"))
print(f"Found {len(wav_files)} WAV recordings to backtest.")

# Fetch dispatch metadata from local API gateway if available
api_map = {}
try:
    res = requests.get("http://100.95.146.94:8000/api/dispatches", timeout=5)
    if res.status_code == 200:
        for c in res.json():
            api_map[c.get("dispatch_id")] = c
        print(f"Loaded metadata for {len(api_map)} dispatches from local API.")
except Exception as e:
    print(f"Note: Could not query local API gateway: {e}")

unit_type_freqs = {
    "Engine": Counter(),
    "Rescue": Counter(),
    "Chief": Counter(),
    "Ladder": Counter(),
    "Squad": Counter(),
    "All": Counter()
}

results = []

for wav_path in wav_files:
    fname = os.path.basename(wav_path)
    dispatch_id = os.path.splitext(fname)[0]
    
    try:
        w = wavio.read(wav_path)
        sr = w.rate
        data = w.data
        if data.ndim > 1:
            data = data[:, 0]
        # Normalize to 16-bit PCM
        if data.dtype != np.int16:
            if np.issubdtype(data.dtype, np.floating):
                data = (data * 32767).astype(np.int16)
            else:
                data = data.astype(np.int16)
                
        # Analyze first 3.5s of recording for tones
        samples_3s = data[:int(3.5 * sr)]
        if len(samples_3s) < int(1.0 * sr):
            continue
            
        freqs_set = analyze_live_audio(samples_3s.tobytes(), sr, num_peaks=10, z_threshold=15.0)
        freq_list = sorted([round(f, 1) for f in freqs_set])
        
        matches = get_all_matches(freqs_set, GOLDEN_FINGERPRINTS, FREQUENCY_TOLERANCE_HZ, MATCH_THRESHOLD_PERCENT)
        matched_names = [m[0] for m in matches] if matches else ["Unmatched"]
        
        disp_meta = api_map.get(dispatch_id, {})
        units = disp_meta.get("responding_units") or []
        inc_type = disp_meta.get("incident_type") or "Unknown"
        
        # Categorize into apparatus groups
        cat = "All"
        units_str = " ".join(units).upper() if isinstance(units, list) else str(units).upper()
        if "E1" in units_str or "E2" in units_str or "E3" in units_str or "E4" in units_str:
            cat = "Engine"
        elif "R2" in units_str or "R1" in units_str:
            cat = "Rescue"
        elif "C6" in units_str or "C1" in units_str or "C9" in units_str:
            cat = "Chief"
        elif "L1" in units_str:
            cat = "Ladder"
            
        for f in freq_list:
            # Round frequency to nearest 5 Hz bucket for clustering
            bucket = round(f / 5.0) * 5
            unit_type_freqs[cat][bucket] += 1
            unit_type_freqs["All"][bucket] += 1
            
        results.append({
            "dispatch_id": dispatch_id,
            "filename": fname,
            "category": cat,
            "incident_type": inc_type,
            "units": units,
            "matched_tones": matched_names,
            "peak_frequencies_hz": freq_list
        })
    except Exception as ex:
        pass

print(f"\nSuccessfully backtested {len(results)} audio files.\n")
print("=== FREQUENCY CLUSTER SUMMARY (Top Frequency Peaks in Hz) ===")
for cat, counter in unit_type_freqs.items():
    if counter:
        top_peaks = counter.most_common(10)
        print(f"\nCategory [{cat}] Top Frequency Peaks:")
        for freq_b, count in top_peaks:
            print(f"  - ~{freq_b} Hz: appeared in {count} clips")

# Save detailed backtest report to JSON
out_path = os.path.join(backend_dir, "data", "historical_tone_backtest_report.json")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"\nSaved full spectral backtest report to: {out_path}")
