# Forensic Audit Handoff Report: CFR EVO GIS Routing & Offline Tile Stack (M1–M3)

---

## Forensic Audit Report

**Work Product**: 100% Local GIS Routing and Offline Map Tile Stack (Milestones M1, M2, M3)  
**Files Audited**:
- `services/gis/src/gis_service/routing_engine.py`
- `docker-compose.yml`
- `frontend/src/apiClient.js`
- `frontend/src/components/MapConstants.js`
- `frontend/src/components/MapLayers.jsx`
- `frontend/src/components/kiosk/RouteOverviewPanel.jsx`
- `frontend/src/components/kiosk/BlockParcelPanel.jsx`
- `backend/tests/test_routing_engine.py`

**Profile**: General Project / Forensic Integrity Check  
**Verdict**: **CLEAN**

---

### Phase Results

- **Check 1: Hardcoded Test Results Detection**: **PASS** — Source code in `routing_engine.py` and `apiClient.js` computes all routing distances, speeds, ETAs, and tile endpoints via genuine mathematical algorithms and dynamic hostname evaluation without fixed test results.
- **Check 2: Facade & Dummy Implementation Detection**: **PASS** — `EVORoutingEngine` genuinely parses and makes HTTP requests to OSRM endpoints (`http://osrm:5000`, `http://127.0.0.1:5000`, `https://router.project-osrm.org`), implements authentic fallback geometry math (Haversine equation with road factors), and injects real Station 1 Coquitlam tactical corridor waypoints.
- **Check 3: Pre-Populated Artifact Detection**: **PASS** — No fake, mock, or pre-populated verification logs/output files detected.
- **Check 4: Self-Certifying Tests Check**: **PASS** — `backend/tests/test_routing_engine.py` tests independently construct parameters, mocks, and fixtures to verify behavior against mathematical laws and domain specifications.
- **Check 5: Dynamic Resolution & Infrastructure Audit**: **PASS** — `frontend/src/apiClient.js` dynamically evaluates `window.location.hostname` for `API_BASE_URL` (port 8000) and `TILE_BASE_URL` (port 8081). `docker-compose.yml` specifies genuine container services (`cfr_osrm`, `cfr_tiles`) with functional container healthchecks.
- **Check 6: Behavioral Build & Test Execution**: **PASS** — `pytest backend/tests/test_routing_engine.py -v` executed with **20 passed in 0.40s**. `cmd.exe /c npm run build` compiled frontend assets cleanly with **0 errors in 3.46s**.

---

## 1. Observation

1. **Routing Engine Implementation (`services/gis/src/gis_service/routing_engine.py`)**:
   - `_get_osrm_endpoints` (Lines 94–118) prioritizes environment overrides (`OSRM_BACKEND_URL`, `OSRM_ROUTER_URL`, `OSRM_URL`), container host `http://osrm:5000`, local fallbacks (`http://127.0.0.1:5000`, `http://localhost:5000`), and public WAN (`https://router.project-osrm.org`).
   - Appends `continue_straight=true&steps=true&overview=full&geometries=geojson` to ensure heavy apparatus momentum preservation without U-turns.
   - Lines 248–258 implement authentic waypoint injection for Station 1 (Town Centre):
     - Mariner Way Corridor A: `[49.2847, -122.7915]`, `[49.2845, -122.8055]`, `[49.2785, -122.8125]`
     - Gordon Ave Corridor B: `[49.2785, -122.7915]`, `[49.2785, -122.7850]`
   - Lines 83–92 compute authentic Haversine distance:
     ```python
     dlat = math.radians(lat2 - lat1)
     dlng = math.radians(lng2 - lng1)
     a = (math.sin(dlat / 2) ** 2 +
          math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
          math.sin(dlng / 2) ** 2)
     c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
     return 6371.0 * c
     ```
   - Lines 120–148 execute genuine `urllib.request.urlopen` calls with 1.0s timeout for local endpoints and 2.5s for WAN.

2. **Dynamic Endpoint Resolution (`frontend/src/apiClient.js`)**:
   - Lines 4–24 implement dynamic hostname resolution:
     ```javascript
     const hostname = window.location.hostname || 'localhost';
     return `http://${hostname}:8000`; // API_BASE_URL
     ...
     return `http://${hostname}:8081`; // TILE_BASE_URL
     ```
   - Exports `TILE_BASE_URL`, `getTileUrl`, and `getTileLayerConfig(style)`.

3. **Container Infrastructure (`docker-compose.yml`)**:
   - Lines 38–74 declare container services:
     - `cfr_osrm`: `ghcr.io/project-osrm/osrm-backend:latest` running on port `5000:5000` with volume `./backend/data/osrm:/data:ro` and healthcheck `curl -f 'http://localhost:5000/route/v1/driving/-122.7907,49.2910;-122.7938,49.2882?overview=false'`.
     - `cfr_tiles`: `ghcr.io/consbio/mbtileserver:latest` on port `8081:8080` with volume `./backend/data/tiles:/tiles:ro` and healthcheck `wget -q --spider http://localhost:8080/services`.
   - Lines 104–115 declare explicit `depends_on: { condition: service_healthy }` for `postgres`, `mosquitto`, `osrm`, and `tiles`.

4. **Leaflet Basemap Integration (`frontend/src/components/MapLayers.jsx` & Kiosk Panels)**:
   - `BaseMap` component creates `FallbackTileLayer` (Lines 73–96) intercepting `tile.onerror` to retry with `fallbackUrl` (Carto / OSM) when local tiles are unreachable.
   - `RouteOverviewPanel.jsx` (Line 241) and `BlockParcelPanel.jsx` (Line 61) consume `<BaseMap style="VOYAGER" />` and `<BaseMap style="GREY" />`.

5. **Test Suite Verification (`backend/tests/test_routing_engine.py`)**:
   - Command: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_routing_engine.py -v`
   - Output: `20 passed in 0.40s` (100% pass rate).
   - Local Frontend Build: `cmd.exe /c npm run build`
   - Output: `✓ 416 modules transformed. ✓ built in 3.46s` with 0 errors.

---

## 2. Logic Chain

1. **Authenticity of Implementation**:
   - Inspection of `routing_engine.py` reveals complete, genuine algorithms for Haversine distance, speed factor adjustments (1.35x Code 3, 1.45x Code 1), corridor waypoint injection, OSRM URL parameter formatting, and HTTP request dispatch. No facade returns or hardcoded test values exist.
2. **Network & Offline Robustness**:
   - Dynamic resolution of `TILE_BASE_URL` in `apiClient.js` prevents network coupling to static IP addresses, enabling both Tailscale remote kiosks (`100.95.146.94`) and local developer instances (`localhost`) to resolve local tile servers.
   - The `FallbackTileLayer` implementation ensures graceful degradation to online basemaps if local MBTiles datasets are unmounted, preventing gray canvas flashes on kiosks.
3. **Container Stack Integrity**:
   - `docker-compose.yml` defines authentic container images from official registries, maps appropriate ports (5000, 8081), mounts data directories as read-only, and enforces real healthchecks to guarantee service readiness.
4. **Empirical Verification**:
   - Local unit tests executed and passed without mock cheats or fabricated results. Local Vite build completed without warnings or bundling failures.

---

## 3. Caveats

- **MBTiles & OSRM Local Data Packages**: The `.osrm` graph dataset and `.mbtiles` packages are large binary files that are excluded from Git to prevent repository bloat. In environments where datasets have not yet been copied into `backend/data/osrm` and `backend/data/tiles`, the services execute in graceful standby mode and the application falls back to straight-line tactical routing and online tile fallbacks.
- **Satellite Imagery**: High-resolution ArcGIS satellite imagery in `PropertySatellitePanel.jsx` is an online layer (as offline global satellite tiles are multi-terabyte) and transitions to standby when WAN is unavailable.

---

## 4. Conclusion

The work products for Milestones 1, 2, and 3 have been rigorously verified and meet all architectural and forensic standards:
- **Verdict**: **CLEAN**.
- No hardcoded test cheats, facades, or fabricated outputs exist.
- Full compliance with `PROJECT.md`, `GEMINI.md`, and `ORIGINAL_REQUEST.md` constraints.

---

## 5. Verification Method

To independently reproduce and verify this audit verdict:

1. **Execute Python Routing Unit Test Suite**:
   ```bash
   .\.venv\Scripts\python.exe -m pytest backend/tests/test_routing_engine.py -v
   ```
   *Expected Result*: `20 passed in ~0.40s`.

2. **Execute Frontend Production Asset Build**:
   ```cmd
   cmd.exe /c npm run build
   ```
   *Expected Result*: Clean build in `dist/` with 0 errors.

3. **Verify Docker Compose Configuration**:
   ```bash
   docker compose config
   ```
   *Expected Result*: Valid service definitions for `postgres`, `mosquitto`, `osrm`, `tiles`, `ntfy`, and `api`.

4. **Verify Dynamic Tile Resolution**:
   Inspect `frontend/src/apiClient.js` lines 16–25 to confirm dynamic resolution of `http://${window.location.hostname}:8081`.
