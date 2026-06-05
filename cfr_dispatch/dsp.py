# cfr_dispatch/dsp.py
# Digital Signal Processing and Tone Detection algorithms

import numpy as np
from scipy import signal
from cfr_dispatch.config import (
    AUDIO_SAMPLE_RATE,
    NUM_PEAKS_TO_FIND,
    GOLDEN_FINGERPRINTS,
    FREQUENCY_TOLERANCE_HZ,
    MATCH_THRESHOLD_PERCENT
)

def get_rms(data: np.ndarray) -> float:
    """Computes the root-mean-square value of a PCM audio array."""
    if data.size == 0:
        return 0.0
    return np.sqrt(np.mean(data.astype(np.float32)**2))

def analyze_live_audio(data: bytes, num_peaks: int = NUM_PEAKS_TO_FIND) -> set:
    """
    Analyzes an audio byte buffer for frequency peaks.
    Applies a high-pass Butterworth filter to eliminate baseline noise/static
    before computing the Fast Fourier Transform (FFT).
    """
    audio_array = np.frombuffer(data, dtype=np.int16)
    if len(audio_array) == 0:
        return set()
        
    cutoff_hz = 300.0
    nyquist_freq = 0.5 * AUDIO_SAMPLE_RATE
    normal_cutoff = cutoff_hz / nyquist_freq
    
    b, a = signal.butter(5, normal_cutoff, btype='high', analog=False)
    filtered_signal = signal.lfilter(b, a, audio_array)
    
    fft_data = np.fft.rfft(filtered_signal)
    fft_freqs = np.fft.rfftfreq(len(filtered_signal), 1.0 / AUDIO_SAMPLE_RATE)
    fft_magnitude = np.abs(fft_data)
    
    try:
        peak_indices = np.argpartition(fft_magnitude, -num_peaks)[-num_peaks:]
        return set(int(f) for f in fft_freqs[peak_indices])
    except (ValueError, IndexError):
        return set()

def get_best_match(live_frequencies: set) -> tuple[str, float] | tuple[None, None]:
    """
    Compares detected frequency peaks against GOLDEN_FINGERPRINTS.
    Returns the matched tone name and match ratio if it exceeds the MATCH_THRESHOLD_PERCENT.
    """
    best_match_tone = None
    best_match_score = -1.0
    
    for tone_name, golden_freqs in GOLDEN_FINGERPRINTS.items():
        matches_found = sum(1 for gf in golden_freqs if any(abs(lf - gf) <= FREQUENCY_TOLERANCE_HZ for lf in live_frequencies))
        score = matches_found / len(golden_freqs) if golden_freqs else 0.0
        
        if score > best_match_score:
            best_match_score = score
            best_match_tone = tone_name
            
    if best_match_score >= MATCH_THRESHOLD_PERCENT:
        return best_match_tone, best_match_score
    return None, None

def filter_known_tones(audio_data: np.ndarray, tone_name: str, sample_rate: int) -> np.ndarray:
    """
    Applies zero-phase IIR notch filters at the golden fingerprint frequencies
    associated with tone_name to clean up voice transcriptions.
    """
    if not tone_name or tone_name not in GOLDEN_FINGERPRINTS:
        return audio_data
        
    tone_frequencies = GOLDEN_FINGERPRINTS[tone_name]
    filtered_audio = audio_data.copy()
    
    for freq in tone_frequencies:
        b, a = signal.iirnotch(freq, 50.0, fs=sample_rate)
        filtered_audio = signal.lfilter(b, a, filtered_audio)
        
    return filtered_audio.astype(np.int16)
