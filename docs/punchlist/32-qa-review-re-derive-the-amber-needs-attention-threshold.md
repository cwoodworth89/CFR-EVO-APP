# Punch list #32 — QA review: re-derive the amber "needs attention" threshold once more calls are rated

| | |
|:--|:--|
| **Status** | DEFERRED |
| **Severity** | hygiene |
| **Area** | 🏷️ Response Terminology & Status Colour |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L1607 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 32. QA review: re-derive the amber "needs attention" threshold once more calls are rated
> **Status**: 🕓 **Deferred by the operator 2026-08-23 — revisit after more HITL reviews.**
> The threshold stays at **90**, now carrying its measurement inline
> (`frontend/src/utils/dispatchModel.js`). This item exists so the provisional decision is not
> mistaken later for a settled one.

#### What the operator actually wants the flag to mean

Not "low transcript confidence" — **"would the crew have reached the right address."** In the
operator's words, *operational* means the crew would at least get to the right address even if
other data was poor, and that is the factor that matters. So the amber trigger should fire on
**anything below OPERATIONAL, or a poor geocode score**, rather than on overall parser
confidence.

That is a different signal from `confidence_score`, and the two do not agree.

#### Measurement run 2026-08-23 — and a correction to an earlier figure

202 reviewed calls (`feedback_submitted` with a non-empty `verified_address`), comparing the
system address to the operator's correction.

**A first pass compared the strings raw and reported 25% of the `score 100` band as
"corrected". That figure was wrong and is withdrawn.** Most of those diffs were cosmetic —
suffix expansion (`HWY`→`HIGHWAY`, `AVE`→`AVENUE`, `CRES`→`CRESCENT`), unit-number stripping
(`1142 DUFFERIN ST 152` → `1142 DUFFERIN ST`), and removal of the `(street centroid)`
annotation. None of those would send a crew anywhere different.

After normalising suffixes, trailing unit numbers and annotations:

| Confidence | Reviewed | Substantively wrong address |
|:--|--:|--:|
| `0` | 10 | **100%** |
| 45–78 | 20 | **60%** |
| 81–89 | 15 | **0%** |
| 91–96 | 9 | **0%** |
| `100` | 148 | **8%** |

**The break is at 80, not 90.** The 81–89 band — which looked mediocre against
`quality_rating` — is *flawless* on address. So a cutoff at 90 is **conservative rather than
wrong**: it flags a band that has not actually failed. For a warning colour that is the safe
direction to err, which is why 90 is retained rather than moved.

#### Why it is not moved to 80 today

* 81–89 has only **15** reviewed calls. Zero failures in 15 is not yet zero failure rate.
* **`score 100` still gets 8% wrong** (12 of 148). Confidence is not a complete proxy for
  geocode correctness, so *no* threshold on this field alone catches everything the operator
  cares about. A geocode-specific quality signal would serve better than a parser-confidence
  one — see below.
* `confidence_score = 0` is a **distinct failure mode**, not merely "low": all 30 such rows
  are hard resolution failures (13 have no address, 19 already flagged `verify_location`) and
  10 of 10 reviewed had the address corrected. Worth its own amber reason.

#### Data-quality problem this exposed, worth fixing before the next measurement

**`verified_address` is being used for cosmetic edits, which contaminates it as ground truth.**
Reviewers expand suffixes and strip unit numbers, so a naive comparison overstates the geocode
error rate by roughly 3× (37 raw diffs vs 12 real ones in the `100` band). Any future accuracy
metric built on `verified_address` must normalise first, or the numbers will be wrong in the
alarming direction.

Two related observations from the same sample:

* Genuine failures are visible and do look like real defects — `1` → `657 Whiting Way`,
  `1550` → `1550 United Blvd`, `3000 Walton Ave` → `3007 Anson Ave`, and STT damage such as
  `3025 Low Heat Hwy` → `3025 Lougheed Highway` (*"Low Heat"* for *Lougheed*).
* One record looked like a rating inconsistency and turned out to be something else:
  `3030 Gordon Avenue Rain City Housing` verified to `2648 Sandstone Cres`, rated **PERFECT**.
  It was the review form's own placeholder examples saved as data — see **#33**, now closed.
  The operator has corrected the record. It was the only genuine case in the 202 reviewed.

#### To do when revisiting

1. Re-run the banded comparison once the rated sample in 81–96 is materially larger.
2. Decide whether the trigger should key off **`quality_rating < OPERATIONAL`** (the
   operator's stated preference) rather than `confidence_score` — noting ratings are applied
   *retroactively*, so they cannot flag a live call. A live proxy is still needed; the
   question is which one best predicts the retroactive rating.
3. Consider a dedicated **geocode confidence** distinct from parser confidence. The geocoder
   already knows whether it returned an exact parcel match, a street centroid, or a fuzzy
   suggestion — that is a far more direct answer to "will the crew reach the right address"
   than a transcript score. Related to #12.

---
