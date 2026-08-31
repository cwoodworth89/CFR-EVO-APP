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

### 4.1 Orthophoto Ingestion (7.5cm City of Coquitlam MrSID)

> [!CAUTION]
> **`compile_mbtiles.py --layer satellite` does NOT ingest the orthophotos.** It crawls
> **Esri World Imagery** from `server.arcgisonline.com` into `satellite.mbtiles`. Until
> 2026-08-30 this section said otherwise, and as a result the orthos were never ingested at
> all while the UI attributed the layer to the City — every tile in `satellite.mbtiles` was
> measured byte-identical to live Esri. The orthos build a **separate `ortho.mbtiles`**.

**Source**: `/home/tcfire/data_staging/Coquitlam_2025_7.5cm.zip` (9.01 GB) → one MrSID file,
`BCCOQU25-SID-7.5CM.sid` (9.04 GB).

| Property | Value (measured 2026-08-30 via `gdalinfo`) |
|:--|:--|
| Raster size | 279,000 × 216,000 px (60.3 gigapixels) |
| CRS | NAD83 / UTM Zone 10N (EPSG:26910) |
| Pixel size | 0.075 m exactly |
| Extent (WGS84) | −122.8995, 49.2165 → −122.6110, 49.3628 |
| Encoding | MrSID/MG3, GeoExpress 9.5.5 |

The extent fully covers `public.city_boundary` (−122.89343, 49.21987 → −122.62109, 49.35117).

#### The GDAL image matters

**MrSID is a proprietary format.** The official `ghcr.io/osgeo/gdal:ubuntu-full-latest`
image has **no MrSID driver** — verified 2026-08-30, `gdalinfo --formats` returns only the
unrelated NSIDC sea-ice driver. Use **`klokantech/gdal`** (GDAL 2.4.4), which carries the
LizardTech DSDK and also has MBTiles read-write and `gdal2tiles.py`:

```bash
docker run --rm klokantech/gdal gdalinfo --formats | grep -i mrsid
#   MrSID -raster- (rov): Multi-resolution Seamless Image Database (MrSID)
```

#### The pipeline

Four steps, run from `/home/tcfire/data_staging` (see `backend/scripts/ingest_coquitlam_orthos.py`).
Builds into staging and does **not** touch the live tiles directory until verified.

```bash
D=/home/tcfire/data_staging
SID=/data/extracted/BCCOQU25-SID-7.5CM/BCCOQU25-SID-7.5CM.sid
run() { docker run --rm -v $D:/data --memory=10g klokantech/gdal "$@"; }

# 1. Unpack (9.04 GB SID)
unzip -o $D/Coquitlam_2025_7.5cm.zip -d $D/extracted

# 2. Warp UTM 10N -> EPSG:3857 at z21 resolution.
#    -tr is 156543.03392804097 / 2^21; forcing it avoids a second resample in step 3.
#    Output is 430,208 x 334,575 px (144 gigapixels), so COMPRESS=JPEG and BIGTIFF
#    are not optional.
run gdalwarp -t_srs EPSG:3857 -r bilinear     -tr 0.149291068854 0.149291068854     -of GTiff -co TILED=YES -co COMPRESS=JPEG -co PHOTOMETRIC=YCBCR -co BIGTIFF=YES     -multi -wo NUM_THREADS=8 --config GDAL_CACHEMAX 3072     $SID /data/ortho_3857.tif

# 3. Write MBTiles directly -- no TMS directory, no y-flip, no separate compile step.
run gdal_translate -of MBTILES /data/ortho_3857.tif /data/ortho.mbtiles     -co TILE_FORMAT=JPEG -co QUALITY=85 --config GDAL_CACHEMAX 3072

# 4. Overviews ARE the lower zoom levels. Without this the archive is z20 only.
run gdaladdo -r average /data/ortho.mbtiles 2 4 8 16 32 64 128 256 512
```

**Keep `-r bilinear`. Do not "improve" it to lanczos.** 7.5 cm down to z20's 9.7 cm is a
downsample, so the resampling kernel matters. Bilinear and cubic were judged equivalent and
both clearly better than lanczos by the operator on the kiosk display, 2026-08-30 — lanczos
rings on the high-contrast edges that matter here (vehicle outlines, lane markings). An
earlier note in this file recommending lanczos was wrong and is withdrawn.

**Why z21 is the native zoom.** At Coquitlam's latitude z21 is **7.46 cm/px** against the
source's 7.5 cm — a 1.005 ratio, so the warp is effectively pixel-for-pixel and no detail is
resampled away. z20 is 9.74 cm/px, a 1.3× downsample that is visibly softer on vehicle edges
and lane markings at the zoom crews actually use. Operator decision 2026-08-30, after
comparing tiles side by side on the kiosk display.

Cost of z21 over z20: roughly 4× the tiles at the deepest level (~1.4M, ~20 GB) and a
markedly longer build. **Left at z20 the layer is soft; that was the whole reason for
ingesting the orthos rather than staying on Esri, so the extra depth is the point.**

Note this contradicts GDAL's own `ZOOM_LEVEL_STRATEGY=AUTO`, which picks z20 because 7.5 is
numerically nearer 9.74 than 4.87 — that heuristic optimises for tile count, not for keeping
every source pixel. Forcing `-tr` overrides it.

#### Deploy

`gdal_translate` leaves the archive in WAL mode, and `cfr_tiles` mounts
`backend/data/tiles/` read-only, so it **must** be converted before it is moved in
(§4 above, and the finalize step needs `cfr_tiles` stopped — see the tile re-crawl runbook):

`finalize_mbtiles.py` takes **no arguments** — it finalizes every `.mbtiles` in
`backend/data/tiles/`. So the archive must be moved in *first*, and the container must be
stopped *before* both steps: `PRAGMA journal_mode = DELETE` needs an exclusive lock, and
mbtileserver holds the files open. This is the step the 2026-08-27 re-crawl got wrong.

```bash
docker stop cfr_tiles
mv $D/ortho.mbtiles /home/tcfire/CFR-EVO-APP/backend/data/tiles/
/home/tcfire/CFR-EVO-APP/.venv/bin/python     /home/tcfire/CFR-EVO-APP/backend/scripts/finalize_mbtiles.py
docker start cfr_tiles
curl -s http://localhost:8081/services | python3 -m json.tool   # expect an "ortho" entry
```

Confirm every archive reports `Journal Mode: delete` and `Integrity: ok` before starting the
container — a WAL-mode archive fails only later, under the read-only mount.

`mbtileserver` picks up any `.mbtiles` in the mounted directory and names the service after
the filename, so `ortho.mbtiles` is served at `/services/ortho/tiles/{z}/{x}/{y}.jpg` with
no config change.

#### Verifying it is actually the orthos

The failure this whole section exists to prevent is *imagery that looks right but comes from
somewhere else*. Compare a tile against live Esri — if they match byte for byte, you are
looking at Esri, not the City:

```bash
python3 backend/scripts/verify_ortho_provenance.py
```

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


