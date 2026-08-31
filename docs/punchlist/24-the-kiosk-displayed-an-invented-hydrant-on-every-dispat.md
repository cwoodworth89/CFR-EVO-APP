# Punch list #24 — The kiosk displayed an invented hydrant on every dispatch

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🧱 Duplicated & Unsourced Frontend Constants |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L973 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 24. The kiosk displayed an invented hydrant on every dispatch
> **Status**: ✅ **Closed 2026-08-22.** Found from an operator screenshot of a live call.

The screenshot showed `City Hydrant: D-163 (42m)` in the alert banner and
`City Hydrant: D-165 (42m)` in the route panel — **two different hydrants at the same
distance**, for one incident. Neither is near the dispatch coordinate: the actual nearest
hydrants to `49.26312, -122.79819` are `L-191` (72 m), `L-114` (85 m) and `L-221` (108 m).

They were not data. They were string literals in the JSX:

```jsx
// ActiveAlertBanner.jsx
{activeCall?.target?.nearest_city_hydrant || activeCall?.nearest_city_hydrant || 'D-163'}
{activeCall?.target?.nearest_city_dist   || activeCall?.nearest_city_dist   || '42'}m

// RouteOverviewPanel.jsx
{activeCall?.hydrant || activeCall?.target?.hydrant || 'City Hydrant: D-165 (42m)'}
```

**The fallback fired on every call ever displayed.** Measured: **0 of 422** dispatches
carry `nearest_city_hydrant`, `nearest_city_dist` or `hydrant`, and no such field exists
anywhere in `backend/` or `services/`. The fields were always absent, so the kiosk always
showed the invented values.

This is the §6.1 defect in its most direct form: a specific hydrant ID and distance,
presented to crews as the nearest water supply, invented in the view layer. Same class as
the `or "AA"` flow rating (#11) and the `COQUITLAM_CENTER` coordinates (#2).

**Fix**: both fallbacks removed. The banner chip renders only when the dispatch carries a
hydrant; the route panel shows *"Nearest hydrant not computed"*.

**Related, fixed in the same pass**: `MapBoard` still fetched
`frontend/public/data/hydrants.json`, deleted when hydrants moved to the database. The
request 404'd, the handler swallowed it into an empty array, and the console's
nearest-hydrant panel was silently empty on every search. It now reads `/api/hydrants`, as
`MapLayers` already did.

**Still open**: nothing computes a nearest hydrant for a dispatch. `public.hydrants` and
`/api/hydrants` exist, and the console already computes one for a searched address, so
wiring it into the dispatch payload is a feature rather than a repair. Until then the
kiosk correctly reports that it does not know.
