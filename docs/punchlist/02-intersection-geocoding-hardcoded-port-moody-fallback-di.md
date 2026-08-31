# Punch list #2 — Intersection Geocoding & Hardcoded Port Moody Fallback (`DISP-2026-F1F345`)

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🧭 Routing Engine & Pathfinding Anomalies |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L60 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 2. Intersection Geocoding & Hardcoded Port Moody Fallback (`DISP-2026-F1F345`)
> **Status**: ✅ **Closed 2026-08-21 (second pass).** Reopened during the reconciliation,
> then fixed — see the resolution note at the end of this item. **Two** fallbacks had
> survived the sweep, not one. Original reopening follows.
>
> ⚠️ **REOPENED 2026-08-21.** Mostly fixed, but **one fallback survived the
> sweep** — and it is on the live new-dispatch path. `frontend/src/components/MapBoard.jsx:471`:
>
> ```js
> const target = newCall.target || (newCall.address
>   ? { address: newCall.address, lat: newCall.lat || COQUITLAM_CENTER[0],
>                                 lng: newCall.lng || COQUITLAM_CENTER[1] } : null);
> ```
>
> This is the exact defect this item describes, one commit short of closed: a null
> coordinate silently becomes `49.2838, -122.7907` (City Centre), inside the §5 bounds
> check, so tiles render and routing proceeds and nothing warns. It is the same shape as
> the bug that routed **every live MQTT call** to Town Centre.
>
> The claim "all hardcoded coordinate fallbacks have now been removed frontend-wide" was
> **reported, not verified**, and is wrong.
>
> ~~The other four `COQUITLAM_CENTER` uses in `MapBoard.jsx` were checked and are
> legitimate — initial map view (`:176`, `:836`), a distance comparison (`:380–381`), and
> an idle "reset view" `flyTo` (`:998`). **Only line 471 needs to change.**~~
>
> **That was wrong, and it is worth recording why.** `:176` is *not* an initial map view —
> it is inside `RoadClosureMarker`, and it was a **second fabrication of the same class**:
>
> ```js
> const markerPos = Array.isArray(closure.coordinates) && closure.coordinates.length >= 2
>   ? [parseFloat(closure.coordinates[0]), parseFloat(closure.coordinates[1])]
>   : COQUITLAM_CENTER;      // <- a road closure with no coordinate drawn at City Centre
> ```
>
> A closure whose point coordinate is missing or malformed was rendered as a closure
> **across City Centre that the municipal feed never reported** — an invented road closure
> on the tactical map, which could push crews off a route that is actually open. It was
> mis-assessed on the first pass because the enclosing function was identified from a grep
> line number rather than by reading the surrounding code.
>
> The remaining three uses were re-read in full and *are* legitimate: initial map centre
> (`:836`), an off-default-view distance comparison (`:380–381`), and the idle "reset
> view" button (`:998`). None substitutes for real data.
>
> ---
>
> **Resolution (2026-08-21).** Both fabrications removed in `MapBoard.jsx`:
>
> 1. **Dispatch target** — the `|| COQUITLAM_CENTER[...]` defaults are gone; `lat`/`lng`
>    now propagate as `null`, so the §5 Tier 1 card fires and routing stays suppressed.
>    Downstream was already safe: `updateTargetAddress` branches only on `address` and
>    `rings`, and the `flyTo` is guarded by `if (map && target.lat && target.lng)`.
> 2. **Road closure marker** — falls back only to the first vertex of the closure's *own*
>    polyline (real data from the same record), and renders **no marker** when there is
>    neither a point nor a polyline. The polyline alone still shows the closure.
>
> Both carry provenance comments citing §6.1. `npm run lint:crash` and `npm run build`
> both pass.
>
> **Note for #6**: the backend already drops closures with unparseable geometry rather
> than pinning them, so the marker path should rarely fire — but the frontend no longer
> depends on that being true.
* **Incident**: `CHRISTMAS WAY AND WESTWOOD ST` (Grid 68, Motor Vehicle Incident).
* **Observed Problem**:
  * The call routed from Hall 1 all the way out into **Port Moody** (`49.27305, -122.88452`).
  * The Cadastral Block & Satellite PIPs were blank (outside Coquitlam municipal tile boundary).
  * Street View was unable to resolve facade.
* **Root Cause Identified**:
  * The dispatch target had `target.lat: null, target.lng: null` because intersection geocoding did not resolve `Christmas Way and Westwood St`.
  * When `lat`/`lng` is null, `App.jsx` (`handleSimulateCall`) and `SimulationControl.jsx` fell back to hardcoded coordinates `49.27305, -122.88452` (Port Moody).
  * OSRM faithfully routed to the Port Moody coordinates, and tile servers have no data outside Coquitlam.
* **Action Required**:
  1. Add authoritative Coquitlam arterial intersection coordinates for `Christmas Way & Westwood St` (`49.2783, -122.7935`) and audit intersection dictionary.
  2. Fix `App.jsx` and `SimulationControl.jsx` fallback coordinates to use verified City Center coordinates (`49.2838, -122.7907`), never out-of-city coordinates.

---
