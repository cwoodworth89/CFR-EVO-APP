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
> [!NOTE]
> **Removed in the v1.0.0 freeze** (commit `d5fbdcc`): these training modes and their static JSON quiz datasets were purged as deprecated pre-PostGIS code. Kept here as historical record. Reimplementation as a decoupled, PostGIS-backed module is tracked in [`docs/PROJECT_IDEAS.md`](./PROJECT_IDEAS.md) (#4).

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
*   **Whisper LoRA Fine-Tuning & Local Quantization** — ⚠️ **corrected 2026-09-01.** This entry reported WER falling from 22.6% to 3.5% at 93.3% SMMR on a 51-sample dataset. That figure does not stand and the model it describes never ran: `WHISPER_MODEL` was `base` for all 37 `cfr-agent` starts in the journal, which reaches back to 2026-06-19, a month before the 2026-07-17 training run. The score was measured train-on-test with no held-out split, and under a labelling defect that paired the first 30 s of audio (where `WhisperFeatureExtractor` silently truncates) with a label covering the whole ~48 s double-round call. The converted model was later found as a headless `backend/models/model.bin`, its config and tokenizer gone, and could not have been loaded. Superseded by the round-1 fine-tune below.
*   **Phonetic Homophone Sanitizer**: Configured fallback corrections mapping `won`, `Juan`, `run`, `Agent 1` to `Engine 1` to prevent apparatus drops.

### 🎨 Milestone 8: HUD Streamlining, City Boundary & Map Grid Optimization
*   **Header HUD Redesign**: Streamlined top header layout by removing redundant Kiosk View and Map Options buttons. Promoted center dropdown as single unified mode selector.
*   **Left Control Panel Integration**: Integrated Basemap Style selection (`GREY MAP` / `DARK MAP`), Routing Config modal trigger, Fire Halls toggle, and Closure Timeframe Window filters (`Active Now`, `Next 24h`, `Next 7d`).
*   **Map Legend Resource Alignment**: Replaced generic placeholders with actual resource icons (`fire_hall.png`, `school.svg`, `railroad_crossing.png`, NFPA 291 flow dots).
*   **Subaddress Collapsing Fix**: Updated house number regex test to ensure multi-unit addresses (e.g. `3000 Riverbend Dr`) collapse correctly down to single base address cards.
*   **Official Coquitlam City Boundary**: Generated high-precision 1,597-vertex vector polygon (`coquitlam_boundary_opt.json`) from Coquitlam ArcGIS Cadastral Server Layer 14 (`City Boundary`).
*   **Emergency Response Zones Optimization**: Replaced heavy ArcGIS raster tiles with local vector polygons color-coded by Fire Hall group (Station 1 Crimson `#f43f5e`, Station 2 Royal Blue `#3b82f6`, Station 3 Emerald `#10b981`, Station 4 Purple `#a855f7`). Centered zone numbers using bounding box midpoints (`[(minLat + maxLat)/2, (minLng + maxLng)/2]`) in clean soft charcoal black text (`#0f172a`, `opacity: 0.85`), with automatic `zoom 16` cutoff, `minZoom={12}` constraint, and default-ON startup state.

### ⚡ Milestone 10: 100% Local Station Stack & Reviewer Ergonomics (v2.1.0-local-station-stack)
*   **100% Local Stack & Complete Supabase Cloud Deprecation**: Fully deprecated Supabase cloud services. Dispatches, audio files, and training evaluation metrics persist 100% locally on station hardware via containerized PostgreSQL 16, FastAPI (`:8000`), and Mosquitto MQTT (`:1883`/`:9001`) with zero monthly cloud dependencies.
*   **10x Vector Shapefile Indexing**: Replaced `iterrows()` sequential loop with vector dict mapping (`to_dict('records')`) in `shapefile_loader.py`, cutting GIS service boot-up indexing time by 10x and lowering memory usage by >80%. Serialized compact JSON (`separators=(',', ':')`) cut `hydrants.json` payload size from ~2.5 MB to ~1.0 MB.
*   **Reviewer Ergonomics & Call Flow Sequence**: Re-ordered review input fields in `DispatchReview.jsx` to follow the verbal dispatch call sequence (`Captured Dispatch Tone` $\rightarrow$ `Verified Units` $\rightarrow$ `Verified Incident Type` $\rightarrow$ `Verified Address` $\rightarrow$ `Subaddress` $\rightarrow$ `Talkgroup & Map Grid` $\rightarrow$ `Verified Ground-Truth Transcript`).
*   **Auto-Advance & Audio Auto-Play**: Pressing `Ctrl+Enter` or clicking Submit saves the verification, auto-selects the next dispatch row in the list, resets form scroll to top, and automatically starts playing the new call recording audio.
*   **Simple Audio Jump-Back & Table Filters**: Added lightweight `⏪ -5s` jump-back button, Status filter tabs (`[All]`, `[Needs HITL Review]`, `[Low Confidence]`, `[Fine-Tuned]`), and metadata dropdown filters (Tone & Units).
*   **Project Rule Architecture**: Established `.agents/rules/local_stack_and_dsp_rules.md` documenting DSP tone parameters, STT pipeline controls, WER symmetric evaluation, Tailscale SSH workflows, and server git-ignored file management for cross-agent collaboration.

---

### 🎙️ Whisper Round-1 Fine-Tune — deployed 2026-09-01

Numbered by date rather than sequence: it is the newest completed work, and 11–14 are
already taken by the roadmap below.

*   **The defect it fixes**: `WhisperFeatureExtractor` truncates to 30.0 s in silence
    (`chunk_length` 30 x 16 kHz, verified against installed transformers 5.14.1). Labels
    covered the whole ~48 s double-round call, so ~18 s of every answer key had no audio
    behind it — training the model to keep talking after the audio stops.
*   **The replacement**: pair each clip with the round it actually contains. Both edges
    measured per call: `onset` = timestamp of the first spoken word, always "Coquitlam"
    (operator, SME; 40 of 40 sampled); `boundary` = start of round 2, from `split_rounds`
    run over the timestamped words. Label = round 1 via `split_rounds`. A midpoint formula
    was tried first and retired: median error +0.22 s, but a range of -9.6 s to +20.3 s on
    recordings that were not two clean rounds.
*   **Dataset**: 457 of 497 operator-flagged calls. 34 dropped for exceeding the 30 s
    window — dropped, never truncated — and 6 for not opening with "Coquitlam".
    Split 411 train / 46 held out.
*   **v2 (measured boundary, 2026-09-01) on 44 held-out calls**: WER 23.2% → **5.28%**,
    exact 20/44, against v1's 6.24% on the same set. v1 (midpoint cut) on its own
    46-call holdout: WER **39.7% → 4.9%**,
    CER 34.8% → 3.9%, overall SMMR **93.5%** (units 100%, incident 97.8%, channel 93.5%,
    map grid 91.3%, address 82.6%). 41 improvements, 4 regressions. Gains concentrate in
    street names — `Yieldford Quay` → `guildford way`, `Lowheed` → `Lougheed`.
*   **Deployed**: `WHISPER_MODEL` points at `backend/models/whisper-base-cfr-ct2`;
    `cfr-agent` restarted 2026-09-01 20:46. Loads with the Hugging Face Hub disabled
    entirely, which the first conversion did not — it silently fetched a tokenizer over
    the WAN. Archived off the kiosk with the database dumps.
*   **Design, measurements and rejected alternatives**:
    [`docs/briefings/whisper_training_round1_labelling.md`](./briefings/whisper_training_round1_labelling.md).

## 🗓️ Future Milestones

### 📺 Milestone 11: Hall Kiosk Hardware Mounts

*   **Objective**: Deploy permanent station monitors.
*   **Implementation**: Package the React client into a localized Electron kiosk container running on wall-mounted touchscreen displays inside hall bays, powered by dedicated Raspberry Pi 5 boards.

### 📲 Milestone 12: Shift-Based Apparatus Subscriptions
*   **Objective**: Filter push notifications dynamically.
*   **Implementation**: Build a mobile-friendly onboarding interface where firefighters can subscribe their devices to a specific apparatus (e.g., E1, L1, or R1) on shift startup, receiving alerts only when their assigned vehicle is dispatched.

### 📍 Milestone 13: Call Pin Mode (Incident Map Analytics)
*   **Objective**: Visualize historical dispatch distribution and spatial call density across Coquitlam.
*   **Implementation**: Add an interactive map mode with timeframe filters (`Last 24 Hours`, `Last 7 Days`, `Last 30 Days`, `Last 365 Days`) and color-coded incident category pins (`Medical`, `Alarms`, `MVA`, `Chief Tone Calls`, `Other`).

### 🏢 Milestone 14: Multi-Hall Expansion (Halls 2–4)
*   **Objective**: Roll out the originally-designed 4-station architecture (Hall 1 master + Halls 2–4 slave kiosks) beyond the current single-hall test deployment.
*   **Implementation**: See [`docs/PROJECT_IDEAS.md`](./PROJECT_IDEAS.md) (#5) for scope — per-hall `VITE_DEFAULT_HALL` verification, shared-backend fan-out testing, multi-kiosk deploy workflow, and hardware provisioning.


