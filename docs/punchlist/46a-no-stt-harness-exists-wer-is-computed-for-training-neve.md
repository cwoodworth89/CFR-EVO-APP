# Punch list #46a — No STT harness exists — WER is computed for training, never for regression

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | hygiene |
| **Area** | 🧾 Import Completeness Audit, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2973 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 46. No STT harness exists — WER is computed for training, never for regression
> **Status**: ✅ **Closed 2026-09-05 — `tools/harness_chain.py` is the harness; first runs recorded.**
> *(Opened as: ⚠️ Open — raised 2026-08-26.)* See [`docs/qa_harnesses.md`](../qa_harnesses.md) §4 and §8.

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
extraction ([`extract_training_data.py:182`](../../tools/extract_training_data.py)),
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

### Closed 2026-09-05

[`tools/harness_chain.py`](../../tools/harness_chain.py) (`eb0f801`, `ec6988a`) does what this item
asked for: it replays the stored recordings through the model in service, scores round 1
against `verified_transcript` (the round trap above is handled by comparing round 1 to round
1), pushes each transcript through the parser and the production payload builder with the
real geocoder, and reports by month with `--json`/`--baseline` for before-and-after and
`--record` into `public.evaluation_history`. The round-1 training clips are left out of the
WER unless `--include-training`; `--only-csv` restricts to the round-1 holdout.

First recorded runs on the kiosk, model `whisper-base-cfr-ct2`:

| Run | n | WER (round 1) | Map grid wrong | Same place |
|:--|--:|--:|--:|--:|
| Verified calls since 2026-08-31 | 12 | 1.92 % on the 2 not in the training set | 2 | 91.7 % |
| Round-1 holdout, 44 clips the model never saw | 44 | **4.55 %** mean, 0 % median | 1 | 88.6 %, p90 22 m |

The holdout figure is the honest one until this week's 32 unreviewed calls are verified; those
become the next holdout automatically because they post-date the training set. What the item
predicted the harness would surface is now measurable rather than argued: a transcription
change that moves the WER but drops the map grid shows up as a `map_grid` WRONG count in the
same run. `tools/harness_history.py` lists every run; `qa_harnesses.md` §8 is the procedure.
