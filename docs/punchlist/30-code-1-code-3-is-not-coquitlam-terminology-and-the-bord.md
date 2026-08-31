# Punch list #30 — "Code 1 / Code 3" is not Coquitlam terminology, and the border has no warning or review state

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🏷️ Response Terminology & Status Colour |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L1297 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 30. "Code 1 / Code 3" is not Coquitlam terminology, and the border has no warning or review state
> **Status**: ⚠️ **Open — found 2026-08-23.** Reported by the operator from a live kiosk
> screenshot (`1347 KENNEY ST`, GRID 88, routine call). The rendering sites below were
> **confirmed** by reading the working tree; the terminology correction itself is the
> operator's, and Coquitlam usage is not currently backed by a document in
> `docs/standards/` (see the gap note at the end).

**Two separate defects in one item, because they share the same `isEmergency` input.**

#### 30a. The code numbers are wrong, and should be removed entirely

The kiosk badge reads **`🟢 ROUTINE (CODE 1)`**. Coquitlam Fire/Rescue does not use Code 1;
the numeric scale in use is **Code 2 and Code 3**, so the label is doubly wrong — the wrong
number *and* a scale the department does not speak.

The operator's direction: **drop the numeric codes from the interface entirely.** The
authoritative terms are **`ROUTINE`** and **`EMERGENCY`**, which is also how the dispatch
itself is transmitted over the radio — so the display would match what crews actually hear.

Confirmed rendering and label sites:

| File | Line | Current |
|:--|:--|:--|
| [`frontend/src/components/hud/ActiveAlertBanner.jsx`](../../frontend/src/components/hud/ActiveAlertBanner.jsx) | `36` | `isEmergency ? '🚨 Emergency (Code 3)' : '🟢 Routine (Code 1)'` |
| [`services/gis/src/gis_service/routing_engine.py`](../../services/gis/src/gis_service/routing_engine.py) | `309`, `433` | `"response_mode": "Routine (Code 1)" if is_routine else "Emergency (Code 3)"` |
| [`backend/tests/test_routing_engine.py`](../../backend/tests/test_routing_engine.py) | `338`, `341` | asserts both strings — **will fail** when the labels change, and must be updated with them |

`response_mode` has **no frontend consumer** — the grep above finds it only in the routing
engine that emits it and the test that asserts it. So the backend and frontend strings are
independently wrong rather than one feeding the other, and both need changing.

**Related, and the reason this is not purely cosmetic** —
[`frontend/src/components/kiosk/KioskView.jsx:93`](../../frontend/src/components/kiosk/KioskView.jsx#L93):

```js
const isEmergency =
  activeCall.priority_code <= 2 ||
  String(activeCall.priority_code).toLowerCase() === 'emergency' ||
  String(activeCall.response_type).toLowerCase() === 'emergency';
```

The numeric branch encodes a **`<= 2` means emergency** rule. If the department's scale is
Code 2/Code 3 rather than 1/2/3, then `priority_code == 2` classifying as *emergency* needs
confirming against what the dispatch feed actually sends — under a 2/3 scale, 2 may well be
the *routine* value, which would invert the classification and the border colour with it.
**This branch must be resolved before the labels are cosmetically renamed**, or the display
will read correctly while classifying incorrectly.

> **Resolved by #31**: `priority_code` is not a column in `public.dispatches` and appears
> nowhere in the backend. Every branch of this expression reads an undefined field, so
> `isEmergency` is **always false** and *every* call — including all 343 emergency ones —
> renders green. The branch is to be deleted, not renumbered. **Fix #31 first; #30 is the
> wording on top of it.**

#### 30b. The border colour has only two of the four required states

Confirmed at [`KioskView.jsx:175`](../../frontend/src/components/kiosk/KioskView.jsx#L175):

```js
const borderColor = isEmergency ? 'border-red-600' : 'border-emerald-500';
```

Applied as a `border-[6px]` ring on the fixed full-screen container (`:180`). The operator
confirms **green for routine is correct and worth keeping**. The required state set is:

| State | Border | Present today |
|:--|:--|:--|
| Routine | **Green** | ✅ `border-emerald-500` |
| Emergency | **Red** | ✅ `border-red-600` |
| Warning | **Amber** | ❌ no amber border state exists |
| Review mode | **Blue** | ❌ review keeps the red/green border; it is signalled only by a *purple* `🧪 REVIEW REPLAY` badge in `ActiveAlertBanner.jsx:39` |

Two follow-on notes for whoever implements this:

* **Review mode is currently purple, not blue** — the badge at `ActiveAlertBanner.jsx:39`
  uses `purple-950/purple-500/purple-200`. If blue becomes the review colour, the badge
  should move with the border or the two will disagree.
* **What drives the amber warning state is undefined.** The §5 Tier 1 unresolved-location
  card and the queued-call banner (`KioskView.jsx:185`) are both already amber, so they are
  the natural candidates — but which conditions raise the *border* to amber, and what
  happens when a warning coincides with an emergency (does amber override red, or red win?),
  is a precedence decision that has not been made. **Ask before implementing.**

#### Answered by the operator, 2026-08-23

1. **Numeric codes are removed from the system entirely.** Use the bare terms **`routine`** /
   **`emergency`** everywhere — that is how the dispatch is transmitted and how the parser and
   `public.vocabulary` already represent it, so there is nothing to translate. Code 2 / Code 3
   are **deleted, not renamed**, and no numeric mapping is retained as a fallback; if one is
   ever needed the operator will add it themselves. The `priority_code <= 2` branch is to be
   **deleted**, not corrected; see **#31**, which found it tests a column that does not exist.
2. **Amber is orthogonal to response type.** Green/red are *"stylistic, and a minor reminder
   to drivers"*. **Amber flags the call for additional attention regardless of response
   type**, so it **overrides** both green and red. Current triggers:
   * the system applied a **correction**,
   * **low confidence**,
   * a **call is queued**,
   * *(added 2026-08-23)* the **response type is `NULL`** — shown as `UNKNOWN`; see #31.
3. **Review stays purple.** No change; the existing `🧪 REVIEW REPLAY` badge colour is
   correct and the border should match it rather than going blue.

Revised target state for the border:

| State | Border | Precedence | Present today |
|:--|:--|:--|:--|
| Review mode | **Purple** | highest | badge only, border unchanged |
| Warning | **Amber** | overrides green/red | ❌ does not exist |
| Response type `NULL` | **Amber**, labelled `UNKNOWN` | as warning | ❌ cannot occur yet — see #31 |
| Emergency | **Red** | — | ✅ but never fires — see #31 |
| Routine | **Green** | — | ✅ fires on *every* call — see #31 |

**The "low confidence" threshold, measured 2026-08-23.** The operator asked for a new number
on the grounds that the existing `confidence_score >= 90` in `dispatchModel.js:74` is
unsourced. It is unsourced — but **the corpus supports it**, so the defect is the missing
provenance, not the value.

`confidence_score` is heavily quantised (435 rows, none NULL):

| Score | Rows |
|:--|--:|
| `0` | 30 |
| 45–78 | 25 |
| 81–89 | 27 |
| 91–96 | 19 |
| `100` | 334 |

Cross-referenced against HITL `quality_rating`, counting only **rated** calls:

| Band | Rated | Perfect | Failed |
|:--|--:|--:|--:|
| `0` | 5 | **0%** | **100%** |
| 45–78 | 14 | 14% | 21% |
| 81–89 | 13 | 15% | 8% |
| 91–96 | 8 | **63%** | **0%** |
| `100` | 116 | 59% | 3% |

**The behavioural break is between 89 and 91.** 91–96 behaves like 100 (≈60% perfect, no
failures); 81–89 behaves like 45–78 (≈15% perfect, failures present). A cut at 90 lands
exactly on that boundary. Moving it to 80 would sweep the 81–89 band — the band that
actually behaves badly — into the "confident" side.

At `< 90`, **82 of 435 calls (19%)** would raise amber.

⚠️ **Caveats, stated rather than buried**: the 91–96 and 81–89 bands have only 8 and 13
*rated* calls, so the boundary is suggestive, not established. 77% of the `100` band is
unrated. And `quality_rating` is the operator's own judgement, so this measures agreement
between the parser's self-assessment and the reviewer, not ground truth.

**Recommendation**: keep **90**, and convert it from an unsourced constant into a §6.3 tier-3
*measured* one by citing this analysis inline. Revisit once the rated sample in the 81–96
range grows. **Operator decision still required** — see the question below.

`confidence_score = 0` is a distinct case, not merely "low": all 30 such rows are hard
resolution failures (13 have no address at all, 19 are already flagged `verify_location`),
and every rated one was graded FAILED. Worth treating as its own amber reason rather than
folding into the threshold.

Still to pin down: the predicate for "applied a correction". `isRecentlyUpdated` (already
plumbed into `ActiveAlertBanner`) is the likely signal, and `queuedCalls.length > 0` the
queued one.

**Operator decision 2026-08-23**: **keep 90 for now**, commented with its measurement, and
tag it for future QA review once more dispatches have been rated. Tracked as **#32**, which
also records what the operator wants the flag to *mean* — "would the crew have reached the
right address", i.e. below OPERATIONAL or a poor geocode score — and a re-measurement against
`verified_address` that partly contradicts the `quality_rating` analysis above.

> **Standards gap** — Coquitlam Fire/Rescue response-mode terminology is not held in
> `docs/standards/`. Recorded there per CLAUDE.md §7.5; until it exists, the operator is the
> authority, and the authority's ruling is: **`routine` / `emergency`, no numeric code.**

---
