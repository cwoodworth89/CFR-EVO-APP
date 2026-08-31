# Punch list #4 — Remove Satellite View from Call Review Panel

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | hygiene |
| **Area** | 🎨 Kiosk & Review Panel UI/UX Refinements |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L150 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 4. Remove Satellite View from Call Review Panel
> **Status**: ✅ **Fixed, but the record was wrong.** The defect is gone: `SatelliteMiniMap`
> is no longer in `VerificationSidebar.jsx`, and the Burlington & Pinetree pin is
> impossible — the component early-returns `null` on falsy `lat`/`lng`
> (`hud/SatelliteMiniMap.jsx:7`) and its one caller guards as well, rendering
> "Coordinates missing" instead (`hud/ActiveDispatchPanel.jsx:120–126`).
>
> **The claim "deleted entirely" is false.** The file exists at
> `frontend/src/components/hud/SatelliteMiniMap.jsx` and is used by
> `ActiveDispatchPanel.jsx` — a different, intended surface. It was removed from the
> review panel, not from the codebase.
>
> Cosmetic follow-up, not a data defect: that panel is labelled
> `🛰️ GOOGLE SATELLITE VIEW`, but the layer is the local offline MBTiles service
> (`TILE_BASE_URL/services/satellite/...`). The label names a cloud provider this
> architecture deliberately does not use.

* **Observed Problem**: `VerificationSidebar.jsx` includes a `<SatelliteMiniMap />` component that was never intended in the plan. When target coordinates are missing, it persistently defaults to pinning at Burlington Ave & Pinetree Way (`49.2838, -122.7932`).
* **Fix**: Remove `SatelliteMiniMap` from `VerificationSidebar.jsx`.
