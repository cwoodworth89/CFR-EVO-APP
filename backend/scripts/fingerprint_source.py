import argparse
import os
import sys
import glob
import numpy as np
import soundfile as sf
from scipy import signal

def extract_tone_fingerprint(file_path: str, target_sr: int = 16000, num_peaks: int = 5, prominence_ratio: float = 0.1):
    """
    Analyzes a clean audio source file, applies FFT with parabolic peak interpolation,
    and extracts dominant frequencies with sub-Hz precision.
    """
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return None

    try:
        data, sr = sf.read(file_path)
    except Exception as e:
        print(f"[ERROR] Could not read audio file '{file_path}': {e}")
        return None

    # Convert stereo to mono
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)

    # Resample to target sample rate if needed
    if sr != target_sr:
        num_samples = int(len(data) * target_sr / sr)
        data = signal.resample(data, num_samples)
        sr = target_sr

    duration_s = len(data) / sr

    # High-pass filter above 300 Hz (remove AC rumble / DC offset)
    cutoff_hz = 300.0
    nyquist = 0.5 * sr
    b, a = signal.butter(4, cutoff_hz / nyquist, btype='high')
    data_filtered = signal.lfilter(b, a, data)

    # Apply Hamming window to eliminate spectral leakage
    window = np.hamming(len(data_filtered))
    windowed = data_filtered * window

    # Compute FFT
    fft_complex = np.fft.rfft(windowed)
    fft_mag = np.abs(fft_complex)
    fft_freqs = np.fft.rfftfreq(len(windowed), 1.0 / sr)

    if len(fft_mag) == 0:
        return None

    # Calculate spectral statistics (Z-score and SNR)
    max_val = np.max(fft_mag)
    mean_val = np.mean(fft_mag)
    std_val = np.std(fft_mag)
    z_score = (max_val - mean_val) / std_val if std_val > 0 else 0.0

    # Minimum distance between distinct tone peaks (15 Hz)
    bin_hz = sr / len(windowed)
    min_dist_bins = max(1, int(15.0 / bin_hz))

    peaks, _ = signal.find_peaks(fft_mag, distance=min_dist_bins, prominence=max_val * prominence_ratio)

    if len(peaks) == 0:
        # Fallback to top bins
        peaks = np.argpartition(fft_mag, -num_peaks)[-num_peaks:]

    # Sort peaks by magnitude descending and take top num_peaks
    sorted_peaks = sorted(peaks, key=lambda p: fft_mag[p], reverse=True)[:num_peaks]

    # Parabolic sub-bin interpolation for exact resonant peak frequency:
    # delta = 0.5 * (alpha - gamma) / (alpha - 2*beta + gamma)
    interpolated_freqs = []
    for p in sorted_peaks:
        if 0 < p < len(fft_mag) - 1:
            alpha = fft_mag[p - 1]
            beta = fft_mag[p]
            gamma = fft_mag[p + 1]
            denom = alpha - 2 * beta + gamma
            if denom != 0:
                delta = 0.5 * (alpha - gamma) / denom
                true_bin = p + delta
                true_freq = true_bin * bin_hz
            else:
                true_freq = fft_freqs[p]
        else:
            true_freq = fft_freqs[p]
        
        # Only keep frequencies in audible tone band (300 Hz - 3000 Hz)
        if 300.0 <= true_freq <= 3500.0:
            interpolated_freqs.append(round(float(true_freq), 2))

    interpolated_freqs.sort()

    return {
        "file": os.path.basename(file_path),
        "duration_s": round(duration_s, 2),
        "sample_rate": sr,
        "z_score": round(float(z_score), 2),
        "frequencies": interpolated_freqs
    }

def main():
    parser = argparse.ArgumentParser(description="CFR EVO: Audio Tone Fingerprint Extractor")
    parser.add_argument("--input", "-i", default="backend/audio_files/original/Locution Source Files",
                        help="Path to an audio file or directory of tone files")
    parser.add_argument("--peaks", "-p", type=int, default=4, help="Maximum number of frequency peaks to extract")
    parser.add_argument("--sample-rate", "-sr", type=int, default=16000, help="Target sample rate (default: 16000 Hz)")
    args = parser.parse_args()

    input_path = args.input
    if not os.path.exists(input_path):
        print(f"[ERROR] Input path does not exist: {input_path}")
        sys.exit(1)

    if os.path.isdir(input_path):
        audio_files = sorted(glob.glob(os.path.join(input_path, "*.wav")) + glob.glob(os.path.join(input_path, "*.mp3")))
        if not audio_files:
            print(f"No .wav or .mp3 audio files found in directory '{input_path}'")
            return
        
        print(f"\n{'='*70}")
        print(f"CFR EVO: Batch Tone Fingerprint Extraction ({len(audio_files)} files)")
        print(f"Directory: {input_path}")
        print(f"{'='*70}\n")

        results = {}
        for fpath in audio_files:
            fname = os.path.basename(fpath)
            res = extract_tone_fingerprint(fpath, target_sr=args.sample_rate, num_peaks=args.peaks)
            if res and res["frequencies"]:
                results[fname] = res
                freq_str = ", ".join([f"{f:.2f}" for f in res["frequencies"]])
                print(f"  {fname:<38} | {res['duration_s']:>4.1f}s | Z={res['z_score']:>5.1f} | [{freq_str}] Hz")

        print(f"\n{'-'*70}")
        print("PYTHON CONFIGURATION SNIPPET (Copy to backend/cfr_dispatch/config/dsp.py):")
        print(f"{'-'*70}\n")
        print("GOLDEN_FINGERPRINTS = {")
        for fname, res in results.items():
            clean_key = os.path.splitext(fname)[0].replace("0_cfr_source_tone_", "").replace("0_cfr_", "").replace("_", " ").title()
            print(f'    "{clean_key}": {res["frequencies"]},')
        print("}\n")

    else:
        print(f"\n--- Analyzing: {input_path} ---")
        res = extract_tone_fingerprint(input_path, target_sr=args.sample_rate, num_peaks=args.peaks)
        if res:
            print(f"File:        {res['file']}")
            print(f"Duration:    {res['duration_s']}s")
            print(f"Z-Score:     {res['z_score']}")
            print(f"Frequencies: {res['frequencies']} Hz")
            print(f'\nPython Dict: "{os.path.splitext(res["file"])[0]}": {res["frequencies"]}')

if __name__ == "__main__":
    main()