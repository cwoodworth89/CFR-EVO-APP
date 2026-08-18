---
name: gis-pipeline-sync
description: Procedures for updating Coquitlam ESRI shapefiles, caching NFPA 291 fire hydrants, compacting GIS JSON datasets, and verifying 1..134 emergency zone spatial boundaries.
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

## 2. Sync & Compact NFPA 291 Hydrant Cache

Download and serialize Coquitlam's 3,381 fire hydrants into compact JSON:
```powershell
python backend/scripts/sync_hydrants.py
```
* **Serialization Constraint**: Enforce `separators=(',', ':')` in JSON dumping to keep payload under $1.0\text{ MB}$.
* **Color Ratings**: Verify Class AA Blue ($\ge 1500\text{ GPM}$), Class A Green ($1000\text{--}1499$), Class B Orange ($500\text{--}999$), Class C Red ($<500$).

---

## 3. Spatial Boundary Checks

Verify that CAD boundary slicing matches Coquitlam Emergency Response Zones ($1 \le N \le 134$) and ensure `coquitlam_boundary_opt.json` vector points remain within bounds:
* **Lat range**: `49.20` to `49.38`
* **Lng range**: `-122.88` to `-122.70`

---

## 4. MBTiles Packaging & Slippy XYZ Pyramid Pipeline

All offline base layers are packaged into monolithic SQLite MBTiles archives hosted under `backend/data/tiles/` for serving via `cfr_tiles` (port 8081).

### 4.1 Orthophoto Ingestion (7.5cm City of Coquitlam ECW / MrSID / GeoTIFF)
Tiling pipeline generates standard **OpenStreetMap Slippy XYZ** tiles (`EPSG:3857`, top-left origin) across zoom levels **Z12 through Z20**:
```powershell
python backend/scripts/ingest_coquitlam_orthos.py --min-zoom 12 --max-zoom 20 --workers 8
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

---

## 5. Tile Server Health & Offline Verification

Verify that the `cfr_tiles` container serves all base layers with zero WAN requests:
```powershell
curl -s http://localhost:8081/services
```
Expected response contains JSON array of available services (`satellite`, `street`, `street_nolabels`).

Sample tile verification:
```powershell
# Verify Z18 satellite tile for Town Centre Fire Hall (Hall 1)
curl -I -s http://localhost:8081/services/satellite/tiles/18/41984/89445.jpg
```
Expected response: `HTTP/1.1 200 OK`, `Content-Type: image/jpeg`.

