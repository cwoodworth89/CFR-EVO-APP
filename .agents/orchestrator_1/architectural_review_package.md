# CFR EVO v1.0.0 — Comprehensive Multi-Perspective Architectural Review Package

**Milestone**: CFR EVO v1.0.0 Feature Freeze, Component Decomposition, Model Tier Cost Allocation & 100% Offline Hardening  
**Date**: 2026-08-14  
**Author**: Project Orchestration Team (Orchestrator, Backend/DSP Specialist, Frontend/Kiosk Specialist, GIS/Routing Specialist, MLOps/STT Specialist)  
**System Integrity Mode**: Development & 100% Offline Emergency Dispatch Kiosk Hardening  

---

## Executive Summary & System Overview

CFR EVO is a 100% local, zero-cloud, containerized emergency dispatch mapping, digital signal processing (DSP), speech-to-text (STT), and tactical navigation platform engineered for fire apparatus bay kiosks and mobile station consoles. The v1.0.0 release establishes complete feature freeze, component decomposition of monolithic modules, strict model tier AI credit allocation, and zero-online-fallback offline verification.

```
+---------------------------------------------------------------------------------------------------------+
|                                    CFR EVO v1.0.0 SYSTEM ARCHITECTURE                                   |
+---------------------------------------------------------------------------------------------------------+
|                                                                                                         |
|   +--------------------------+    PortAudio    +----------------------------------------------------+   |
|   | Physical Radio Receiver  | --------------> | Audio Listener Loop (RMS Noise Floor & Gating)     |   |
|   +--------------------------+                 +----------------------------------------------------+   |
|                                                                  |                                      |
|                                                                  v                                      |
|                                                +----------------------------------------------------+   |
|                                                | 5th-Order HPF + Hamming FFT + Z-Score Spotter      |   |
|                                                | Intercepts PA Tones (595/647 Hz) vs Apparatus Tones|   |
|                                                +----------------------------------------------------+   |
|                                                                  | (Apparatus Tone Detected)            |
|                                                                  v                                      |
|                                                +----------------------------------------------------+   |
|                                                | Multi-Processing Background Worker (Isolated GIL)  |   |
|                                                | Faster-Whisper int8 CPU + LoRA Merged Weights      |   |
|                                                +----------------------------------------------------+   |
|                                                    /                                    \               |
|                                (Phase 1: <15s TTA)/                                      \(Phase 2: End)|
|                                                  v                                        v             |
|                    +-------------------------------------+                +---------------------------+ |
|                    | Preliminary Address & Unit Broadcast|                | Full Audio WAV & Parser   | |
|                    +-------------------------------------+                | Cross-Verification Engine | |
|                                       \                                   +---------------------------+ |
|                                        \                                                /               |
|                                         v                                              v                |
|   +-------------------------------------------------------------------------------------------------+   |
|   |                                LOCAL CONTAINER STACK (Docker Compose)                           |   |
|   |  - FastAPI REST Gateway (:8000)                - PostgreSQL 16 DB (:5432)                       |   |
|   |  - Mosquitto MQTT Broker (:1883 / :9001 WS)    - Local OSRM MLD Routing Engine (:5000)          |   |
|   |  - Ntfy Notification Server (:8080)            - Local Vector & Raster Tile Server (:8081)      |   |
|   +-------------------------------------------------------------------------------------------------+   |
|                                       |                                                |                |
|               (MQTT WebSockets: cfr/dispatches)                  (REST /api/ & Tile Server :8081)       |
|                                       v                                                v                |
|   +-------------------------------------------------------------------------------------------------+   |
|   |                       REACT + VITE FRONTEND (Station Bay Kiosk & Laptop Console)                |   |
|   |  - 10-Foot Bay HUD (High-contrast 70px address, Apparatus ETAs, Tactical Hydrants, Alert Chime) |   |
|   |  - 3-Panel Split View (Route Overview + Micro-Cadastral Parcel + Satellite + Street View atan2) |   |
|   |  - Decomposed Rapid Reviewer (ReviewTable, AudioWaveformPlayer, VerificationSidebar, Shortcuts) |   |
|   +-------------------------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------------------------+
```

---

## 1. Backend & Digital Signal Processing (DSP) Perspective

### 1.1 Core Architecture & Mechanics
1. **Audio Ingestion & Gating**:
   - `sounddevice.InputStream` captures 1-channel, 16,000 Hz, 16-bit PCM in 1024-sample blocks (`backend/cfr_dispatch/audio_listener.py`).
   - Rolling noise floor baseline uses a 50-element deque (`baseline_rms_history`) tracking ambient background sound. Loudness gating requires $\ge 4$ out of 5 consecutive chunks ($\approx 256\text{ ms}$) exceeding $\max(40, \mu_{\text{baseline}} \times 2.5)$ before capturing a 3.5s analysis buffer.
2. **Spectral Tone Discrimination & PA Page Interception**:
   - Audio is filtered through a 5th-order Butterworth high-pass filter ($f_c = 300\text{ Hz}$), windowed with a Hamming window, and transformed via Real FFT.
   - Spectral purity is enforced via Z-score $Z = \frac{\max(|X|) - \mu}{\sigma} \ge 30.0$.
   - **Station PA Golden Fingerprints**: PA System paging tones (`595.00 Hz`, `647.00 Hz`) are intercepted in real-time. If PA tones are detected without matching apparatus wake-tones, the listener immediately resets without recording, logging the event to `data/tone_spectral_history.json`.
   - **Tone Notch Filtering**: Detected tone frequencies are filtered via an IIR notch filter ($Q=50$) before passing audio to speech recognition, preventing acoustic tone interference during Whisper decoding.
3. **Two-Phase Dispatch Slicing**:
   - **Phase 1 (Rapid Alert, TTA < 15s)**: Evaluates audio every 3.0s after reaching 10.0s duration. Checks for semantic completion (unit repetition $\ge 2$ or valid Map Grid 1..134). Transcribes preliminary audio, geocodes address, and pushes an immediate `INSERT` event to PostgreSQL, MQTT, and Ntfy with $1.2\text{s} - 3.5\text{s}$ execution latency.
   - **Phase 2 (Final Verification & Audio Archival)**: Triggered when continuous silence persists for $\ge 3.0\text{s}$. Transcribes complete recording, archives WAV file, cross-verifies Phase 1 vs Phase 2 entities, and executes corrective database patches (`PATCH /api/dispatches/{id}`) and MQTT broadcast updates if discrepancies exist.
4. **Multiprocessing Concurrency Safety**:
   - Hardware audio streaming runs in the main process, while heavy STT transcription and GIS lookups run in an isolated `multiprocessing.Process` (`background_worker_loop`). This eliminates GIL contention and guarantees zero audio buffer overruns or dropped calls.

### 1.2 Identified Edge Cases & Mitigations
- **Radio Squelch Tail Linger**: Squelch bursts can delay silence detection. *Mitigation*: Dynamic noise floor squelch tracking and hard-cap 75s maximum recording timeout.
- **CPU Thread Saturation**: Unconstrained CTranslate2 CPU threads can starve container services. *Mitigation*: Hardcode `cpu_threads = max(1, os.cpu_count() - 1)` in `transcriber.py`.
- **Synchronous HTTP Bias Fetching**: `build_stt_bias_words()` previously fetched `/api/dispatches` synchronously. *Mitigation*: In-memory LRU caching with asynchronous background refresh.

---

## 2. Frontend & Kiosk Ergonomics Perspective

### 2.1 Dual-Mode Layout & Station Ergonomics
1. **Station Bay 10-Foot HUD (`KioskView.jsx`)**:
   - Engineered for 10–25 foot viewing distance across active apparatus bays.
   - **Top 15–20% Alert HUD**: Ultra-bold address heading (`text-4xl` to `text-6xl font-black`), high-contrast incident badges (`🚨 Emergency Code 3` in deep red), apparatus response ETAs (`E1 : 02:30`, `L1 : 03:45`), nearest City and Private hydrants (`💧 D-163 (42m)`), and 5-minute dismiss timer.
   - **Main 80–85% Viewport**: 2/3 primary Route Overview map paired with a 1/3 3-panel stack (Block/Parcel polygon, High-Resolution Satellite, and Street View facade).
   - **Autonomous Lifecycle**: Auto-activates on incoming MQTT events, plays dual-tone queue chime (`587Hz -> 880Hz`) for secondary dispatches, and supports touch dismissal.
2. **Workstation / Laptop Console Client (`DispatchReview.jsx` & `MapBoard.jsx`)**:
   - Optimized for desktop mouse/keyboard interaction, split-screen GIS exploration, and rapid human-in-the-loop (HITL) dispatch review.

### 2.2 Monolith Decomposition: `DispatchReview.jsx` (1,602 lines)
`DispatchReview.jsx` is decomposed into modular sub-packages under `frontend/src/components/review/`:
- `ReviewContext.jsx` & `useReviewState.js`: Shared state machine managing call queue, selection, filters, and mutations.
- `useKeyboardShortcuts.js`: Global shortcut controller (`Ctrl+Space`, `Alt+Enter`, `Ctrl+Enter`).
- `table/`: `DispatchTable.jsx`, `DispatchRow.jsx`, `TableFilterBar.jsx`, `ToneBadgeGroup.jsx`.
- `player/`: `AudioWaveformPlayer.jsx` (HTML5 player, `⏪ -5s` quick jump, auto-play settlement).
- `verification/`: `VerificationSidebar.jsx`, `GroundTruthForm.jsx`, `MetadataFields.jsx`, `PipelineExecutionTimeline.jsx`, `QualityRatingBar.jsx`, `WhisperTrainingOptIn.jsx` (with `<35s` cutoff safeguard).
- `auth/`: `AdminLoginModal.jsx`.

### 2.3 Identified Defects & Remediations
1. **Rule 1 (`GEMINI.md`) Relative `fetch()` Violations**:
   - `MapBoard.jsx:678` (`fetch("/api/road-closures")`) and `SystemMetricsPanel.jsx:22` (`fetch("/api/metrics/summary")`) violate remote kiosk URL resolution.
   - *Fix*: Replace with `fetch(`${API_BASE_URL}/api/...`)`.
2. **External CDN Marker Leaks**:
   - `RouteOverviewPanel.jsx`, `BlockParcelPanel.jsx`, and `PropertySatellitePanel.jsx` referenced external GitHub/CDN icons (`raw.githubusercontent.com`, `cdnjs.cloudflare.com`).
   - *Fix*: Bundle all Leaflet marker icons and shadows locally in `frontend/public/icons/`.
3. **Offline Dynamic MapServer Layers**:
   - `MapLayers.jsx` referenced `geodata.coquitlam.ca` ArcGIS MapServers.
   - *Fix*: Provide local GeoJSON vector layer fallbacks (`zones.json`, `coquitlam_city_boundary.json`) when offline.

---

## 3. GIS, Master Properties & Emergency Routing Perspective

### 3.1 Local Data Authority & Spatial Indexing
1. **High-Speed In-Memory Geocoding**:
   - Ingests `Addresses.shp` (69,708 records) into an in-memory hash dictionary `house_number_index` (`dict[str, list[dict]]`), reducing geocode lookups from ~100ms to $<2\text{ms}$ ($O(1)$ complexity).
   - Subaddress parser strips unit/suite tokens (`Unit 105`, `Apt 204`) for clean shapefile matching while preserving `target.subaddress`.
   - **Station Overrides**: Hardcoded overrides handle complex campuses (Riverview Hospital cottages -> `2601 Lougheed Hwy`, Station 15/37 -> `49.245830, -122.805330`, 3080 Gordon -> 3030 Gordon).
   - Extracts Option 2 parcel boundary polygon rings (`target.rings`) for cadastre visualization.
2. **Hydrant Spatial Caching & NFPA 291 Standards**:
   - 3,381 Coquitlam hydrants cached in serialized compact JSON (`hydrants.json`, $<1\text{MB}$).
   - Turf.js client-side bounding box filtering with 25% viewport buffer renders markers in $<1\text{ms}$ on pan/zoom.
   - NFPA 291 color coding: Class AA ($\ge 1500$ GPM, `#00a8ff`), Class A ($1000-1499$ GPM, `#4cd137`), Class B ($500-999$ GPM, `#e1b12c`), Class C ($< 500$ GPM, `#e84118`).
   - Tactical selector extracts top 3 on-route hydrants within 300m radius and 25m route proximity.
3. **Containerized OSRM Routing & Tactical Corridors**:
   - Local OSRM MLD container on port 5000 provides sub-10ms route calculations with `continue_straight=true` momentum preservation.
   - **Station 1 Tactical Corridors**:
     - *Southbound Apron Offset* (`49.2905, -122.7915`): Prevents illegal/impossible U-turns over the Pinetree Way concrete median.
     - *Mariner Way Corridor*: Injects Guildford Way -> Johnson St -> Mariner Way waypoints for southwest quadrant dispatches, avoiding Lougheed barrier islands.
     - *Gordon Ave Corridor*: Directs apparatus via Pinetree Way for rolling-green optical signal preemption (EmTrac).
   - 3-tier apparatus speed physics (Light 52 km/h, Standard 45 km/h, Heavy 38 km/h) with turn penalties and hill-climb drag adjustments.
4. **Street View Vantage Math & Cadastre Persistence**:
   - Forward azimuth angle $\theta = \text{atan2}(y, x)$ calculates exact camera heading from street frontage to building facade centroid.
   - Drag-sync listener updates `parcels` table in PostgreSQL (`streetview_heading`, `streetview_pitch`, `front_lat`, `front_lng`, `lock_box_notes`).
   - Offline standby mode renders local vector building footprint canvas when WAN is disconnected.
5. **Road Closure & Hazard Ingestion**:
   - Ingests DriveBC Open511 and Municipal 511 feeds with ray-casting point-in-polygon filtering against 134 emergency zones.
   - Categorizes passability (`NO_ACCESS`, `ACCESS_ONLY`, `CAUTION`) with automated 30-day purge cycles.

---

## 4. MLOps & Whisper Speech-to-Text Perspective

### 4.1 Model Architecture, Fine-Tuning & Quantization
1. **LoRA Fine-Tuning & CTranslate2 int8 Quantization**:
   - Fine-tunes `openai/whisper-base` using PEFT LoRA ($r=32$, $\alpha=64$, target modules `q_proj`, `v_proj`, dropout $0.05$).
   - Merges LoRA adapters (`merge_and_unload()`) and converts to CTranslate2 `int8` quantization (`faster-whisper`).
   - Achieves $<1.5\text{s}$ CPU inference latency on station kiosk hardware with ~180MB RAM footprint.
2. **Dataset Curation & Audio Alignment**:
   - `extract_training_data.py` extracts verified dispatches (`feedback_submitted: true`).
   - **<35s Cut-Off Filter**: Automatically excludes cut-off dispatches to prevent training on truncated audio.
   - **Double-Round Duplication**: For full double-round broadcasts ($>25\text{s}$), single-round human labels are duplicated (`normalized_text = f"{text} {text}"`) to teach Whisper exact timeline alignment and eliminate hallucinated early termination tokens.
   - `learn_new_incident_types()` dynamically updates `call_types.txt` with verified categories.
   - Sync flag updates PostgreSQL `live_calls` setting `model_updated = true`.
3. **Benchmarking, SMMR & Telemetry**:
   - `backtest_regression.py` and `backtest_parser.py` calculate symmetric Levenshtein WER/CER and Structured Metadata Match Rate (SMMR) across 5 core dispatch entities.
   - Evaluates: Units (97.5%), Incident (88.9%), Grid (75.3%), Address (67.9%), Talk Group (59.3%).
   - Inserts evaluation runs into local PostgreSQL `evaluation_history` table for dashboard graphing.
4. **Triple-Layer Phonetic & Spatial Hardening**:
   - *Pre-decoding*: Dynamic CAD prompt biasing & hotword weighting (`bias_prompt.py`).
   - *Post-decoding*: Regex phonetic homophone sanitization (`sanitize_transcript()` in `parser.py` maps `won`/`juan` -> `1`, `ancient`/`agent` -> `engine`, `colquitt loom` -> `coquitlam`, `low heat highway` -> `lougheed highway`).
   - *Post-parsing*: Spatial-phonetic 1..134 map grid zone validation (`gis_service.geocoder`).
5. **Zero-Cost Colab GPU Workflow**:
   - Connects station kiosk training cache via `rclone` to Google Colab T4 GPU (`docs/cfr_whisper_colab_fine_tuning.ipynb`) for zero-cost fine-tuning and CTranslate2 export.

---

## 5. Architectural Synthesis & Cross-Domain Validation Matrix

| Domain Pillar | Core Asset / Module | Key Operational Guarantee | Failure Mode | Offline Resilience Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Backend / DSP** | `audio_listener.py`, `dsp_tone_spotter.py` | Sub-15s Phase 1 alert; 0 false PA page recordings | Audio buffer overflow | Multiprocessing core isolation; RMS dynamic floor |
| **Frontend / UI** | `KioskView.jsx`, `DispatchReview.jsx` | 10-ft bay HUD ergonomics; rapid keyboard review | Relative fetch 404 / CDN leak | `API_BASE_URL` enforcement; local icon bundling |
| **GIS / Routing** | `geocoder.py`, `routing_engine.py` | $<2\text{ms}$ $O(1)$ geocoding; sub-10ms OSRM routing | Corrupted city server | In-memory shapefile hash; local OSRM container |
| **MLOps / STT** | `transcriber.py`, `train_whisper_lora.py` | $<1.5\text{s}$ CPU STT; 97.5% unit extraction | Acoustic hallucination | CTranslate2 int8; double-round label duplication |
