---
name: mbtiles-tile-server
description: Runbook for cfr_tiles, the kiosk's offline tile server (mbtileserver on :8081). The three archives it serves (street_vector, the OpenStreetMap vector basemap; ortho, the aerial imagery; cadastral, the City overlay), how each is built, the read-only volume's journal-mode rule, registering a changed archive, and probes that tell a real tile from a blank. Read before touching an .mbtiles file.
---

# MBTiles Tile Server (`cfr_tiles`)

Every map layer the kiosk draws comes from SQLite MBTiles archives in `backend/data/tiles/`,
served offline by `cfr_tiles`. Where each layer's data comes from and the date of our copy:
[`docs/standards/data_sources.md`](../../../docs/standards/data_sources.md).

---

## 1. What it serves

`cfr_tiles` runs `ghcr.io/consbio/mbtileserver:latest` as `-d /tiles -p 8080`, published on
host port `8081`, with `backend/data/tiles/` mounted read-only at `/tiles`
(`docker-compose.yml`). It registers every `.mbtiles` file in that directory **when it
starts**, under the file's name.

| Service | Archive | Tiles | Zooms | Built by |
|:--|:--|:--|:--|:--|
| `street_vector` | `street_vector.mbtiles`, 40 MB | Vector PBF, gzip, OpenMapTiles schema 3.16.0 | z0–14, drawn at any zoom | `backend/scripts/build_vector_basemap.sh` (§5.1) |
| `ortho` | `ortho.mbtiles`, 8.1 GB | JPEG | z12–20 | Nothing in the repo reproduces the served archive (§5.2) |
| `cadastral` | `cadastral.mbtiles`, 1.0 GB | Transparent PNG | z14–20 | `backend/scripts/crawl_cadastral_tiles.py` (§5.3) |

Tiles are at `${TILE_BASE_URL}/services/<service>/tiles/{z}/{x}/{y}.pbf|jpg|png`, TileJSON at
`${TILE_BASE_URL}/services/<service>`, and the list at `/services`.

**Which aerial imagery is served.** The photographs are the City's 2025 7.5 cm capture, but the
archive is the Esri World Imagery crawl of them (511,118 tiles), possibly with City gap tiles, and
it reaches beyond the City at every zoom (punch-list #47b). Its metadata and the map's credit line
(`BASE_LAYERS.SATELLITE` in `frontend/src/components/MapConstants.js`) both say *"served via Esri
World Imagery"*. On 2026-08-31 the operator kept Esri because a crawl of the City's own tiles read
as harsh on the bay display. **Operator ruling 2026-09-15: City imagery is the goal**, and Esri
stays live until a process gives City imagery at a quality he accepts (post-freeze backlog). Do
not re-crawl or swap this archive without the operator's word.

---

## 2. The read-only volume needs journal mode DELETE

> [!IMPORTANT]
> `cfr_tiles` mounts the tiles read-only, and SQLite cannot open an archive left in **WAL**
> mode there (`SQLITE_CANTOPEN: unable to open database file`). Every archive must be in
> `journal_mode = DELETE` before the server sees it.

* `build_vector_basemap.sh` and `crawl_cadastral_tiles.py` convert their own output.
* `compile_mbtiles.py` writes in WAL mode and leaves it. Run
  `python3 backend/scripts/finalize_mbtiles.py` afterwards: it converts every archive in
  `backend/data/tiles/` and exits 1 if any of them fails.

To fix one archive by hand on the kiosk:
```bash
python3 -c "import sqlite3; c = sqlite3.connect('backend/data/tiles/<name>.mbtiles'); c.execute('PRAGMA wal_checkpoint(FULL)'); c.execute('PRAGMA journal_mode = DELETE'); c.close()"
chmod 644 backend/data/tiles/<name>.mbtiles
```
Then register it (§3).

---

## 3. Registering a new, replaced or deleted archive

The server reads its directory only at start, so a changed archive needs a `cfr_tiles`
restart, and **every basemap on every display blanks for a few seconds**. The operator runs
it once `tools/kiosk_capture_state.sh` says SAFE; `.claude/hooks/kiosk_restart_guard.py`
blocks it for Claude Code. On the kiosk, from the repo root:
```bash
bash tools/kiosk_capture_state.sh && docker restart cfr_tiles
```

---

## 4. Health checks

> [!WARNING]
> **GET only.** mbtileserver answers `HEAD` (`curl -I`) with `405 Method Not Allowed`.

```bash
curl -s http://localhost:8081/services
```
Expect exactly `cadastral`, `ortho` and `street_vector`.

**A `200` does not mean the tile exists.** A raster tile the archive does not hold answers
`200 image/png` with a 116-byte blank, even from `ortho`, which stores JPEG. A vector tile
outside the archive answers `204` with no body (both measured 2026-09-15). So check the type
and the size. These probes are the tiles under Hall 1 (`STATIONS` in `MapConstants.js`):

```bash
for p in cadastral/tiles/16/10414/22425.png ortho/tiles/18/41658/89702.jpg street_vector/tiles/14/2603/5606.pbf; do
  curl -s -o /dev/null -w "%{http_code} %{content_type} %{size_download}  $p\n" "http://localhost:8081/services/$p"
done
```

| Probe | Healthy answer, 2026-09-15 |
|:--|:--|
| cadastral z16 | `200 image/png 21489` |
| ortho z18 | `200 image/jpeg 16983` |
| street_vector z14 | `200 application/x-protobuf 81889` |

An `image/png` of 116 bytes from any of them means the archive has no tile there. The sizes change
when an archive is rebuilt, so re-measure after one. Tile numbers for another point, with the
arithmetic the build scripts use:
```bash
python3 -c "import math; lat, lon, z = 49.2911, -122.7907, 16; n = 2**z; print(int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n))"
```

---

## 5. Building each archive

### 5.1 `street_vector`: the OpenStreetMap vector basemap

The street basemap since 2026-09-09, last rebuilt 2026-09-15. `backend/scripts/build_vector_basemap.sh`
builds it on the kiosk in about a minute:

* **Planetiler** runs as a container image pinned by digest (0.10.3-SNAPSHOT, git `9af0823`),
  because the kiosk has no Java. Its OpenMapTiles profile writes z0–14.
* **Inputs**: `EXTRACT`, by default `backend/data/osrm/coquitlam_region.osm.pbf`, Geofabrik's
  British Columbia extract (downloaded 2026-09-09) cut with osmium to the bounds below.
  `BASEMAP_PBF` overrides it, and it must sit under `backend/data`, which the container sees as
  `/data`. The tiles' `osmosisreplicationtime` reads 1970-01-01 for this cut, so date the data by
  the extract, not the tiles. Plus three auxiliary sources in `backend/data/planetiler_sources/`
  (water polygons, Natural Earth, lake centrelines; 1.4 GB) that the script never downloads.
* **Bounds**: tiles are cut to `-123.31,48.99,-122.45,49.52`, the workstation's scroll limits
  with a margin. The app paints land colour only inside the TileJSON bounds, and the "no map
  data" hatch shows outside them (punch-list #40).
* **Safety**: it refuses to run during a capture (`tools/kiosk_capture_state.sh`) or beside an
  OSRM graph build. It writes `street_vector.building.mbtiles`, sets journal mode DELETE and
  the service name, and only then moves it over the live file, so a failed build never
  replaces the served archive. Log: `backend/data/tiles/street_vector.build.log`.
* `--restart-tiles` restarts `cfr_tiles` at the end, which makes it an operator-only command
  (§3).

```bash
backend/scripts/build_vector_basemap.sh    # then the operator registers the archive (§3)
```

**The style, sprite and glyphs are not in the archive.** They are served from the app's own
origin under `/basemap/`:

* `tools/build_basemap_style.py` generates `frontend/public/basemap/street.style.json` from the
  vendored `frontend/public/basemap/upstream/osm-bright.style.json`. The operator's 2026-09-09
  label and POI rulings are written in the generator, so change the generator, not the JSON.
  `python tools/build_basemap_style.py --check` exits 1 when the committed style is stale.
* The sprite is committed. The glyphs (`frontend/public/basemap/fonts/`, Noto Sans, 102 MB) are
  git-ignored and were copied to the kiosk by hand; `npm run build` carries them into
  `frontend/dist/basemap/`.
* `frontend/src/components/map/vectorBasemap.js` fetches the style and the TileJSON and fills
  the style's `{{TILEJSON_URL}}` and `{{ASSETS_URL}}` placeholders.
* `frontend/src/components/MapLayers.jsx` draws it with `L.maplibreGL`
  (`@maplibre/maplibre-gl-leaflet` 0.1.4 over `maplibre-gl` 4.7.1) in Leaflet's `tilePane`, under
  every overlay. Labels are style layers the app shows or hides, not a second tile set. If
  the style or TileJSON fetch fails, nothing is drawn and the hatch stays (CLAUDE.md §6.1).
* Every map carries the credit `© OpenMapTiles · © OpenStreetMap contributors (ODbL)`.
  Licences: [`docs/standards/basemap/README.md`](../../../docs/standards/basemap/README.md).

### 5.2 `ortho`: aerial imagery

The served archive is the Esri crawl (§1). The scripts that fetched it were deleted in `d4a04fc8`,
so the tree cannot rebuild it. `backend/scripts/compile_mbtiles.py --layer ortho` crawls the City's own
`CachedServices/Imagery_2025` cache instead: z12–20 inside the municipal coverage polygon, held
to ~20 requests a second, about 6 hours. Before running it:

* **It resumes.** It skips every tile the archive already holds, so run over today's archive it
  would only fill gaps, and with the City's render. A rebuild goes to a staging directory
  (`--tiles-dir`), is checked there, and is swapped in.
* It calls the City's servers (`docs/external_calls.md` §5), which needs the operator's
  permission (CLAUDE.md §1).

Crawl detail, the z20 limit and the annual refresh: `gis-pipeline-sync` skill §4.1.

### 5.3 `cadastral`: the City overlay

`backend/scripts/crawl_cadastral_tiles.py` renders the City's
`DynamicServices/Cadastral/MapServer/export` with `layers=show:0,1,16` (road labels, address
labels, parcels) into transparent PNGs, z14–20, and resumes like §5.2. `--delay` defaults to
0.05 s, about 20 requests a second (operator decision 2026-08-27), a single ceiling that
`--workers` does not multiply. It calls the City's servers, so the same permission applies.

```bash
python3 backend/scripts/crawl_cadastral_tiles.py    # defaults: z14-20, 0.05 s, 8 workers, backend/data/tiles/cadastral.mbtiles
```

---

## 6. XYZ and TMS rows

MBTiles stores rows bottom-up (TMS), while tile URLs count them top-down (XYZ). The build
scripts write TMS rows and mbtileserver serves XYZ, so nothing in the frontend flips rows.
When you read an archive directly:

$$\text{tile\_row} = (2^{z} - 1) - y$$

```bash
python3 -c "import sqlite3; c = sqlite3.connect('file:backend/data/tiles/cadastral.mbtiles?mode=ro', uri=True); z, x, y = 16, 10414, 22425; print(c.execute('select length(tile_data) from tiles where zoom_level=? and tile_column=? and tile_row=?', (z, x, 2**z - 1 - y)).fetchone())"
```
This returned `(21489,)` on 2026-09-15, the same bytes as the Hall 1 probe in §4.

---

## 7. Frontend contract

1. Every tile and TileJSON URL is built from `TILE_BASE_URL`, imported from
   `frontend/src/apiClient.js`: never a hardcoded `localhost:8081`, never a relative path
   (CLAUDE.md §1).
2. `BASE_LAYERS` in `frontend/src/components/MapConstants.js` is the one definition:
   * `STREET`: `type: 'vector'`, `service: 'street_vector'`, `maxZoom: 22`.
   * `SATELLITE`: `/services/ortho/tiles/{z}/{x}/{y}.jpg`, `maxNativeZoom: 20`, `maxZoom: 22`.
   * `CADASTRAL`: `/services/cadastral/tiles/{z}/{x}/{y}.png`, `maxNativeZoom: 20`,
     `maxZoom: 22`. `CADASTRAL_MIN_ZOOM` (14) comes from the tileset's own metadata.
3. The raster layers carry `fallbackUrl: null`. No CDN sits behind any layer.
