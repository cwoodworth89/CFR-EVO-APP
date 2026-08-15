# CFR EVO: Database & Data Stores Architecture

This document catalogs all primary databases, local spatial shapefile stores, and offline storage engines in the **CFR EVO** ecosystem, along with the **Zero Online Fallback** hardening protocol.

---

## 📊 Master Data Stores Map

```mermaid
graph TD
    subgraph PrimaryDB ["1. Primary Relational DB (PostgreSQL 16)"]
        direction TB
        PG[("PostgreSQL 16 (Port 5432)")]
        T1["live_calls (Dispatches, Transcripts, Target JSONB, Reviews)"]
        T2["evaluation_history (WER/CER Metrics, Quality Ratings)"]
        T3["road_closures (Municipal Hazards & Detours)"]
        PG --> T1
        PG --> T2
        PG --> T3
    end

    subgraph SpatialData ["2. Spatial Master Datasets (Offline Shapefiles)"]
        direction TB
        S1["Addresses.shp (38,000+ Coquitlam Civic Addresses & Centroids)"]
        S2["Cadastral.shp (Parcel Property Boundary Polygon Rings)"]
        S3["Emergency_Response_Zones.shp (1..134 Fire Grid Zones)"]
        S4["hydrants.json (NFPA 291 Color-Coded Flow Classes)"]
        S5["coquitlam_boundary_opt.json (1,597-vertex City Boundary)"]
    end

    subgraph RoutingGraph ["3. Offline Routing Engine"]
        direction TB
        R1["backend/data/osrm/ (Local OSRM Road Graph & Contraction Hierarchies)"]
    end

    subgraph Storage ["4. Persistent Audio & Offline Map Tiles"]
        direction TB
        A1["backend/audio_files/recordings/ (Raw Dispatch WAV Recordings)"]
        A2["backend/data/tiles/ (Offline MapLibre / PMTiles Basemap)"]
    end

    subgraph Vocabulary ["5. Dispatch Lexicon Dictionaries"]
        direction TB
        V1["street_names.txt (Coquitlam Street Names & Suffix Normalization)"]
        V2["call_types.txt (Standard Incident Types)"]
        V3["unit_names.txt (Apparatus Abbreviations: E1, L1, R1, etc.)"]
    end

    PrimaryDB --> SpatialData
    SpatialData --> RoutingGraph
    RoutingGraph --> Storage
    Storage --> Vocabulary
```

---

## 🚫 Zero Online Fallback Protocol

To guarantee total offline resilience and prevent masked errors, the system enforces **zero online fallbacks**:

| Component | Hardened Offline Engine | Removed Online Fallback |
| :--- | :--- | :--- |
| **Address Geocoding** | Local `Addresses.shp` via `/api/gis/search` | ❌ External ArcGIS REST MapServer queries |
| **Emergency Routing** | Local containerized OSRM graph | ❌ Google Maps Directions API |
| **Speech-to-Text (STT)** | Local Whisper engine (`backend/models/`) | ❌ Google Cloud STT API |
| **Map Basemap** | Local vector tiles (`/tiles/`) | ❌ Remote Mapbox / OSM CDN tile fetches |

*The only allowed online network calls are the optional visual PiP augmentations (Google Street View panorama & Satellite photo).*
