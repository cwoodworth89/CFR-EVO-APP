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
# Half a fingerprint counts as a match. With two-tone fingerprints that means ONE
# frequency decides, which is what lets PA pages graze apparatus tones -- see the
# note above GOLDEN_FINGERPRINTS and punch-list #14.
MATCH_THRESHOLD_PERCENT = 0.50
# Measured 2026-08-29: observed drift across 98 real dispatch events is at most
# 1.3 Hz, so +/-8 is generous. Tightening to 4 loses no real dispatch on that
# corpus, but it does NOT fix the PA collision on its own (PA 595 vs Engine 600 is
# 5 Hz) and Chief Tone has only 4 samples behind it. Do not tighten without
# re-running the analysis in docs/briefings/pa_tone_discriminator.md.
FREQUENCY_TOLERANCE_HZ = 8
MIN_TONE_BURST_DURATION_S = 2.0
NUM_PEAKS_TO_FIND = 10
TONE_ZSCORE_THRESHOLD = 30.0

# ---------------------------------------------------------------------------
# PAGER TONE FINGERPRINTS
#
# ORIGIN: unknown. These were derived early in the project and NO provenance was
# recorded -- not the date, the sample count, the hardware, nor the recorder.
# The question was asked on 2026-08-29 and could not be answered from the code,
# the docs, or the git history. Treat the paragraphs below as the only source.
#
# VALIDATED 2026-08-29 (CLAUDE.md 6.3 tier 3, measured on this system) against
# backend/data/tone_spectral_history.jsonl -- 122 real tone events logged by the
# live listener, of which 98 are confirmed real dispatches:
#
#   Engine Tone   54 events   600 Hz and 1350 Hz observed in ALL 54, zero variance
#   Rescue Tone   40 events   726 Hz (-1.1 from 727.09) and 892 Hz, all 40
#   Chief Tone     4 events   440 Hz and 659 Hz (-1.3 from 660.34), all 4
#
# So the VALUES are correct: observed drift is at most 1.3 Hz. What is missing is
# their history, not their accuracy.
#
# CAVEAT: Chief Tone rests on only 4 observations. It is the least evidenced of
# the three and should be re-checked as the corpus grows.
#
# INTEGERS, DELIBERATELY. analyze_live_audio() reports integer Hz
# (int(fft_freqs[p]) in dsp_tone_spotter.py), so a two-decimal fingerprint states a
# precision the detector can neither produce nor match. The former values
# (440.20 / 660.34 / 727.09 / 891.99) were rounded to whole Hz on 2026-08-29 --
# every shift was under 0.35 Hz against a tolerance of 8.
#
# Re-scored across all 122 logged events, exactly ONE match set changed, and it was
# already garbage: TRIGGER-1787533320 gained "Rescue Tone" because 891.99 -> 892
# admits a peak at exactly 900 Hz. That event's peaks are 300/420/540/660/780/900/
# 1260/1380/1500 -- every one an odd harmonic of 60 Hz, i.e. MAINS HUM, not a pager
# tone. It had already false-matched Chief Tone on 660 and produced a 6.6 s
# "dispatch" (DISP-2026-483052, transcript "recording"). See punch-list #14.
#
# TWO OTHER COPIES OF THESE NUMBERS EXIST AND DISAGREE:
#   backend/scripts/calibrate_audio_interactive.py -- Chief 437.50/656.25,
#       Engine 601.56/1351.56, Rescue 726.56/890.62/2179.69
#   backend/tests/test_listener.py -- 5-point spreads marked "Source fingerprints,
#       16kHz", spaced 7.8125 Hz apart (= 16000/2048, a 2048-point FFT at 16 kHz),
#       which is the closest thing to a record of how the originals were derived
# Neither is imported from here. This file is the one the pipeline uses.
#
# "PA Tone" 595.00 IS A LIABILITY, NOT A SIGNATURE. Measured 2026-08-29: 595 Hz
# appears in 59 of 107 non-PA events -- more than half of real dispatches -- while
# 647 Hz appears in 15 of 15 labelled PA events. With MATCH_THRESHOLD_PERCENT at
# 0.50, half a fingerprint is a match, so 595 alone marks a real dispatch as PA-ish
# and 647's partner harmonics graze apparatus tones. Engine's 600 Hz also sits 5 Hz
# from 595, inside FREQUENCY_TOLERANCE_HZ, so those two are not separable on that
# component at all. See docs/briefings/pa_tone_discriminator.md and punch-list #14
# before changing the PA entry.
# ---------------------------------------------------------------------------
GOLDEN_FINGERPRINTS = {
    "PA Tone":               [595, 647],
    "Chief Tone":            [440, 660],
    "Engine Tone":           [600, 1350],
    "Rescue Tone":           [727, 892],
    "Dispatch Announcement": [1000],
}



# ---------------------------------------------------------------------------
# NON-DISPATCH REJECTION (punch-list #14) — LOG-ONLY UNTIL EXPLICITLY ENABLED
#
# Two rules that identify audio which triggered the listener but is NOT a
# dispatch. Both are validated (see docs/briefings/pa_tone_discriminator.md), and
# both are DISABLED by default: with ENFORCE False they only log what they WOULD
# have rejected, changing no behaviour.
#
# The asymmetry is why. Admitting a PA page is an annoyance; suppressing a real
# dispatch means a crew is not alerted. Log-only converts a 122-event sample into
# live operational evidence before anything is actually suppressed, and it leaves
# two open operator questions harmless in the meantime: whether six untagged 647 Hz
# candidates are genuinely PA, and whether a PA tone occurring mid-dispatch could
# ever reach this decision.
#
# To enforce, set REJECT_NON_DISPATCH_ENFORCE = True and restart cfr-agent.
# Review backend/dispatch.log for "WOULD REJECT" lines first.
REJECT_NON_DISPATCH_ENFORCE = False

# --- PA pages -------------------------------------------------------------
# 647 Hz is the only stable PA marker: present in 15/15 labelled PA events and
# 18/18 under strict ground truth, with 0 of 98 real dispatches touched. Measured
# 2026-08-29 over backend/data/tone_spectral_history.jsonl (§6.3 tier 3).
#
# Do NOT use the PA Tone fingerprint's other component, 595 Hz, for this: it
# appears in 59 of 107 non-PA events. Letting PA win on a 595 match drops 54 real
# dispatches. 647 alone is the discriminator.
PA_DISCRIMINATOR_HZ = 647

# --- Mains hum ------------------------------------------------------------
# 60 Hz odd harmonics land on Chief's 660 and Rescue's 892+8, so interference can
# register as a dispatch. Confirmed once: DISP-2026-483052, a 6.6 s "dispatch"
# transcribed as "recording", whose peaks were 300/420/540/660/780/900/1260/1380/
# 1500 — every one an odd multiple of 60.
#
# Safe BY CONSTRUCTION, not merely by sample: every apparatus fingerprint contains
# at least one frequency that is NOT a multiple of 60 (Engine 1350 = 22.5x, Chief
# 440 = 7.33x, Rescue both, PA both), so a genuine page cannot satisfy "every peak
# is a multiple of 60".
#
# !! That guarantee is tied to the values in GOLDEN_FINGERPRINTS above. If any
# !! fingerprint is ever revised so that ALL of its frequencies are multiples of
# !! 60 (e.g. Chief -> [420, 660]), this rule would start rejecting real pages.
# !! Re-check the table in docs/briefings/pa_tone_discriminator.md on any change.
MAINS_HUM_FUNDAMENTAL_HZ = 60.0      # North American grid
MAINS_HUM_TOLERANCE_HZ = 4.0
MAINS_HUM_MIN_PEAKS = 4              # too few peaks is not evidence of a series
