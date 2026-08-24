# Briefing: Persist `response_type`, and add a verification control for it

**Written 2026-08-23 for the agent working on the parser scripts.**
Source items: [`docs/debug_and_qa_punchlist.md`](../debug_and_qa_punchlist.md) **#31** (this
work) and **#30** (the display wording that sits on top of it).

---

## The one-line version

The parser already extracts the response type correctly. It is then **dropped before it
reaches the database**, so the kiosk has never once shown an emergency call as an emergency.
Persist it, and give the reviewer a way to correct it.

---

## What is actually broken

`payload_builder.py:186` parses it, uses it, and discards it:

```python
detected_resp = next((d.response_type for d in all_candidates if d.response_type), "emergency")
routing_metrics = router.calculate_units_routing(
    responding_units, lat, lng, response_type=detected_resp, ...)
```

`detected_resp` is never added to `target_payload` (`:195-202`). It dies in local scope.

**Confirmed against the live kiosk database, not inferred:**

* `public.dispatches` has 22 columns; **no `response_type`, no `priority_code`**.
* Zero `target` JSONB keys matching `%resp%`, `%prior%`, `%code%` across all 435 rows.
* But **343 of 435** transcripts contain `respond emergency`; 66 contain `respond routine`.
* It survives only incidentally inside per-unit routing metrics — 405 unit rows `null`,
  8 `Emergency (Code 3)`, 2 `Routine (Code 1)`.

Downstream, `KioskView.jsx:93` tests `priority_code` and `response_type`, both undefined, so
`isEmergency` is **always false** and every dispatch renders with the green routine border.

**The parser side is fine — do not "fix" it.** `destructive_parser.py:74` and
`announcement.py:171` both extract the value, and `public.vocabulary` already stores the
category `response_type` with exactly two entries, `routine` and `emergency`
(`backend/migrations/2026-08-21_vocabulary_seed.sql:232-233`). The break is purely that the
value is not carried into the payload.

---

## Operator ruling (2026-08-23) — read before designing anything

**Store the strings. Do not introduce a numeric code.**

The dispatch is transmitted as *"respond routine"* / *"respond emergency"*; the parser emits
exactly those lowercase strings; `public.vocabulary` already stores them. A numeric code
would be a translation layer with no source and two more places to invert.

* Canonical values: **`'routine'`**, **`'emergency'`**, and **`NULL`** when not parsed.
  Those three. There is no fourth state and no default.
* **Remove Code 2 / Code 3 from the system entirely.** Not renamed, not retained as a
  mapping, not kept as a fallback for a hypothetical consumer — *deleted*. No numeric
  response code should exist anywhere in the codebase when this work is done. If a numeric
  scale is ever genuinely required, **the operator will make that change themselves**; do
  not leave a translation layer in place in anticipation of it.
* This is recorded as an operator-authority gap in
  [`docs/standards/README.md`](../standards/README.md); no department policy document is held.

---

## Task 1 — Persist it

Add the parsed value to `target_payload` in
[`backend/cfr_dispatch/pipeline/payload_builder.py`](../../backend/cfr_dispatch/pipeline/payload_builder.py).

**No migration is required.** `target` is JSONB and already carries `radio_channel`,
`map_grid`, `tone_name`, `subaddress` and the `verified_*` corrections. Follow that pattern:

```python
target_payload = {
    ...
    "response_type": detected_resp,   # 'routine' | 'emergency' | None
}
```

Then surface it through [`frontend/src/utils/dispatchModel.js`](../../frontend/src/utils/dispatchModel.js)
alongside `radio_channel` / `map_grid`, and **delete** the `priority_code: record.priority_code`
line at `:73` — it maps a field the backend has never produced.

### Unparsed means NULL — this is decided, not open (CLAUDE.md §6.1)

**Operator ruling 2026-08-23: an unparsed response type is `NULL`. Never a guess.**

The same unparsed call is currently routed as emergency but reconstructed as routine:

| Site | Current default | Required |
|:--|:--|:--|
| `payload_builder.py:186` (routing) | **`"emergency"`** | `None` |
| `payload_builder.py:228` (template reconstruction) | `"routine"` | `None` |
| `phase2.py:177`, `phase2.py:260` | `"routine"` | `None` |
| `destructive_parser.py:39` | `"routine"` | `None` |

All four `or "routine"` / `, "emergency")` fallbacks come out. A call whose response type
could not be parsed stores `NULL` and displays as unknown. Accept that this means some calls
render as **amber / `UNKNOWN`** rather than green or red — see the next section. That is the
intended, correct outcome under §6.1: the gap is shown to the operator, not filled in.

#### What `NULL` looks like on the kiosk, and what it does to the ETA

Both settled by the operator, 2026-08-23.

**Display — amber border, response type `UNKNOWN`.** A NULL response type is treated as an
error condition needing attention, which is exactly the amber trigger set already defined in
**#30** (correction applied / low confidence / call queued). So NULL does not mean "no
border" — it means **amber**, with the response type rendered as `UNKNOWN` rather than
blank. The unknown is surfaced loudly instead of quietly, which is the §6.1 intent.

**ETA — emergency speeds, as a stated assumption.** `routing_engine.py:279` and `:407` derive:

```python
is_routine = str(response_type).lower().strip() == "routine"
```

A boolean cannot represent unknown, so `None` already falls through to the emergency branch.
**The operator has ruled that this is the correct behaviour** — most calls are emergency and
time-critical, so emergency speeds are the conservative choice — but it must stop being
accidental:

* Add a provenance comment at both sites naming the decision and who made it (§6.3 tier 4:
  *department operational policy*), e.g. `# Unknown response type routes at emergency speed:
  operator decision 2026-08-23 — most calls are emergency and time-critical. Not a parser
  default; see punch-list #31.`
* This is a **deliberate stated assumption, not a fallback**. The distinction matters: the
  banned behaviour was inventing a *stored* response type. Computing an ETA under a declared,
  documented assumption while the stored value remains `NULL` and the UI shows `UNKNOWN` is
  the honest version of the same computation.
* Do **not** change the stored `response_type` to `'emergency'` to achieve this. The value in
  `target` stays `NULL`; only the routing calculation assumes emergency.

**Context the operator gave, worth recording**: ETAs are not currently relied upon
operationally. That lowers the stakes here — but it is a statement about today, so the
assumption is documented rather than buried, in case ETAs become load-bearing later.

### Also in scope, small

`services/gis/src/gis_service/routing_engine.py:309` and `:433` emit
`"response_mode": "Routine (Code 1)" / "Emergency (Code 3)"`. Per the ruling the parenthesised
codes are **deleted**, leaving the bare terms. Grep the tree for `Code 1`, `Code 2`, `Code 3`
and `priority_code` before you finish and confirm nothing survives. **`backend/tests/test_routing_engine.py:338,341` assert both strings and will
fail** — update them in the same commit. Nothing on the frontend consumes `response_mode`.

---

## Task 2 — Reviewer verification control

The operator wants this verifiable in the review panel **"like the tone selectors"**.

**Pattern to copy**: the Captured Dispatch Tone control at
[`frontend/src/components/review/VerificationSidebar.jsx:344-384`](../../frontend/src/components/review/VerificationSidebar.jsx#L344)
— a labelled grid of `type="button"` toggles, tinted when active, greyed when not.

**One difference that matters**: tones are **multi-select** (`handleToneToggle` pushes into an
array). Response type is **mutually exclusive**. Model it as a single-value selector with
three states, not a toggle array:

| Button | Value | Suggested tint (matches the kiosk border) |
|:--|:--|:--|
| 🟢 Routine | `'routine'` | emerald, as `verifiedTones` uses sky/amber/rose |
| 🔴 Emergency | `'emergency'` | rose |
| ⬜ Unknown | `null` | slate / inactive |

Wire it exactly like `verifiedTalkgroup`:

1. `useState` in [`DispatchReview.jsx`](../../frontend/src/components/DispatchReview.jsx)
   (~`:49`, beside `verifiedTones`).
2. Hydrate on selection (~`:164`):
   `setVerifiedResponseType(selectedCall.target?.verified_response_type ?? selectedCall.target?.response_type ?? null)`
3. Include a **`Sys:` prefill affordance** — every other field has one
   (`onPrefillField('talkgroup')` at `:507`), showing what the parser produced so the reviewer
   can see and accept it. Add the matching case to `onPrefillField`.
4. Save into `updatedTarget` at `:313-320`, next to `verified_talkgroup`:
   `verified_response_type: verifiedResponseType || null`

That keeps the correction in the same JSONB envelope as the other `verified_*` fields, so
again **no schema change**.

### Why this control is worth having

It creates ground truth for a field with a 435-row backlog and no verified column today. Per
the [handoff](../review_status_handoff.md), `verified_*` + audio is the paired
system-vs-actual corpus the backtest suite is built on — so verified response type
immediately becomes a measurable parser accuracy metric, which it currently is not.

---

## Out of scope for this briefing

The kiosk border work is **#30** and depends on this landing first: the border states are
green routine / red emergency / **amber overriding both** for a call needing attention
(correction applied, low confidence, a call queued, **or a `NULL` response type**) / purple
review. Do not implement the
border here — fixing the wording on a signal that never fires would just relabel a stuck
badge.

---

## Verification

Per the handoff, the pattern that gave real confidence is: **freeze the old behaviour, run
both over the real corpus, diff** — see `frontend/scripts/verify_dispatch_model.mjs`. For this
change the cheap equivalent is a re-parse of all 435 `sanitized_transcript` values, checking
the extracted response type against the `respond (routine|emergency)` literal in the
transcript. Expect roughly 343 emergency / 66 routine; the ~26 that match neither are the
interesting ones and **must land as `NULL`** — if that count comes back as zero, a fallback
survived somewhere and the ruling has not actually been implemented.
