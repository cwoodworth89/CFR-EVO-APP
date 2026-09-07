# Punch list #37 — Close button and timer timeout should not dismiss to the same place

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | hygiene |
| **Area** | 🖥️ Live Operation Batch, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2133 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 37. Close button and timer timeout should not dismiss to the same place
> **Status**: ✅ **Closed 2026-09-06 — a timeout lands on the map, a Close returns to the screen the operator was on.** *(Opened as: Open — noted for change by the operator 2026-08-23.)*

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

### Closed 2026-09-06

Built as the fix direction said. `dismissActiveCall(reason)` in `useKioskQueue.js` takes
`'timeout'` from the countdown and `'manual'` from the banner's Close, and records the last
one as `lastDismiss`. `App.jsx` no longer clobbers `returnMode` when a live call arrives; it
watches the call end and sets EXPLORE only when the reason was a timeout. So:

| Dismissal | Goes to |
|:--|:--|
| countdown ran out | the map, as decided 2026-08-22 |
| Close pressed | whatever was underneath: the map, or the review list a replay was launched from |
| EXIT REVIEW on a replay | unchanged, the review list |

Not verified on the kiosk: it needs a live call to close by hand and another to let time
out, and neither can be staged from here (CLAUDE.md 6.5). The build is on the kiosk; the
next two calls will show it.

