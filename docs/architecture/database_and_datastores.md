# CFR EVO: Database & Data Stores Architecture

> [!WARNING]
> **Partially stale 2026-08-30.** Two corrections, both verified:
>
> * **`parcels` is 65,401 rows, not 69,708.** 69,708 is the row count of the source
>   `Addresses.shp`; deduplication by normalized address yields 65,401 unique properties
>   (see `docs/development_freeze_summary.md` and `docs/city_gis_data_register.md`).
>   The figure below labels the pre-deduplication shapefile count as the table count.
> * **`hydrants.json` is no longer a frontend datastore.** The frontend reads
>   `public.hydrants` through the API (moved 2026-08-22). The JSON fetch path it replaced,
>   and the endpoint notes that described it, were retired with `docs/gis_endpoints.md`
>   on 2026-09-04.
>
> The overall store map is otherwise current.

This document catalogs all primary databases, local spatial shapefile stores, and offline storage engines in the **CFR EVO** ecosystem, along with the **Zero Online Fallback** hardening protocol.

---

## 📊 Master Data Stores Map

```mermaid
graph TD
    subgraph PrimaryDB ["1. Primary Relational DB (PostgreSQL 16)"]
        direction TB
        PG[("PostgreSQL 16 (Port 5432)")]
        T1["dispatches (Dispatches, Transcripts, Target JSONB, Reviews)"]
        T2["evaluation_history (WER/CER Metrics, Quality Ratings)"]
        T3["road_closures (Municipal Hazards & Detours)"]
        T4["parcels (69,708 Civic Properties, Units, Pre-computed Zones 1..134, Tactical Pre-Plans)"]
        PG --> T1
        PG --> T2
        PG --> T3
        PG --> T4
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

    subgraph Storage ["4. Persistent Audio & Offline MBTiles Tile Server"]
        direction TB
        A1["backend/audio_files/recordings/ (Raw Dispatch WAV Recordings)"]
        A2["cfr_tiles / mbtileserver (Port 8081, mounted from backend/data/tiles/)"]
        M1["ortho.mbtiles (Z12–Z20 City 7.5cm Aerial Orthophotos)"]
        M2["street.mbtiles (Z12–Z18 Carto Voyager Basemap)"]
        M3["street_nolabels.mbtiles (Z12–Z18 Tactical Grey Basemap)"]
        M4["cadastral.mbtiles (Z14–Z20 Municipal Parcel & Address Overlay)"]
        A2 --> M1
        A2 --> M2
        A2 --> M3
        A2 --> M4
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
| **Address Geocoding** | Local `Addresses.shp` & PostgreSQL `public.parcels` via `/api/parcels/search` | ❌ External ArcGIS REST MapServer queries |
| **Emergency Routing** | Local containerized OSRM graph (Port 5000) | ❌ Google Maps Directions API |
| **Speech-to-Text (STT)** | Local Whisper engine (`backend/models/`) | ❌ Google Cloud STT API |
| **Map Basemaps & Imagery** | Local MBTiles server (`cfr_tiles:8081` - Satellite, Street, Grey) | ❌ Remote Mapbox / OSM CDN tile fetches |
| **Cadastral & Property Overlay** | Local MBTiles server (`cadastral.mbtiles` on `cfr_tiles:8081`) | ❌ External ArcGIS MapServer `/export` queries |

*The only allowed online network calls are the optional visual PiP augmentations (Google Street View panorama & Satellite photo).*

<!-- audit-ok: docs/gis_endpoints.md -- deleted 2026-09-04; the correction above records it -->
