# CFR EVO v1.0.0 — Adversarial Challenger Handoff Report

**Agent Role**: Adversarial Challenger (critic, specialist)  
**Working Directory**: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\challenger_review_validation\`  
**Target Milestone**: CFR EVO v1.0.0 Architectural Review, Model Tier Allocation & Offline Hardening Validation  
**Date**: 2026-08-14  
**Handoff Type**: Hard (Task Complete)  

---

## 1. Observation

1. **Unsupervised Multiprocessing Worker Process**:
   In `backend/cfr_dispatch/orchestration.py:77-83`:
   ```python
   worker_process = multiprocessing.Process(target=background_worker_loop, args=(dispatch_queue,), daemon=True)
   worker_process.start()
   run_audio_listener_loop(dispatch_queue)
   ```
   No health check or restart logic exists if `worker_process` crashes during Whisper transcription.

2. **Intersection Drop in Local Geocoder**:
   In `services/gis/src/gis_service/geocoder.py:183`:
   ```python
   if " and " in parsed_address.lower() and not re.match(r'^\d+', parsed_address):
       return None
   ```
   Cross-street dispatches (e.g. "Guildford Way and Pinetree Way") return `None`, causing `lat=None, lng=None` and dropping route calculations.

3. **Direct WAN DriveBC Fetch Leak in Frontend**:
   In `frontend/src/components/MapBoard.jsx:688`:
   ```javascript
   const fetchDirectDriveBC = fetch("https://api.open511.gov.bc.ca/events?format=json&limit=100")
   ```
   Direct browser fetch to external WAN endpoint is executed on every road closure load, causing unhandled network errors and DNS timeouts when offline.

4. **Missing Building Footprint Vector Canvas**:
   In `frontend/src/components/kiosk/StreetViewPanel.jsx:119`, execution returns early when `!isOnline`, leaving a blank container instead of the claimed vector canvas.

5. **External CDN Marker Icon Dependencies**:
   In `frontend/src/components/kiosk/BlockParcelPanel.jsx:32-33`, `PropertySatellitePanel.jsx:50-51`, and `RouteOverviewPanel.jsx:63-64`, Leaflet icon URLs reference `https://raw.githubusercontent.com/...` and `https://cdnjs.cloudflare.com/...`.

6. **Routing Engine Parameter Contradiction**:
   In `services/gis/src/gis_service/routing_engine.py:114`:
   ```python
   query_params = "overview=full&geometries=geojson&continue_straight=false&steps=true"
   ```
   Contradicts the architecture package claim of `continue_straight=true`.

7. **False IT Health Alert in Offline Mode**:
   In `backend/cfr_dispatch/health_watchdog.py:35, 93`:
   `check_network_connectivity("https://1.1.1.1")` flags `overall_status = "UNHEALTHY"` when the system operates offline as intended.

8. **Broken Regression Test Import**:
   In `backend/tests/test_parcels_and_streetview_api.py:18`:
   ```
   ImportError: cannot import name 'StreetViewOverrideModel' from 'api.models'
   ```
   `StreetViewOverrideModel` was removed from `backend/api/models.py` during parcel schema unification.

9. **Frontend Vite Build Execution**:
   `npm.cmd run build` in `frontend/` succeeds in 2.69s, producing a single 1.6MB bundle (`dist/assets/index-CtNBvDFZ.js: 1,601.66 kB`), confirming the need for component decomposition.

10. **Model Tier Matrix Misclassifications**:
    `P4-05` (Ray-casting PIP) was over-allocated to Pro (standard Shapely/GeoPandas operation), and `P0-03` (Sibling path injection) was allocated to Flash (standard 6-line sys.path append).

---

## 2. Logic Chain

1. **Step 1 (From Observation 1)**: If `worker_process` throws an unhandled exception or terminates under memory pressure, the listener in `orchestration.py` keeps running, but audio is never transcribed or broadcast. -> **Conclusion: Worker supervision and automatic restart logic is mandatory.**
2. **Step 2 (From Observation 2)**: Radio dispatches frequently involve motor vehicle accidents at intersections (e.g. "Mariner and Austin"). When `geocoder.py:183` returns `None`, the dispatch fails to geocode, failing route polylines and hydrants. -> **Conclusion: `local_geocode()` must resolve cross-streets against `intersections.json`.**
3. **Step 3 (From Observation 3 & 5)**: In an isolated station bay without internet, external HTTP requests to Open511 and GitHub/cdnjs fail with network timeouts. -> **Conclusion: Purge direct browser WAN fetches and bundle Leaflet marker icons locally.**
4. **Step 4 (From Observation 4)**: The claimed offline vector building footprint canvas is not implemented in `StreetViewPanel.jsx`. -> **Conclusion: Add an HTML5 `<canvas>` parcel footprint renderer when `!isOnline`.**
5. **Step 5 (From Observation 6)**: `continue_straight=false` allows OSRM to generate sharp U-turns inappropriate for heavy fire apparatus. -> **Conclusion: Set `continue_straight=true` for heavy/standard apparatus profiles.**
6. **Step 6 (From Observation 7)**: `health_watchdog.py` pinging `1.1.1.1` causes spurious alerts in offline deployments. -> **Conclusion: Guard WAN connectivity checks behind `DISABLE_WAN_FALLBACK`.**
7. **Step 7 (From Observation 8)**: `test_parcels_and_streetview_api.py` imports a deleted model. -> **Conclusion: Update test imports to target `ParcelModel`.**
8. **Step 8 (From Observation 9 & 10)**: Vite build yields a 1.6MB monolith, and model tier allocation can save additional credits. Downgrading `P4-05` (Pro -> Flash) and `P0-03` (Flash -> Flash-Lite) increases net savings from 68% to 72.4% without risk. -> **Conclusion: Approve updated 33-task Model Tier Allocation Matrix.**

---

## 3. Caveats

1. **Hardware Audio Capture in CI**: Physical PortAudio hardware streaming (`sounddevice.InputStream`) requires an attached soundcard; automated non-interactive CI tests must mock the input stream.
2. **Local Tile Server Container**: Local vector/raster basemaps on port `8081` require pre-seeded MBTiles/PMTiles volumes.
3. **Street View WAN Dependence**: Interactive 360° street view and high-res satellite tiles are acknowledged external add-ons that gracefully fall back when offline.

---

## 4. Conclusion

The CFR EVO v1.0.0 architecture is **sound and approved for implementation** with a final verdict of **CONDITIONAL APPROVAL**, subject to the remediation of the 12 identified gaps detailed in `challenge_report.md`. The revised Model Tier Allocation Matrix (12 Flash-Lite, 14 Flash, 7 Pro) is finalized with **72.4% net AI credit savings**.

---

## 5. Verification Method

1. **Verify Frontend Offline Purity & Build**:
   ```bash
   cd frontend && npm.cmd run build
   ```
   Inspect `frontend/src/components/MapBoard.jsx:688` and verify zero external WAN URLs.
2. **Verify Python Unit Tests & Models**:
   ```bash
   python -m unittest discover -s backend/tests
   ```
3. **Inspect Challenge Deliverables**:
   - `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\challenger_review_validation\challenge_report.md`
   - `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\challenger_review_validation\handoff.md`
   - `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\challenger_review_validation\progress.md`
