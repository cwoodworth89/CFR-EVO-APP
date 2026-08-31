# Punch list #45a — Geocoder harness needs a review pass before its numbers are trusted again

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | hygiene |
| **Area** | 🧾 Import Completeness Audit, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2947 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 45. Geocoder harness needs a review pass before its numbers are trusted again
> **Status**: ⚠️ **Open — raised 2026-08-26** while building the parser harness. Not a defect
> in the geocoder; a staleness risk in the tool used to measure it. See
> [`docs/qa_harnesses.md`](qa_harnesses.md) §3.

`backend/scripts/trace_geocode_corpus.py` (committed `8d00ea3`) replays verified dispatches
through the live geocoder and records which of seven resolver steps answered. Four reasons its
output should not be quoted until it is re-checked:

1. **It predates the 2026-08-21/23 geocoder rewrite.** Nine commits landed on `services/gis/`
   in that window — map-grid tie-breaking, near-road ranking, bounded civic substitution,
   honest centroid labelling. Whether the seven-step ladder it wraps is still the seven steps
   that run has not been verified.
2. **No date split.** Its headline "30 of 34 stored defects already remediated" is a historical
   statement. Every pooled rate over this corpus is suspect (#5 below, and `qa_harnesses.md` §5).
3. **No cosmetic bucketing.** Reviewers use `verified_address` for suffix expansion and unit
   stripping, which inflates a naive error rate roughly 3×. `backtest_parser_corpus.py` buckets
   EXACT / COSMETIC / WRONG; this should adopt the same.
4. **It measures the geocoder's own output** (`target->>'address'`), so it can never see how the
   parser arrived at that string. The parser harness now fills that gap — read them together.

**Work:** re-run against current `services/gis/`, confirm the resolver list, add `--by-month`
and cosmetic bucketing, record a fresh baseline in `qa_harnesses.md` §3.

---
