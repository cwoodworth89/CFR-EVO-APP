# CFR EVO v1.0.0 — Zero-Online-Fallback & Offline Verification Rubrics

> [!NOTE]
> **Status (as of 2026-08-20)**: This rubric was drafted 2026-08-14 as a planning/review artifact and was never executed as a formal test pass — every checkbox below is unchecked and stayed that way. It does not reflect current implementation status. For what has actually been built, committed, and verified on the kiosk, see [`docs/development_freeze_summary.md`](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/docs/development_freeze_summary.md) (Phase A–F), which is the authoritative record going forward.

**Mandate**: The CFR EVO platform must operate with **100% local data authority, zero recurring monthly costs, and zero cloud WAN dependencies** for all critical emergency dispatch, routing, and station bay display operations (with graceful local fallback for optional add-on satellite/street-view PiPs).

---

## 1. Zero-Online-Fallback Principles & Architectural Guardrails

```
+-------------------------------------------------------------------------------------------------------------------+
|                                     STRICT ZERO-ONLINE-FALLBACK ARCHITECTURAL RULES                                |
+-----------------------+---------------------------------------------+---------------------------------------------+
| Operational Domain    | Local Data Authority (Primary)              | Strict Offline Behavior & Fallback          |
+-----------------------+---------------------------------------------+---------------------------------------------+
| **Database & Auth**   | Local PostgreSQL 16 on `localhost:5432`     | Zero Supabase / Firebase / Cloud DBs        |
| **Event Broadcast**   | Local Mosquitto MQTT on `localhost:9001`    | WebSockets on local subnet / Tailscale      |
| **Speech-to-Text**    | CTranslate2 `int8` Whisper on local CPU     | Zero OpenAI / Google STT cloud API calls    |
| **Geocoding**         | Local `Addresses.shp` in-memory hash table  | Zero Google Geocoding / Mapbox API calls    |
| **Map Basemap Tiles** | Local `cfr_tiles` container on port `8081`  | Suppress external Carto/OSM CDN fallbacks   |
| **Emergency Routing** | Local `cfr_osrm` container on port `5000`   | In-memory straight-line road-factor fallback|
| **Hydrant Water Map** | Local `hydrants.json` (<1MB) in Turf.js RAM | Zero online ArcGIS MapServer dependencies   |
| **Street View / PiP** | Google Maps JS SDK (optional add-on)        | Graceful local building vector canvas       |
+-----------------------+---------------------------------------------+---------------------------------------------+
```

---

## 2. Phase-by-Phase Offline Verification Rubrics (Phase 0 to Phase 5)

### Phase 0: Local Infrastructure, Container Stack & Microservice Isolation
* **Objective**: Establish 100% local persistence, messaging, routing, and sibling module execution without cloud databases.
* **Verification Rubric**:
  - [ ] **R0.1 (Docker Containers Healthy)**: `docker compose ps` shows `cfr_postgres` (:5432), `cfr_mosquitto` (:1883/:9001), `cfr_osrm` (:5000), `cfr_tiles` (:8081), `cfr_api` (:8000), and `cfr_ntfy` (:8080) in `healthy` state.
  - [ ] **R0.2 (PostgreSQL Persistence)**: Direct SQL queries verify local tables: `live_calls`, `evaluation_history`, `road_closures`, `parcels`.
  - [ ] **R0.3 (Sibling Import Independence)**: Sibling packages in `/services/*/src` resolve cleanly via `sys.path` injection in `backend/cfr_dispatch/__init__.py` without modifying sibling imports.
  - [ ] **R0.4 (Zero Cloud Database References)**: Codebase scan for legacy Supabase/Firebase connection strings yields zero active operational references.
* **Pass / Fail Criterion**: All 6 local containers healthy; database queries succeed on `localhost:5432`.

---

### Phase 1: Local Audio Ingestion, Dynamic RMS Gating & DSP Harmonic Spotting
* **Objective**: Ingest continuous hardware audio stream, gate noise dynamically, spot dual-tones via FFT, and intercept station PA pages without false alarms.
* **Verification Rubric**:
  - [ ] **R1.1 (Audio Hardware Stream)**: PortAudio stream opens at 16,000 Hz, 1 channel, 1024-sample blocks (`sounddevice.InputStream`).
  - [ ] **R1.2 (Dynamic RMS Noise Gating)**: Rolling baseline `deque(maxlen=50)` adapts to ambient room noise; sustained loudness window requires $\ge 4/5$ chunks above $\max(40, \mu \times 2.5)$.
  - [ ] **R1.3 (5th-Order HPF & Hamming FFT)**: Butterworth filter ($f_c=300\text{ Hz}$) rejects rumble; Hamming windowed FFT resolves dual-tones with minimum 15 Hz spacing.
  - [ ] **R1.4 (Station PA Page Interception)**: Radio broadcast of station PA tone (`595.00 Hz` / `647.00 Hz`) without apparatus tones triggers immediate listener reset with `is_pa_page=True` in `tone_spectral_history.json` (zero false dispatches).
  - [ ] **R1.5 (Multiprocessing Isolation)**: Main audio listening process remains active and latency-free while worker process executes STT and GIS queries.
* **Pass / Fail Criterion**: White noise & station PA pages are rejected; valid apparatus tones trigger dispatch pipeline within 256ms.

---

### Phase 2: Offline Speech-to-Text, CTranslate2 int8 & Two-Phase Slicing
* **Objective**: Transcribe radio dispatch audio offline on CPU in <1.5s, sanitize phonetic ambiguities, and execute two-phase alert slicing.
* **Verification Rubric**:
  - [ ] **R2.1 (Offline CTranslate2 Model Load)**: `get_whisper_model()` instantiates `faster_whisper.WhisperModel` from `backend/models/whisper-base-cfr-ct2/` with `device="cpu"` and `compute_type="int8"` with WAN disconnected.
  - [ ] **R2.2 (Two-Phase Slicing Latency)**:
    - *Phase 1*: Broadcasts preliminary address & units within 15s of audio onset ($1.2\text{s} - 3.5\text{s}$ compute latency).
    - *Phase 2*: Transcribes complete audio upon $\ge 3.0\text{s}$ silence, saves `.wav` archive, and patches database.
  - [ ] **R2.3 (Phonetic Homophone Sanitizer)**: Verified mappings: `won`/`juan` -> `1`, `ancient`/`agent` -> `engine`, `colquitt loom` -> `coquitlam`, `low heat highway` -> `lougheed highway`.
  - [ ] **R2.4 (Double-Round Duplication Safeguard)**: Dispatches $>25\text{s}$ automatically duplicate single-round human labels in `extract_training_data.py`, preventing hallucinated early EOS tokens.
  - [ ] **R2.5 (<35s Cutoff Protection)**: Dispatches $<35.0\text{s}$ default to `include_in_training: false` to prevent dataset poisoning from truncated calls.
* **Pass / Fail Criterion**: Audio transcribes in $<1.5\text{s}$ offline; Phase 1 alert publishes to MQTT topic `cfr/dispatches` in $<15\text{s}$ total elapsed time.

---

### Phase 3: Local In-Memory GIS Geocoding, Shapefile Index & Hydrant Caching
* **Objective**: Match civic addresses against 69k+ municipal records in $<2\text{ms}$ and provide instant hydrant flow intelligence.
* **Verification Rubric**:
  - [ ] **R3.1 ($O(1)$ In-Memory Hash Geocoding)**: `shapefile_loader.py` indexes `Addresses.shp` (69,708 records) into `house_number_index` dictionary. Address lookup completes in $<2\text{ms}$.
  - [ ] **R3.2 (Subaddress & Suite Stripping)**: Unit/suite tokens (`Unit 105`, `Apt 204`) are cleanly stripped from geocoding queries while preserved under `target.subaddress`.
  - [ ] **R3.3 (Campus & Station Overrides)**: Calls to Riverview Hospital (`Station 15`, `Station 37`, `Brookside`, `Centrale`) resolve to `2601 Lougheed Hwy` (`49.245830, -122.805330`).
  - [ ] **R3.4 (Parcel Boundary Polygon Extraction)**: Resolves and exports Option 2 parcel boundary polygon coordinates (`target.rings`) in WGS84 format.
  - [ ] **R3.5 (NFPA 291 Hydrant Client-Side Caching)**: 3,381 Coquitlam hydrants load from local `hydrants.json` (<1MB); client-side Turf.js bounding box filtering updates in $<1\text{ms}$ on map pan/zoom.
  - [ ] **R3.6 (NFPA 291 Flow Color Standards)**: Hydrants render with exact color classes: Class AA ($\ge 1500$ GPM, `#00a8ff`), Class A ($1000-1499$ GPM, `#4cd137`), Class B ($500-999$ GPM, `#e1b12c`), Class C ($< 500$ GPM, `#e84118`).
* **Pass / Fail Criterion**: Geocoding succeeds in $<2\text{ms}$ without internet; hydrants render with NFPA 291 color classes.

---

### Phase 4: Local Containerized OSRM Emergency Routing & Street View Math
* **Objective**: Calculate sub-10ms emergency apparatus routes with momentum preservation and orientation geometry without WAN.
* **Verification Rubric**:
  - [ ] **R4.1 (Local OSRM MLD Execution)**: `EVORoutingEngine` queries containerized OSRM (`http://osrm:5000`) and returns route polylines, duration, and distance in $<10\text{ms}$.
  - [ ] **R4.2 (Apparatus Momentum Preservation)**: Injects `continue_straight=true` query parameter to prevent abrupt heavy vehicle U-turns.
  - [ ] **R4.3 (Station 1 Tactical Corridors)**:
    - *Southbound Apron Offset* (`49.2905, -122.7915`): Injected when `dest_lat < 49.290` to avoid Pinetree Way median loops.
    - *Mariner Way Corridor*: Routes southwest calls via Guildford -> Johnson -> Mariner.
    - *Gordon Ave Corridor*: Directs apparatus via Pinetree Way for EmTrac optical signal preemption.
  - [ ] **R4.4 (Zero-Online Routing Fallback)**: If OSRM container is stopped, engine falls back to straight-line waypoints with road-factor kinematics ($1.25\text{x}-1.45\text{x}$) without throwing runtime exceptions.
  - [ ] **R4.5 (Street View `atan2` Vantage Math & Standby Mode)**: Forward azimuth angle $\theta = \text{atan2}(y, x)$ orients camera toward parcel facade. If WAN is disconnected, UI renders local building footprint canvas.
  - [ ] **R4.6 (Road Closure Spatial Filtering)**: Ray-casting point-in-polygon filters DriveBC/Municipal 511 events against 134 zones with emergency passability classes (`NO_ACCESS`, `ACCESS_ONLY`, `CAUTION`).
* **Pass / Fail Criterion**: Route calculations return valid GeoJSON polylines in $<10\text{ms}$; Station 1 Southbound apron offset is correctly applied.

---

### Phase 5: Kiosk Ergonomics, Component Decomposition & MLOps Backtesting
* **Objective**: Deliver 10-foot bay display ergonomics, modularize `DispatchReview.jsx`, eliminate relative fetch violations, and verify MLOps regression pipelines.
* **Verification Rubric**:
  - [ ] **R5.1 (Rule 1 Relative `fetch()` Remediation)**: Zero relative `fetch('/api/...')` calls in `frontend/src/` (all use `API_BASE_URL` from `apiClient.js`).
  - [ ] **R5.2 (Local Marker Icon Bundling)**: Zero external CDN URLs (`raw.githubusercontent.com`, `cdnjs.cloudflare.com`) in Leaflet icon definitions; all assets served from `dist/icons/`.
  - [ ] **R5.3 (Component Decomposition of `DispatchReview.jsx`)**: 1,602-line monolith decomposed into `frontend/src/components/review/` (`ReviewTable/`, `AudioPlayer/`, `VerificationSidebar/`, `Auth/`, and `ReviewContext`).
  - [ ] **R5.4 (10-Foot Bay HUD Ergonomics)**: 80px touch targets, high-contrast address banner, 5-minute auto-dismiss timer, dual-tone chime on queue, and container-aware map auto-fitting.
  - [ ] **R5.5 (Rapid Reviewer Ergonomics)**: `Ctrl+Space` / `Alt+Enter` system prefill, double-click import, `Ctrl+Enter` submit, `⏪ -5s` jump-back, auto-advance, and auto-audio playback operate seamlessly.
  - [ ] **R5.6 (Dynamic Tile Base URL Resolution)**: Consumes local tiles on port `8081` (`http://${window.location.hostname}:8081`) with `VITE_DISABLE_WAN_FALLBACK=true` suppressing external Carto/OSM calls.
  - [ ] **R5.7 (SMMR & WER Regression Pipeline)**: `backtest_regression.py` and `backtest_parser.py` execute against ground-truth dataset, recording metrics to PostgreSQL `evaluation_history` (Units $\ge 95\%$, Incidents $\ge 85\%$).
  - [ ] **R5.8 (Remote Kiosk Deploy & Build)**: `npm run build` succeeds locally and remotely on `tcfire@100.95.146.94`.
* **Pass / Fail Criterion**: Clean Vite production build; 0 relative fetch violations; 0 external CDN leaks; 100% offline kiosk operation verified.
