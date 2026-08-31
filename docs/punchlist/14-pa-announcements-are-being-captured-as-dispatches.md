# Punch list #14 — PA announcements are being captured as dispatches

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 📢 PA Page Leakage |
| **Blocks** | 2 |
| **Origin** | `debug_and_qa_punchlist.md` L636–3617 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 14. PA announcements are being captured as dispatches
> **Status**: ⚠️ **Open — mechanism identified; blocked on corpus.** Re-checked 2026-08-21:
> **0 of 408** dispatches carry the `[PA]` tag
> (`count(*) FILTER (WHERE review_notes LIKE '%[PA]%')`).
>
> The negative-control suite described below cannot start until the operator has tagged
> some captures, so this item is **waiting on data, not on engineering**. The
> post-transcription retraction option is the one that can be designed in the meantime,
> since it depends on the Locution template rather than on audio fingerprints.

Several PA (station paging) announcements have been captured and persisted as real
dispatches. The likely mechanism is in `audio_listener.py`:

```python
pa_matches        = [m for m in all_matches if m[0] == "PA Tone"]
apparatus_matches = [m for m in all_matches if m[0] in ("Chief Tone", "Engine Tone", "Rescue Tone")]

if pa_matches and not apparatus_matches:
    # disregard, reset listener
elif apparatus_matches:
    # CAPTURE
```

A PA page is only discarded when it matches the PA tone **and no apparatus tone**. The
operator has confirmed that PA announcements can themselves carry apparatus tones. Any
such page satisfies `apparatus_matches` and is captured as a dispatch — the `elif`
branch wins.

That ordering is deliberate for the opposite case (a real dispatch preceded by a PA
chime must not be discarded), so the fix is not simply reversing the precedence. Options
worth evaluating against real audio:

* Whether a PA page's apparatus tones differ measurably from a dispatch's — the DSP
  already logs peak frequencies and Z-scores per capture.
* Whether the announcement that follows the tones can disambiguate: a dispatch always
  states units, an address and a map grid in the Locution template, a PA page does not.
  A post-transcription check could retract a capture that parses to nothing.
* Tightening `FREQUENCY_TOLERANCE_HZ` (currently 8 Hz) — but note item #1.4, where an
  event matched PA Tone on peaks 588/647 against golden 595/647, inside tolerance by a
  single hertz. Tolerance is implicated in **both** directions.

**Tagging convention (current, no code change needed)**: accidental PA captures are
marked by putting `[PA]` in the HITL **review notes** field. That field is already wired
end to end — editable in `VerificationSidebar.jsx`, submitted by `DispatchReview.jsx`,
accepted by `DispatchUpdateSchema`, returned by the API. A dedicated checkbox was
considered and rejected as not worth the UI weight for how rare these are.

Once a corpus of `[PA]`-tagged dispatches exists, their audio can be pulled from
`backend/audio_files/recordings/` by dispatch_id and run against the fingerprinting code
as a negative-control suite:

```sql
SELECT dispatch_id, audio_url FROM public.dispatches WHERE review_notes LIKE '%[PA]%';
```

As of 2026-08-21 no dispatches carry the tag yet, and the single
`pa_page_DISP-2026-AB76A8.wav` fixture was deleted rather than kept as a separate file —
its dispatch had no row in `public.dispatches`, and the corpus will come from tagged
captures instead.


---

## 🔎 Geocoder Substitution

---

## 14 (analysed). PA leakage — the discriminator is 647 Hz, and 595 Hz is what breaks the filter
> **Status**: ⚠️ **Open — root cause found and a rule validated against 122 real tone events.
> Not implemented: the change affects whether a real dispatch can be dropped (§7.2).**
> Full analysis: [`docs/briefings/pa_tone_discriminator.md`](../briefings/pa_tone_discriminator.md).

**647 Hz appears in 15 of 15 system-labelled PA events**, and in all three operator-`[PA]`-tagged
dispatches that occurred while `tone_spectral_history.jsonl` was running. It is the only
consistent PA marker — the tone's other component wanders (588, 576, 610, 526, 556…).

**Why the existing PA rejection fails.** `audio_listener.py:139` reads
`if pa_matches and not apparatus_matches`, so any apparatus match wins the tie — and with
`MATCH_THRESHOLD_PERCENT = 0.50`, a single frequency within ±8 Hz is enough to "match" a
two-tone fingerprint. A PA page's harmonics routinely graze one:

```
TRIGGER-1787409188  [561, 591, 647, 728, 842, 905, 1338]
   647 -> PA 647      | 591 -> PA 595   => PA 100%
   728 -> Rescue 727  => Rescue 50%     => apparatus wins, PA page dispatched
```

**And 595 Hz is not a PA signature at all** — it is present in **59 of 107** non-PA events, more
than half of real dispatches. Engine Tone's 600 Hz also sits 5 Hz from it, inside the ±8 Hz
tolerance, so those fingerprints are not separable on that component.

**Rules scored against all 122 events:**

| Rule | PA caught | **Real dispatches wrongly dropped** |
|:--|--:|--:|
| Current (`pa and not apparatus`) | 15 / 24 | 0 |
| **`647 Hz present`** | **24 / 24** | **0** |
| `647 Hz and apparatus < 100%` | 23 / 24 | 0 |
| `PA >= 50%` (PA wins outright) | 24 / 24 | **54** |
| `PA = 100%` | 6 / 24 | 0 |

Against strict ground truth only (15 system-labelled + 3 operator-tagged, excluding inference),
`647 Hz present` is **18/18 with zero false positives**.

The intuitive fix — letting PA win outright — is the **worst** option, dropping 54 real
dispatches, exactly because 595 Hz is common in genuine tones.

**Blocked on the operator** (all three in the briefing): confirm six untagged candidates are
PA (`87EA26`, `A9D408`, `8E6CAD`, `2410A2`, `D467FE`, `002248`); confirm the mid-call PA tone
case recorded on `DISP-2026-282647` cannot be affected; and choose whether to ship directly or
run log-only first.

**Also noted**: `647.00` already sits in `GOLDEN_FINGERPRINTS` with no provenance. Whatever
ships should cite this analysis (§6.3 tier 3) or a published PA tone spec if one exists.

---

## 🔊 Audio Playback & UI State
