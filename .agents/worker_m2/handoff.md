# Worker M2: Local Offline Map Tile Server & Leaflet Integration Handoff Report

**Milestone**: Milestone 2 — Local Offline Map Tile Server & Leaflet Integration  
**Author**: Worker M2 (`implementer`, `qa`, `specialist`)  
**Date**: 2026-08-14T05:36:50Z  

---

## 1. Observation

1. **Docker Compose Missing Tile & OSRM Services**:
   - In `docker-compose.yml`, the local container stack only defined `postgres`, `mosquitto`, `ntfy`, and `api`. The offline map tile server (`cfr_tiles`) on port `8081` and OSRM emergency routing backend (`cfr_osrm`) on port `5000` were missing.
   - The `api` service was missing healthcheck conditions for database, broker, routing, and tile container dependencies.

2. **Frontend Basemap Hardcoding & Network Coupling**:
   - In `frontend/src/apiClient.js`, `API_BASE_URL` resolved dynamically to `http://${window.location.hostname}:8000`, but there was no dynamic `TILE_BASE_URL` or tile endpoint resolver for port `8081`.
   - In `frontend/src/components/MapConstants.js`, `BASE_LAYERS` hardcoded external cloud URLs:
     - `GREY`: `https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png`
     - `DARK`: `https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png`
     - `VOYAGER`: `https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png`
     - `OSM`: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
   - In `frontend/src/components/kiosk/RouteOverviewPanel.jsx` (Lines 240–246) and `frontend/src/components/kiosk/BlockParcelPanel.jsx` (Lines 60–65), raw `<TileLayer>` components referenced `BASE_LAYERS` directly without local fallback mechanisms.

---

## 2. Logic Chain

1. **Premise 1 (Zero External WAN Dependency)**: Station bay kiosks and emergency consoles must be capable of rendering basemap tiles without an external internet connection (e.g. during fiber cuts or storm events).
2. **Premise 2 (Dynamic Host Resolution)**: Remote kiosks connect over Tailscale (`http://100.95.146.94:5173`) while developers use `localhost`. Hardcoding host IPs breaks either remote kiosks or local development. Dynamically resolving `TILE_BASE_URL` using `window.location.hostname` ensures both `http://100.95.146.94:8081` and `http://localhost:8081` resolve correctly.
3. **Premise 3 (Local Priority with Graceful Online Fallback)**: By pointing `BASE_LAYERS.url` to the local tile server (`${TILE_BASE_URL}/services/vancouver...`) and maintaining `fallbackUrl` pointing to standard providers (CartoDB / OSM), the client prioritizes local offline tiles.
4. **Premise 4 (Automatic Error Fallback)**: By implementing `FallbackTileLayer` (extending `L.TileLayer` in `MapLayers.jsx`), when a local tile is not found or the server is starting up, Leaflet intercepts `tile.onerror` and transparently retries against `fallbackUrl`.
5. **Premise 5 (Centralized Kiosk UI Basemap Rendering)**: Migrating `RouteOverviewPanel.jsx` and `BlockParcelPanel.jsx` to consume `<BaseMap style="VOYAGER" />` and `<BaseMap style="GREY" />` standardizes map tile resolution and error handling across the entire kiosk HUD.

---

## 3. Caveats

1. **MBTiles / PMTiles Dataset Mount**: The container service mounts `./backend/data/tiles` into `/tiles:ro`. To serve local offline raster/vector tiles in production, the Metro Vancouver tile dataset (`.mbtiles` / `.pmtiles`) should reside in `backend/data/tiles/` (which is excluded from Git to prevent repository bloat).
2. **ArcGIS Satellite Imagery**: High-resolution 3D satellite imagery remains an online-only layer in `PropertySatellitePanel.jsx` and gracefully transitions to "Offline Satellite Standby" when WAN is unavailable, as satellite tile sets are multi-gigabyte.

---

## 4. Conclusion

1. **Docker Compose**: Added `cfr_tiles` (`consbio/mbtileserver` on `8081:8080`) and `cfr_osrm` (`osrm/osrm-backend:v5.27.1` on `5000:5000`) with comprehensive health checks (`wget`, `curl`, `pg_isready`, `mosquitto_sub`).
2. **API & Dynamic Resolution**: Exported `TILE_BASE_URL`, `getTileUrl()`, and `getTileLayerConfig()` in `frontend/src/apiClient.js`.
3. **Leaflet Basemaps**: Updated `MapConstants.js` and `MapLayers.jsx` with local tile endpoints and dynamic online fallback handling.
4. **Kiosk Panels**: Updated `RouteOverviewPanel.jsx` and `BlockParcelPanel.jsx` to consume `BaseMap`.
5. **Build & Test Verification**: `npm run build` completed with zero errors in 2.69s; all 20 backend routing tests passed with 100% success rate.

---

## 5. Verification Method

To independently verify these changes:

1. **Verify Frontend Asset Build**:
   ```bash
   cd frontend
   npm run build
   # Confirm vite builds dist/ cleanly with 0 errors
   ```

2. **Verify Python Routing Engine Test Suite**:
   ```bash
   .venv/Scripts/pytest.exe backend/tests/test_routing_engine.py
   # 20 passed in 0.40s
   ```

3. **Verify Docker Compose Configuration**:
   ```bash
   docker compose config
   ```

4. **Verify Dynamic Tile Resolution in Browser**:
   Open `http://localhost:5173` or `http://100.95.146.94:5173` in browser and verify that tile requests route to port `8081` on the matching host.
