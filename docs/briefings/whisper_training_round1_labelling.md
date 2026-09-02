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

One round fits the window. The whole problem is locating it -- and both edges are measured
per call, neither is derived.

```
onset    = start time of the first spoken word ("Coquitlam")
boundary = start time of round 2, from split_rounds() over the timestamped words
clip     = audio[onset : boundary]
label    = round 1 of the verified transcript, via split_rounds()
```

### Why each term is knowable

| Term | Source |
|:--|:--|
| `onset` | **The first spoken word of a dispatch is always "Coquitlam"** (operator, 15-year SME, 2026-08-31). faster-whisper returns it with `word_timestamps=True`. 40 of 40 flagged calls sampled began with it. |
| `boundary` | `split_rounds()` is the parser's own rule for where a round ends ("map grid NN", or the next "Coquitlam" that opens a round). Rebuild the normalised text from the timestamped words, split it, map the boundary offset back to the word that starts round 2. Same rule for the audio cut and for the text label. |
| `split_rounds` | Already exists, text-only, [`parser/announcement.py:296`](../../backend/cfr_dispatch/parser/announcement.py). |

### The midpoint formula, and why it was retired

The first version cut at `onset + (duration - 3.0 - onset) / 2` -- the 3.0 s being the
recorder's silence rule -- on the assumption that the recording holds exactly two rounds. The
broadcast is computerised and the rounds are exact repeats, so on a clean recording that
midpoint *is* the boundary. But a trailing addendum broke it silently, and when both methods
were run over the whole corpus on 2026-09-01:

```
measured boundary vs the midpoint formula:  median +0.22 s,  range -9.6 s to +20.3 s
```

A median near zero and a range of thirty seconds means the assumption held on most calls and
failed badly on a minority -- recordings that do not contain two clean rounds. The measured
boundary cuts those correctly; the retired formula cut them wrong and said nothing. The
cut diagnostic (words heard in the clip / words in the label) moved from 1.07 to **1.00**.

### "Cut at the second Coquitlam" -- rejected

The obvious shortcut is wrong: round 1 contains "Coquitlam" twice ("...use talk group 10
Combined Response **Coquitlam**, map grid 97, **Coquitlam** Engine 1..."), so a
second-occurrence cut slices mid-round-1. `split_rounds` already encodes the real rule; a
second rule that could drift from the parser's was not written (CLAUDE.md §6.2).

### Approaches rejected earlier, and why

| Approach | Why not |
|:--|:--|
| Split on the inter-round pause | The system has no acoustic pause detector; `split_rounds` is text regex and yields no timestamp. |
| `librosa.effects.trim` to find speech start | Trims **silence**. Tones are loud, so they survived trimming and were counted as speech -- the midpoint then landed `T/2` early. |
| Spectral flatness to separate tone from speech | Measured on 8 recordings; did not discriminate. Discarded. The explanation offered at the time ("bandlimited radio audio") was invented and wrong -- the audio is not radio. |
| A constant tone offset | Onset is bimodal across the corpus (2-4 s and a distinct 6-8 s cluster). |
| Reuse the capture-time seam | `TONE_ANALYSIS_DURATION_SECONDS = 3.5` is the analysis window, not the tone end. |

## Label quality is checked before training

Two of six holdout address failures on 2026-09-02 were the **label**: "Norbur Pl" for
Norbury Pl (the model's "norbery" was closer to the truth than its reference), and
"driveuse". `check_verified_transcripts.py` validates every flagged transcript against
`public.roads`, `public.vocabulary`, `public.parcels` and the corpus, and
`prepare_training_clips.py` refuses to build while a main-address street the city does not
have remains. First run over the corpus: 12 blocking, 72 advisory. Operator ruling 2026-09-02.

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
