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


---

## Addendum 2026-08-29 — do the apparatus fingerprints have provenance?

**No. None of it.** The operator asked what date the Chief/Engine/Rescue fingerprints were
analysed, from how many calls, on what hardware and recorder. Searched the config, the docs
(`hardware_specification.md`, `test_procedures.md`), the calibration script and the git
history: **there is no record of any of it.** The values simply appear.

The nearest thing to a clue is `backend/tests/test_listener.py`, whose values are marked
*"Source fingerprints, 16kHz"* and are spaced exactly **7.8125 Hz** apart — `16000 / 2048`,
i.e. a 2048-point FFT at a 16 kHz sample rate. That is a fingerprint of the *analysis*, not a
provenance record, but it is consistent with the current `AUDIO_SAMPLE_RATE = 16000`.

### Three copies exist and they disagree

| Source | Chief | Engine | Rescue |
|:--|:--|:--|:--|
| **`config/dsp.py`** (used by the pipeline) | 440.20, 660.34 | 600.00, 1350.00 | 727.09, 891.99 |
| `scripts/calibrate_audio_interactive.py` | 437.50, 656.25 | 601.56, 1351.56 | 726.56, 890.62, **2179.69** |
| `tests/test_listener.py` | 5-point spread | 5-point spread | 5-point spread |

None imports from another. The calibration tool the docs tell operators to run for tone
verification is therefore checking against **different numbers than the live system uses**.

### But the values themselves are correct

Validated against the 98 confirmed real-dispatch events in `tone_spectral_history.jsonl`:

| Tone | Events | Observed | Configured | Drift |
|:--|--:|:--|:--|--:|
| Engine | 54 | 600 and 1350, **zero variance** | 600.00, 1350.00 | 0.0 Hz |
| Rescue | 40 | 726 and 892 | 727.09, 891.99 | −1.1 Hz |
| Chief | **4** | 440 and 659 | 440.20, 660.34 | −1.3 Hz |

**So re-deriving them is not needed — the numbers are right.** What was missing is their
history, and that has now been written into `config/dsp.py` citing this measurement.

Two things worth acting on:

* **Chief Tone rests on 4 observations.** Re-check as the corpus grows; it is the least
  evidenced of the three.
* **The two-decimal precision is fictional.** `analyze_live_audio()` returns
  `int(fft_freqs[p])`, so the detector cannot produce or match 0.01 Hz. Harmless under the
  tolerance, but it reads as a precision that was never measured.

### Tolerance could tighten, but it is not the PA fix

Observed drift is ≤1.3 Hz against a ±8 Hz tolerance. Scored across all 122 events, tightening
loses **no** real dispatch even at ±2 Hz — but it does not solve the PA collision either:

| Tolerance | Real dispatches losing their tone | PA pages still grazing apparatus |
|--:|--:|--:|
| 8 (current) | 0 | 9 |
| 4 | 0 | 9 |
| 3 | 0 | 7 |
| 2 | 0 | 3 |

Even at ±2 Hz three PA pages still graze an apparatus fingerprint, so **647 Hz remains the
fix**. Tightening to 4 is free hardening on this corpus, but Chief Tone's 4 samples are thin
evidence for narrowing anything — recommend leaving tolerance alone until the corpus grows.


---

## Addendum 2026-08-29b — fictional precision removed, and a third leak class found

Operator decision: drop the two-decimal values. `GOLDEN_FINGERPRINTS` is now whole Hz:

```python
"PA Tone":     [595, 647]      "Chief Tone":  [440, 660]
"Engine Tone": [600, 1350]     "Rescue Tone": [727, 892]
"Dispatch Announcement": [1000]
```

Every shift was under 0.35 Hz against a ±8 Hz tolerance. Re-scored across all 122 logged
events, **exactly one** match set changed — and it turned out to be worth finding.

### The one changed event is mains hum, not a pager tone

`TRIGGER-1787533320` gained `Rescue Tone`, because `891.99 → 892` admits a peak at exactly
900 Hz that was previously outside by 0.01 Hz. Its peaks:

```
300, 420, 540, 660, 780, 900, 1260, 1380, 1500
```

Every one is an **odd harmonic of 60 Hz** — 60 × 5, 7, 9, 11, 13, 15, 21, 23, 25. That is
electrical mains interference, not a dispatch tone.

It had **already** false-matched `Chief Tone` before the rounding, because 660 is both an odd
60 Hz harmonic and Chief's second frequency. It produced a real record: **`DISP-2026-483052`**,
6.59 s, transcript *"recording"*.

So the rounding did not create a false positive — it exposed one that was already there, and
the tightened value simply gave the same garbage event a second wrong label.

### This is a third leak class, separate from PA

| Class | Mechanism | Status |
|:--|:--|:--|
| PA pages | 647 Hz page grazes an apparatus fingerprint at the 50% floor | rule validated, awaiting operator |
| **Mains hum** | **60 Hz odd harmonics land on 660 (Chief) and 900 (Rescue)** | **newly found, unaddressed** |
| Short noise | — | not investigated |

A harmonic-series test would be a clean discriminator: if the detected peaks are all integer
multiples of ~60 Hz, it is interference, and no pager tone should be reported. That is a
different filter from the 647 Hz PA rule and should be evaluated on its own evidence rather
than bolted on — there is currently **one** confirmed example, which is not enough to design
against.

**Worth watching for**: `DISP-2026-483052` is a 6.6-second "dispatch" with the transcript
*"recording"*. If more short records with that shape appear, they are candidates for the same
cause.


### Is the harmonic gap worth fixing on its own? Measured 2026-08-29

**Rule tested**: every detected peak within 4 Hz of a multiple of 60 Hz, with at least 4 peaks.

```
flagged as hum:                    1 of 122 events  (TRIGGER-1787533320)
real dispatch events wrongly hit:  0 of 98
```

**The safety argument is structural, not just empirical**, which matters given the sample is
n=1. A genuine page can never satisfy "all peaks are multiples of 60" because every apparatus
fingerprint contains at least one frequency that is not:

| Tone | Frequencies | as multiples of 60 |
|:--|:--|:--|
| Engine | 600, 1350 | 10.0, **22.5** |
| Chief | 440, 660 | **7.33**, 11.0 |
| Rescue | 727, 892 | **12.12**, **14.87** |
| PA | 595, 647 | **9.92**, **10.78** |

So false positives are excluded by construction, not by luck of the sample.

> ⚠️ **That guarantee is tied to the current fingerprints.** If Chief were ever revised to
> something like `[420, 660]` — both multiples of 60 — the rule would start eating real Chief
> pages. Anyone changing `GOLDEN_FINGERPRINTS` must re-check this table.

**Recommendation: do not ship it on its own.** It is safe and small, but it touches the live
tone gate in `audio_listener.py`, and deploying that requires `sudo systemctl restart
cfr-agent`, which briefly drops the audio listener — a real call in that window is missed. That
is a poor trade for a defect seen once in 122 events.

**Bundle it with the 647 Hz PA fix instead.** Both change the same decision point in the same
function, so they share one deploy, one restart and one verification pass. The PA fix is
already validated and waiting only on operator decisions; when those land, both go together.


---

## Implemented 2026-08-29 — LOG-ONLY, not enforcing

Both rules are in, bundled as one change to the tone gate. **`REJECT_NON_DISPATCH_ENFORCE`
defaults to `False`**, so behaviour is unchanged: the listener logs what it *would* have
rejected and carries on.

That deliberately defers all three open decisions rather than pre-empting them — nothing is
suppressed, so an unconfirmed candidate or a mid-call PA tone cannot cost a dispatch, and the
log supplies the live evidence to settle both.

| File | Change |
|:--|:--|
| `config/dsp.py` | `REJECT_NON_DISPATCH_ENFORCE`, `PA_DISCRIMINATOR_HZ = 647`, mains-hum constants, all with provenance |
| `dsp_tone_spotter.py` | `has_pa_marker()`, `is_mains_hum()` |
| `audio_listener.py` | rejection evaluated **before** the apparatus branch |
| `config/__init__.py`, `audio_service/__init__.py` | re-exports |

Named `has_pa_marker`, not `is_pa_page`, because `log_tone_spectral_history` already takes an
`is_pa_page` parameter and shadowing it would be a trap.

**Verified with the shipped helpers** against all 122 logged events:

```
PA pages caught             : 24/24
mains hum caught            :  1/1
GENUINE DISPATCHES REJECTED :  0 of 97
```

### To enforce, later

1. Read the log first: `ssh tcfire@100.95.146.94 "grep 'WOULD REJECT' /home/tcfire/CFR-EVO-APP/backend/dispatch.log"`
2. Every line should be a PA page or hum. **If a real dispatch appears there, do not enforce.**
3. Then set `REJECT_NON_DISPATCH_ENFORCE = True` and `sudo systemctl restart cfr-agent`.

> Deploying this needs a `cfr-agent` restart, which briefly drops the audio listener — a live
> call in that window is missed. Worth timing.


---

## Operator decisions, 2026-08-29 — all three answered

1. **All six candidates are PA**, and tagged as such. `87EA26`, `A9D408`, `8E6CAD`, `2410A2`,
   `D467FE`, `002248`. The 647 Hz rule's ground truth is now operator-confirmed rather than
   partly inferred.
2. **`DISP-2026-282647` is excluded from the analysis.** Its PA tone arrives mid-call; the
   operator has also excluded it from the STT training set.
3. **Log-only for now.** `REJECT_NON_DISPATCH_ENFORCE` stays `False`.

### Re-verified against the confirmed labels, 125 events

```
confirmed PA / system-PA : 25   caught 25
everything else          : 99   flagged  1   <- the known mains-hum event
GENUINE DISPATCHES WRONGLY FLAGGED: 0
```

The 647 Hz rule is now **25/25 on operator-confirmed ground truth**, with the only other flag
being the interference case it is meant to catch.

---

## Chief Tone: 4 → 3, and why tagging alone will not grow it

Re-measured after screening out PA and hum:

| Tone | Events | Observed | Configured | Drift |
|:--|--:|:--|:--|--:|
| Engine | 55 | 600 / 1350, zero variance | 600, 1350 | 0.0 |
| Rescue | 41 | 726 / 892 | 727, 892 | −1.0 |
| **Chief** | **3** | 440 / 659 | 440, 660 | −1.0 |

**Chief dropped from 4 to 3: one of the original four was the mains-hum event.** The warning
that hum might be contaminating the Chief sample turned out to be true, and it was 25% of it.

### The important practical point

**Tagging historical records in the review panel does not add spectral samples.**
`tone_spectral_history.jsonl` is written by the listener at detection time, so it only grows
when new calls actually arrive. The log went 122 → 125 today; the operator's tagging improved
the PA *ground truth* (via the database join) but added nothing to the Chief *frequency*
evidence.

**But the audio is archived, so it can be backfilled.** There are **20 Chief-toned dispatches
with stored WAVs** against 3 in the spectral log. Re-running `analyze_live_audio()` over the
first 3.5 s of each archived recording would reconstruct the same peak data the listener would
have logged, taking Chief from 3 samples to as many as 20 — enough to actually judge the
fingerprint.

That is a contained offline script over `backend/data/audio/`, touching no live path. Worth
doing before any decision about the Chief fingerprint, and it would also let every apparatus
tone be re-validated on the full 487-recording corpus rather than on whatever happened to be
live since 2026-08-21.
