# CFR EVO: Project Ideas & Feature Backlog

This document tracks feature requests, operational enhancements, and future ideas for **CFR EVO**.

---

## 📌 Feature Ideas & Roadmap Backlog

### 1. 📍 Call Pin Mode (Incident Map Analytics)
* **Description**: Interactive historical call map layer displaying pins across Coquitlam for past dispatches, allowing station crews and department leadership to review incident geography, seasonal call volume, and emergency spatial patterns.
* **Timeframe Filters**:
  - ⏱️ `Last 24 Hours`
  - 📅 `Last 7 Days`
  - 🗓️ `Last 30 Days` (Month)
  - 📊 `Last 365 Days` (Year)
* **General Call Type Pin Categorization**:
  - 🚑 **Medical**: Medical Aid, Cardiac, Overdose, Assault, Medical Emergency.
  - 🔔 **Alarms**: Commercial/Residential Fire Alarms, Waterflow, Smoke Detector Activation.
  - 🚗 **MVA**: Motor Vehicle Accidents, Vehicle Entrapments, Highway Collisions, Rollovers.
  - 🚨 **Chief Tone Calls**: Structure Fires, Working Fires, Hazardous Materials, Technical Rescues, Commercial Fires.
  - 📋 **Other**: Public Assistance, Power Lines Down, Burn Complaints, Misc Incidents.
* **Key Features**:
  - **Color-Coded Map Pins**: Distinct visual pins/markers corresponding to each call category on the Leaflet map.
  - **Time-Range Slider / Selector**: Quick toggle buttons for 24h / 7d / Month / Year views.
  - **Category Filtering**: Checkbox toggles to isolate or layer specific call types (e.g. view only MVAs or Chief Tone calls).
  - **Incident Detail Popups**: Click/hover popups displaying call timestamp, unit responses, address, and incident summary.

---

### 2. 🗺️ Cross-Road Spatial-Phonetic Radius Correction & Block-Segmented Preprocessing
* **Description**: Enhance cross-street transcription and extraction accuracy by applying a preprocessed spatial radius filter derived from the primary address block segment.
* **Core Concept**:
  1. **Primary Address Anchor**: Once the primary address is geocoded with high confidence (e.g. `3030 Gordon Ave`), extract its block number (`3000-Block Gordon Ave`) and spatial coordinate $(Lat, Lng)$.
  2. **Block-Segmented Linear Neighbor Map (`spatial_street_index.json`)**:
     - **Short Residential Streets** (e.g. `Sandstone Cres`): Single entry mapping to all nearby intersecting streets.
     - **Long Arterial Corridors** (e.g. `Lougheed Hwy`, `Como Lake Rd`): Divided into linear block buckets (e.g. `LOUGHEED HWY (2000-Block)`, `LOUGHEED HWY (3000-Block)`, `LOUGHEED HWY (4000-Block)`).
     - **Linear Overlap (No Border Edge-Effects)**: Each block segment's spatial buffer overlaps neighboring blocks by ±600ft, ensuring cross-streets right on block or zone boundaries are never missed.
  3. **$O(1)$ Instant Preprocessed Lookup**:
     - At runtime, query `STREET_NEIGHBORS["3000-BLOCK LOUGHEED HWY"]` for zero-latency $O(1)$ retrieval of candidate cross-streets (~10–15 streets).
  4. **Two-Stage Integration (Prompt Weighting & Post-Processing Snapping)**:
     - **Stage 1 (Transcription Biasing)**: Inject candidate block-neighbor street names into Whisper's `initial_prompt` / `hotwords` to weight audio decoding toward correct phonetic spelling.
     - **Stage 2 (Post-Processing Extraction)**: Extract the raw cross-street phrase and fuzzy-match against candidate block-neighbors (Levenshtein / Double Metaphone).
  5. **Safe Pass-Through Fallback (Zero Risk)**:
     - Enforces a strict 75%+ similarity threshold. If no local candidate matches above threshold (or if audio is ambiguous), the engine **safely passes raw text through unchanged**. It will NEVER force an inaccurate match.
* **Benefits**:
  - Eliminates phonetic ambiguity for misheard cross-streets (e.g. snapping "near Christmas Way" vs "near Cristmas Way").
  - Prevents zone-boundary edge effects by using linear road-geometry buffer overlaps instead of hard polygon borders.
  - $O(1)$ instant execution with zero runtime spatial calculation overhead.
  - Safe pass-through fallback ensures zero risk of forced false matches.

---

### 3. 🏷️ Isolated Target Property Address Badge on Satellite PIP View
* **Description**: On the high-resolution 7.5cm Satellite Picture-in-Picture (PIP) and expanded modal views, render an isolated, high-contrast civic address number badge directly centered on the dispatched target parcel polygon (without loading the entire municipal cadastral grid or surrounding street line overlays).
* **Key Concept**:
  - Keep the base aerial orthophoto 100% clean and uncluttered (zero surrounding cadastral lines or neighboring lot numbers).
  - Extract the house number from `activeCall.address` and render a lightweight, glowing Leaflet DivIcon badge (e.g. `📍 428`) centered on the target parcel centroid.
* **Benefits**:
  - Instant target property identification for apparatus operators during nighttime arrival and rooftop/driveway size-up.
  - Preserves maximum visual contrast of high-resolution 7.5cm aerial imagery.

---

### 4. 🎮 Driver Training & Recruit Game Engine (Standalone Module Reimplementation)
* **Description**: Reimplement the original map-quiz training modes (Emergency Zones, Street Intersections, Block Ranges, Parcel Addresses) that were removed from `MapBoard.jsx`/`DashboardHUD.jsx` (commit `d5fbdcc`) during the v1.0.0 feature freeze. The original implementation was purged because it relied on deprecated processes: static pre-extracted JSON quiz datasets (`addresses.json` ~18MB, `blocks.json`, `intersections.json`) built from the old in-memory shapefile pipeline, predating the PostGIS migration.
* **Core Concept**:
  - Rebuild as a **decoupled standalone module** rather than `appMode` branches woven through the live dispatch kiosk components, so training logic can't tangle with real-time dispatch code again.
  - Source quiz data live from PostGIS (`public.zones`, `public.roads`, `public.intersections`, `public.parcels`) instead of static pre-baked JSON snapshots, so it stays in sync with GIS updates automatically.
  - Preserve the 4 original training modes (Zones, Intersections, Blocks, Addresses) with score/feedback/tolerance-based guessing.
* **Benefits**:
  - Keeps recruit map-training available without reintroducing the deprecated data pipeline or the maintenance burden of hand-synced static datasets.
  - Clean separation means training mode can be developed/tested independently of the dispatch HUD without risking regressions there.

---

### 5. 🏢 Multi-Hall Expansion (Halls 2–4 Kiosk Rollout)
* **Description**: CFR EVO currently runs as a single-hall deployment (one test kiosk, `tcfire@100.95.146.94`). The original design (per `README.md`) targets 4 station kiosks (Hall 1 master DB server + Halls 2–4 slave displays) sharing one backend. This entry tracks the feature work needed when expanding beyond the single-hall test setup.
* **Core Concept**:
  - **Hall Identification**: `frontend/.env.local` already supports `VITE_DEFAULT_HALL` per kiosk; verify this cleanly differentiates hall-specific UI/behavior (e.g. home station highlighting, default map center) across multiple simultaneous kiosk instances.
  - **Shared Backend, Multiple Displays**: Confirm FastAPI (`:8000`), MQTT (`:1883`/`:9001`), and the PostGIS database on Hall 1 correctly fan out to Halls 2–4 over the local network/Tailscale without per-hall data drift.
  - **Per-Hall Deployment & Update Workflow**: Extend the current single-kiosk git-pull-and-rebuild workflow to cover multiple physical kiosks (e.g. a deploy script that pulls/rebuilds across all hall IPs rather than just one).
  - **Hardware Provisioning**: Physical kiosk hardware, audio input devices, and network/Tailscale setup for Halls 2–4 (see `docs/hardware_specification.md`, `docs/laptop_kiosk_setup.md`).
* **Benefits**:
  - Realizes the originally designed multi-station architecture once single-hall testing is stable.
  - Scoping this as its own feature effort (rather than assuming it "just works" from the single-hall docs) avoids surprises when Halls 2–4 come online.
