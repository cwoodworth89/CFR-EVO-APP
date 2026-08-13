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
  4. **Phonetic & Levenshtein Cross-Street Snap**: Match raw transcribed cross-street words against the preprocessed candidate list using Double Metaphone and fuzzy string matching.
* **Benefits**:
  - Eliminates phonetic ambiguity for misheard cross-streets (e.g. snapping "near Christmas Way" vs "near Cristmas Way").
  - Prevents zone-boundary edge effects by using linear road-geometry buffer overlaps instead of hard polygon borders.
  - $O(1)$ instant execution with zero runtime spatial calculation overhead.
  - Drastically improves overall transcript accuracy even when cross-streets are not explicitly displayed in main UI metadata.

