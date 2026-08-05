# NOTE: For calibration of audio thresholds, device selection, and test procedures, see:
#   - docs/hardware_specification.md
#   - docs/test_procedures.md
# DSP settings and thresholds
NOISE_AMPLITUDE_THRESHOLD = 150
NOISE_AMPLITUDE_THRESHOLD_MIN = 100
SUSTAINED_LOUDNESS_WINDOW = 5
SUSTAINED_LOUDNESS_CHUNKS_REQUIRED = 5
TONE_ANALYSIS_DURATION_SECONDS = 3.5

# Dispatch capture timing thresholds
MAX_DISPATCH_DURATION_S = 75
END_OF_DISPATCH_SILENCE_S = 3.0
END_OF_DISPATCH_RMS_THRESHOLD = 80
POST_EVENT_RESET_SILENCE_S = 3.0

# Two-Phase Capture checkpoints
PHASE_1_CHECK_INTERVAL_S = 3.0
MIN_PHASE_1_DURATION_S = 10.0

# Pager Tones matching thresholds & fingerprints
MATCH_THRESHOLD_PERCENT = 0.50
FREQUENCY_TOLERANCE_HZ = 20
NUM_PEAKS_TO_FIND = 10
TONE_ZSCORE_THRESHOLD = 30.0

GOLDEN_FINGERPRINTS = {
    "PA Tone":     [595.00, 647.00],
    "Chief Tone":  [437.50, 440.00, 656.25, 660.00, 1320.00],
    "Engine Tone": [600.00, 601.56, 1350.00, 1351.56, 1800.00, 4050.00],
    "Rescue Tone": [725.00, 726.56, 890.00, 890.62, 2180.00, 2675.00]
}
