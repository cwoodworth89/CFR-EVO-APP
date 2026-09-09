# Vector basemap: the first-hour trial, 2026-09-09

**Stream brief**: [`../briefs/vector_basemap_agent.md`](../briefs/vector_basemap_agent.md).
**Licences**: [`../standards/basemap/README.md`](../standards/basemap/README.md), written
before the second hour as the brief required. **Status: a trial, nothing in the app is
touched.** The raster street layers are untouched on disk and still serve the kiosk.

## What was measured

Kiosk at the start: 8 cores, 14.8 GB RAM (12 GB available), 400 GB free, load 1.0, no
capture in progress (`tools/kiosk_capture_state.sh`), OSRM idle. No Java on the kiosk, so
Planetiler ran as its container image (869 MB pull). The trial lives outside the repository
in `/home/tcfire/basemap-trial/` and touches nothing under `backend/data/`.

Two builds from the extract the kiosk already routes on (`vancouver.osm.pbf`, 64 MB,
copied, not moved). Both at Planetiler's default `maxzoom=14`; the client overzooms from
there. Run at `--cpu-shares=128` (yields to anything else under contention, the container
equivalent of `nice -n 15`), 6 GB memory cap, 3 GB heap.

| Build | Bounds | Wall clock | Of which downloads | Tiles | Size |
|:--|:--|--:|--:|--:|--:|
| `coquitlam_z14.mbtiles` | City bbox `-122.92,49.20,-122.70,49.39` (CLAUDE.md §5) | 4 m 03 s | 3 m 16 s (1.4 GB of auxiliary sources, once) | 236 | 6.9 MB |
| `vancouver_z14.mbtiles` | the whole extract, `-123.307,48.999,-122.668,49.416` | 55 s | none (sources cached) | 1,251 | 32 MB |

Per zoom, the full extract: z14 holds 900 tiles, 24 MB, largest tile 216 KB; z13 240
tiles, 5.5 MB; everything below z13 is under 1.5 MB. Journal mode is already `delete`, so
the read-only volume rule in the tile skill needs no fix. OSM pass 1 and 2 take 10 s
together; the extract is small enough that the build is dominated by the one-time download.

The extract's own bounds are the routing coverage, so a basemap built from it shows exactly
what OSRM can route on and nothing it cannot: a useful property the Carto crawl never had.

**tilemaker was not run.** With the build under a minute and the archive under the size of
one raster zoom level, the second candidate has nothing to win on build time or size, and
both are permissive (Planetiler Apache 2.0; tilemaker FTL). Planetiler is the choice on that
evidence. Reopen only if the OpenMapTiles profile turns out to lack a layer the crews need.

## What it looks like

Served beside the raster, not in its place: a second `mbtileserver` container on **:8082**
(`cfr_tiles_trial`, reading the trial's `out/` directory read-only) and an nginx container on
**:8083** (`cfr_static_trial`) serving a scratch MapLibre page, the vendored Positron and
OSM Bright styles, the Noto Sans glyphs and both sprite sheets. Nothing on the page names a
host outside the LAN; every URL is built from `location.hostname`.

Open it from the kiosk itself at `http://127.0.0.1:8083/` or over Tailscale at
`http://100.95.146.94:8083/`. Controls: style, labels on/off, the production cadastral
overlay from :8081, zoom presets, jumps to Hall 1, Hall 3 and Lougheed & Mariner.

Rendered in Chrome over Tailscale on 2026-09-09 and checked at each zoom:

* **z12, z14, z16, z18 at Hall 1**: draws correctly in both styles. Lines at z18 are clean
  from the z14 tiles (Planetiler's default simplification tolerance at max zoom is 1/16 of a
  tile pixel, about 0.6 m at z14, which is under one screen pixel at z18).
* **Labels are a style property.** Switching them off is `visibility: none` on the symbol
  layers, with no tile reload and no basemap swap: the thing the raster could not do
  (2026-09-08 backlog note). With the cadastral overlay on and the basemap's labels off,
  z17 shows the City's parcel lines and road names once, over the vector roads.
* **The western strip** (Hall 3, z18): clean roads and buildings where the raster holds the
  Carto `API KEY REQUIRED` watermark.
* **No-data hatch (#40)**: the style's `background` layer is replaced by a fill over the
  tileset's own TileJSON bounds, and the container's CSS hatch shows outside it. Confirmed at
  the west edge of the city clip at z14: hatch to the west of −122.92, map to the east.
  `mbtileserver` answers a missing vector tile with `204 No Content`, which MapLibre treats
  as empty; nothing paints land where there is no data.
* **Console**: no errors. OSM Bright warns that its published sprite lacks 24 point-of-
  interest icons (`parking_11`, `toilets_11` …). Cosmetic, and a dispatch map will not draw
  POIs anyway.

Positron is the light grey look the crews see today (the raster `street_nolabels` is Carto's
`light_nolabels`, of which Positron is the vector original). OSM Bright colours the arterials
yellow and draws parks green and is easier to read for road hierarchy. Which one, and what
of each, is the operator's call; both start from the same tiles.

## Assumptions, and what would falsify them (CLAUDE.md §7.6)

| Assumption | Cheapest measurement | State |
|:--|:--|:--|
| The kiosk's own browser (snap Chromium 151 on the AMD Renoir iGPU, Wayland) renders MapLibre GL smoothly | Open `http://127.0.0.1:8083/` on the hall display and pan and zoom | **Not measured.** Only Chrome on the workstation, over Tailscale, has rendered it |
| z14 tiles overzoomed to z18 are sharp enough for the SNAP TO CALL view | The z18 render above | Holds on the workstation |
| Leaflet can host MapLibre under the existing overlay panes | `@maplibre/maplibre-gl-leaflet` 0.1.4 declares `leaflet ^1.9.3` and `maplibre-gl ^4.3.2` as peers; the project holds 1.9.4 and 4.7.1 | Declared compatible; not yet run |
| The OpenMapTiles schema carries every road the crews read on the paper map book | Compare `transportation` at z14 against `public.roads` for one zone | Not measured |

## Decisions for the operator

1. **Look at it on the hall display** and say whether it stays: the raster stays on disk
   until then (brief, *Measure before deploying*).
2. **Positron or Bright** as the starting design, or a stated preference for what the crews
   read best. The style becomes the project's own file either way.
3. **Coverage**: the whole extract (32 MB, matches routing) or the City clip (7 MB). The
   whole extract is the recommendation; the routing stream's re-extract would then rebuild
   the map too, which is the right coupling.
4. **The credit line** in `../standards/basemap/README.md`, *Credit line*.

## What is left running on the kiosk

`cfr_tiles_trial` (:8082) and `cfr_static_trial` (:8083), both stoppable with
`docker rm -f` and outside `docker-compose.yml`. `/home/tcfire/basemap-trial/` holds 1.7 GB:
the 1.4 GB of downloaded sources (keep; every rebuild needs them), the two archives, the
static assets and the logs. The production tile server, the compose stack and `cfr-agent`
were not restarted.

## Next

* A build script under `backend/scripts/` with the exact Planetiler invocation, the
  `journal_mode` check and a README row (the tile skill's §5 pattern).
* The project's own style file, derived from whichever design the operator picks, with the
  POI layer off, the cadastral handover at `CADASTRAL_MIN_ZOOM`, and glyphs and sprites
  served from the tile server's host.
* `BaseMap` in `MapLayers.jsx` grows a `vector` layer type beside `tile`, via
  `@maplibre/maplibre-gl-leaflet`, so the overlays do not change. The dead WAN-fallback
  class goes at the same time.
* The Planetiler source download already has its row in `../external_calls.md` §5; the
  script that replaces the by-hand invocation inherits it.
