# Which cross-round disagreements are worth showing a crew

**Date:** 2026-08-30
**Re:** punch-list #54 — the confidence score is scrapped; warnings move to the amber flag model
**Harness:** `backend/scripts/backtest_round_comparison.py` (read-only, real records only)
**Module:** `backend/cfr_dispatch/pipeline/round_comparison.py`

---

## Why measure before building

A flag that fires on most calls is noise, and a flag that fires on the wrong calls is worse
than none. Every field the pipeline parses is observed twice — Locution announces each call
twice — so *every* field could carry a disagreement flag. Most of them should not.

Replayed 493 stored transcripts through the current parser and comparator, scored against
the operator's own `quality_rating` and `verified_address`.

---

## Result: two signals worth having, five that are noise

### Worth flagging

**Address disagreement between rounds** — fires on 98 of 493 calls (20%):

| Address verdict | n | rated FAILED | operator corrected |
|:--|--:|--:|--:|
| **disagree** | 98 | **14.1%** | **28.6%** |
| agree | 305 | 5.3% | 13.5% |
| single (one round only) | 87 | 5.2% | 6.9% |

2.7× the failure rate and 2.1× the correction rate, at a 20% flag rate. This is the signal.

**No call type or response type in either round** — fires on 14 calls (3%):

| | n | rated FAILED | operator corrected |
|:--|--:|--:|--:|
| `call_type` absent from both rounds | 14 | **30.0%** | **46.2%** |
| `response_type` absent from both rounds | 14 | **30.0%** | **46.2%** |
| (baseline, agree) | ~360 | ~6.8% | ~16% |

**The strongest signal in the corpus**, and one nobody was looking for: roughly 4× the
failure rate and 3× the correction rate. It is not about the call type at all — if the
parser could not find a call type or a response type in *either* round, the transcript is
badly damaged overall, and the address is likely wrong too. Low recall, high precision.

### Not worth flagging

| Field | disagree FAILED% | agree FAILED% | Verdict |
|:--|--:|--:|:--|
| `cross_streets` | 8.9% | 5.8% | marginal — 1.5×, not enough separation |
| `subaddress` | 8.5% | 7.1% | **no signal** — and correction rate is *lower* when disagreeing (12.0% vs 14.8%) |
| `units` | 5.3% | 7.2% | **inverted** — disagreement is associated with *fewer* failures |
| `map_grid` | 0.0% (n=8) | 7.4% | no usable signal |
| `call_type` (disagreeing) | 0.0% (n=7) | 6.8% | no signal — the *absence* case above is the one that matters |
| `radio_channel` | — | 7.4% | never disagrees at all across 493 calls |

Had every field's disagreement been flagged, most flags would have been noise and two would
have pointed the wrong way. That is the whole reason for measuring first.

---

## The disagreements are STT street-name variance, and neither round is reliably right

Every address disagreement sampled is the same shape — two transcriptions of one street
name. What matters is the third column:

| Dispatch | Round 1 | Round 2 | **Operator** |
|:--|:--|:--|:--|
| `1388CD` | 3415 Harbour Rd | 3415 Harbor Rd | **3415 Harper Road** |
| `959DD1` | 3100 Osada Ave | 3100 Ozeita Ave | **3100 Ozada Avenue** |
| `A2B5AE` | 3133 Patulow Cres | 3133 Petulo Cres | **3133 Patullo Cres** |
| `E792B0` | 2900 Barnette Hwy | 2900 Barnett Hwy | **2900 Barnet Highway** |
| `1EBEA3` | 5 Dayanee Springs Blvd | 5 Dhyani Springs Blvd | 3105 Dayanee Springs Boulevard |
| `4F427E` | 3000 Lowheed Hwy | 3000 Lougheed Hwy | 3000 Lougheed Highway |

**In four of six, the operator's answer matches neither round.** Any arbitration rule —
"prefer round 2", "prefer the higher-scoring street match" — would have produced a
confident wrong answer on those. This is the measured case for the comparator reporting
both values and choosing neither (CLAUDE.md §6.1), and it is why no
"pick the better round" logic was built.

It also suggests where the real fix lives: these are **STT vocabulary failures**, not
parser failures. `Harper` → `Harbour`/`Harbor` is the street-biasing problem
(punch-list #18), reached from a different direction.

---

## Caveats, stated rather than buried

* **The rated subset is not a random sample.** The operator reviews what the operator
  reviews. The flagged and unflagged buckets are comparable *to each other* within this
  corpus; none of these rates estimate a citywide rate.
* **Replay uses today's parser**, not the one that ran at the time. That is deliberate — it
  scores the signal as it would behave now — but the numbers do not describe what the
  operator historically saw.
* **Phase 1 is not in this measurement.** Its parse lives in ephemeral session state and is
  not stored, so only Phase 2 round 1 vs round 2 is recoverable. That is also the pairing
  that matters: Phase 1 and Phase 2 transcribe overlapping audio through the same model and
  agree largely by construction, which is why 389 of 510 records carried confidence 100.
* **18 calls produced only one round** and cannot be cross-checked at all. Absence of a
  disagreement is not evidence of agreement, which is why the comparator reports `SINGLE`
  as its own verdict rather than folding it into `AGREE`.

---

## Recommended next step

Flag two things, not eight:

1. **Address disagreement between rounds** — show both values, pick neither.
2. **No call type or response type parsed from either round** — a "transcript quality"
   warning rather than a field-specific one.

Everything else measured here should stay silent. Wiring is not yet done: the comparator is
built and tested but not called from `phase2.py`, deliberately, while the confidence-column
removal is in flight.
