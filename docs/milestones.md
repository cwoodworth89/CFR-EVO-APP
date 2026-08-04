# Project Milestones & Roadmap

This document outlines the key milestones achieved during the development of CFR-EVO, alongside the planned roadmap for future releases.

---

## 🏆 Completed Milestones

### 📍 Milestone 1: Core Real-Time Dispatch Pipeline
*   **Audio Listening Agent**: Implemented ALSA audio stream capture and continuous passive monitoring in local memory.
*   **Alert Wake-Tones**: Configured offline 2-tone frequency matching to trigger transcription recording automatically.
*   **Speech-to-Text & Parsing**: Integrated Whisper and Google STT API processing to transcribe and parse dispatch text.
*   **Supabase Real-Time Sync**: Configured remote database RLS policies, triggers, and real-time replication to push dispatches instantly to web screens.
*   **React Leaflet Mapping**: Created the frontend dashboard displaying home-station location and OSRM route overlays.

### 🚧 Milestone 2: Live Traffic Hazard & Road Closure Integration
*   **Multi-Feed Aggregation**: Integrated live event feeds from **DriveBC (Open511)** and **Municipal 511**.
*   **CORS Bypass**: Implemented automated CORS proxy fallbacks to fetch and parse dynamic XML/JSON payloads directly from client screens.
*   **Hazard Visual overlays**: Decoded GeoJSON geometries and encoded polyline details to draw barricade icons and highlight affected streets in red.
*   **Passability Filters**: Implemented visual indicators distinguishing Full Closures (`NO_ACCESS`), Emergency Access Only (`ACCESS_ONLY`), and Lane Closures (`CAUTION`).

### 📖 Milestone 3: Local Address Geocoding & Strict Validation
*   **Offline Geocoder**: Swapped dynamic online geocoders with a local offline geocoding index loading 69,708 Coquitlam property points from ESRI Shapefiles.
*   **Dynamic Vocabulary Lists**: Consolidated units, grid numbers, talk groups, response priorities, and street names under `agent/data/vocabulary/` to validate all parsed text against strict ground-truth listings.
*   **Speech Bias Rules**: Added context-aware validation logic to prevent phonetically similar speech errors (e.g. dropping unassigned apparatus types or invalid grids).

### 💧 Milestone 4: Local Hydrant Cache & NFPA 291 Visuals
*   **ArcGIS Spatial Bypass**: Developed local caching to download all 3,381 Coquitlam fire hydrants, protecting the dashboard from the city's corrupted server spatial indexes.
*   **In-Memory Bbox Filters**: Implemented Turf.js client-side filtering to update map markers immediately on pan/zoom in <1ms.
*   **NFPA 291 Color Standards**: Replaced missing MapServer raster tiles with custom Leaflet markers, color-coded by GPM flow ratings (Class AA blue, Class A green, Class B orange, Class C red).
*   **Change-Tracking GIS Update**: Integrated difference logging in the monthly maintenance task to report added, deleted, or updated hydrants automatically.

### 🎓 Milestone 5: Recruits Geographical Simulator
*   **Map Training Games**: Developed 4 interactive training modes to test and score recruits on response coordinates:
    *   *Emergency Zones*: Identify fire station response grid boundaries.
    *   *Street Intersections*: Pinpoint cross-streets on an unmarked map.
    *   *Block Ranges*: Locate individual street blocks.
    *   *Parcel Addresses*: Click the exact lot boundaries corresponding to addresses.
*   **Score Tracking**: Added high-score, timer, and visual feedback states to gamify study reviews.

### ⏱️ Milestone 6: Two-Phase Dispatch Slicing
*   **Objective**: Minimize time-to-alert down to <15 seconds.
*   **Implementation**: Refactored the listening loop to process incoming dispatch announcements in two stages: Phase 1 sends a rapid preliminary geocoded location to the UI/Map within 15 seconds, and Phase 2 uploads the finalized call recording, full transcript, and executes correction verifications after the broadcast finishes.

### 🏢 Milestone 7: Subaddress, Business Name, DSP PA Tone & HITL Corrections Optimization
*   **Subaddress & Business Extractor**: Automatically parses unit numbers (`Unit 105`, `Apt 204`) and business names (`Save-on-Foods`), isolating them under `target.subaddress` while stripping them from geocoding queries for clean shapefile matching.
*   **Riverview Hospital Station Overrides**: Added geocoding overrides for historic Riverview Hospital cottages (`Station 15`, `Station 37`, `Brookside`, `Centrale`) pointing to Riverview grounds (`49.245830, -122.805330`).
*   **DSP PA System Page Interception**: Configured `PA Tone` (`595 Hz` / `647 Hz`) in `GOLDEN_FINGERPRINTS` to intercept station PA pages at the hardware DSP stage, immediately resetting the audio listener without saving or recording non-call pages.
*   **Rapid Review & Keyboard Shortcuts**: Enhanced the dispatch verification panel with `Ctrl` + `Space` and `Alt` + `Enter` hotkeys, double-click input prefilling, and clickable `Sys: [val] 📥` badges to import system-parsed metadata instantly.
*   **Sequential Dispatch Alignment**: Reordered input fields to match verbal dispatch announcements (Units $\rightarrow$ Tone $\rightarrow$ Incident $\rightarrow$ Address $\rightarrow$ Subaddress $\rightarrow$ Talk Group & Map Grid).
*   **Whisper LoRA Fine-Tuning & Local Quantization**: Trained `openai/whisper-base` on local CPUs using the 51-sample station dataset, reducing Word Error Rate (WER) from **22.6% to 3.5%** with **93.3% SMMR overall accuracy**. Merged LoRA adapters and quantized to `int8` (CTranslate2) for high-performance offline CPU execution on the kiosk.
*   **Phonetic Homophone Sanitizer**: Configured fallback corrections mapping `won`, `Juan`, `run`, `Agent 1` to `Engine 1` to prevent apparatus drops.

### 🎨 Milestone 8: HUD Streamlining, City Boundary & Map Grid Optimization
*   **Header HUD Redesign**: Streamlined top header layout by removing redundant Kiosk View and Map Options buttons. Promoted center dropdown as single unified mode selector.
*   **Left Control Panel Integration**: Integrated Basemap Style selection (`GREY MAP` / `DARK MAP`), Routing Config modal trigger, Fire Halls toggle, and Closure Timeframe Window filters (`Active Now`, `Next 24h`, `Next 7d`).
*   **Map Legend Resource Alignment**: Replaced generic placeholders with actual resource icons (`fire_hall.png`, `school.svg`, `railroad_crossing.png`, NFPA 291 flow dots).
*   **Subaddress Collapsing Fix**: Updated house number regex test to ensure multi-unit addresses (e.g. `3000 Riverbend Dr`) collapse correctly down to single base address cards.
*   **Official Coquitlam City Boundary**: Generated high-precision 1,597-vertex vector polygon (`coquitlam_boundary_opt.json`) from Coquitlam ArcGIS Cadastral Server Layer 14 (`City Boundary`).
*   **Emergency Response Zones Optimization**: Replaced heavy ArcGIS raster tiles with local vector polygons color-coded by Fire Hall group (Station 1 Crimson `#f43f5e`, Station 2 Royal Blue `#3b82f6`, Station 3 Emerald `#10b981`, Station 4 Purple `#a855f7`). Centered zone numbers using bounding box midpoints (`[(minLat + maxLat)/2, (minLng + maxLng)/2]`) in clean soft charcoal black text (`#0f172a`, `opacity: 0.85`), with automatic `zoom 16` cutoff, `minZoom={12}` constraint, and default-ON startup state.

### 🖥️ Milestone 9: Containerized Local Stack & Multi-Kiosk Sync (v2.0 Major Revision)
*   **PostgreSQL 16 & FastAPI Gateway**: Replaced cloud Supabase with local containerized PostgreSQL 16 and a FastAPI REST API (`backend/api`), preserving JSONB schema, `live_calls`, `evaluation_history`, and `dispatch_uploads` tables with zero monthly cloud dependencies.
*   **Mosquitto MQTT Real-Time WebSockets**: Replaced cloud Supabase Realtime & `ntfy.sh` with a local Mosquitto MQTT broker (`services/mosquitto`), broadcasting `cfr/dispatches` alerts over TCP `1883` and WebSockets `9001` to all station kiosks simultaneously with sub-millisecond latency.
*   **Master-Slave Multi-Kiosk Topography**: Hall 1 acts as the single Master Server. Kiosks in Halls 2, 3, and 4 connect directly over the station network using IP-agnostic dynamic resolution (`http://${window.location.hostname}:8000` and `ws://${window.location.hostname}:9001`).
*   **Smart Local Audio Sync & Migration**: Created `migrate_supabase_to_local.py` script that scans local `backend/audio_files/recordings/` first, downloads missing audio from Supabase Storage, and rewrites audio URLs to local static paths (`/api/audio/{dispatch_id}.wav`).
*   **Dual-Push Safety Net**: Configured `supabase_sync.py` to push dispatches to local FastAPI first, with optional background cloud backup (`ENABLE_SUPABASE_BACKUP`) for zero-risk cutover.

---

## 🗓️ Future Milestones

### 📺 Milestone 10: Hall Kiosk Hardware Mounts
*   **Objective**: Deploy permanent station monitors.
*   **Implementation**: Package the React client into a localized Electron kiosk container running on wall-mounted touchscreen displays inside hall bays, powered by dedicated Raspberry Pi 5 boards.

### 📲 Milestone 11: Shift-Based Apparatus Subscriptions
*   **Objective**: Filter push notifications dynamically.
*   **Implementation**: Build a mobile-friendly onboarding interface where firefighters can subscribe their devices to a specific apparatus (e.g., E1, L1, or R1) on shift startup, receiving alerts only when their assigned vehicle is dispatched.

