# Punch list #31 — `response_type` never reaches the kiosk — every call renders as ROUTINE

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🏷️ Response Terminology & Status Colour |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L1470 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 31. `response_type` never reaches the kiosk — every call renders as ROUTINE
> **Status**: ⚠️ **Open — found 2026-08-23 while investigating #30.** **Confirmed** against
> the running kiosk database and the working tree. This is the defect #30 was sitting on
> top of; #30 is the wording, this is the data.

**The kiosk cannot tell an emergency call from a routine one. It never receives the field.**

#### Confirmed by query, not by reading

`public.dispatches` has **22 columns and none of them carry a response type**:

```
id, dispatch_id, timestamp, incident_type, responding_units, target,
raw_transcript, sanitized_transcript, confidence_score, verify_location,
origins, audio_url, audio_duration, verified_transcript, verified_address,
verified_incident, verified_units, feedback_submitted, quality_rating,
model_updated, review_notes, routing_metrics
```

There is **no `priority_code` column, and no `response_type` column.** Neither key appears
anywhere in the `target` JSONB either — a scan of every `target` key across all 435 rows
matching `%resp%`, `%prior%` or `%code%` returns **zero**.

Yet the information is plainly present in the audio:

| | rows |
|:--|--:|
| Total dispatches | 435 |
| Transcript contains `respond emergency` | **343** |
| Transcript contains `respond routine` | 66 |

#### Consequence

[`KioskView.jsx:93`](../../frontend/src/components/kiosk/KioskView.jsx#L93):

```js
const isEmergency =
  activeCall.priority_code <= 2 ||                                  // undefined <= 2      -> false
  String(activeCall.priority_code).toLowerCase() === 'emergency' || // "undefined"          -> false
  String(activeCall.response_type).toLowerCase() === 'emergency';   // "undefined"          -> false
```

All three branches read fields that do not exist, so `isEmergency` is **always `false`**.
Every dispatch renders with the green routine border and the `🟢 ROUTINE` badge — including
all **343 emergency calls**. The screenshot in #30 happens to be a genuine routine call,
which is why the error is invisible there.

The operator states the border is *"stylistic, and a minor reminder to drivers"*, so this is
not a life-safety failure — but it is a signal that has never once been correct for an
emergency call, and drivers have been receiving a green cue on every call regardless.

`dispatchModel.js:73` faithfully maps `priority_code: record.priority_code` — it is
propagating a field the backend has never produced.

#### Root cause: the value is computed, used, and then discarded

[`payload_builder.py:186`](../../backend/cfr_dispatch/pipeline/payload_builder.py#L186):

```python
detected_resp = next((d.response_type for d in all_candidates if d.response_type), "emergency")
routing_metrics = router.calculate_units_routing(
    responding_units, lat, lng, response_type=detected_resp, ...)
```

`detected_resp` is parsed correctly from the transcript, passed to the routing engine, logged
— and then **never added to `target_payload`** (`:195–202`). It dies in the local scope. The
parser side is fine: `destructive_parser.py:74` and `announcement.py:171` both extract it,
and `public.vocabulary` already stores `response_type` as the two strings **`routine`** and
**`emergency`** (`2026-08-21_vocabulary_seed.sql:232-233`).

The only place it survives to the database is incidentally, inside per-unit routing metrics —
and almost never:

| `target.routing_metrics[].response_mode` | unit rows |
|:--|--:|
| `null` | **405** |
| `Emergency (Code 3)` | 8 |
| `Routine (Code 1)` | 2 |

#### Two smaller defects found alongside

1. **The defaults disagree — resolved to `NULL`.** When no candidate carries a response type,
   `payload_builder.py:186` defaults to **`"emergency"`**, while `payload_builder.py:228`
   (template reconstruction), `phase2.py:177`/`:260` and `destructive_parser.py:39` all default
   to **`"routine"`**. The same unparsed call is therefore routed as emergency but
   reconstructed as routine. **Operator ruling 2026-08-23: all four fallbacks are removed and
   an unparsed response type propagates as `None`** (§6.1), displaying as unknown. The visible
   consequence — some calls showing neither the green nor the red border — is accepted.

   **Where `NULL` surfaces — both settled by the operator 2026-08-23:**
   * **Border**: a `NULL` response type is an **amber** condition with the response type shown
     as `UNKNOWN`. It joins the amber trigger set in #30 rather than producing a borderless
     call, so the gap is loud rather than quiet.
   * **ETA**: `routing_engine.py:279` and `:407` derive
     `is_routine = str(response_type).lower().strip() == "routine"`; a boolean cannot represent
     unknown, so `None` already falls through to the **emergency** branch. The operator has
     ruled this **correct** — most calls are emergency and time-critical, and ETAs are not
     currently relied upon operationally. It must stop being *accidental*: both sites need a
     §6.3 tier-4 provenance comment naming the decision. The **stored** value stays `NULL`;
     only the routing calculation assumes emergency. That distinction is the whole point —
     inventing a stored response type is banned, computing under a declared and displayed
     assumption is not.
2. **`public.dispatches.routing_metrics`** (the top-level column, distinct from
   `target.routing_metrics`) is an empty object on every row scanned. Possibly dead; worth
   confirming before anything new is written to it.

#### Direction agreed with the operator (2026-08-23)

**Use the strings; do not introduce a numeric code.** The dispatch is transmitted as
"respond routine" / "respond emergency", the parser already produces exactly those two
lowercase strings, and `public.vocabulary` already stores them — so a numeric code would be a
translation layer with no source and two more places to get inverted.

Accordingly:

* Persist `response_type` (`'routine'` | `'emergency'` | `NULL` when unparsed) through
  `target_payload` so it reaches the kiosk.
* Replace the three-branch `isEmergency` in `KioskView.jsx:93` with a single string test.
  **Delete the `priority_code <= 2` branch outright** — it tests a field that has never
  existed, and under the department's Code 2/Code 3 scale its arithmetic would be inverted
  anyway. This resolves open question 1 of #30.
* **Remove Code 2 / Code 3 from the system entirely** (operator, 2026-08-23) — deleted, not
  renamed and not retained as a mapping. No numeric response code should survive anywhere in
  the codebase. If a numeric scale is ever genuinely needed, the operator will make that
  change themselves; no translation layer is to be left in place in anticipation.
* **An unparsed response type is `NULL`, never a guess** (operator, 2026-08-23). This closes
  the conflicting-defaults question below: all four fallbacks come out.
* Add a **reviewer verification control** for response type in the HITL panel, modelled on
  the tone selectors — see the briefing below.

> **Handed to the parser agent 2026-08-23**:
> [`docs/briefings/response_type_persistence.md`](../briefings/response_type_persistence.md)
> covers both the persistence fix and the review-panel control, with the operator ruling and
> the conflicting-defaults question that must be raised before implementing.

---

---

## 31 (closed). `response_type` reaches the kiosk — clean cutover verified in the database

> **Status**: ✅ **Closed 2026-08-30.** Verified against the running kiosk database (§6.6).

`response_type` now persists into `target`. The cutover is unambiguous — it is not a
gradual improvement, it is a dated switch:

| Day | Calls | With `response_type` | With `review_flags` |
|:--|--:|--:|--:|
| 2026-08-31 | 2 | **2** | 2 |
| 2026-08-30 | 11 | 5 | 5 |
| 2026-08-29 | 13 | 0 | 0 |
| 2026-08-28 | 12 | 0 | 0 |
| 2026-08-27 | 13 | 0 | 0 |

Zero before the fix landed mid-day on the 30th, every call after it. `public.vocabulary`
holds exactly two `response_type` terms, matching the operator ruling that the authoritative
terms are `routine` and `emergency` with the numeric codes deleted rather than renamed.

The frontend carries no live numeric-code logic — every remaining `priority_code` reference
in `KioskView.jsx`, `useMqttListener.js` and `dispatchModel.js` is a comment recording that
the field never existed.
