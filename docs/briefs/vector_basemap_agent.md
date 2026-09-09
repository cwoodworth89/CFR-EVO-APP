# Brief: the self-hosted vector basemap

**For a fresh agent, written 2026-09-08.** Read `CLAUDE.md` first, then
[`../review_status_handoff.md`](../review_status_handoff.md). This brief is the scope, the
starting facts, the rules of the road on the shared kiosk, and the boundary with the other
stream running at the same time ([`osrm_routing_agent.md`](osrm_routing_agent.md)).

## What this stream is for

The street basemap is **Carto's raster rendering of OpenStreetMap, crawled and served
offline** from `mbtileserver`. Carto started stamping unauthenticated tiles `API KEY
REQUIRED` between the original crawl and the 2026-08-27 re-crawl (CLAUDE.md §1 caution,
punch-list #47b, closed as accepted risk). About 5,600 watermarked z18 tiles per layer remain
in the western strip, and the street layers stop at z18. The labels-versus-cadastral
handover at z14 has been fought over three times on the raster (the 2026-09-08 revert and
its backlog note explain why a raster fix cannot work: two rendered images cannot share a
label decision).

The replacement: **vector tiles generated from the OSM extract the kiosk already routes on,
rendered on the kiosk by MapLibre GL, with one style the project owns.** Then labels, the
cadastral handover, zoom depth and the licence are all ours:

* Generate `vancouver.osm.pbf` → an MBTiles of vector tiles (Planetiler or tilemaker with
  the OpenMapTiles schema are the two mature routes; pick on evidence: build time on the
  kiosk's 8 cores, output size, and licence).
* Serve it from the existing `mbtileserver` (it serves vector MBTiles as well as raster).
* Render with MapLibre GL JS in Leaflet (`@maplibre/maplibre-gl-leaflet`) or move the map
  surface to MapLibre outright; the first keeps every existing Leaflet layer (zones,
  hydrants, parcels, routes) working and is the smaller step.
* A style that draws roads and names the way the crews read the paper map book, with the
  cadastral overlay taking over names at z14 (the tile server's own metadata: cadastral
  minzoom 14, maxzoom 20).

The aerial basemap is **not** in scope: it is the City's 2025 7.5 cm orthophoto, OGL, served
from `ortho.mbtiles`, and stays.

## Where things are

| | |
|:--|:--|
| Tile server | `tiles` in `docker-compose.yml` (`ghcr.io/consbio/mbtileserver`), port 8081, `./backend/data/tiles:/tiles:ro`; the `mbtiles-tile-server` skill (read-only volume, `PRAGMA journal_mode = DELETE`, `GET`/`OPTIONS` only) |
| Current layers | `street`, `street_nolabels` (Carto raster, z12–18), `cadastral` (City, z14–20), `ortho` (City, to z20) |
| Frontend | `frontend/src/components/MapConstants.js` `BASE_LAYERS` and `CADASTRAL_MIN_ZOOM`; `MapLayers.jsx` `BaseMap` (raster tile layer with a dead WAN fallback class to delete) and `CoquitlamOverlays`; `map/MapSurface.jsx` (the one map both surfaces share) |
| Crawl and compile | `backend/scripts/crawl_cadastral_tiles.py`, `compile_mbtiles.py`, `finalize_mbtiles.py`, `export_tile_coverage.py`, `calc_tile_counts.py`, `inspect_loose_tiles.py` |
| The extract | kiosk `backend/data/osrm/vancouver.osm.pbf` (2026-08-14, git-ignored), shared with routing |
| Architecture | [`../architecture/unified_map_surface.md`](../architecture/unified_map_surface.md); the operator's UX brief [`../ux_notes.md`](../ux_notes.md) §3 and §4 |

## Rules that bind this stream

* **§1**: everything offline. Fonts (glyph PBFs) and sprites for the style are served
  locally too; a MapLibre style that fetches glyphs from a CDN is a WAN dependency and is
  registered in `docs/external_calls.md` only if the operator allows it, which they will not.
* **Licence, in writing, before the first tile is served**: OSM data is ODbL, attribution
  required; the OpenMapTiles schema and any style you start from carry their own licences;
  Planetiler and tilemaker are permissive. Vendor the texts under `docs/standards/` and add
  the row. #47b is the record of what happens when this is skipped.
* **§6.1 in the style**: a zoom with no tile draws the "no map data" hatch (#40), never a
  blank that looks like open ground.
* **Measure before deploying**: tile counts and sizes per zoom (`calc_tile_counts.py`),
  render checks at z12, z14, z16, z18 on the workstation and on a replayed call on the
  kiosk, the operator shown both, and the raster kept on disk until they say the vector map
  stays.
* **The OSM extract is shared** with the routing stream. Generate tiles from it; do not
  replace or re-download it without telling the other agent and the operator.

## The kiosk, shared with another agent

* Deploy by `git pull` on the kiosk. **Never restart `cfr-agent`**; the operator picks the
  moment (`tools/kiosk_capture_state.sh` first, always).
* Tile generation is the heaviest job this project has run on the kiosk: all cores for
  tens of minutes and gigabytes of disk. Run it `nice -n 15`, detached
  (`setsid nohup … &`), announced, never while a capture is running and never while the
  routing stream is rebuilding its graph. Check free disk first (`df -h`); the tiles volume
  holds the 10 GB of raster and ortho archives already.
* The tile server reads its directory at start; a new MBTiles means a `docker compose
  restart tiles`, which blanks every basemap on every kiosk for a few seconds. Announce it.

## Working in parallel

* Own branch and worktree: `git worktree add ../CFR-EVO-APP-basemap -b basemap` from
  `main`. Stage by name, never `git add -A`; another session may be committing.
* Files this stream owns: the `tiles` compose service, `backend/data/tiles/`,
  `BASE_LAYERS` and `CADASTRAL_MIN_ZOOM`, `MapLayers.jsx` `BaseMap` and
  `CoquitlamOverlays`, `MapSurface.jsx`, the crawl and compile scripts, the tile skill.
  Files it must not touch: the `osrm` service, `backend/data/osrm/`, `routing_engine.py`,
  `routing.py`, `RoutingOverlay.jsx`.
* The overlays (zones, hydrants, parcels, routes, road closures) are Leaflet layers with
  `pane` assignments; keeping Leaflet as the container with MapLibre underneath means none
  of them change. Going MapLibre-only means every one of them is rewritten, and that is a
  different, larger project; say which before starting.
* Merge to `main` when the operator has seen the map; small merges, often. Pull `main`
  into the branch daily; the routing stream's merges do not touch the files above.

## First hour

1. On the kiosk: `df -h`, `nproc`, free memory; the tile server's metadata for each layer
   (`curl http://127.0.0.1:8081/services`).
2. A one-zone trial: generate vector tiles for the extract clipped to the City bounding box
   (CLAUDE.md §5) with Planetiler, serve them beside the raster under a new service name,
   and render them in a scratch MapLibre page. Report build time, size and what it looks
   like at z14 and z18 before touching the app.
3. Write the licence rows before the second hour.

<!-- audit-ok: backend/data/osrm/vancouver.osm.pbf -- git-ignored, kiosk only -->
<!-- audit-ok: backend/data/osrm/ -- git-ignored, kiosk only -->
<!-- audit-ok: backend/data/tiles/ -- git-ignored, kiosk only -->
