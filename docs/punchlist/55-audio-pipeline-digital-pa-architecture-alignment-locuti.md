# Punch list #55 — Audio Pipeline & Digital PA Architecture Alignment (Locution CAD, 15s Phase 1, 3s Silence)

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | operational |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L4103 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 55. Audio Pipeline & Digital PA Architecture Alignment (Locution CAD, 15s Phase 1, 3s Silence)
> **Status**: ⚠️ **Open — originated from Gemini team review, needs verification against live kiosk.** Documented 2026-08-30.
>
> [!IMPORTANT]
> **Origin & Verification Guard (CLAUDE.md §6.6)**: This punchcard entry was compiled during the Gemini team architectural review. All parameters and operational model descriptions are staged/reported and must be verified against the running kiosk system (`tcfire@100.95.146.94`) and live Locution broadcast audio before marking complete.

**Physical & Acoustic Reality:**
1. **Locution CAD Automated TTS Dispatch**: The audio source is not a human dispatcher. It is a computer-generated Locution CAD text-to-speech voice system.
   * Cadence is fixed and machine-timed with a consistent $\approx 1.0\text{s} - 1.5\text{s}$ pause between Round 1 and Round 2.
   * There are no human hesitations, breathing pauses, or conversational delays.
2. **Direct Digital Speaker Feed**: Audio is captured via direct digital line-in / station PA computer feed, not an over-the-air analog RF radio receiver.
   * **No RF squelch tails, carrier drops, or radio key clicks**.
   * When Locution finishes speaking, the audio drops directly into clean digital silence ($<10\text{ RMS}$).

**Identified Parameter & Documentation Discrepancies:**
* **Silence Window Divergence**: `backend/cfr_dispatch/config/dsp.py` correctly defines `END_OF_DISPATCH_SILENCE_S = 3.0`, but `services/audio_analysis/src/audio_service/sound_capture.py` defaulted to `8.0s` in its function signature, and `.claude/skills/dispatch-pipeline-ops/SKILL.md` documented `8.0s`.
  * Because Locution's inter-round pause is only $\approx 1.0 - 1.5\text{s}$ and the line drops into true digital silence at call end, **`3.0s`** is authoritative, prevents trailing dead air in recordings, and speeds up Phase 2 verification.
* **Phase 1 Minimum Duration**: `config/dsp.py` had `MIN_PHASE_1_DURATION_S = 10.0`, while `sound_capture.py` defaulted to `20.0s`.
  * Calibrated standard is **`15.0s`** to ensure Locution has completed the entire Round 1 announcement (Units $\rightarrow$ Priority $\rightarrow$ Call Type $\rightarrow$ Address $\rightarrow$ Cross Streets $\rightarrow$ Talk Group $\rightarrow$ Map Grid) before the worker takes its first slice.
* **Max Dispatch Ceiling**: `MAX_DISPATCH_DURATION_S = 75` (~80s safety ceiling to prevent indefinite capture).
* **RMS Amplitude Provenance (40 RMS)**: 16-bit PCM integer amplitude floor ($5-18\text{ RMS}$ digital idle vs $300-2500+\text{ RMS}$ speech), with adaptive gate $\text{Threshold} = \max(40.0, \overline{\text{RMS}}_{\text{baseline}} \times 2.5)$ and silence cutoff at `30.0 RMS` (`END_OF_DISPATCH_RMS_THRESHOLD`).

#### Action Items for Implementation:
1. **Code Defaults**: Update `sound_capture.py:capture_full_dispatch()` default arguments to:
   * `max_duration_s: float = 75.0`
   * `min_phase_1_duration_s: float = 15.0`
   * `phase_1_check_interval_s: float = 3.0`
   * `end_of_dispatch_silence_s: float = 3.0`
2. **Config Alignment**: Set `MIN_PHASE_1_DURATION_S = 15.0` in `backend/cfr_dispatch/config/dsp.py` with inline provenance comments citing Locution CAD automated timing.
3. **Terminology Prune**: Purge outdated analog RF terminology ("squelch tails", "channel unkey", "radio carrier noise") across code comments and skill files, replacing with digital station PA feed descriptions.
4. **Skill Runbooks**: Update `dispatch-pipeline-ops/SKILL.md` (both `.claude/skills/` and `.agents/skills/`) sequence diagrams and parameter tables.



---
