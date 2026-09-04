# CFR EVO: GIS Endpoints & Offline Migration Notes

> [!CAUTION]
> **Superseded 2026-08-30. The datasets described below are no longer how the app reads GIS data.**
> This file documents a `frontend/public/data/*.json` fetch path that has been replaced by
> PostGIS as the single source of truth (CLAUDE.md §1), served through the API:
>
> * `data/hydrants.json` — the frontend now reads `public.hydrants` via the API.
>   `MapBoard.jsx:138` and `MapLayers.jsx:251` both record the change, and punch-list
>   **#24** (an invented hydrant shown on every dispatch) is why.
> * `data/zones.json`, `data/blocks.json` — `public.zones` / `public.roads`.
> * `data/intersections.json` — described here as feeding "driver training games";
>   training mode was removed entirely at `d5fbdcc`. Intersections are now derived from
>   road geometry into `public.intersections` (punch-list **#9**, **#13**).
>
> The "Dynamic Viewport API (Option A)" roadmap below is not the direction taken.
> **Do not use this file to decide where GIS data comes from.** Read
> [`docs/architecture/database_and_datastores.md`](architecture/database_and_datastores.md)
> and CLAUDE.md §1 instead. Retained for history only.

This document provides a guide to the local GIS datasets currently packaged with the app, their configuration, and the future roadmap for replacing the external municipal servers at `geodata.coquitlam.ca` with local hosting via the **Dynamic Viewport API (Option A)**.

---

## 🗺️ Current Packaged GIS Datasets

The frontend app runs in a local-first capacity by caching spatial databases under `frontend/public/data/`. These files are fetched relative to the application's base URL:

*   **`data/hydrants.json`**: Cached municipal fire hydrants database containing flow rate classification (Class AA/A/B/C), status (Operating/Private/Out-of-Service), ID, and lat/lng coordinates.
*   **`data/zones.json`**: Boundaries and geographic features of 134 emergency response zones mapped to apparatus dispatch groups (Station 1 E1, Station 2 E2, Station 3 E3/Q5, Station 4 E4). Rendered locally using vector polygons with Turf.js bounding box centroid number labels (`zoom 13-15` soft black text `#0f172a`, `zoom 16+` auto-cutoff).
*   **`data/coquitlam_boundary_opt.json`**: High-precision 1,597-vertex vector polygon of the official City of Coquitlam Municipal Boundary, extracted directly from City of Coquitlam ArcGIS Cadastral Server Layer 14 (`City Boundary`).
*   **`data/intersections.json`**: Street intersection coordinate mappings for driver training games.
*   **`data/blocks.json`**: Street segment blocks and address ranges.

---

## 🏛️ Implemented 100% Offline GIS & Cadastral Architecture

All reliance on external servers at `geodata.coquitlam.ca` has been completely eliminated. The system operates 100% offline using a dual-channel architecture:

### 1. Raster Cadastral MBTiles Overlay (cfr_tiles Container on Port 8081)
* **Endpoint**: `http://${window.location.hostname}:8081/services/cadastral/tiles/{z}/{x}/{y}.png`
* **Format**: 32-bit transparent PNG tiles pre-crawled across Zooms 14–20 (`layers=show:0,1,16` — Road Labels, House Address Numbers, Parcels).
* **Serving Container**: `cfr_tiles` (`ghcr.io/consbio/mbtileserver:latest`) mounting `backend/data/tiles/cadastral.mbtiles`.
* **Frontend Component**: [`MapLayers.jsx`](../frontend/src/components/MapLayers.jsx) (`CoquitlamOverlays`) using a standard Leaflet `TileLayer` with `transparent: true`, `opacity: 0.9`, and `fallbackUrl: null`.

### 2. Relational Vector Property & Parcel API (FastAPI on Port 8000)
* **Endpoint**: `GET /api/parcels/bbox?min_lon=...&min_lat=...&max_lon=...&max_lat=...`
* **Database**: Local containerized PostgreSQL 16 (`public.parcels`), holding 65,400+ authoritative municipal parcels ingested from `Cadastral.shp` and `Addresses.shp`.
* **Frontend Integration**: High-performance Leaflet Canvas polygon renderer displaying `#0284c7` boundary lines and crisp municipal typography address labels with transparent backgrounds.

### 3. Autocomplete & Address Geocoding
* **Endpoint**: `GET /api/gis/search?q=<query>`
* **Processing**: Fast local full-text and trigram search across 38,000+ civic addresses with point-in-polygon resolution to Emergency Response Zones 1–134. Zero external network calls.

