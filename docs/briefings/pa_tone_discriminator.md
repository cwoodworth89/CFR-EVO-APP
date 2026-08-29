# PA page leakage: the discriminator is 647 Hz, and 595 Hz is why the filter fails

**Written 2026-08-29.** Punch-list **#14**. Findings from the operator's `[PA]`-tagged calls
and the kiosk's own spectral history. **Nothing implemented yet** — the fix changes whether a
real dispatch can be dropped, which is an operator decision (CLAUDE.md §7.2).

---

## The evidence

`backend/data/tone_spectral_history.jsonl` on the kiosk holds **122 real tone events** with
their measured peak frequencies, written at detection time. This is measured data from the
running system, not a re-derivation from audio.

**647 Hz appears in 15 of 15 system-labelled PA events.** No other frequency comes close to
that consistency — the PA tone's second component wanders (588, 576, 610, 526, 556…), but 647
is present every single time.

Cross-referencing the operator's nine `[PA]`-tagged dispatches by timestamp (the log keys on
`TRIGGER-<epoch>`, the database on `DISP-…`, so they only join on time):

* **Three** of the nine occurred while the spectral log was running — `5AC92A`, `6DE4A5`,
  `9FAA52`. **All three contain 647 Hz.**
* The other six predate the log (it starts 2026-08-21).

Six further events carry 647 Hz and were **not** tagged, but match the PA profile exactly:
8–16 s duration, `transcription failed` or fragments like *"watch us up"*, no units, confidence
0. They are almost certainly untagged PA pages — see **What needs your confirmation** below.

---

## Why the existing filter misses them

The config already has a PA fingerprint, and the listener already tries to reject PA pages:

```python
GOLDEN_FINGERPRINTS = {
    "PA Tone":     [595.00, 647.00],
    "Engine Tone": [600.00, 1350.00],
    "Chief Tone":  [440.20, 660.34],
    "Rescue Tone": [727.09, 891.99],
}
MATCH_THRESHOLD_PERCENT = 0.50   # half a fingerprint is a match
FREQUENCY_TOLERANCE_HZ  = 8
```

`audio_listener.py:139`:

```python
if pa_matches and not apparatus_matches:   # <-- apparatus wins any tie
```

**Two things combine to defeat it.**

**1. A PA page's harmonics graze an apparatus fingerprint at the 50% floor.** Only *one* of two
frequencies must land within ±8 Hz. A real leaked event:

```
TRIGGER-1787409188  [561, 591, 647, 728, 842, 905, 1338]
   647 -> PA Tone      (1/2 = 50%)  matched
   591 -> PA Tone 595  (2/2 = 100%) matched
   728 -> Rescue 727.09 (1/2 = 50%) matched   <-- apparatus
```

Both match, so `not apparatus_matches` is false and the PA page is dispatched as a Rescue call.

**2. 595 Hz is not a PA signature at all.** It is in **59 of 107** non-PA events — more than
half of *real* dispatches. Because 50% of the PA fingerprint is enough, 595 alone marks a real
dispatch as PA-ish, which is what makes PA and apparatus collide so often. Note also that
Engine Tone's 600 Hz sits 5 Hz from PA's 595 — inside the ±8 Hz tolerance, so those two
fingerprints are not separable at all on that component.

---

## Candidate rules, scored against all 122 events

| Rule | PA caught | **Real dispatches wrongly dropped** |
|:--|--:|--:|
| **Current** (`pa and not apparatus`) | 15 / 24 | 0 |
| **`647 Hz present`** | **24 / 24** | **0** |
| `647 Hz and apparatus < 100%` | 23 / 24 | 0 |
| `PA >= 50%` (PA wins outright) | 24 / 24 | **54** ← catastrophic |
| `PA = 100%` (both 595 and 647) | 6 / 24 | 0 |

Against **strict** ground truth only — the 15 system-labelled plus the 3 operator-tagged,
excluding my six inferences — `647 Hz present` catches **18 of 18 with zero false positives**,
and flags exactly the six unconfirmed candidates.

"PA wins outright" is the intuitive fix and it is the *worst* option: it drops 54 real
dispatches, precisely because 595 Hz is common in genuine tones.

---

## Proposed change

1. **Make 647 Hz the discriminator.** Either drop 595 from the PA fingerprint, or special-case
   647 rather than relying on the 50% rule. 595 is actively harmful as a PA marker.
2. **Let PA take precedence over an apparatus match** when 647 is present — inverting
   `audio_listener.py:139`.
3. Keep the spectral history logging; it is what made this diagnosable.

---

## What needs your decision

**The safety asymmetry runs one way.** Admitting a PA page is an annoyance. Dropping a real
dispatch means a crew is not alerted. So a rule that is perfect on 122 events still deserves a
conservative rollout.

1. **Confirm the six candidates are PA.** `DISP-2026-87EA26`, `A9D408`, `8E6CAD`, `2410A2`,
   `D467FE`, `002248` — all 8–16 s with failed transcription. If any is a **real** dispatch,
   the 647 Hz rule has a false positive and must not ship as written.

2. **A real dispatch interrupted by a PA tone.** Your own note on `DISP-2026-282647` records
   *"a [PA] tone mid dispatch call"*. Tone analysis runs on the first 3.5 s, so a mid-call PA
   tone should not reach the decision — but that is reasoning, not a measurement, and it is the
   one scenario where this change could drop a live call. Worth confirming before rollout.

3. **Rollout shape.** Suggested: log-only first — record what the rule *would* have rejected,
   without acting on it — for a week of live traffic. That converts a 122-event sample into
   operational evidence before anything is suppressed. Say if you would rather just ship it.

> **Provenance note**: 647.00 Hz currently appears in `GOLDEN_FINGERPRINTS` with no source.
> Whatever ships should cite this analysis (§6.3 tier 3, measured on this system) and, if the
> station PA has a published tone specification, that should supersede it.
