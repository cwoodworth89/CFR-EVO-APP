# Punch list #45b — Retire `confidence_score`, replace it with named review flags

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 2 |
| **Origin** | `debug_and_qa_punchlist.md` L4139–4360 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 45. Retire `confidence_score`, replace it with named review flags
> **Status**: 📐 **Design agreed with the operator 2026-08-29, not implemented.**
> Full spec: [`docs/briefings/replace_confidence_with_flags.md`](../briefings/replace_confidence_with_flags.md).
> **Supersedes #32** — re-measuring that threshold is polishing a number computed from the
> wrong ingredients.

**The operator's observation was right**: *"the confidence percent shown in the admin review
dashboard always seems wildly off."* Tracing it, `confidence_score` is **a
metadata-completeness score wearing a confidence label** (`payload_builder.py:154-176`): the
geocoder's score, minus 30 for no coordinates, 20 for no units, 15 for no map grid, 15 for no
talk group.

So a call with a **perfectly correct address** but no transcribed talk group scores **85**,
while a call the geocoder resolved confidently to the **wrong** address scores **100**.

Three structural defects, none of them fixable by tuning:

1. It conflates *"is the address right?"* with *"did every field transcribe?"*, so neither can
   be read off the result.
2. The penalties have no provenance (§6.3) and are not commensurable — subtracting "missing
   talk group" from "geocoder certainty" gives a number in no unit at all.
3. It destroys the information it consumes: by the time the operator sees `85`, *which* field
   was missing is gone.

**This is why #32 was unresolvable.** The 81–89 band looked flawless on address accuracy
because **9 of its 29 calls are merely missing a radio channel** and none is missing
coordinates — nothing in that band was penalised for anything address-related.

**The replacement** (operator's proposal): emit a list of **named flags**, show an amber flag
**count** in the review row with the reasons on hover, surface the same reasons on the kiosk,
and let the HITL reviewer **confirm or refute** each one. A refuted flag is a false positive
*with a name* — raw material for improving the detectors, which a score can never produce.

**Measured: the count is sparse enough to mean something.** Across 491 non-PA dispatches,
**391 (80%) carry zero flags**, 91 carry one, and only 9 carry two or more. Compare with the
score it replaces, where 388 calls sit at `100` and ~8% of those have a substantively wrong
address.

Ten flags already exist as conditions in the code; the largest are `LOCATION_UNRESOLVED` (50
calls), `NO_TALK_GROUP` (26), `LOCATION_SUBSTITUTED` (15), `NO_UNITS` (11), `NO_MAP_GRID` (10).

**Open decisions and a four-step sequencing (additive first, removal last) are in the
briefing.** Blocked behind **#31**: `RESPONSE_TYPE_UNKNOWN` is one of the flags, and #30's
amber border should be driven by this same flag set rather than a second parallel mechanism —
otherwise the kiosk grows two independent notions of "needs attention", which is the defect
this item exists to remove.

---

---

## 45 (closed). `confidence_score` retired, named review flags shipped
> **Status**: ✅ **Closed 2026-08-30.** Deployed and verified on the kiosk. Supersedes #32.

The score is gone from code, database and every UI surface. `compute_review_flags()`
(`backend/cfr_dispatch/pipeline/review_flags.py`) emits eight named conditions stored in
`target.review_flags`, with the count in `target.review_flag_count`. No severity tiers, per
the operator — weights would reintroduce the unsourced-constant problem being removed.

**Surfaces**: flag count in the review row with reasons on hover; the full list in the
verification sidebar (that is the reviewer's actual job, so it is not hidden behind a hover);
a badge on the kiosk so crews see what is uncertain. `low_confidence` filter → `flagged`.

**Three fabricated numbers found and removed on the way**, all the same defect class as the
score itself:

* `phase2` set `"confidence_score": 100.0` after address verification — **erasing metadata
  flags it had never looked at**. Now recomputes.
* Elsewhere it took the geocoder's confidence `or 80.0` — inventing a number when the
  resolver reported none.
* `evaluations.py` returned a hardcoded **96.4** average confidence when the query was null:
  a fabricated statistic presented as measured. Nothing consumed it; replaced by a flagged
  count, which needs no default because zero rows means zero.

Also removed one of the two independent copies of the 90 threshold — `verify_location` now
derives from a named condition (`LOCATION_UNRESOLVED` / `LOCATION_SUBSTITUTED`).

#### The operator's question found a bug I had introduced

*"Phase 1 flags a missing map grid, phase 2 round 2 picks it up — is the flag still valid?"*

Checking it revealed the flags were being written at the **top level** of the payload. There
is no `review_flags` column, and the API applies updates via `setattr` over a Pydantic
`model_dump`, so a top-level key with no schema field is **silently dropped**. The flags were
computed and thrown away — precisely the defect as `response_type` dying in local scope, which
is what this whole thread began with.

They now live in `target`, which the frontend already reads and which phase 2 replaces
wholesale. That makes the lifecycle correct by construction. Of four phase-2 update paths, the
two that recompute the address recompute the flags with it; the two that retain phase 1 data
(geocoding failed, no candidate) keep phase 1's flags, which is right because phase 1's data
is what remains stored.

**26 tests**, including that resolving one field must not clear the others — superseding is a
recompute, not a reset. Full suite **203 passed** before the flag-lifecycle additions.

#### Deployment note — a sequencing error worth not repeating

**The migration was run before the code was deployed.** The correct order is code first (the
new code tolerates the column present or absent), then migrate. Instead there was a ~40 minute
window in which the running API still mapped a dropped column, so a dispatch arriving would
have failed to persist. No call arrived, but that was luck rather than design.

Migration: `backend/migrations/2026-08-29_drop_confidence_score.sql`. 513 rows intact. The
dropped values remain recoverable from `cfr-critical-20260829-200615.sql.gz`.

---
