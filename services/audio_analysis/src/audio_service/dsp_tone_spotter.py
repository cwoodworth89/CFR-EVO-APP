# NOTE: For hardware specs, PortAudio device setup, and ambient noise floor thresholds, see hardware_specification.md
import numpy as np
from scipy import signal

def get_rms(data: np.ndarray) -> float:
    """Computes the root-mean-square value of a PCM audio array."""
    if data.size == 0:
        return 0.0
    return np.sqrt(np.mean(data.astype(np.float32)**2))

def analyze_live_audio(data: bytes, sample_rate: int, num_peaks: int, zscore_threshold: float = 50.0) -> set:
    """
    Analyzes an audio byte buffer for frequency peaks.
    Applies a high-pass Butterworth filter, a Hamming window to prevent spectral leakage,
    and checks for spectral purity (Z-score) to filter out speech/noise false positives.
    """
    audio_array = np.frombuffer(data, dtype=np.int16)
    if len(audio_array) == 0:
        return set()
        
    cutoff_hz = 300.0
    nyquist_freq = 0.5 * sample_rate
    normal_cutoff = cutoff_hz / nyquist_freq
    
    b, a = signal.butter(5, normal_cutoff, btype='high', analog=False)
    filtered_signal = signal.lfilter(b, a, audio_array)
    
    # Apply Hamming window to prevent spectral leakage
    window = np.hamming(len(filtered_signal))
    windowed_signal = filtered_signal * window
    
    fft_data = np.fft.rfft(windowed_signal)
    fft_freqs = np.fft.rfftfreq(len(windowed_signal), 1.0 / sample_rate)
    fft_magnitude = np.abs(fft_data)
    
    if len(fft_magnitude) == 0:
        return set()
        
    # Check spectral purity (Z-score of the maximum peak) to reject non-tone voice/noise triggers
    max_val = np.max(fft_magnitude)
    mean_val = np.mean(fft_magnitude)
    std_val = np.std(fft_magnitude)
    z_score = (max_val - mean_val) / std_val if std_val > 0 else 0.0
    
    # Enforce minimum peak separation distance of 15 Hz to avoid duplicate adjacent bin detections
    bin_spacing = sample_rate / len(filtered_signal)
    min_distance_bins = max(1, int(15.0 / bin_spacing))
    
    detected_freqs = set()
    try:
        # Find local peaks that stand out (prominence filter)
        peaks, _ = signal.find_peaks(fft_magnitude, distance=min_distance_bins, prominence=max_val * 0.05)
        # Sort found peaks by magnitude descending and take top num_peaks
        sorted_peaks = sorted(peaks, key=lambda p: fft_magnitude[p], reverse=True)[:num_peaks]
        detected_freqs = set(int(fft_freqs[p]) for p in sorted_peaks)
    except Exception:
        # Fallback to partition if find_peaks fails or is unavailable
        try:
            peak_indices = np.argpartition(fft_magnitude, -num_peaks)[-num_peaks:]
            detected_freqs = set(int(fft_freqs[p]) for p in peak_indices)
        except (ValueError, IndexError):
            pass

    import logging
    logging.info(f"[DSP Analysis] Z-score: {z_score:.2f} (threshold: {zscore_threshold:.2f}) | Peaks: {sorted(list(detected_freqs))}")
    
    if z_score < zscore_threshold:
        return set() # Rejected as non-pure tone
        
    return detected_freqs

def get_best_match(live_frequencies: set, golden_fingerprints: dict, frequency_tolerance_hz: float, match_threshold_percent: float) -> tuple[str, float] | tuple[None, None]:
    """
    Compares detected frequency peaks against golden_fingerprints.
    Returns the matched tone name and match ratio if it exceeds the match_threshold_percent.
    """
    best_match_tone = None
    best_match_score = -1.0
    
    for tone_name, golden_freqs in golden_fingerprints.items():
        matches_found = sum(1 for gf in golden_freqs if any(abs(lf - gf) <= frequency_tolerance_hz for lf in live_frequencies))
        score = matches_found / len(golden_freqs) if golden_freqs else 0.0
        
        if score > best_match_score:
            best_match_score = score
            best_match_tone = tone_name
            
    if best_match_score >= match_threshold_percent:
        return best_match_tone, best_match_score
    return None, None

def filter_known_tones(audio_data: np.ndarray, tone_name: str, sample_rate: int, golden_fingerprints: dict) -> np.ndarray:
    """
    Applies causal forward IIR notch filters at the golden fingerprint frequencies
    associated with tone_name to clean up voice transcriptions.
    """
    if not tone_name or tone_name not in golden_fingerprints:
        return audio_data
        
    tone_frequencies = golden_fingerprints[tone_name]
    filtered_audio = audio_data.copy()
    
    for freq in tone_frequencies:
        b, a = signal.iirnotch(freq, 50.0, fs=sample_rate)
        filtered_audio = signal.lfilter(b, a, filtered_audio)
        
    return filtered_audio.astype(np.int16)
