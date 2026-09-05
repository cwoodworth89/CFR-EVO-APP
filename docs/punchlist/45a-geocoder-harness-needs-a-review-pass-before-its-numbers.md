# Punch list #45a — Geocoder harness needs a review pass before its numbers are trusted again

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | hygiene |
| **Area** | 🧾 Import Completeness Audit, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2947 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 45. Geocoder harness needs a review pass before its numbers are trusted again
> **Status**: ✅ **Closed 2026-09-05 — reviewed point by point; see the closing note.**
> *(Opened as: ⚠️ Open — raised 2026-08-26 while building the parser harness. Not a defect
> in the geocoder; a staleness risk in the tool used to measure it.)* See
> [`docs/qa_harnesses.md`](../qa_harnesses.md) §3.

`tools/trace_geocode_corpus.py` (committed `8d00ea3`) replays verified dispatches
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

### Closed 2026-09-05

The four points, in order: the seven wrapped resolvers are the seven `get_coordinates` calls
today, in that order; the per-month split was added 2026-09-04; cosmetic bucketing was already
in `classify()`; and point 4 turned out to be the whole story. `target->>'address'` is the
geocoder's output, canonical, identical to the verified address on every resolved call
sampled, so replaying it through the geocoder measures whether a canonical address
round-trips, not whether the geocoder is right. The tool now reports "then" (the stored
outcome, history) and "now" (re-resolved by current code, a stability check) by name, and
refuses `--record`. The geocoder regression number moved to `tools/harness_chain.py
--skip-stt`, which re-parses the stored transcript and re-geocodes through production's own
payload builder. On the same window (verified calls since 2026-08-01, n=303) the stored
outcome reads 92.7 % same place and the chain reads 92.4 %: the cross-check this item wanted.
Fresh baseline recorded in `qa_harnesses.md` §3. The first full chain run the same day found
#62.
