# Punch list #23 — Live dispatches lost their street-section fields on the way to the kiosk

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🧱 Duplicated & Unsourced Frontend Constants |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L943 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 23. Live dispatches lost their street-section fields on the way to the kiosk
> **Status**: ✅ **Closed 2026-08-22.** Found while unifying the dispatch state model.

`useMqttListener.formatDispatchPayload` was a **third** hand-written dispatch translation,
alongside `App.jsx:handleReviewCall` and MapBoard's own handling. It built an explicit
object with **no spread**, so every field it did not know about was silently dropped.

**The live defect**: `location_type`, `segment`, `endpoints`, `length_m` and
`resolution_note` were absent from it, so a street-section dispatch (#16) arriving over
MQTT reached the kiosk without them. `StreetSectionBanner` checks
`activeCall?.location_type`, so the amber banner and the highlighted road section **never
appeared for a real call** — only for a review replay, which went through `App.jsx`
instead. The fields were plumbed through the geocoder, payload builder, App.jsx and the
panels the same day and this path was missed.

Two further §6.1 violations in the same function:

* `address: ... || 'Unknown Location'` and `incident_type: ... || 'EMERGENCY DISPATCH'` —
  fabricated defaults standing in for missing data.
* `priority_code: record.priority_code ?? record.response_type ?? 1` — and `KioskView`
  treats `priority_code <= 2` as an emergency, so **a dispatch with no priority was
  rendered as an emergency**.

It also ignored `verified_address` and `verified_incident` entirely, so an operator's
correction never reached a live kiosk call.

**Fix**: one translation, `frontend/src/utils/dispatchModel.js`, used by the MQTT listener,
`App.jsx` and `MapBoard`. Verified with `frontend/scripts/verify_dispatch_model.mjs`
against **421 real dispatch records: 0 field mismatches** before and after.
