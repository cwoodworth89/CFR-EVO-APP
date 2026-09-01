# Whisper fine-tuning: how a dispatch recording becomes a training pair

**Status**: agreed 2026-08-31. Supersedes the whole-call labelling used by the
2026-07-17 run.

---

## The defect this replaces

`train_whisper_lora.py` calls `feature_extractor(speech, sampling_rate=16000)` with no
`max_length`. Verified against the installed source
(`transformers/models/whisper/feature_extraction_whisper.py`, 5.14.1, kiosk, 2026-08-31):
`truncation=True`, `padding="max_length"`, `max_length=n_samples = chunk_length * sr =
30.0 s`. See [`dependency-behaviour.md`](../standards/dependency-behaviour.md).

The label was the **whole call**. Locution broadcasts each dispatch twice, and the flagged
training set averages ~48 s, so:

```
audio the model is played :  [ 0:00 ──────────── 0:30 ]         hard stop
answer key it is graded on :  [ 0:00 ──────────────────── 0:48 ]
```

For ~18 s of every answer key there was no audio. Training has no way to express "I could
not hear that" — the only available lesson is *after the audio stops, keep talking*. The
2026-07-17 run trained a hallucination into the model, deliberately, once per sample. Its
reported 22.6% -> 3.5% WER was measured under this same setup and should not be trusted.

## The replacement: train on round 1

One round fits the window. The whole problem is locating it.

```
onset  = start time of the first spoken word
cut    = onset + (duration - 3.0 - onset) / 2
clip   = audio[onset : cut]
label  = round 1 of the verified transcript, via split_rounds()
```

### Why each term is knowable

| Term | Source |
|:--|:--|
| `onset` | **The first spoken word of a dispatch is always "Coquitlam"** (operator, 15-year SME, 2026-08-31). Whisper returns it with `word_timestamps=True`. Measured on 40 of the 497 flagged calls: **40 of 40** began with it. |
| `3.0` | The recorder ends a capture on a 3-second silence rule (operator, 2026-08-31). Independently measured across 15 recordings: trailing silence 3.14–3.39 s, leading 0.03–0.38 s. |
| `/ 2` | Locution reads the same text twice. Confirmed by transcribing both halves of three calls: each half independently produced the full round content. |
| `split_rounds` | Already exists, text-only, [`parser/announcement.py:296`](../../backend/cfr_dispatch/parser/announcement.py). |

### Why onset is measured per call, not assumed

Tone length varies. Measured onset across 40 flagged calls is **bimodal**, not a spread:

```
  2-3 s : ################ (16)
  3-4 s : ################## (18)
  6-8 s : ###### (6)          <- second tone pattern
  median 3.10s   mean 3.54s   max 6.62s
```

A fixed offset would be wrong by 2–3 s on that second cluster. An early cut loses the
"map grid NN" that ends round 1 — observed directly before onset was measured, on all
three calls tested. Per call it costs one word timestamp and is exact.

### Approaches rejected, and why

| Approach | Why not |
|:--|:--|
| Split on the inter-round pause | The system has no acoustic pause detector, and `split_rounds` is text regex on keywords — it yields no timestamp. |
| `librosa.effects.trim` to find speech start | Trims **silence**. Tones are loud, so they survive trimming and were counted as speech; this is what made the midpoint land `T/2` early. |
| Spectral flatness to separate tone from speech | Measured on 8 recordings; did not discriminate. Discarded. |
| A constant tone offset | The onset distribution is bimodal (above). |
| Reuse the capture-time seam | `TONE_ANALYSIS_DURATION_SECONDS = 3.5` is the analysis window, not the tone end. |

## Selection rules

A call enters the dataset when **all** hold:

1. `feedback_submitted` and a non-empty `verified_transcript` — a human wrote the label.
2. `include_in_training` is not false — the operator flagged it. This flag is authoritative;
   sampling the recordings directory instead swept in PA pages
   (*"Wilson, Wilson, you're good to go"*) that the flag had already excluded.
3. First word matches "Coquitlam" (fuzzy >= 0.7, so STT variants such as `COQUITLUM` pass).
4. **`round_len <= 30.0` — a clipped round is dropped, not truncated.** Operator ruling
   2026-08-31: prefer the cleanest dataset. Measured at ~5% of the flagged set.
5. `round_len >= 8.0` — below this the geometry is implausible; a bad cut, not a short call.

Rule 4 is the one that matters. Keeping a 34 s round would reintroduce the original defect
in miniature: 4 s of label with no audio behind it.

## What is NOT decided here

Whether the resulting model is deployed. Training produces an artifact and a backtest
number; changing `WHISPER_MODEL` on the kiosk is a separate, explicit decision made against
those numbers. The 2026-07-17 model was never deployed either — the kiosk has run stock
`base` for all 37 daemon starts on record.
