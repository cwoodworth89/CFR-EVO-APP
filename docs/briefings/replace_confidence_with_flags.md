# Proposal: retire `confidence_score`, replace it with named review flags

**Written 2026-08-29** from the operator's proposal. **Design only — nothing implemented.**
Punch-list **#45**, supersedes the deferred threshold work in **#32**.

---

## Why the current score has to go

The operator's observation — *"the confidence percent shown in the admin review dashboard
always seems wildly off"* — is correct, and tracing it explains why.

[`payload_builder.py:154-176`](../../backend/cfr_dispatch/pipeline/payload_builder.py#L154):

```python
base_confidence = confidence_score          # the GEOCODER's score
penalties = 0.0
if lat is None or lng is None:      penalties += 30.0
if not responding_units:            penalties += 20.0
if not map_grid:                    penalties += 15.0
if not radio_channel:               penalties += 15.0
confidence_score = max(0.0, base_confidence - penalties)
```

**It is a metadata-completeness score wearing a confidence label.** A call whose address is
perfectly correct but whose talk group did not transcribe scores **85**. A call the geocoder
resolved confidently to the **wrong** address scores **100**.

Three defects, all structural rather than tuning problems:

1. **It conflates two unrelated questions** — "is this address right?" and "did every field
   transcribe?" — into one number, so neither can be read off it.
2. **The penalties have no provenance.** 30 / 20 / 15 / 15 are invented constants shaping an
   operational display (CLAUDE.md §6.3), and they are not commensurable: subtracting
   "missing talk group" from "geocoder certainty" yields a number in no unit at all.
3. **It destroys the information it consumes.** By the time the operator sees `85`, *which*
   field was missing is gone.

This is also what made the threshold analysis in #32 unresolvable. The 81–89 band looked
flawless on address accuracy — because **9 of its 29 calls are simply missing a radio channel**
and none is missing coordinates. Nothing in that band was penalised for anything
address-related, so of course its addresses were fine.

---

## The proposal (operator, 2026-08-29)

Drop the score. Emit a **list of named flags** — the specific reasons the system believes a
call needs a human look. Then:

* **Review row**: an amber flag **count**, hovering shows a bullet list of the reasons.
* **Kiosk**: the same reasons surface on the dispatch, so the crew sees what is uncertain.
* **HITL**: the reviewer investigates and **confirms or refutes** each flag.

The last point is the real prize. A flag the reviewer refutes is a **false positive with a
name** — which is the raw material for improving the detectors. A confidence score can never
produce that, because there is nothing specific to refute.

---

## Flags that already exist in the code

Not invented for this proposal — each is a condition the system already computes and, in most
cases, already draws a banner for. Counts are over **491 non-PA dispatches**.

| Flag | Source | Calls | Already shown? |
|:--|:--|--:|:--|
| `LOCATION_UNRESOLVED` | `target.lat` is null | **50** | Yes — §5 Tier 1 card |
| `LOCATION_SUBSTITUTED` | `resolution_note` set by the resolver | **15** | Yes — `ApproximateLocationBanner` |
| `NO_TALK_GROUP` | `radio_channel` empty | **26** | No — only a −15 penalty |
| `NO_UNITS` | `responding_units` empty | **11** | No — only a −20 penalty |
| `NO_MAP_GRID` | `map_grid` empty | **10** | No — only a −15 penalty |
| `STREET_SECTION_ONLY` | `location_type = 'street_section'` | 0 | Yes — section banner |
| `UNKNOWN_CALL_TYPE` | `incident_type` empty or generic | 0 | No |
| `OUT_OF_BOUNDS` | fails `isWithinCoquitlam()` | — | Yes — §5 Tier 2 card |
| `AMBIGUOUS_LOCATION` | `is_ambiguous` / multiple candidates | — | Yes — dual-junction selector |
| `RESPONSE_TYPE_UNKNOWN` | `response_type` null | — | Pending #31 |

`UNKNOWN_CALL_TYPE` and `STREET_SECTION_ONLY` currently score zero. They are kept because the
conditions are real and the operator named the first explicitly; a flag that never fires is
harmless, whereas discovering later that it was omitted is not.

---

## The count is sparse enough to be useful — measured

The obvious risk is that everything gets flagged and the signal is worthless. Measured across
491 non-PA dispatches:

| Flags | Calls | Share |
|--:|--:|--:|
| **0** | **391** | **80%** |
| 1 | 91 | 19% |
| 2 | 7 | 1.4% |
| 3 | 1 | 0.2% |
| 4 | 1 | 0.2% |

**Four calls in five are completely clean.** A flag genuinely means something, and the handful
carrying two or more are exactly the ones worth opening first. Compare with the score it
replaces, where 388 calls sit at `100` and roughly 8% of those have a substantively wrong
address.

---

## What this replaces, and what has to be decided

**Removals**, once flags are in place:

* `confidence_score` computation in `payload_builder.py` (the penalty block).
* The `< 90` threshold at `payload_builder.py:174` **and** the independent duplicate at
  `dispatchModel.js:98`. Two copies of an unsourced constant, free to drift.
* The `Conf >90%` column and `low_confidence` filter in the review panel.

**Open questions for the operator:**

1. **Keep the column or the database field?** `confidence_score` is on `public.dispatches` and
   has 507 rows of history. Suggest **retaining the column, stopping the writes** — deleting it
   would rewrite the past, and the historical values still describe what the system believed at
   the time.
2. **Do flags need severity?** `LOCATION_UNRESOLVED` (crew cannot be routed) and
   `NO_TALK_GROUP` (crew picks the channel up on the radio) are not equally serious, yet a bare
   count weights them the same. Two tiers would fix that at the cost of another judgement call.
3. **Where does the reviewer's confirm/refute live?** A `verified_flags` structure in `target`
   fits the existing `verified_*` pattern and needs no migration.
4. **Does a refuted flag stop showing on the kiosk for that call?** It should, but that means
   the kiosk must read HITL state it currently ignores.

---

## Suggested sequencing

1. **Emit flags alongside the existing score** — additive, nothing removed, nothing to break.
2. **Show them in the review row** (count + hover). Operator sanity-checks the flags against
   real calls for a while.
3. **Add confirm/refute** to the verification sidebar.
4. **Only then** remove the score and its two thresholds.

Steps 1–2 are safe and reversible. Step 4 changes what the kiosk and review panel display, so
it should not run ahead of the operator's own confidence in the flags.

> **This work is on hold behind #31** (`response_type` persistence, with the parser agent).
> `RESPONSE_TYPE_UNKNOWN` is one of the flags, and #30's amber border ought to be driven by the
> same flag set rather than a second parallel mechanism — otherwise the kiosk grows two
> independent notions of "needs attention", which is the defect this proposal exists to remove.
