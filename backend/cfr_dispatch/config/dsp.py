# NOTE: For calibration of audio thresholds, device selection, and test procedures, see:
#   - docs/hardware_specification.md
#   - docs/test_procedures.md
# DSP settings and thresholds
NOISE_AMPLITUDE_THRESHOLD = 40
SUSTAINED_LOUDNESS_WINDOW = 5
SUSTAINED_LOUDNESS_CHUNKS_REQUIRED = 4
TONE_ANALYSIS_DURATION_SECONDS = 3.5

# Dispatch capture timing thresholds
MAX_DISPATCH_DURATION_S = 75
END_OF_DISPATCH_SILENCE_S = 3.0
END_OF_DISPATCH_RMS_THRESHOLD = 30

# Two-Phase Capture checkpoints
PHASE_1_CHECK_INTERVAL_S = 3.0
MIN_PHASE_1_DURATION_S = 10.0

# Pager Tones matching thresholds & fingerprints
MATCH_THRESHOLD_PERCENT = 0.50
FREQUENCY_TOLERANCE_HZ = 8
MIN_TONE_BURST_DURATION_S = 2.0
NUM_PEAKS_TO_FIND = 10
TONE_ZSCORE_THRESHOLD = 30.0

GOLDEN_FINGERPRINTS = {
    "PA Tone":     [595.00, 647.00],
    "Chief Tone":  [437.50, 656.25],
    "Engine Tone": [601.56, 1351.56],
    "Rescue Tone": [726.56, 890.62]
}

