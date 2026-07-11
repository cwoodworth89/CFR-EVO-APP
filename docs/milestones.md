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

---

## 🗓️ Future Milestones

### 📺 Milestone 7: Hall Kiosk Touchscreen Mounts
*   **Objective**: Deploy permanent station monitors.
*   **Implementation**: Package the React client into a localized Electron kiosk container running on wall-mounted touchscreen displays inside hall bays, powered by dedicated Raspberry Pi 5 boards.

### 📲 Milestone 8: Shift-Based Apparatus Subscriptions
*   **Objective**: Filter push notifications dynamically.
*   **Implementation**: Build a mobile-friendly onboarding interface where firefighters can subscribe their devices to a specific apparatus (e.g., E1, L1, or R1) on shift startup, receiving alerts only when their assigned vehicle is dispatched.
