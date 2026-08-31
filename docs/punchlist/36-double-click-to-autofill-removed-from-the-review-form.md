# Punch list #36 — Double-click-to-autofill removed from the review form

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | hygiene |
| **Area** | 🖥️ Live Operation Batch, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2120 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 36. Double-click-to-autofill removed from the review form
> **Status**: ✅ **Closed 2026-08-23.** Operator request: Ctrl+Space alone is working well.

Six `onDoubleClick={() => onPrefillField(...)}` handlers removed from
`VerificationSidebar.jsx` (transcript, units, incident, address, subaddress, map grid), and
the five tooltips advertising the gesture updated to
`"Click, or press Ctrl+Space, to import the system value"`.

The `Sys:` click affordance and the Ctrl+Space handler are untouched. `lint:crash` and
`npm run build` both pass. **Not yet deployed to the kiosk.**

---
