# Worker M2 Dispatch: Local Offline Map Tile Server & Leaflet Integration

## Mission Objective
Implement offline local map tile integration across frontend Leaflet components and configure the local tile server service in `docker-compose.yml`.

## Mandatory Reading
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\PROJECT.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\GEMINI.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\survey_explorer_2\handoff.md`

## Write Ownership
- `frontend/src/apiClient.js`
- `frontend/src/components/MapConstants.js`
- `frontend/src/components/MapLayers.jsx`
- `frontend/src/components/kiosk/RouteOverviewPanel.jsx`
- `frontend/src/components/kiosk/BlockParcelPanel.jsx`
- `docker-compose.yml`

## Specific Requirements
1. **`frontend/src/apiClient.js`**:
   - Add `getTileBaseUrl()` helper and export `TILE_BASE_URL` using `window.location.hostname` on port `8081` (with `import.meta.env.VITE_TILE_BASE_URL` override support).
2. **`frontend/src/components/MapConstants.js`**:
   - Import `TILE_BASE_URL` from `../apiClient`.
   - Update `BASE_LAYERS` (`GREY`, `DARK`, `VOYAGER`, `OSM`) to point to local tile URLs (`${TILE_BASE_URL}/styles/...` or `${TILE_BASE_URL}/{z}/{x}/{y}.png`) as primary with `fallbackUrl` for graceful online fallback if local tile server has missing tiles.
   - Maintain `maxNativeZoom: 18` / `maxZoom: 22`.
3. **`frontend/src/components/MapLayers.jsx`**:
   - Update `BaseMap` component to cleanly consume the updated `BASE_LAYERS` config with tile error handling.
4. **`frontend/src/components/kiosk/RouteOverviewPanel.jsx` & `BlockParcelPanel.jsx`**:
   - Verify they use `BASE_LAYERS.VOYAGER` / `BASE_LAYERS.GREY` without hardcoded external URLs.
5. **`docker-compose.yml`**:
   - Add `cfr_tiles` container service on port `8081:8080` (or `8081:8081`) with volume `./frontend/public/data/tiles:/tiles:ro` or `./backend/data/tiles:/data:ro`.
   - Add `cfr_osrm` container service on port `5000:5000` with volume `./backend/data/osrm:/data:ro`.
   - Update `cfr_api` environment with `OSRM_BACKEND_URL: http://osrm:5000` and `TILE_SERVER_URL: http://tiles:8080`.
6. **Frontend Build Verification**:
   - Run `npm run build` inside `frontend/` to verify clean compilation without syntax or packaging errors.
7. Write your completion report to `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m2\handoff.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
