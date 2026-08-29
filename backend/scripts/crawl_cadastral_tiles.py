#!/usr/bin/env python3
"""
crawl_cadastral_tiles.py
========================
Pre-caches the City of Coquitlam ArcGIS Cadastral MapServer overlay into
a local `cadastral.mbtiles` SQLite archive for 100% offline emergency dispatch mapping.

Features:
- Converts Slippy XYZ tile coordinates to Web Mercator (EPSG:3857) bounding boxes
- Fetches transparent PNG32 tiles for layers [0: Road Labels, 1: Address Labels, 16: Parcels]
- Writes directly to standard MBTiles SQLite format (tiles & metadata tables)
- Uses Slippy XYZ -> TMS coordinate conversion for MBTiles spec compliance
- Multi-threaded worker pool with configurable thread-safe rate-limiting
- Resumable: automatically skips tiles already present in the SQLite archive
- Real-time ETA, throughput (tiles/s), and progress reporting
"""

import os
import sys
import math
import time
import sqlite3
import argparse
import logging
import threading
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any, Optional, Set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("cadastral_crawler")

# Municipal coverage: the extent of public.city_boundary plus a ~1 km buffer,
# matching backend/data/gis/coquitlam_tile_coverage.geojson and compile_mbtiles.py.
#
# The previous values (-122.92 .. -122.72) were hand-picked and stopped 0.1 deg
# short of the eastern city limit at -122.621, so Pinecone Burke and Minnekhada
# had no parcel or address labels at any zoom -- the wildland end of the
# response area. Punch-list #40. Re-derive from the boundary table with
# backend/scripts/export_tile_coverage.py; do not hand-edit.
DEFAULT_MIN_LAT = 49.21087
DEFAULT_MAX_LAT = 49.36017
DEFAULT_MIN_LON = -122.90723
DEFAULT_MAX_LON = -122.60732

# Tiles are additionally tested against the real boundary polygon, because
# Coquitlam is an L wrapped around Port Moody and Port Coquitlam and fills only
# 44.8% of its own bounding box.
COVERAGE_GEOJSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "gis", "coquitlam_tile_coverage.geojson"
)


class CoverageUnavailable(RuntimeError):
    """The municipal coverage polygon could not be loaded. Deliberately fatal.

    There is no bounding-box fallback: it would silently crawl 55% more tiles
    over neighbouring municipalities while reporting success, producing an
    archive wrong in a way nothing downstream could detect. Operator decision
    2026-08-26 -- show an error instead (CLAUDE.md 6.1, punch-list #40).
    """


def load_coverage_filter():
    """Return a predicate(z, x, y) -> bool restricting the crawl to the city.

    Raises CoverageUnavailable rather than degrading to the bounding box.
    """
    try:
        import json as _json
        from shapely.geometry import shape, box as _box
        from shapely.prepared import prep
    except ImportError as exc:
        raise CoverageUnavailable(
            "shapely is required to select tiles by the municipal boundary."
            "\n  Install it:  .venv/bin/pip install shapely"
            "\n  Refusing to fall back to a bounding box -- see punch-list #40."
        ) from exc
    try:
        with open(COVERAGE_GEOJSON, "r", encoding="utf-8") as fh:
            poly = prep(shape(_json.load(fh)["features"][0]["geometry"]))
    except (OSError, KeyError, IndexError, ValueError) as exc:
        raise CoverageUnavailable(
            f"Could not read the coverage polygon at {COVERAGE_GEOJSON}: {exc}"
            "\n  Regenerate it:  python backend/scripts/export_tile_coverage.py"
            "\n  Refusing to fall back to a bounding box -- see punch-list #40."
        ) from exc

    def keep(z: int, x: int, y: int) -> bool:
        n = 1 << z
        w = x / n * 360.0 - 180.0
        e = (x + 1) / n * 360.0 - 180.0
        north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
        south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
        # Intersects, not contains: a tile straddling the line holds real city
        # ground and must be kept.
        return poly.intersects(_box(w, south, e, north))

    logger.info(f"Loaded municipal coverage polygon from {COVERAGE_GEOJSON}")
    return keep


MAPSERVER_EXPORT_URL = (
    "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Cadastral/MapServer/export"
)

USER_AGENT = "CFR-EVO/1.0 (Coquitlam Fire Rescue Offline Cadastral Tile Crawler)"

# EPSG:3857 Web Mercator constants
ORIGIN_SHIFT = 20037508.342789244  # Earth circumference / 2 in Web Mercator meters

# Minimum interval between requests to the City's ArcGIS MapServer, enforced
# globally by RateLimiter below (one lock, so this is a hard ceiling on total
# throughput -- the worker count does NOT multiply it).
#
# 0.05s = ~20 req/s. Operator decision 2026-08-27, chosen deliberately as a
# middle ground rather than removing the limiter:
#
#   * The previous 0.2s (5 req/s) was measured, not guessed, as the cause of an
#     8h35m cadastral crawl -- 153,094 tiles at exactly 5.0 tiles/s, pinned to
#     the ceiling for the entire run. At 0.05s the same crawl is roughly 2h.
#   * It is NOT raised to match compile_mbtiles.py, which runs 32 workers with no
#     limiter at all (~110 tiles/s). That is aimed at Carto and Esri -- commercial
#     CDNs built for request volume. This one hits municipal infrastructure that
#     is likely modest and may be shared with public-facing services, and the City
#     is both the department's data partner and the licensor of this data under
#     the Open Government Licence. Being a bad neighbour here costs more than time.
#
# Raise or lower with --delay for a one-off run; prefer off-hours for a full
# re-crawl. See punch-list #40 and docs/briefings/tile_recrawl_runbook.md.
DEFAULT_DELAY_SEC = 0.05


class RateLimiter:
    """Thread-safe pacing limiter to prevent overwhelming municipal servers."""
    def __init__(self, min_interval_sec: float):
        self.min_interval = max(0.0, min_interval_sec)
        self.lock = threading.Lock()
        self.last_request_time = 0.0

    def wait(self):
        if self.min_interval <= 0:
            return
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()


def deg2num(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    """Convert WGS84 lat/lon to Slippy map tile X, Y coordinates."""
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    x = max(0, min(x, n - 1))
    y = max(0, min(y, n - 1))
    return (x, y)


def tile_to_web_mercator_bbox(z: int, x: int, y: int) -> Tuple[float, float, float, float]:
    """
    Convert Slippy map tile coordinates (z, x, y) to Web Mercator (EPSG:3857) bounding box.
    Returns (west, south, east, north) in Web Mercator meters.
    """
    n = 1 << z
    tile_size = (ORIGIN_SHIFT * 2.0) / n
    west = -ORIGIN_SHIFT + x * tile_size
    east = -ORIGIN_SHIFT + (x + 1) * tile_size
    north = ORIGIN_SHIFT - y * tile_size
    south = ORIGIN_SHIFT - (y + 1) * tile_size
    return (west, south, east, north)


def calculate_tiles(min_lat: float, min_lon: float, max_lat: float, max_lon: float, z: int) -> List[Tuple[int, int, int]]:
    """Calculate all Slippy tile coordinates (z, x, y) for a bounding box at zoom z."""
    x_nw, y_nw = deg2num(max_lat, min_lon, z)
    x_se, y_se = deg2num(min_lat, max_lon, z)
    x_min, x_max = min(x_nw, x_se), max(x_nw, x_se)
    y_min, y_max = min(y_nw, y_se), max(y_nw, y_se)

    tiles = []
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tiles.append((z, x, y))
    return tiles


def init_mbtiles_db(
    db_path: str,
    min_zoom: int,
    max_zoom: int,
    bounds: Tuple[float, float, float, float]
) -> sqlite3.Connection:
    """Initialize an MBTiles SQLite database with metadata and tiles schema."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()

    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA synchronous = NORMAL;")
    cur.execute("PRAGMA cache_size = -64000;")  # 64MB RAM cache

    cur.execute("CREATE TABLE IF NOT EXISTS metadata (name text, value text);")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS tiles ("
        "  zoom_level integer, "
        "  tile_column integer, "
        "  tile_row integer, "
        "  tile_data blob"
        ");"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS tile_index "
        "ON tiles (zoom_level, tile_column, tile_row);"
    )

    west, south, east, north = bounds
    metadata = {
        "name": "cadastral",
        "type": "overlay",
        "version": "1.0",
        "description": "City of Coquitlam ArcGIS Cadastral MapServer Offline Tile Cache (Roads, Addresses, Parcels)",
        "format": "png",
        "bounds": f"{west},{south},{east},{north}",
        "minzoom": str(min_zoom),
        "maxzoom": str(max_zoom),
        "center": f"{(west + east) / 2.0:.5f},{(south + north) / 2.0:.5f},{min_zoom}",
    }
    for k, v in metadata.items():
        cur.execute("INSERT OR REPLACE INTO metadata (name, value) VALUES (?, ?);", (k, v))

    conn.commit()
    return conn


def get_existing_tile_keys(conn: sqlite3.Connection) -> Set[Tuple[int, int, int]]:
    """Return set of existing (zoom_level, tile_column, tile_row) in the MBTiles database."""
    cur = conn.cursor()
    cur.execute("SELECT zoom_level, tile_column, tile_row FROM tiles;")
    return set(cur.fetchall())


def download_cadastral_tile(
    tile: Tuple[int, int, int],
    rate_limiter: RateLimiter,
    layers: str = "show:0,1,16",
    tile_size: str = "256,256",
    max_retries: int = 3
) -> Optional[Tuple[int, int, int, bytes]]:
    """
    Download a single transparent PNG32 tile from ArcGIS Cadastral MapServer.
    Converts Slippy y -> TMS tile_row: tile_row = (1 << z) - 1 - y.
    Returns (z, x, tile_row, tile_data) or None if failed.
    """
    z, x, y = tile
    y_tms = (1 << z) - 1 - y

    west, south, east, north = tile_to_web_mercator_bbox(z, x, y)
    bbox_str = f"{west:.4f},{south:.4f},{east:.4f},{north:.4f}"

    params = {
        "bbox": bbox_str,
        "bboxSR": "3857",
        "imageSR": "3857",
        "size": tile_size,
        "format": "png32",
        "transparent": "true",
        "layers": layers,
        "f": "image"
    }

    url = f"{MAPSERVER_EXPORT_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/png,image/*;q=0.9,*/*;q=0.8"
        }
    )

    for attempt in range(1, max_retries + 1):
        rate_limiter.wait()
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    data = resp.read()
                    # Verify PNG signature (89 50 4E 47 0D 0A 1A 0A) and minimum byte size.
                    #
                    # A BLANK TILE IS A VALID RESULT -- DO NOT FILTER IT OUT.
                    # The MapServer answers any request outside its cadastral extent
                    # with an 885-byte fully transparent PNG (256x256, alpha 0, one
                    # distinct pixel, md5 72accbca6aa1edbf6fec07c32f2df94a). Measured
                    # 2026-08-27: 488,668 of the archive's 606,946 tiles are exactly
                    # that image -- 80.5% of it.
                    #
                    # Blank does NOT mean wrong, and most blanks are INSIDE the city:
                    # at z20 a tile is ~30 m across and parcels render as outlines, so
                    # a tile landing inside a lot, a park or the river has nothing to
                    # draw. Storing them is what lets the tile server answer
                    # "correctly empty" rather than the frontend painting its "no map
                    # data" hatch over real but featureless ground. Discarding blanks
                    # to save space would reintroduce punch-list #40 at the edges.
                    if len(data) >= 50 and data[:8] == b'\x89PNG\r\n\x1a\n':
                        return (z, x, y_tms, data)
                    elif b"error" in data[:200].lower():
                        logger.warning(f"ArcGIS returned an error body for tile {tile}: {data[:120]}")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(1.0 * (2 ** (attempt - 1)))
            else:
                # WARNING, not debug: logging runs at INFO, so a debug line is
                # discarded and the run reports only a failure COUNT with no cause.
                # That cost a re-run with forced DEBUG to identify 8 failures on
                # 2026-08-27 -- the same defect class as punch-list #26.
                logger.warning(f"HTTPError {e.code} for tile {tile} (retries exhausted)")
        except Exception as e:
            if attempt < max_retries:
                time.sleep(0.5 * (2 ** (attempt - 1)))
            else:
                logger.warning(f"Exception fetching tile {tile} (retries exhausted): {e}")

    return None


def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS string."""
    seconds = int(seconds)
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"


def crawl_cadastral(
    output_file: str,
    min_zoom: int = 14,
    max_zoom: int = 20,
    min_lat: float = DEFAULT_MIN_LAT,
    max_lat: float = DEFAULT_MAX_LAT,
    min_lon: float = DEFAULT_MIN_LON,
    max_lon: float = DEFAULT_MAX_LON,
    delay_sec: float = DEFAULT_DELAY_SEC,
    workers: int = 8,
    layers: str = "show:0,1,16",
    tile_size: str = "256,256",
    dry_run: bool = False
):
    """Main execution function to crawl and compile cadastral.mbtiles."""
    bounds = (min_lon, min_lat, max_lon, max_lat)

    logger.info("=" * 75)
    logger.info(" COQUITLAM CADASTRAL MAPSERVER OFFLINE MBTILES CRAWLER")
    logger.info("=" * 75)
    logger.info(f" Target MBTiles : {output_file}")
    logger.info(f" Zoom Range     : {min_zoom} -> {max_zoom}")
    logger.info(f" Bounding Box   : Lon [{min_lon}, {max_lon}], Lat [{min_lat}, {max_lat}]")
    logger.info(f" Layers         : {layers}")
    logger.info(f" Workers / Delay: {workers} concurrent workers | {delay_sec * 1000:.0f}ms delay (~{1.0/delay_sec:.1f} req/s)")
    logger.info("=" * 75)

    # 1. Calculate tile grid per zoom level
    zoom_tile_map: Dict[int, List[Tuple[int, int, int]]] = {}
    total_grid_tiles = 0

    coverage = load_coverage_filter()

    for z in range(min_zoom, max_zoom + 1):
        z_tiles = [t for t in calculate_tiles(min_lat, min_lon, max_lat, max_lon, z)
                   if coverage(*t)]
        zoom_tile_map[z] = z_tiles
        total_grid_tiles += len(z_tiles)
        logger.info(f"  * Zoom {z:>2}: {len(z_tiles):>7,} tiles")

    logger.info(f" Total Grid Tiles: {total_grid_tiles:,}")
    logger.info("-" * 75)

    if dry_run:
        logger.info("Dry run requested. Exiting without downloading.")
        return

    # 2. Initialize or connect to MBTiles database
    conn = init_mbtiles_db(output_file, min_zoom, max_zoom, bounds)
    existing_keys = get_existing_tile_keys(conn)
    logger.info(f" Existing cached tiles in MBTiles: {len(existing_keys):,}")

    # 3. Filter missing tiles to download
    tiles_to_download: List[Tuple[int, int, int]] = []
    for z in range(min_zoom, max_zoom + 1):
        for t in zoom_tile_map[z]:
            tz, tx, ty = t
            t_tms = (1 << tz) - 1 - ty
            if (tz, tx, t_tms) not in existing_keys:
                tiles_to_download.append(t)

    logger.info(f" Missing tiles to download: {len(tiles_to_download):,}")

    if not tiles_to_download:
        logger.info("All cadastral tiles are already cached in the MBTiles archive!")
        conn.close()
        return

    # 4. Multi-threaded download with rate-limiting
    rate_limiter = RateLimiter(min_interval_sec=delay_sec)
    start_time = time.time()
    downloaded = 0
    failed = 0
    batch = []
    cur = conn.cursor()
    total_missing = len(tiles_to_download)

    logger.info(f"Starting crawl of {total_missing:,} tiles...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_tile = {
            executor.submit(
                download_cadastral_tile,
                t,
                rate_limiter,
                layers,
                tile_size
            ): t
            for t in tiles_to_download
        }

        for future in as_completed(future_to_tile):
            res = future.result()
            if res is not None:
                batch.append(res)
                downloaded += 1
                if len(batch) >= 100:
                    cur.executemany(
                        "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?);",
                        batch
                    )
                    conn.commit()
                    batch = []
            else:
                failed += 1

            total_done = downloaded + failed
            if total_done % 25 == 0 or total_done == total_missing:
                elapsed = time.time() - start_time
                rate = total_done / elapsed if elapsed > 0 else 0.0
                remaining_tiles = total_missing - total_done
                eta_sec = remaining_tiles / rate if rate > 0 else 0.0
                pct = (total_done / total_missing) * 100.0

                sys.stdout.write(
                    f"\r Progress: {total_done:,}/{total_missing:,} ({pct:5.1f}%) | "
                    f"[+] {downloaded:,} ok | [x] {failed:,} fail | "
                    f"{rate:4.1f} tiles/s | ETA: {format_duration(eta_sec)}"
                )
                sys.stdout.flush()

    # Commit any remaining batched tiles
    if batch:
        cur.executemany(
            "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?);",
            batch
        )
        conn.commit()

    total_elapsed = time.time() - start_time
    print(
        f"\nCrawl phase completed in {format_duration(total_elapsed)} "
        f"({downloaded:,} ok, {failed:,} failed, {downloaded/total_elapsed:.1f} tiles/s)."
    )

    # 5. Summary & verification
    cur.execute("SELECT zoom_level, count(*) FROM tiles GROUP BY zoom_level ORDER BY zoom_level;")
    zoom_stats = cur.fetchall()

    logger.info("=" * 75)
    logger.info(" CADASTRAL MBTILES SUMMARY")
    logger.info("=" * 75)
    total_db_tiles = 0
    for z, cnt in zoom_stats:
        total_db_tiles += cnt
        logger.info(f"  * Zoom {z:>2}: {cnt:>7,} tiles")

    file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
    logger.info(f" Total Tiles in Archive : {total_db_tiles:,}")
    logger.info(f" Final Archive File Size: {file_size_mb:.2f} MB")
    logger.info("=" * 75)

    # Checkpoint WAL and convert journal mode to DELETE for read-only container mount compatibility
    cur.execute("PRAGMA wal_checkpoint(FULL);")
    cur.execute("PRAGMA journal_mode = DELETE;")
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Pre-crawl City of Coquitlam ArcGIS Cadastral MapServer overlay into offline MBTiles archive."
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Target MBTiles output path (default: backend/data/tiles/cadastral.mbtiles)"
    )
    parser.add_argument(
        "--min-zoom",
        type=int,
        default=14,
        help="Minimum zoom level (default: 14)"
    )
    parser.add_argument(
        "--max-zoom",
        type=int,
        default=20,
        help="Maximum zoom level (default: 20)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SEC,
        help=f"Minimum delay between requests in seconds "
             f"(default: {DEFAULT_DELAY_SEC}s = {DEFAULT_DELAY_SEC * 1000:.0f}ms "
             f"= ~{1.0 / DEFAULT_DELAY_SEC:.0f} req/s)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of concurrent worker threads (default: 8)"
    )
    parser.add_argument(
        "--bbox",
        type=str,
        default=f"{DEFAULT_MIN_LON},{DEFAULT_MIN_LAT},{DEFAULT_MAX_LON},{DEFAULT_MAX_LAT}",
        help=f"Bounding box as west,south,east,north (default: {DEFAULT_MIN_LON},{DEFAULT_MIN_LAT},{DEFAULT_MAX_LON},{DEFAULT_MAX_LAT})"
    )
    parser.add_argument(
        "--layers",
        type=str,
        default="show:0,1,16",
        help="ArcGIS MapServer layers to export (default: show:0,1,16 for Road Labels, Address Labels, Parcels)"
    )
    parser.add_argument(
        "--size",
        type=str,
        default="256,256",
        help="Tile image size in pixels (default: 256,256)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate and report tile counts without downloading"
    )

    args = parser.parse_args()

    # Parse bbox
    try:
        parts = [float(p.strip()) for p in args.bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("Bounding box must have 4 float values: west,south,east,north")
        west, south, east, north = parts
    except Exception as e:
        logger.error(f"Invalid --bbox argument: {e}")
        sys.exit(1)

    # Determine output path
    if args.output:
        out_path = Path(args.output).resolve()
    else:
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent
        out_path = repo_root / "data" / "tiles" / "cadastral.mbtiles"

    crawl_cadastral(
        output_file=str(out_path),
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom,
        min_lat=south,
        max_lat=north,
        min_lon=west,
        max_lon=east,
        delay_sec=args.delay,
        workers=args.workers,
        layers=args.layers,
        tile_size=args.size,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
