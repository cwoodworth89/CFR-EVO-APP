# Punch list #46a — No STT harness exists — WER is computed for training, never for regression

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | hygiene |
| **Area** | 🧾 Import Completeness Audit, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2973 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 46. No STT harness exists — WER is computed for training, never for regression
> **Status**: ⚠️ **Open — raised 2026-08-26.** See [`docs/qa_harnesses.md`](qa_harnesses.md) §4.

`extract_training_data.py` and `backtest_regression.py` compute Word Error Rate to feed Whisper
training. Neither answers **"did this STT change make the system better or worse against
historical audio?"** — so STT configuration changes currently ship unmeasured.

Audio is available on essentially every dispatch (`audio_url`), so the corpus supports this.

**What it needs:**

* Replay stored audio through the current faster-whisper configuration.
* Score against `verified_transcript` — **after** handling the round trap below.
* Report **by month**, and report *both* WER and downstream field accuracy. A WER improvement
  that loses the map grid off the tail is not an improvement, and WER alone cannot see that.

#### ⚠️ The trap that will corrupt any STT measurement

**`verified_transcript` holds ONE round; `raw_transcript` holds two.** The reviewer verifies a
single round; the duplication that matches it to the two-round audio happens only at training
extraction ([`extract_training_data.py:182`](../backend/scripts/extract_training_data.py)),
never in the database column. Confirmed by query: `respond` appears once in 197 of 202 verified
transcripts.

**Diffing the two columns directly reports ~50% error on a perfect transcription.** Duplicate
the verified text first the way the extractor does, or compare round-for-round.

#### Two findings already waiting for it

* **Tail truncation** — 2026-07 lost `map grid` from 37 transcripts (18%) while those calls had
  *longer* median audio (50.6s vs 47.5s) and *fewer* words (37 vs 51). Fixed by the operator's
  audio-listener work around 2026-07-29; zero since. A harness would have flagged it the week
  it started.
* **Stable mis-recognitions** — faster-whisper writes `smoldering` 5/5 (never `smouldering`)
  and `Tassus` for Tahsis in 2 of 3 occurrences. These belong as recognition aliases in the
  street vocabulary, the same pattern already applied to call types in #43.

---
