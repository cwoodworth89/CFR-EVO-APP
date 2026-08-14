# Milestone 2 Forensic Audit Report: Local Offline Map Tile Server & Leaflet Integration

**Work Product**: `frontend/src/apiClient.js`, `frontend/src/components/MapConstants.js`, `frontend/src/components/MapLayers.jsx`, `frontend/src/components/kiosk/RouteOverviewPanel.jsx`, `frontend/src/components/kiosk/BlockParcelPanel.jsx`, `docker-compose.yml`  
**Integrity Mode**: Demo Mode (Follow-up Request line 47, `ORIGINAL_REQUEST.md`)  
**Auditor**: `auditor_m2`  
**Verdict**: **CLEAN**  

---

## 1. Executive Summary

A comprehensive forensic audit was conducted on the Milestone 2 deliverables for the CFR EVO Local GIS Routing & Map Tile Stack. All source code changes, layer architectures, dynamic resolution mechanics, container health checks, and build outputs were evaluated against the strict anti-facade and genuine implementation standards defined in the system prompt.

The implementation is verified to be **CLEAN**. There are **no hardcoded test bypasses, no dummy facade methods, and no fabricated verification outputs**.

---

## 2. Phase-by-Phase Forensic Verification

### Phase 1: Source Code & Integrity Analysis

| Check | Target | Status | Evidence / Observation |
|---|---|:---:|---|
| **Hardcoded Output Detection** | `frontend/src/apiClient.js` | **PASS** | Dynamic URL generation in `getTileBaseUrl()`, `getTileUrl()`, and `getTileLayerConfig()` resolves against `window.location.hostname` / env vars without hardcoded responses. |
| **Facade Detection** | `frontend/src/components/MapLayers.jsx` | **PASS** | `BaseMap` implements a genuine `L.TileLayer.extend` (`FallbackTileLayer`) with real DOM tile creation, error interception, sub-domain rotation, and fallback URL retry logic. |
| **Centralized Tile Configuration** | `frontend/src/components/MapConstants.js` | **PASS** | `BASE_LAYERS` defines styles (`GREY`, `DARK`, `VOYAGER`, `OSM`, `SATELLITE`) with local tile endpoints (`${TILE_BASE_URL}/services/...`), online fallback URLs, and zoom boundary parameters (`maxNativeZoom: 18`, `maxZoom: 22`). |
| **Kiosk Panel Integration** | `RouteOverviewPanel.jsx` & `BlockParcelPanel.jsx` | **PASS** | Kiosk panels consume `<BaseMap style="VOYAGER" />` and `<BaseMap style="GREY" />` through centralized Leaflet layer bindings. |
| **Container Specification** | `docker-compose.yml` | **PASS** | `cfr_tiles` (`consbio/mbtileserver` on `8081:8080`) and `cfr_osrm` (`osrm-backend` on `5000:5000`) configured with volume mounts (`backend/data/tiles`, `backend/data/osrm`), restart policies, and shell healthchecks (`wget`, `curl`). |
| **Pre-populated Artifact Detection** | Repository workspace | **PASS** | No pre-baked test output mocks or fake verification tokens were introduced into the workspace. |

---

## 3. Behavioral & Empirical Verification

### 3.1 Frontend Production Build Execution
Command: `npm.cmd run build` in `frontend/`
- **Exit Code**: `0`
- **Build Duration**: `3.79s`
- **Output Artifacts**:
  - `dist/index.html` (0.46 kB)
  - `dist/assets/index-B6fKcVvr.css` (70.62 kB)
  - `dist/assets/index-CFRFWIRD.js` (1,601.62 kB)
- **Result**: Zero syntax, import, or bundling errors.

### 3.2 Docker Compose YAML Validation
Command: `.venv\Scripts\python.exe -c "import yaml; ..."`
- **Exit Code**: `0`
- **Discovered Services**: `['postgres', 'mosquitto', 'osrm', 'tiles', 'ntfy', 'api']`
- **Dependencies**: `api` service cleanly specifies `depends_on` conditions (`service_healthy` for `postgres`, `mosquitto`, `osrm`, `tiles`).

### 3.3 Backend Routing Engine Tests
Command: `.venv\Scripts\pytest.exe backend/tests/test_routing_engine.py`
- **Exit Code**: `0`
- **Result**: `20 passed in 0.50s` (100% pass rate).

---

## 4. Adversarial & Edge Case Analysis

1. **Remote Kiosk Host Resolution**: When accessed from the station kiosk (`http://100.95.146.94:5173`), `window.location.hostname` resolves to `100.95.146.94`, routing tile requests to `http://100.95.146.94:8081` without CORS or localhost conflicts.
2. **Infinite Fallback Loop Defense**: In `MapLayers.jsx`, `FallbackTileLayer` sets `let fallbackTried = false` per tile instance and flips to `true` upon first error, guaranteeing that consecutive 404s terminate cleanly rather than generating an infinite event loop.
3. **Container Dataset Missing Resilience**: `cfr_osrm` command includes bash fallback check (`if [ -f /data/metro-vancouver.osrm ]; then ... else sleep 3600; fi`), preventing container crash loops when datasets are being mounted.

---

## 5. Final Forensic Verdict

**Verdict**: **CLEAN**  
Milestone 2 satisfies all architectural, integrity, and functional requirements.
