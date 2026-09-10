---
name: mbtiles-tile-server
description: Operational runbook and architectural guide for managing the containerized MBTiles server (cfr_tiles on port 8081), compiling SQLite MBTiles archives, and crawling offline map layers.
---

# MBTiles Tile Server & Offline Raster Cache

This skill covers operating the containerized `mbtileserver`, building and crawling SQLite MBTiles archives, resolving Slippy vs. TMS coordinate systems, and troubleshooting offline map rendering for CFR EVO.

---

## 1. Architecture Overview

CFR EVO serves all high-resolution aerial imagery, street basemaps, and municipal cadastral property overlays from a dedicated local container:

* **Container Name**: `cfr_tiles`
* **Image**: `ghcr.io/consbio/mbtileserver:latest`
* **Host Port**: `8081` (maps to internal container port `8080`)
* **Volume Mount**: `backend/data/tiles/` mounted to `/tiles:ro` (read-only)
* **Specification**: Slippy XYZ Web Mercator (`EPSG:3857`), top-left origin `{z}/{x}/{y}`

### Published Services

| Service Name | Archive File | Format | Zoom Levels | URL Endpoint |
|---|---|---|---|---|
| `ortho` | `ortho.mbtiles` | JPEG | Z12–Z20 | `http://${hostname}:8081/services/ortho/tiles/{z}/{x}/{y}.jpg` |
| `street` | `street.mbtiles` | PNG | Z12–Z18 | `http://${hostname}:8081/services/street/tiles/{z}/{x}/{y}.png` |
| `street_nolabels` | `street_nolabels.mbtiles` | PNG | Z12–Z18 | `http://${hostname}:8081/services/street_nolabels/tiles/{z}/{x}/{y}.png` |
| `cadastral` | `cadastral.mbtiles` | PNG32 (Transparent) | Z14–Z20 | `http://${hostname}:8081/services/cadastral/tiles/{z}/{x}/{y}.png` |
| `street_vector` | `street_vector.mbtiles` | PBF vector tiles (OpenMapTiles schema, gzip) | Z0–Z14, drawn to any zoom | `http://${hostname}:8081/services/street_vector/tiles/{z}/{x}/{y}.pbf`; TileJSON at `/services/street_vector` |

---

## 2. Critical SQLite & Docker Volume Constraint

> [!IMPORTANT]
> **SQLite WAL Mode Read-Only Lock Failure**:
> Because `cfr_tiles` mounts `/tiles` as **read-only (`:ro`)**, SQLite cannot open or register an archive if it was left in **WAL (Write-Ahead Logging)** mode (`SQLITE_CANTOPEN: unable to open database file`).
>
> Any script or tool that creates or modifies an `.mbtiles` file **MUST** convert the journal mode to `DELETE` and run a full checkpoint before closing the connection:
> ```python
> cur.execute("PRAGMA wal_checkpoint(FULL);")
> cur.execute("PRAGMA journal_mode = DELETE;")
> conn.commit()
> conn.close()
> ```

### Recovery Command (Fixing Unmounted MBTiles on Kiosk)

If `mbtileserver` logs show `SQLITE_CANTOPEN` for any archive:
```bash
python3 -c "import sqlite3; conn = sqlite3.connect('backend/data/tiles/<name>.mbtiles'); conn.execute('PRAGMA wal_checkpoint(FULL)'); conn.execute('PRAGMA journal_mode = DELETE'); conn.close()"
chmod 644 backend/data/tiles/<name>.mbtiles
docker restart cfr_tiles
```

---

## 3. HTTP Method & Health Verification Rules

> [!WARNING]
> **Never use `curl -I` (HEAD request) against `mbtileserver`**:
> The `mbtileserver` Go server strictly implements `GET` and `OPTIONS`. Probing with `HEAD` (`curl -I`) returns `HTTP/1.1 405 Method Not Allowed`.

### Health Check Commands

List all published services:
```bash
curl -s http://localhost:8081/services
```
Expected output: JSON array containing metadata for `ortho`, `street`, `street_nolabels`, and `cadastral`.

Probe individual tile delivery (using `GET`):
```bash
# Verify Cadastral Z16 tile
curl -s -w "%{http_code} %{content_type} (%{size_download} bytes)\n" -o /dev/null http://localhost:8081/services/cadastral/tiles/16/10400/22800.png

# Verify Satellite Z18 tile
curl -s -w "%{http_code} %{content_type} (%{size_download} bytes)\n" -o /dev/null http://localhost:8081/services/ortho/tiles/18/41984/89445.jpg
```
Expected response: `200 image/png (...) bytes` or `200 image/jpeg (...) bytes`.

---

## 4. Coordinate Math & Schema Standards

### Slippy XYZ vs TMS Coordinates in SQLite

MBTiles specification standardizes on **TMS** (bottom-left origin), whereas Leaflet and web tile endpoints use **Slippy XYZ** (top-left origin).

* **Conversion formula**:
  $$\text{tile\_row} = (2^{\text{zoom}} - 1) - y_{\text{xyz}}$$
* **Web Mercator (EPSG:3857) Bounding Box Calculation**:
  $$\text{origin\_shift} = 20037508.342789244$$
  $$\text{tile\_size} = \frac{2 \times \text{origin\_shift}}{2^{\text{zoom}}}$$
  $$\text{west} = -\text{origin\_shift} + x \times \text{tile\_size}$$
  $$\text{east} = -\text{origin\_shift} + (x + 1) \times \text{tile\_size}$$
  $$\text{north} = \text{origin\_shift} - y \times \text{tile\_size}$$
  $$\text{south} = \text{origin\_shift} - (y + 1) \times \text{tile\_size}$$

---

## 5. Tile Generation & Crawler Runbooks

### 5.1 Cadastral MapServer Crawler (`crawl_cadastral_tiles.py`)

Crawls the authentic City of Coquitlam ArcGIS DynamicServices Cadastral MapServer (`layers=show:0,1,16` — road labels, civic address numbers, parcel boundaries) into transparent PNG32 tiles:

```bash
# Full municipal crawl across Z14–Z20 (resumable)
python3 backend/scripts/crawl_cadastral_tiles.py \
  --min-zoom 14 \
  --max-zoom 20 \
  --delay 0.2 \
  --workers 8 \
  --output backend/data/tiles/cadastral.mbtiles
```

* **Delay**: Default `0.2` ($200\text{ ms}$) provides polite rate-limiting (~5 req/s) against municipal infrastructure.
* **Resumable**: Skips already downloaded `(zoom_level, tile_column, tile_row)` keys present in SQLite.

### 5.0 The street basemap (`build_vector_basemap.sh`)

**Since 2026-09-09 the street basemap is `street_vector.mbtiles`**, vector tiles the project
builds itself from the OSM extract the kiosk routes on (`backend/data/osrm/vancouver.osm.pbf`),
with Planetiler in a pinned container, in about a minute:

```bash
backend/scripts/build_vector_basemap.sh --restart-tiles
```

It reads its three auxiliary sources from `backend/data/planetiler_sources/` (1.4 GB, seeded
once; never downloaded by the script), writes to a temporary name and moves the archive into
place only after the journal-mode check, so a failed build never replaces the served one. The
guard refuses to run over a live capture or beside an OSRM graph build. The frontend draws it
with MapLibre GL under the Leaflet overlays (`frontend/src/components/map/vectorBasemap.js`);
the style, sprite and glyphs are served from the app's own origin under `/basemap/`, the
glyphs (102 MB, git-ignored) copied to the kiosk by hand. A missing vector tile answers
`204 No Content`, not a blank PNG. `street.mbtiles` and `street_nolabels.mbtiles` are no
longer drawn and stay on disk as the rollback. Licences: `docs/standards/basemap/README.md`.

### 5.2 Multi-Layer Compiler (`compile_mbtiles.py`)

Crawls and compiles `ortho.mbtiles` (City imagery service), `street.mbtiles` and `street_nolabels.mbtiles` (Carto). The `gdal2tiles`/MrSID ingest path was removed 2026-08-31 — see `gis-pipeline-sync` §4.1:

```bash
python3 backend/scripts/compile_mbtiles.py --layer all --workers 32
```

---

## 6. Frontend Integration Contract

1. **Base URL Resolution**: All components must import `TILE_BASE_URL` from `frontend/src/apiClient.js`. Never hardcode `localhost:8081`.
2. **Layer Definitions** in `frontend/src/components/MapConstants.js`:
   ```javascript
   export const BASE_LAYERS = {
     STREET: { type: 'vector', service: 'street_vector', attribution: '© OpenMapTiles · © OpenStreetMap contributors (ODbL)', maxZoom: 22 },
     SATELLITE: {
       url: `${TILE_BASE_URL}/services/ortho/tiles/{z}/{x}/{y}.jpg`,
       fallbackUrl: null,
       maxNativeZoom: 20,
       maxZoom: 22,
     },
     CADASTRAL: {
       url: `${TILE_BASE_URL}/services/cadastral/tiles/{z}/{x}/{y}.png`,
       fallbackUrl: null,
       maxNativeZoom: 20,
       maxZoom: 22,
     },
   };
   ```
3. **Offline Fallback Guard**: `fallbackUrl: null` is strictly enforced to prevent external CDN/ArcGIS network leaks during live emergency operations.
