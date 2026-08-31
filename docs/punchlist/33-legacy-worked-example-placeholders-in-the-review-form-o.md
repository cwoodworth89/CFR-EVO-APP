# Punch list #33 — Legacy worked-example placeholders in the review form — one reached the training set

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🏷️ Response Terminology & Status Colour |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L1860 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 33. Legacy worked-example placeholders in the review form — one reached the training set
> **Status**: ✅ **Closed 2026-08-23.** Removed from
> `frontend/src/components/review/VerificationSidebar.jsx`; `lint:crash` and `npm run build`
> both pass. Not yet deployed to the kiosk.

Four fields in the HITL verification sidebar fell back to hand-written worked examples when
the parser produced no value:

| Field | Line | Legacy fallback |
|:--|:--|:--|
| Responding units | `:444` | `"e.g. E1, L1"` |
| Incident type | `:473` | `"e.g. Structure Fire"` |
| Address | `:511` | `"e.g. 2648 Sandstone Cres"` |
| Map grid | `:597` | `"e.g. 92"` |

**These are obsolete.** They predate the current design, in which the **system hypothesis is
itself the placeholder** and the reviewer presses **Ctrl+Space** to accept it — which is what
saves typing and prevents spelling drift. Once the real value sits in the background, a worked
example is dead weight.

#### How it was found — one of them reached the corpus

`DISP-2026-D106EB` (2026-07-13) was saved with **all three text examples as its verified
data**, an exact three-for-three match:

| Field | System output (matches the audio) | What was saved |
|:--|:--|:--|
| Address | `3030 Gordon Avenue Rain City Housing` | `2648 Sandstone Cres` |
| Incident | `Medical Aid - Overdose` | `Structure Fire` |
| Units | `M1` | `E1, L1` |

Its own `verified_transcript` says *"medic 1 respond emergency medical aid overdose 3030
gordon avenue rain city housing"* — so the system was right on every field and the
corrections were the form's examples. The record was rated **PERFECT**, carried
`include_in_training = true` and `model_updated = true`, and had therefore **already been
exported as ground truth** — teaching Whisper that audio describing an overdose on Gordon
Avenue transcribes to a structure fire on Sandstone Cres.

Attributed by the operator to an early-system reviewer mistake, from before the prefill
design; the record has since been corrected by hand. A scan of all 202 reviewed calls for
verified addresses whose street never appears in the transcript found **no other genuine
case** — the other three hits were `Crt`→`Court` suffix expansions.

The **mechanism was not reproduced**. The placeholders are conditional
(`selectedCall.incident_type || "e.g. …"`), and that call had a real incident type, so the
examples should not have been visible on that record at all.

#### Why it was worth removing rather than tolerating

* `2648 Sandstone Cres` matches exactly **one real parcel** in `public.parcels` — a real
  Coquitlam property, used as decorative example text in a form that writes to the
  ground-truth corpus.
* All four examples are *plausible dispatch values*. §6.1 and §6.5 exist because a
  plausible-looking wrong answer cannot be distinguished from a real one; this is that rule
  applied to a UI affordance rather than to a computed value.

#### Fix

A single `NO_SYSTEM_VALUE = '-- nothing parsed --'` constant replaces all four, carrying the
history above as an inline comment. When the parser produced nothing, the field now says so
instead of showing something that reads like data. The system-hypothesis placeholder and the
Ctrl+Space prefill are untouched — they were always the point.

---
