---
name: gis-pipeline-sync
description: Procedures for updating Coquitlam ESRI shapefiles, syncing NFPA 291 fire hydrants into public.hydrants, packaging MBTiles archives, and verifying 1..134 emergency zone spatial boundaries.
---

# GIS Pipeline & Spatial Sync

This skill guides updating Coquitlam municipal spatial datasets, caching fire hydrants, and generating optimized vector assets for the frontend HUD.

---

## 1. Execute Monthly GIS Data Sync

Run the shapefile updater to download and diff municipal parcel and street layers:
```powershell
python backend/scripts/update_gis_data.py
```
* **Inputs**: ESRI shapefiles located in `backend/data/Property_Information/`.
* **Outputs**: Updated `addresses.json` and `blocks.json` in `frontend/public/data/`.

---

## 2. Sync NFPA 291 Hydrants

Hydrants sync from the municipal source into **`public.hydrants`**; the kiosk reads them
from `/api/hydrants`.
```powershell
python backend/scripts/sync_hydrants.py
```

> [!WARNING]
> **Corrected 2026-08-22.** This previously described serializing hydrants into a compact
> JSON cache with a 1 MB payload budget. That cache (`frontend/public/data/hydrants.json`)
> was deleted when hydrants moved to the database. The cache mattered: a code fix alone
> changed nothing while fabricated values lived in a file nobody re-generated.

* **UNRATED IS A VALID STATE, AND THE ONE MOST IMPORTANT TO GET RIGHT.** `flow_class` is
  `NULL` for **853 of 3,390** hydrants -- the municipal source has no rating for them.
  They must render as an explicit unknown (grey, `WARNING: UNRATED`), never as a class.
  `sync_hydrants.py` previously substituted `"AA"`, the *highest* class, telling crews an
  unrated hydrant was the best available water supply. Punch-list #11, CLAUDE.md 6.1.
* **Colour ratings, only where a rating exists**: Class AA Blue (>= 1500 GPM), Class A
  Green (1000-1499), Class B Orange (500-999), Class C Red (< 500). NFPA 291 itself is
  **not held** -- see `docs/standards/README.md`.
* Counts drift as the municipal source updates. Read them from the table rather than
  trusting a number written here.

---

## 3. Spatial Boundary Checks

Verify that CAD boundary slicing matches Coquitlam Emergency Response Zones
($1 \le N \le 134$).

**Use the bounding box in CLAUDE.md §5 — `isWithinCoquitlam(lat, lng)` — as the single
source. Do not restate it here.**

> [!WARNING]
> **Corrected 2026-08-22.** This section previously stated a *narrower* box than CLAUDE.md
> §5: lat `49.20`–`49.38` and lng `-122.88`–`-122.70`, against the canonical
> `lat < 49.20 || lat > 49.39 || lng < -122.92 || lng > -122.70`.
>
> Measured against `public.intersections`: **168 of 1,785 real intersections fall outside
> the box this file used to state and inside the canonical one.** They are the entire
> North Rd / Clarke Rd corridor — the Coquitlam/Burnaby boundary, a major arterial. An
> agent following the old figures would have rejected the western edge of the city as
> out-of-bounds.
>
> This is why a boundary is defined in exactly one place.

---

## 4. MBTiles Packaging & Slippy XYZ Pyramid Pipeline

All offline base layers and property overlays are packaged into monolithic SQLite MBTiles archives hosted under `backend/data/tiles/` for serving via `cfr_tiles` (`ghcr.io/consbio/mbtileserver:latest` on port 8081).

> [!IMPORTANT]
> **SQLite WAL Mode Read-Only Lock Constraint**:
> Because `cfr_tiles` mounts `backend/data/tiles/` as **read-only (`:ro`)**, all scripts compiling `.mbtiles` archives must execute `PRAGMA wal_checkpoint(FULL)` and `PRAGMA journal_mode = DELETE` before closing the database to avoid `SQLITE_CANTOPEN` errors.

### 4.1 Orthophoto Ingestion (7.5cm City of Coquitlam ECW / MrSID / GeoTIFF)
Tiling pipeline generates standard **OpenStreetMap Slippy XYZ** tiles (`EPSG:3857`, top-left origin) across zoom levels **Z12 through Z20**:
```powershell
python backend/scripts/compile_mbtiles.py --layer satellite --workers 32
```
* **Output Archive**: `backend/data/tiles/satellite.mbtiles`
* **Tile Schema**: XYZ Mercator `EPSG:3857` (JPEG format for satellite raster compression).
* **Zoom Depth**:
  - `Z12–Z15`: Coquitlam regional response context
  - `Z16–Z18`: Tactical approach, parcel footprints, street layout
  - `Z19–Z20`: Sub-decimeter structure clarity (roof peaks, building frontages, hydrants)

### 4.2 Vector & Street Basemap MBTiles
* **Street Layer**: `backend/data/tiles/street.mbtiles` (`/services/street/tiles/{z}/{x}/{y}.png`)
* **Dark / Grey No-Labels**: `backend/data/tiles/street_nolabels.mbtiles` (`/services/street_nolabels/tiles/{z}/{x}/{y}.png`)

### 4.3 Cadastral Property Overlay Pre-Cache
Crawls the authentic municipal ArcGIS DynamicServices Cadastral overlay (`layers=show:0,1,16` — road labels, house address numbers, parcel boundaries) into transparent PNG32 tiles:
```powershell
python backend/scripts/crawl_cadastral_tiles.py --min-zoom 14 --max-zoom 20 --delay 0.2 --workers 8
```
* **Output Archive**: `backend/data/tiles/cadastral.mbtiles`
* **Endpoint**: `http://${hostname}:8081/services/cadastral/tiles/{z}/{x}/{y}.png`

---

## 5. Tile Server Health & Offline Verification

> [!WARNING]
> `mbtileserver` only accepts `GET` and `OPTIONS`. Probing with `HEAD` (`curl -I`) returns `HTTP/1.1 405 Method Not Allowed`. Always probe with `GET`.

Verify that the `cfr_tiles` container serves all 4 services with zero WAN requests:
```powershell
curl -s http://localhost:8081/services
```
Expected response contains JSON array of available services (`satellite`, `street`, `street_nolabels`, `cadastral`).

Sample tile verification (using GET):
```powershell
# Verify Z18 satellite tile for Town Centre Fire Hall (Hall 1)
curl -s -w "%{http_code} %{content_type} (%{size_download} bytes)\n" -o /dev/null http://localhost:8081/services/satellite/tiles/18/41984/89445.jpg

# Verify Z16 Cadastral overlay tile
curl -s -w "%{http_code} %{content_type} (%{size_download} bytes)\n" -o /dev/null http://localhost:8081/services/cadastral/tiles/16/10400/22800.png
```
Expected response: `200 image/jpeg (...) bytes` and `200 image/png (...) bytes`.

For deep troubleshooting, coordinate math, and recovery commands, see [`.agents/skills/mbtiles-tile-server/SKILL.md`](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.agents/skills/mbtiles-tile-server/SKILL.md).


