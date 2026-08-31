# Punch list #37 — Close button and timer timeout should not dismiss to the same place

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | hygiene |
| **Area** | 🖥️ Live Operation Batch, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2133 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 37. Close button and timer timeout should not dismiss to the same place
> **Status**: ⚠️ **Open — noted for change by the operator 2026-08-23.**

Required behaviour:

| Dismissal | Should go to |
|:--|:--|
| **Call timer times out** | main map (EXPLORE) |
| **Operator presses Close** | back to whatever screen they were on |

Today both do the same thing, and the "drop to map" is *forced*. `App.jsx:52-54`:

```js
const activeIsLive = !!kioskState.activeCall && !kioskState.activeCall.isReview;
if (activeIsLive && returnMode !== 'EXPLORE') setReturnMode('EXPLORE');
```

That is a deliberate decision recorded on 2026-08-22 — a live call interrupting a review was
meant to return the crew to the map, not to an admin table. The reasoning is sound for a real
response; it is simply wrong for the operator doing review work, which is what this item
changes.

`useKioskQueue.js:177` `dismissActiveCall` is shared by **both** paths — the Close button
(`KioskView.jsx:226`) and the countdown (`:199`) call the identical function, so nothing
downstream can distinguish them.

**Fix direction**: give `dismissActiveCall` a reason (`'timeout' | 'manual'`); stop clobbering
`returnMode` on activation and instead capture the pre-call mode; on `'timeout'` set EXPLORE,
on `'manual'` restore what was captured. **Note this touches the live dispatch path**, so the
2026-08-22 intent must survive: a live call that interrupts a review and then *times out*
still lands on the map.

---
