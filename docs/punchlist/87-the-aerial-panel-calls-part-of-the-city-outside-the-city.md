# Punch list #87 — The aerial panel's "outside the City" test is a box that cuts off the City's east side

| | |
|:--|:--|
| **Status** | RULED 2026-09-15; being built (frontend-kiosk-architect). |
| **Severity** | 🔴 crew-visible: a real Coquitlam address would read "NOT AVAILABLE OUTSIDE OF CITY" |
| **Area** | 🖥️ Kiosk · 🗺️ Geocoding |
| **Origin** | Lead, 2026-09-15, while checking the basemap extract (#86) |
| **Related** | #86 · CLAUDE.md §5 Tier 2 · the `gis-pipeline-sync` skill, which depends on the same bounds |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

* **Frontend, box only.** `PropertySatellitePanel.jsx:79` decides Tier 2 with
  `isWithinCoquitlam(destLat, destLng)`, which is the box in `frontend/src/utils/addressUtils.js:48`:
  lat 49.20–49.39, lng -122.92 to **-122.70**. CLAUDE.md §5 specifies that box.
* **Backend, polygon first.** `is_within_city` (`services/gis/src/gis_service/spatial_queries.py:242`)
  uses `ST_Contains` on `public.city_boundary` and falls back to the same box only when the query
  returns nothing or errors (`:249`, `:252`).

The operator expected the polygon everywhere (2026-09-15).

## Measured, 2026-09-15 (kiosk database)

* `public.city_boundary` extends east to **-122.621**; the box stops at -122.70.
* **158 parcels** in `public.parcels` have their centroid east of -122.70.
* Not measured: how many of those carry a civic address a call could name, and whether any past
  dispatch landed there.
* Not checked: the box's north (49.39) and south (49.20) edges against the polygon.

## Not decided

Whether the kiosk should take the backend's polygon answer (e.g. a flag on the payload) or keep a
client-side test with corrected bounds. §5 names the box and says the `gis-pipeline-sync` skill
depends on it, so either change is the operator's ruling. Owner once ruled: `gis-spatial-engineer`.
Note also that `ST_Contains` excludes the boundary itself (CLAUDE.md §7.3a).

## Operator ruling, 2026-09-15

"Kiosk should use the city boundary. No fall backs should be needed on that." The kiosk's Tier 2 answer comes from
`public.city_boundary`, with no box anywhere, including the backend's two box fallbacks. An unknown answer renders as
unknown (§6.1). CLAUDE.md §5 and the `gis-pipeline-sync` skill are updated to match once the change lands.
