# BRIEFING — 2026-08-14T05:28:00Z

## Mission
Investigate offline map tile serving requirements, frontend Leaflet integration (`MapBoard.jsx`, `apiClient.js`), existing tile assets, and local tile server container options (`cfr_tiles` on port 8081).

## 🔒 My Identity
- Archetype: explorer
- Roles: Teamwork explorer (Read-only investigation)
- Working directory: c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\survey_explorer_2\
- Original parent: e1e3b83e-229d-4daa-984a-1ac449027ff3
- Milestone: 100% Local Containerized GIS Routing & Map Tile Stack

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- 100% local container stack architecture (zero external internet dependency, no cloud dependencies)
- All frontend API fetches must resolve via API_BASE_URL/TILE_BASE_URL from apiClient.js (never raw localhost strings)

## Current Parent
- Conversation ID: e1e3b83e-229d-4daa-984a-1ac449027ff3
- Updated: 2026-08-14T05:28:00Z

## Investigation State
- **Explored paths**:
  - `frontend/src/apiClient.js`
  - `frontend/src/components/MapBoard.jsx`
  - `frontend/src/components/MapConstants.js`
  - `frontend/src/components/MapLayers.jsx`
  - `frontend/src/components/kiosk/RouteOverviewPanel.jsx`
  - `frontend/src/components/kiosk/BlockParcelPanel.jsx`
  - `frontend/src/components/kiosk/PropertySatellitePanel.jsx`
  - `frontend/src/components/DashboardHUD.jsx`
  - `docker-compose.yml`
  - `backend/data/`, `frontend/public/data/`
- **Key findings**:
  - All current Leaflet tile layer configurations in `MapConstants.js` and kiosk components point to external cloud endpoints (CartoCDN, Esri ArcGIS, OpenStreetMap.org).
  - No `.mbtiles` or `.pmtiles` files currently exist in the repo; `docker-compose.yml` needs a `cfr_tiles` service on port 8081 mounted to a local tile directory.
  - `frontend/src/apiClient.js` requires an exported `TILE_BASE_URL` with dynamic hostname resolution to support remote kiosk access over Tailscale (`http://100.95.146.94:8081`).
  - `MapConstants.js`, `MapLayers.jsx`, `MapBoard.jsx`, and kiosk panels require refactoring to use `TILE_BASE_URL` for local basemap tile rendering.
- **Unexplored areas**: None.

## Key Decisions Made
- Recommended container architecture for `cfr_tiles` in `docker-compose.yml` (e.g. `ghcr.io/protomaps/go-pmtiles` or `maptiler/tileserver-gl-light`).
- Designed IP-agnostic `TILE_BASE_URL` resolution pattern in `frontend/src/apiClient.js`.
- Outlined precise code diffs and configuration blueprints for `MapBoard.jsx`, `MapConstants.js`, `MapLayers.jsx`, and kiosk components.

## Artifact Index
- `.agents/survey_explorer_2/DISPATCH.md` — Initial task dispatch
- `.agents/survey_explorer_2/BRIEFING.md` — Agent working memory
- `.agents/survey_explorer_2/progress.md` — Heartbeat & progress tracker
- `.agents/survey_explorer_2/handoff.md` — Final survey & recommendations report
