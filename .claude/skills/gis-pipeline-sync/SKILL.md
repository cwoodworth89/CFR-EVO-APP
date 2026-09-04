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

### 4.1 Orthophoto Crawl (7.5cm City of Coquitlam imagery)

**The City serves its own imagery cache. Crawl that — do not build tiles from the raw
MrSID.** Measured 2026-08-31 on the same ground at z20, edge-energy sharpness:

| Source | Sharpness |
|:--|--:|
| **City `Imagery_2025` service** | **1344** |
| Best possible local build from the raw MrSID | 954 |
| Esri World Imagery | 664 |
| The MrSID-derived archive this replaced | 540 |

The City's own rendering is the sharpest available and needs no resampling from us, so its
tiles are stored exactly as published. The MrSID pipeline that preceded this is retired —
see the deprecation note at the end of this section.

```bash
python backend/scripts/compile_mbtiles.py --layer ortho --workers 8
```

* **Output**: `backend/data/tiles/ortho.mbtiles` → `/services/ortho/tiles/{z}/{x}/{y}.jpg`
* **Source**: `CachedServices/Imagery_2025/MapServer/tile/{z}/{row}/{col}` — a
  `singleFusedMapCache` in EPSG:3857 whose LOD resolutions match the standard Web Mercator
  scheme exactly (verified), so `{z}/{y}/{x}` maps 1:1 onto our grid.
* **Licence**: Open Government Licence – Coquitlam. Attribution:
  `Contains information licensed under the Open Government Licence – Coquitlam.`
* **Scale**: 430,845 tiles over z12–20 within the municipal polygon, roughly 11 GB and
  ~6 hours at the configured rate.

#### z20 is the maximum, and that is not a choice

**`z21` returns HTTP 404 from the City service** — verified at Pinetree, Austin Heights and
Burke Mountain. The service metadata advertises LODs to 23, but only z0–20 are actually
cached; the metadata is aspirational, the same way our own archives once declared bounds
they did not hold (#40).

It also matches the physics. At Coquitlam's latitude:

| Zoom | Ground resolution | vs the 7.5 cm source |
|:--|--:|:--|
| z19 | 19.48 cm/px | 2.6× coarser |
| **z20** | **9.74 cm/px** | 1.30× coarser |
| z21 | 4.87 cm/px | 1.54× **finer than the source** |

Set `maxNativeZoom: 20` and let Leaflet upscale beyond it. **Do not compute ground
resolution as `156543.03 / 2**z` — that is EPSG:3857 units, not metres. Multiply by
`cos(latitude)`.** Omitting that factor is what produced a 22 GB z21 archive holding no more
information than a 6 GB one.

#### Rate limiting is deliberate

`compile_mbtiles.py` runs 32 workers with no pacing against Carto. The `ortho` layer sets
`rate_limit_sec: 0.05` (~20 req/s) because `geodata.coquitlam.ca` is municipal
infrastructure belonging to the department's data partner, not a commercial CDN. Matches the
operator decision of 2026-08-27 for the cadastral crawl.

**The limiter is a hard ceiling that worker count does not multiply** — every request
serialises behind one lock. The 2026-08-27 cadastral crawl ran 8.5 hours pinned at exactly
5 req/s while 8 workers appeared to be running in parallel.

#### The City source is self-limiting, and that is a feature

**The City renders nothing outside its own boundary — requests beyond it return HTTP 404.**
So the ortho layer physically cannot ingest Port Moody, Coquitlam's watershed, Belcarra or
Anmore. The municipal extent is enforced *by the source*, not by our configuration.

That is a real change in where the guarantee lives. Carto and Esri are global: with those,
`filter_tiles_to_city()` and the coverage polygon were the **only** thing stopping the crawl
walking into neighbouring municipalities, and a bug in that filter would have silently pulled
data the department has no claim to. With the City's service, a filter bug just wastes
requests — it cannot over-reach.

Practical consequence, observed on the 2026-08-31 crawl: our coverage polygon carries a ~1 km
mutual-aid buffer, and **13,699 of 430,845 requests 404'd** because that buffer overhangs the
City's imagery. Predicted 14,061 from the service's published `fullExtent`, so the failures
are the self-limiting behaving exactly as designed, not a fault.

The buffer is still correct for `street` (regional context genuinely helps an operator panning
out) but is dead weight for `ortho`. Clipping the ortho tile list to the service `fullExtent`
would remove those wasted requests and about 13 minutes of crawl. Left as-is for now: a
predictable 404 is cheaper than another bespoke bounds constant, and #40 was caused by exactly
that kind of hand-tuned box.

#### Maintenance: crawl the new year, do not diff

The City publishes a **new service per year** — `Imagery_2021` … `Imagery_2025`. Verified
2026-08-31 that these are genuinely distinct captures, not one image relabelled (mean absolute
difference on the same tile: 2021→22 **51.8**, 22→23 **31.2**, 23→24 **37.8**, 24→25 **19.3**).

So the refresh cycle is annual and trivial to detect:

```bash
curl -s 'https://geodata.coquitlam.ca/arcgis/rest/services/CachedServices?f=json'   | grep -o 'Imagery_[0-9]*' | sort -u | tail -3
```

When a new year appears, add it to `LAYER_CONFIGS["ortho"]["url_template"]` and run a fresh
crawl into a staging directory, verify, then swap.

**Do not build a diff step. It cannot save anything.** Detecting which of 430,845 tiles
changed requires a request per tile, which is the entire cost of the crawl — the bytes are
the cheap part, the 20 req/s courtesy ceiling is the expensive part. Conditional requests
(`If-None-Match`) would still be 430,845 round trips and still ~6 hours. A full crawl once a
year is the simpler thing and costs the same.

Within a year, the tiles are static and need no attention at all.

#### Deprecated 2026-08-31: the MrSID pipeline and the Esri layer

Both are **retired**, not merely unused:

* `satellite.mbtiles` (Esri World Imagery) — removed. It was never City data, its terms were
  never read (#47), and the City's own imagery covers the same ground better.
* `ingest_coquitlam_orthos.py`, `precache_satellite_tiles.py` — deleted.
* `Coquitlam_2025_7.5cm.zip` and the MrSID/GDAL warp path — no longer part of any pipeline.
  The raw SID remains a valid archival source, but nothing builds tiles from it.

If you find yourself reaching for `klokantech/gdal` or a `.sid` file to make basemap tiles,
stop: crawl the City service instead.

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
Expected response contains JSON array of available services (`ortho`, `street`, `street_nolabels`, `cadastral`).

Sample tile verification (using GET):
```powershell
# Verify Z18 ortho tile for Town Centre Fire Hall (Hall 1)
curl -s -w "%{http_code} %{content_type} (%{size_download} bytes)\n" -o /dev/null http://localhost:8081/services/ortho/tiles/18/41984/89445.jpg

# Verify Z16 Cadastral overlay tile
curl -s -w "%{http_code} %{content_type} (%{size_download} bytes)\n" -o /dev/null http://localhost:8081/services/cadastral/tiles/16/10400/22800.png
```
Expected response: `200 image/jpeg (...) bytes` and `200 image/png (...) bytes`.

For deep troubleshooting, coordinate math, and recovery commands, see [`.claude/skills/mbtiles-tile-server/SKILL.md`](../mbtiles-tile-server/SKILL.md).


