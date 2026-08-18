#!/usr/bin/env python3
"""
precache_satellite_tiles.py
===========================
Pre-caches satellite raster tiles for the Coquitlam emergency response area.
Downloads tiles from Esri World Imagery (ArcGIS REST) and saves them locally
under `backend/data/tiles/satellite/{z}/{x}/{y}.jpg` (and optionally .png).

Features:
- Bounding box calculation for Web Mercator / Slippy map tile coordinates (z, x, y)
- Multi-threaded concurrent downloads with rate-limiting and retry backoff
- Resume capability (skips already downloaded non-empty tile files)
- Configurable zoom range, bounding box, worker threads, and rate delay
- Dry-run mode for tile count inspection
- Graceful shutdown on Ctrl+C (KeyboardInterrupt)
"""

import os
import sys
import math
import time
import argparse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any, Optional

# Default Bounding Box for Coquitlam Emergency Response Area
# Regional Operational Response Bounding Box:
# Lat: 49.15 (Port Mann / North Surrey) -> 49.48 (Pinecone Burke / Widgeon)
# Lon: -123.04 (Burnaby / New Westminster / Belcarra) -> -122.60 (Pitt Meadows / Pitt River)
DEFAULT_MIN_LAT = 49.15
DEFAULT_MAX_LAT = 49.48
DEFAULT_MIN_LON = -123.04
DEFAULT_MAX_LON = -122.60

DEFAULT_MIN_ZOOM = 12
DEFAULT_MAX_ZOOM = 18
DEFAULT_WORKERS = 8

ESRI_WORLD_IMAGERY_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)

USER_AGENT = "CFR-EVO/1.0 (Emergency Response Pre-Cache; Coquitlam Fire Rescue)"


def deg2num(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    """
    Convert WGS84 latitude and longitude to Slippy map tile X, Y coordinates.
    """
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (x, y)


def num2deg(xtile: int, ytile: int, zoom: int) -> Tuple[float, float]:
    """
    Convert Slippy map tile X, Y coordinates to northwest WGS84 lat/lon.
    """
    n = 1 << zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)


def calculate_tiles_for_bbox(
    min_lat: float, min_lon: float, max_lat: float, max_lon: float, min_zoom: int, max_zoom: int
) -> List[Tuple[int, int, int]]:
    """
    Calculate all tile coordinates (z, x, y) covering the bounding box across specified zoom levels.
    """
    tiles = []
    for z in range(min_zoom, max_zoom + 1):
        # Upper-left (North-West) gives min X and min Y (Y increases southwards)
        x_nw, y_nw = deg2num(max_lat, min_lon, z)
        # Lower-right (South-East) gives max X and max Y
        x_se, y_se = deg2num(min_lat, max_lon, z)

        x_start, x_end = min(x_nw, x_se), max(x_nw, x_se)
        y_start, y_end = min(y_nw, y_se), max(y_nw, y_se)

        for x in range(x_start, x_end + 1):
            for y in range(y_start, y_end + 1):
                tiles.append((z, x, y))
    return tiles


def parse_bbox(bbox_str: str) -> Tuple[float, float, float, float]:
    """
    Parse bounding box string in format 'min_lat,min_lon,max_lat,max_lon'
    or 'lat1,lon1,lat2,lon2'.
    """
    parts = [float(p.strip()) for p in bbox_str.split(",")]
    if len(parts) != 4:
        raise ValueError(
            f"Invalid bbox '{bbox_str}'. Expected 4 comma-separated values: min_lat,min_lon,max_lat,max_lon"
        )
    lat1, lon1, lat2, lon2 = parts
    min_lat = min(lat1, lat2)
    max_lat = max(lat1, lat2)
    min_lon = min(lon1, lon2)
    max_lon = max(lon1, lon2)
    return (min_lat, min_lon, max_lat, max_lon)


def download_single_tile(
    tile: Tuple[int, int, int],
    output_dir: str,
    tile_format: str = "jpg",
    force: bool = False,
    delay: float = 0.0,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Download a single satellite tile and save it to the local cache directory.
    Returns a dict with status: 'downloaded', 'cached', or 'failed'.
    """
    z, x, y = tile

    # Target directory structure: {output_dir}/{z}/{x}/
    tile_folder = os.path.join(output_dir, str(z), str(x))
    os.makedirs(tile_folder, exist_ok=True)

    # Determine files to check/write
    files_to_write = []
    if tile_format in ("jpg", "both"):
        files_to_write.append(os.path.join(tile_folder, f"{y}.jpg"))
    if tile_format in ("png", "both"):
        files_to_write.append(os.path.join(tile_folder, f"{y}.png"))

    primary_path = files_to_write[0]

    # Resume check: if not forcing, check if file exists and has content (> 100 bytes)
    if not force and os.path.exists(primary_path) and os.path.getsize(primary_path) > 100:
        # If 'both' was requested, ensure secondary format exists too
        if len(files_to_write) > 1 and not os.path.exists(files_to_write[1]):
            try:
                with open(primary_path, "rb") as f_in:
                    data = f_in.read()
                with open(files_to_write[1], "wb") as f_out:
                    f_out.write(data)
            except Exception:
                pass
        return {"tile": tile, "status": "cached", "bytes": os.path.getsize(primary_path)}

    if delay > 0:
        time.sleep(delay)

    # Esri World Imagery URL: tile/{z}/{y}/{x}
    url = ESRI_WORLD_IMAGERY_URL.format(z=z, y=y, x=x)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/jpeg,image/png,image/*;q=0.9,*/*;q=0.8",
        },
    )

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                if response.status == 200:
                    data = response.read()
                    if len(data) < 50:
                        raise ValueError(f"Tile payload too small ({len(data)} bytes)")

                    for path in files_to_write:
                        with open(path, "wb") as f:
                            f.write(data)

                    return {"tile": tile, "status": "downloaded", "bytes": len(data)}
                else:
                    raise urllib.error.HTTPError(
                        url, response.status, f"HTTP {response.status}", response.headers, None
                    )
        except (urllib.error.HTTPError, urllib.error.URLError, Exception) as e:
            last_error = str(e)
            if attempt < max_retries:
                backoff = 0.5 * (2 ** (attempt - 1))
                time.sleep(backoff)

    return {"tile": tile, "status": "failed", "error": last_error}


def run_precache(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    min_zoom: int,
    max_zoom: int,
    output_dir: str,
    tile_format: str = "jpg",
    workers: int = 8,
    force: bool = False,
    dry_run: bool = False,
    delay: float = 0.0,
) -> Dict[str, Any]:
    """
    Executes the pre-caching workflow.
    """
    print("=" * 70)
    print(" CFR EVO SATELLITE TILE PRE-CACHING ENGINE")
    print("=" * 70)
    print(f" Bounding Box : Lat [{min_lat:.4f}..{max_lat:.4f}], Lon [{min_lon:.4f}..{max_lon:.4f}]")
    print(f" Zoom Range   : {min_zoom} -> {max_zoom}")
    print(f" Output Dir   : {output_dir}")
    print(f" Format       : {tile_format}")
    print(f" Concurrency  : {workers} workers (delay: {delay}s, force: {force})")
    print("=" * 70)

    total_tiles_by_zoom = {}
    all_tiles = []

    for z in range(min_zoom, max_zoom + 1):
        z_tiles = calculate_tiles_for_bbox(min_lat, min_lon, max_lat, max_lon, z, z)
        total_tiles_by_zoom[z] = len(z_tiles)
        all_tiles.extend(z_tiles)

    total_tile_count = len(all_tiles)

    print(" Tile Distribution by Zoom Level:")
    for z in range(min_zoom, max_zoom + 1):
        x_nw, y_nw = deg2num(max_lat, min_lon, z)
        x_se, y_se = deg2num(min_lat, max_lon, z)
        x_min, x_max = min(x_nw, x_se), max(x_nw, x_se)
        y_min, y_max = min(y_nw, y_se), max(y_nw, y_se)
        print(
            f"   * Zoom {z:2d}: {total_tiles_by_zoom[z]:5d} tiles  "
            f"(X: {x_min}..{x_max}, Y: {y_min}..{y_max})"
        )
    print(f" Total Tiles to Process: {total_tile_count:,}")
    print("-" * 70)

    if dry_run:
        print(" [DRY-RUN] Calculation complete. No tiles downloaded.")
        return {
            "total": total_tile_count,
            "downloaded": 0,
            "cached": 0,
            "failed": 0,
            "dry_run": True,
        }

    os.makedirs(output_dir, exist_ok=True)

    start_time = time.time()
    downloaded_count = 0
    cached_count = 0
    failed_count = 0
    total_bytes = 0
    failed_tiles = []

    print(f" Starting download pool with {workers} workers...\n")

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_tile = {
                executor.submit(
                    download_single_tile,
                    tile,
                    output_dir,
                    tile_format,
                    force,
                    delay,
                ): tile
                for tile in all_tiles
            }

            processed = 0
            for future in as_completed(future_to_tile):
                processed += 1
                res = future.result()
                status = res.get("status")

                if status == "downloaded":
                    downloaded_count += 1
                    total_bytes += res.get("bytes", 0)
                elif status == "cached":
                    cached_count += 1
                elif status == "failed":
                    failed_count += 1
                    failed_tiles.append((res.get("tile"), res.get("error")))

                if processed % max(1, min(50, total_tile_count // 10)) == 0 or processed == total_tile_count:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    pct = (processed / total_tile_count) * 100
                    sys.stdout.write(
                        f"\r Progress: {processed:,}/{total_tile_count:,} ({pct:5.1f}%) | "
                        f"[+] {downloaded_count:,} new | [=] {cached_count:,} cached | "
                        f"[x] {failed_count:,} fail | {rate:4.1f} tiles/s"
                    )
                    sys.stdout.flush()

    except KeyboardInterrupt:
        print("\n\n [!] Pre-caching interrupted by user. Saved partial progress.")

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(" PRE-CACHING SUMMARY")
    print("=" * 70)
    print(f" Total Processed  : {downloaded_count + cached_count + failed_count:,} / {total_tile_count:,}")
    print(f" Newly Downloaded : {downloaded_count:,} ({total_bytes / (1024 * 1024):.2f} MB)")
    print(f" Already Cached   : {cached_count:,}")
    print(f" Failed / Errors  : {failed_count:,}")
    print(f" Elapsed Time     : {elapsed:.2f}s ({((downloaded_count + cached_count) / elapsed if elapsed > 0 else 0):.1f} tiles/s)")
    print("=" * 70)

    if failed_tiles:
        print(f"\n [!] First {min(5, len(failed_tiles))} failed tile errors:")
        for t, err in failed_tiles[:5]:
            print(f"     Tile {t}: {err}")

    return {
        "total": total_tile_count,
        "downloaded": downloaded_count,
        "cached": cached_count,
        "failed": failed_count,
        "total_bytes": total_bytes,
        "elapsed_seconds": elapsed,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Pre-cache satellite raster tiles for Coquitlam emergency response."
    )
    parser.add_argument(
        "--min-zoom",
        type=int,
        default=DEFAULT_MIN_ZOOM,
        help=f"Minimum zoom level (default: {DEFAULT_MIN_ZOOM})",
    )
    parser.add_argument(
        "--max-zoom",
        type=int,
        default=DEFAULT_MAX_ZOOM,
        help=f"Maximum zoom level (default: {DEFAULT_MAX_ZOOM})",
    )
    parser.add_argument(
        "--bbox",
        type=str,
        default=f"{DEFAULT_MIN_LAT},{DEFAULT_MIN_LON},{DEFAULT_MAX_LAT},{DEFAULT_MAX_LON}",
        help="Bounding box as min_lat,min_lon,max_lat,max_lon (default: Coquitlam response area)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for tile storage (default: backend/data/tiles/satellite)",
    )
    parser.add_argument(
        "--format",
        choices=["jpg", "png", "both"],
        default="jpg",
        help="File format to save on disk: jpg (default), png, or both",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of concurrent worker threads (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Rate-limiting delay between requests in seconds per worker (default: 0.0)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download of tiles even if already cached locally",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute tile counts without downloading",
    )

    args = parser.parse_args()

    # Determine default output directory relative to repository structure
    if args.output_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(script_dir)
        output_dir = os.path.join(repo_root, "data", "tiles", "satellite")
    else:
        output_dir = os.path.abspath(args.output_dir)

    min_lat, min_lon, max_lat, max_lon = parse_bbox(args.bbox)

    if args.min_zoom > args.max_zoom:
        parser.error(f"--min-zoom ({args.min_zoom}) cannot be greater than --max-zoom ({args.max_zoom})")

    run_precache(
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom,
        output_dir=output_dir,
        tile_format=args.format,
        workers=args.workers,
        force=args.force,
        dry_run=args.dry_run,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
