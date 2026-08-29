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
    matches = get_all_matches(live_frequencies, golden_fingerprints, frequency_tolerance_hz, match_threshold_percent)
    if matches:
        return matches[0][0], matches[0][1]
    return None, None

def get_all_matches(live_frequencies: set, golden_fingerprints: dict, frequency_tolerance_hz: float, match_threshold_percent: float) -> list[tuple[str, float]]:
    """
    Compares detected frequency peaks against golden_fingerprints.
    Returns all matched tone names and match ratios that meet or exceed match_threshold_percent, sorted by score.
    """
    matched = []
    for tone_name, golden_freqs in golden_fingerprints.items():
        matches_found = sum(1 for gf in golden_freqs if any(abs(lf - gf) <= frequency_tolerance_hz for lf in live_frequencies))
        score = matches_found / len(golden_freqs) if golden_freqs else 0.0
        if score >= match_threshold_percent:
            matched.append((tone_name, score))
            
    matched.sort(key=lambda x: x[1], reverse=True)
    return matched

def has_pa_marker(live_frequencies, discriminator_hz: float, tolerance_hz: float) -> bool:
    """True when the station PA tone's marker frequency is present.

    Named has_pa_marker, not is_pa_page: audio_listener.log_tone_spectral_history
    already takes an is_pa_page parameter, and shadowing it would be a trap.

    Punch-list #14. 647 Hz is the discriminator: present in 15/15 labelled PA
    events and 18/18 under strict ground truth, and in 0 of 98 real dispatches
    (measured 2026-08-29 against tone_spectral_history.jsonl).

    Deliberately does NOT consider the PA fingerprint's other component, 595 Hz,
    which appears in 59 of 107 non-PA events; matching on it drops 54 real
    dispatches. See docs/briefings/pa_tone_discriminator.md.
    """
    return any(abs(f - discriminator_hz) <= tolerance_hz for f in live_frequencies)


def is_mains_hum(live_frequencies, fundamental_hz: float, tolerance_hz: float,
                 min_peaks: int) -> bool:
    """True when EVERY detected peak is a multiple of the mains fundamental.

    Electrical interference presents as a harmonic series; 60 Hz odd harmonics
    land on Chief's 660 Hz and just above Rescue's 892 Hz, so hum can register as
    a dispatch (DISP-2026-483052).

    Requires ALL peaks to fit the series, which is what makes it safe: every
    apparatus fingerprint contains at least one frequency that is not a multiple
    of 60, so a genuine page cannot satisfy this. That property depends on the
    values in GOLDEN_FINGERPRINTS -- see the warning beside them before changing
    any fingerprint.

    min_peaks guards against calling two or three stray peaks a "series".
    """
    freqs = list(live_frequencies)
    if len(freqs) < min_peaks or fundamental_hz <= 0:
        return False
    return all(
        abs(f - round(f / fundamental_hz) * fundamental_hz) <= tolerance_hz
        for f in freqs
    )


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
