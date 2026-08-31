# Punch list #3 — Missing `responding_units` in Replayed Dispatches

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🧭 Routing Engine & Pathfinding Anomalies |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L138 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 3. Missing `responding_units` in Replayed Dispatches
> **Status**: ✅ **Confirmed fixed (re-verified 2026-08-21).** A tree-wide `SQ1` grep now
> returns exactly one hit — `EVORoutingEngine.js:27`, a descriptive subtitle string in the
> staged `APPARATUS_TIERS` seed data (§6.4), not a fallback. Originally verified in `App.jsx`; `verified_units` → `responding_units` → `[]` resolution is passed through explicitly. The `['SQ1','E1','L1']` invented-apparatus fallbacks have additionally been removed from `EVORoutingEngine.js`, `RouteOverviewPanel.jsx`, and `MapBoard.jsx`.
* **Observed Problem**: Simulated calls in Kiosk view display `SQ1, E1, L1` regardless of what units were dispatched (e.g. `DISP-2026-F1F345` had `E1, E2, R2, C8`).
* **Root Cause**: `handleSimulateCall` in `frontend/src/App.jsx` omitted `responding_units: call.verified_units || call.responding_units || []` when building `mockCall`, causing `EVORoutingEngine.js` to trigger its `['SQ1', 'E1', 'L1']` fallback.
* **Fix**: Pass `responding_units` explicitly in `App.jsx`.

---

## 🎨 Kiosk & Review Panel UI/UX Refinements
