# NOTE: For calibration of audio thresholds, device selection, and test procedures, see:
#   - docs/hardware_specification.md
#   - docs/test_procedures.md
# DSP settings and thresholds
NOISE_AMPLITUDE_THRESHOLD = 3000
NOISE_AMPLITUDE_THRESHOLD_MIN = 1500
SUSTAINED_LOUDNESS_WINDOW = 5
SUSTAINED_LOUDNESS_CHUNKS_REQUIRED = 5
TONE_ANALYSIS_DURATION_SECONDS = 3.5

# Dispatch capture timing thresholds
MAX_DISPATCH_DURATION_S = 59
END_OF_DISPATCH_SILENCE_S = 3.0
END_OF_DISPATCH_RMS_THRESHOLD = 450
POST_EVENT_RESET_SILENCE_S = 3.0

# Two-Phase Capture checkpoints
PHASE_1_CHECK_INTERVAL_S = 3.0
MIN_PHASE_1_DURATION_S = 10.0

# Pager Tones matching thresholds & fingerprints
MATCH_THRESHOLD_PERCENT = 0.85
FREQUENCY_TOLERANCE_HZ = 10
NUM_PEAKS_TO_FIND = 10
TONE_ZSCORE_THRESHOLD = 40.0

GOLDEN_FINGERPRINTS = {
    "Chief Tone":  [437.50, 656.25],
    "Engine Tone": [601.56, 1351.56],
    "Rescue Tone": [726.56, 890.62]
}
