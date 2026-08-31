# Punch list #22 — "Next 24h" / "Next 7d" closure filters matched nothing

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🧱 Duplicated & Unsourced Frontend Constants |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L918 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 22. "Next 24h" / "Next 7d" closure filters matched nothing
> **Status**: ✅ **Closed 2026-08-22 — found and fixed during the MapBoard decomposition.**

The road closure fetch computed `start` and `end` as locals inside its `map()` and then
returned `{ ...evt, isActive, isFuture, isExpired }`, discarding both. The timeframe filter
downstream tested `closure.start`:

```js
const is24hFuture = closure.isFuture && closure.start && (...)
```

`closure.start` never existed — the API returns `startDate` and `endDate` — so both
`is24hFuture` and `is7dFuture` were permanently falsy and **the "Next 24h" and "Next 7d"
toggles matched nothing whatever the data**. Only "Active Now" ever showed a closure.

Measured against the live feed at the time of the fix: **94 closures, 18 future-dated, 13
of them starting within 7 days**. All 13 were unreachable through the UI.

Fixed by carrying `start` and `end` onto the returned object in
`frontend/src/hooks/useRoadClosures.js`. Nothing else changed.

This is the second defect of the shape "a guard tests a field that is never populated" —
see also the `cross_streets` plumbing, which is wired end to end but reached 1 of 410
dispatches. A truthy check on an absent field fails silently and looks like "no results".
