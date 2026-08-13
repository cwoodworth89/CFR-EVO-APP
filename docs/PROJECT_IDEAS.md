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

### 2. 🗺️ Cross-Road Spatial-Phonetic Radius Correction & Spatial Preprocessing
* **Description**: Enhance cross-street transcription and extraction accuracy by applying a preprocessed spatial radius filter derived from the primary address.
* **Core Concept**:
  1. **Primary Address Anchor**: Once the primary address is geocoded with high confidence (e.g. `3030 Gordon Ave`), extract its spatial coordinate $(Lat, Lng)$.
  2. **1,200ft (~400m) Expanded Spatial Radius**: Uses an expanded **1,200-foot (~400m)** spatial buffer to capture nearby arterial crossroads, block corners, and collector intersections (reducing total search space from ~1,200 Coquitlam streets down to just ~15–25 local candidates—a 98% reduction!).
  3. **$O(1)$ Preprocessed Spatial Neighbor Index (`spatial_street_index.json`)**:
     - **Offline Preprocessing**: Pre-calculate and index nearby streets for every Coquitlam address point / 100m grid cell during shapefile build time (`update_gis_data.py`).
     - **Zero-Latency Runtime**: When a dispatch occurs, perform a $O(1)$ dictionary lookup (`STREET_NEIGHBORS["3030 GORDON AVE"]`) with zero spatial computation latency.
  4. **Phonetic & Levenshtein Cross-Street Snap**: Match raw transcribed cross-street words against the preprocessed local candidate list using Double Metaphone and fuzzy string matching.
* **Benefits**:
  - Eliminates phonetic ambiguity for misheard cross-streets (e.g. snapping "near Christmas Way" vs "near Cristmas Way").
  - $O(1)$ instant execution with zero runtime spatial calculation overhead.
  - Drastically improves overall transcript accuracy even when cross-streets are not explicitly displayed in main UI metadata.

