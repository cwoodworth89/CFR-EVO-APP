#!/usr/bin/env bash
# Build the self-hosted street basemap: OpenMapTiles-schema vector tiles from the OSM extract
# the kiosk already routes on, served by cfr_tiles as /services/street_vector.
#
# Replaces the Carto raster crawl (compile_mbtiles.py --layer street*), whose licence the
# project never held and whose tiles Carto began watermarking (punch-list #47b). Licences for
# every input and tool here: docs/standards/basemap/README.md. The trial that sized this:
# docs/briefings/vector_basemap_trial_2026-09-09.md (whole extract: 55 s, 32 MB, 1,251 tiles).
#
# Runs on the kiosk. Planetiler is Java; the kiosk has none, so it runs as the pinned
# container image below. The three auxiliary sources (water polygons, Natural Earth, lake
# centrelines, 1.4 GB) are read from backend/data/planetiler_sources/ and are never
# downloaded by this script -- seed that directory once with `--download` by hand (see the
# external-calls register, section 5) and keep it.
#
# Usage:  backend/scripts/build_vector_basemap.sh [--restart-tiles]
#
#   --restart-tiles   restart the cfr_tiles container afterwards so it registers the new
#                     archive. It reads its directory only at start. The restart blanks every
#                     basemap on every display for a few seconds: say so before running it.
#
# Refuses to run while a dispatch capture is in progress or while an OSRM graph build is
# running (both streams share the kiosk's eight cores; docs/briefs/vector_basemap_agent.md).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# The extract, shared with routing and never replaced here. Since 2026-09-09 it is
# coquitlam_region.osm.pbf, cut from Geofabrik's British Columbia file to the box
# -123.31,48.99,-122.45,49.52 that covers the workstation's scroll limits (OPERATIONAL_BOUNDS)
# with a margin (operator: "fill that with our vector maps"); before that, BBBike's Vancouver
# city extract, whose eastern edge at -122.668 cut the City. BASEMAP_PBF overrides.
EXTRACT="${BASEMAP_PBF:-$REPO/backend/data/osrm/coquitlam_region.osm.pbf}"
# The tiles are cut to this box, not to the extract's header: a clip with complete ways
# keeps whole ways that cross the edge, so the file's nodes reach far past it, and the
# TileJSON bounds (which the app paints the land colour over, punch-list #40) must be the
# box the map can actually scroll, not the stray extent of a boundary way.
BOUNDS="${BASEMAP_BOUNDS:--123.31,48.99,-122.45,49.52}"
SOURCES="$REPO/backend/data/planetiler_sources"
TILES="$REPO/backend/data/tiles"
OUT="$TILES/street_vector.mbtiles"
TMP_OUT="$TILES/street_vector.building.mbtiles"
LOG="$TILES/street_vector.build.log"
WORK="$REPO/backend/data/planetiler_tmp"
# Pinned to the digest that built the 2026-09-09 trial (Planetiler 0.10.3-SNAPSHOT,
# git 9af0823). Change the digest only with a re-measured build.
IMAGE="ghcr.io/onthegomap/planetiler@sha256:db66b104ad08a7cde33ebbb9f371ab0ed2dbe62dc1daeb7a5179709257595e54"

restart=false
for arg in "$@"; do
  case "$arg" in
    --restart-tiles) restart=true ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

for f in "$EXTRACT" "$SOURCES/water-polygons-split-3857.zip" "$SOURCES/natural_earth_vector.sqlite.zip" "$SOURCES/lake_centerline.shp.zip"; do
  [ -f "$f" ] || { echo "missing input: $f" >&2; exit 1; }
done

# Never over a live capture: the state script exits 0 when safe, 1 during a capture or its
# phase 2, 2 when it cannot tell. Run through bash; the file is not marked executable.
state=$(bash "$REPO/tools/kiosk_capture_state.sh") || { echo "not building: $state" >&2; exit 1; }
echo "$state"
# Never beside an OSRM graph build (an osrm-backend container other than the two servers).
if docker ps --format '{{.Names}} {{.Image}}' | grep -v -E '^cfr_osrm(_trial)? ' | grep -q 'osrm-backend'; then
  echo "an OSRM graph build is running; not building" >&2; exit 1
fi

mkdir -p "$WORK"
rm -f "$TMP_OUT"
echo "build started $(date -u +%FT%TZ)" | tee "$LOG"

# --cpu-shares=128: yields to the dispatch agent under contention, the container equivalent
# of nice -n 15. 6 GB cap and a 3 GB heap: the 64 MB extract needed well under 1 GB.
# The output goes to a temporary name so a failed build never replaces the served archive.
docker run --rm --name planetiler_build --user "$(id -u):$(id -g)" \
  --cpu-shares=128 --memory=6g -e JAVA_TOOL_OPTIONS=-Xmx3g \
  -v "$REPO/backend/data:/data" "$IMAGE" \
  --osm_path=/data/osrm/vancouver.osm.pbf \
  --download_dir=/data/planetiler_sources \
  --water_polygons_path=/data/planetiler_sources/water-polygons-split-3857.zip \
  --natural_earth_path=/data/planetiler_sources/natural_earth_vector.sqlite.zip \
  --lake_centerlines_path=/data/planetiler_sources/lake_centerline.shp.zip \
  --tmpdir=/data/planetiler_tmp \
  --output=/data/tiles/street_vector.building.mbtiles \
  --bounds="$BOUNDS" \
  --threads="$(nproc)" --force 2>&1 | sed -e 's/\x1b\[[0-9;]*m//g' | tee -a "$LOG"

# The read-only tiles volume cannot open a WAL-mode archive (mbtiles-tile-server skill, s2).
python3 - "$TMP_OUT" <<'EOF'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
mode = c.execute("PRAGMA journal_mode").fetchone()[0]
if mode.lower() != "delete":
    c.execute("PRAGMA wal_checkpoint(FULL)")
    c.execute("PRAGMA journal_mode = DELETE")
# Planetiler names every archive "OpenMapTiles"; mbtileserver lists services by that name
# while addressing them by file name, so the listing and the URL should agree.
c.execute("update metadata set value = 'street_vector' where name = 'name'")
c.execute("update metadata set value = ? where name = 'description'",
          ("CFR EVO street basemap: OpenMapTiles-schema vector tiles from the routing extract (backend/scripts/build_vector_basemap.sh)",))
c.commit()
meta = dict(c.execute("select name, value from metadata"))
n, size = c.execute("select count(*), sum(length(tile_data)) from tiles").fetchone()
print(f"journal_mode {mode} -> delete; {n} tiles, {size/1e6:.1f} MB payload; bounds {meta.get('bounds')}; z{meta.get('minzoom')}-{meta.get('maxzoom')}")
c.close()
EOF
chmod 644 "$TMP_OUT"
mv -f "$TMP_OUT" "$OUT"
rm -rf "$WORK"
echo "build finished $(date -u +%FT%TZ): $OUT ($(du -h "$OUT" | cut -f1))" | tee -a "$LOG"

if $restart; then
  echo "restarting cfr_tiles so it registers the archive (basemaps blank for a few seconds)"
  (cd "$REPO" && docker compose restart tiles)
  sleep 3
  curl -s http://127.0.0.1:8081/services | python3 -c 'import json,sys; print([s["name"] for s in json.load(sys.stdin)])'
else
  echo "cfr_tiles reads its directory at start: run with --restart-tiles, or 'docker compose restart tiles', when the displays can take a blank moment"
fi
