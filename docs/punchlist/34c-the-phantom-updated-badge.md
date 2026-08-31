# Punch list #34c — The phantom "UPDATED" badge

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🧾 Import Completeness Audit, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3450 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 34 (resolved). The phantom "UPDATED" badge
> **Status**: ✅ **Closed 2026-08-27.** Not yet observed on a live call — the change is
> unit-tested against realistic payloads, but the operator's own confirmation is what closes
> the loop on anything MQTT-driven.

**Cause.** `useKioskQueue.js` called `triggerUpdateFlash()` unconditionally at both merge
sites — `handleNewDispatch` (`:107`) and `handleUpdate` (`:136`) — whenever the incoming
record matched the active one by `dispatch_id`. Nothing compared the payloads. MQTT QoS 1 is
**at-least-once**, so a duplicate delivery of a byte-identical call is the contract rather
than an anomaly, and the badge fired on it every time.

That is an operational claim with nothing behind it (§6.1): the kiosk told the operator data
had changed when frequently none had, which is the same class of defect as a fabricated value
— it just fabricates an *event* instead.

**Fix.** `getVisibleChanges(current, incoming)` in `utils/dispatchModel.js` returns the names
of the **operator-visible** fields that actually differ; `triggerUpdateFlash` is a no-op on an
empty list. The merge still happens either way — the corrected values are what the crew needs
— only the *announcement* is now conditional.

Comparison notes, each deliberate:

* **`routing_metrics` is excluded.** OSRM re-runs per broadcast and can return a duration
  differing by a second for an identical call. Including it would make the badge fire on noise
  — precisely what this fixes.
* `null`, `undefined` and `''` are all "not present" and do not read as a change.
* Numeric strings compare numerically, so `lat: '49.2963'` vs `49.2963` is not a change.
* Unit **order is significant** — it is the dispatch order, which the kiosk preserves
  deliberately — so a reorder counts as a real change.

**The badge now says what changed**, which was the operator's other complaint ("it defaulted
by saying there was an update, but didn't give any"). `⚡ UPDATED: address, map grid`, with the
full list on hover, mapped to operator-facing words (`radio_channel` → "talk group").

**Verified** against 11 realistic payload pairs — all pass:

```
PASS  identical redelivery (QoS1 duplicate)     -> []
PASS  noise only: timestamp/confidence/audio    -> []
PASS  null vs empty string                      -> []
PASS  lat as string vs number                   -> []
PASS  phase2 corrects grid                      -> [map_grid]
PASS  address + coords corrected                -> [address,lat,lng]
PASS  units reordered                           -> [responding_units]
PASS  whitespace only                           -> []
```

`lint:crash` and `npm run build` clean.

---
