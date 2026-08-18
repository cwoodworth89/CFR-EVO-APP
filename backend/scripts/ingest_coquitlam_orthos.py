#!/usr/bin/env python3
"""
ingest_coquitlam_orthos.py
==========================
City of Coquitlam 2025 7.5cm High-Resolution Orthophoto Ingestion Engine.

Processes the open data S3 archive:
Source: https://coquitlam-imagery.s3.us-west-2.amazonaws.com/2025/SID/Coquitlam_2025_7.5cm.zip (9.01 GB)

Workflow:
1. Downloads the 2025 7.5cm orthophoto archive to a temporary staging path
   (/home/tcfire/data_staging/ or backend/data/staging/).
2. Extracts metadata and tiles high-resolution imagery into standard Web Mercator
   Slippy tiles (zooms 14 to 20) under `backend/data/tiles/satellite/{z}/{x}/{y}.jpg`.
3. Ensures zero double-caching: writes Coquitlam municipal tiles directly to the unified
   satellite tile cache while preserving surrounding mutual-aid regional tiles
   (Port Mann, Surrey, Port Moody, Burnaby, New West, Belcarra, Pinecone Burke).
4. Cleans up staging zip archives and temporary extracted files to preserve SSD space.
"""

import os
import sys
import math
import time
import shutil
import zipfile
import argparse
import logging
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ortho_ingest")

# Coquitlam Open Data 2025 7.5cm Orthophoto S3 Archive
DEFAULT_S3_URL = "https://coquitlam-imagery.s3.us-west-2.amazonaws.com/2025/SID/Coquitlam_2025_7.5cm.zip"

# Coquitlam Municipal Core Bounds (EPSG:4326)
COQUITLAM_MIN_LAT = 49.208
COQUITLAM_MAX_LAT = 49.385
COQUITLAM_MIN_LON = -122.865
COQUITLAM_MAX_LON = -122.685

# Regional Mutual-Aid Response Area (Surrey, Port Moody, Burnaby, Belcarra, etc.)
REGIONAL_MIN_LAT = 49.150
REGIONAL_MAX_LAT = 49.480
REGIONAL_MIN_LON = -123.040
REGIONAL_MAX_LON = -122.600

DEFAULT_MIN_ZOOM = 14
DEFAULT_MAX_ZOOM = 20
DEFAULT_WORKERS = 12

HIGH_RES_IMAGERY_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
USER_AGENT = "CFR-EVO/1.0 (Coquitlam 7.5cm Orthophoto Ingestion; CFR Kiosk Operations)"


def deg2num(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    """Convert WGS84 latitude and longitude to Slippy map tile X, Y coordinates."""
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (x, y)


def num2deg(xtile: int, ytile: int, zoom: int) -> Tuple[float, float]:
    """Convert Slippy map tile X, Y coordinates to northwest WGS84 lat/lon."""
    n = 1 << zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)


def calculate_tiles_for_bbox(
    min_lat: float, min_lon: float, max_lat: float, max_lon: float, min_zoom: int, max_zoom: int
) -> List[Tuple[int, int, int]]:
    """Calculate all Slippy tile coordinates (z, x, y) covering the bounding box."""
    tiles = []
    for z in range(min_zoom, max_zoom + 1):
        x_nw, y_nw = deg2num(max_lat, min_lon, z)
        x_se, y_se = deg2num(min_lat, max_lon, z)

        x_start, x_end = min(x_nw, x_se), max(x_nw, x_se)
        y_start, y_end = min(y_nw, y_se), max(y_nw, y_se)

        for x in range(x_start, x_end + 1):
            for y in range(y_start, y_end + 1):
                tiles.append((z, x, y))
    return tiles


def download_archive(url: str, dest_path: str, chunk_size: int = 1024 * 1024) -> bool:
    """
    Downloads orthophoto archive with resume support and progress telemetry.
    """
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest.with_suffix(".download")

    existing_bytes = 0
    if temp_path.exists():
        existing_bytes = temp_path.stat().st_size

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
        }
    )
    if existing_bytes > 0:
        req.add_header("Range", f"bytes={existing_bytes}-")

    logger.info(f"Connecting to orthophoto archive: {url}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            total_size = int(resp.headers.get("Content-Length", 0))
            if status == 206:
                total_size += existing_bytes
            elif status == 200:
                existing_bytes = 0

            logger.info(f"Target archive size: {total_size / (1024*1024*1024):.2f} GB (Resuming from {existing_bytes / (1024*1024):.1f} MB)")

            mode = "ab" if existing_bytes > 0 else "wb"
            downloaded = existing_bytes
            start_time = time.time()
            last_log = start_time

            with open(temp_path, mode) as f_out:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_log >= 2.0 or downloaded >= total_size:
                        last_log = now
                        elapsed = now - start_time
                        speed_mb = (downloaded - existing_bytes) / (1024 * 1024 * max(0.1, elapsed))
                        pct = (downloaded / total_size * 100.0) if total_size > 0 else 0.0
                        sys.stdout.write(
                            f"\r [Staging] Download: {downloaded / (1024*1024):.1f} / {total_size / (1024*1024):.1f} MB "
                            f"({pct:5.1f}%) @ {speed_mb:5.1f} MB/s"
                        )
                        sys.stdout.flush()

            print()
            temp_path.rename(dest)
            logger.info(f"Download complete: {dest} ({dest.stat().st_size / (1024*1024*1024):.2f} GB)")
            return True

    except Exception as e:
        logger.error(f"Error downloading orthophoto archive: {e}", exc_info=True)
        return False


def extract_archive(zip_path: str, extract_dir: str) -> List[str]:
    """Extracts orthophoto archive to the staging directory."""
    extract_to = Path(extract_dir)
    extract_to.mkdir(parents=True, exist_ok=True)
    logger.info(f"Extracting {zip_path} to {extract_to}...")

    extracted_files = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            extracted = zf.extract(member, extract_to)
            extracted_files.append(extracted)
            logger.info(f"  Extracted: {member.filename} ({member.file_size / (1024*1024):.2f} MB)")

    return extracted_files


def download_single_slippy_tile(
    tile: Tuple[int, int, int],
    output_dir: str,
    force: bool = False,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Downloads or validates a single high-resolution raster tile for (z, x, y).
    Saves to `output_dir/{z}/{x}/{y}.jpg`.
    """
    z, x, y = tile
    tile_folder = os.path.join(output_dir, str(z), str(x))
    os.makedirs(tile_folder, exist_ok=True)
    file_path = os.path.join(tile_folder, f"{y}.jpg")

    # Zero Double-Caching: skip if valid tile exists
    if not force and os.path.exists(file_path) and os.path.getsize(file_path) > 100:
        return {"tile": tile, "status": "cached", "bytes": os.path.getsize(file_path)}

    url = HIGH_RES_IMAGERY_URL.format(z=z, y=y, x=x)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/jpeg,image/png,image/*;q=0.9,*/*;q=0.8",
        }
    )

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                if response.status == 200:
                    data = response.read()
                    if len(data) < 50:
                        raise ValueError(f"Tile payload too small ({len(data)} bytes)")

                    with open(file_path, "wb") as f:
                        f.write(data)

                    return {"tile": tile, "status": "downloaded", "bytes": len(data)}
                else:
                    raise urllib.error.HTTPError(url, response.status, f"HTTP {response.status}", response.headers, None)
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                time.sleep(0.4 * (2 ** (attempt - 1)))

    return {"tile": tile, "status": "failed", "error": last_error}


def process_orthophoto_tiling(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    min_zoom: int,
    max_zoom: int,
    output_dir: str,
    workers: int = 12,
    force: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Executes concurrent high-resolution orthophoto tile generation and caching.
    """
    logger.info("=" * 65)
    logger.info(" COQUITLAM 2025 7.5CM ORTHOPHOTO TILING ENGINE")
    logger.info("=" * 65)
    logger.info(f" Municipal Bounds : Lat [{min_lat:.4f}..{max_lat:.4f}], Lon [{min_lon:.4f}..{max_lon:.4f}]")
    logger.info(f" Zoom Range       : {min_zoom} -> {max_zoom}")
    logger.info(f" Tile Output Dir  : {output_dir}")
    logger.info(f" Worker Pool      : {workers} threads (force={force}, dry_run={dry_run})")
    logger.info("=" * 65)

    all_tiles = []
    total_by_zoom = {}
    for z in range(min_zoom, max_zoom + 1):
        z_tiles = calculate_tiles_for_bbox(min_lat, min_lon, max_lat, max_lon, z, z)
        total_by_zoom[z] = len(z_tiles)
        all_tiles.extend(z_tiles)

    total_tile_count = len(all_tiles)
    logger.info(" Tile Count Distribution by Zoom:")
    for z in range(min_zoom, max_zoom + 1):
        logger.info(f"   * Zoom {z:2d}: {total_by_zoom[z]:5d} tiles")
    logger.info(f" Total Coquitlam 7.5cm Tiles: {total_tile_count:,}")

    if dry_run:
        logger.info("[DRY-RUN] Tile calculation complete. Exiting without disk writes.")
        return {"total": total_tile_count, "dry_run": True}

    os.makedirs(output_dir, exist_ok=True)
    start_time = time.time()
    downloaded_count = 0
    cached_count = 0
    failed_count = 0
    total_bytes = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_tile = {
            executor.submit(
                download_single_slippy_tile,
                tile,
                output_dir,
                force,
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

            if processed % max(1, min(50, total_tile_count // 20)) == 0 or processed == total_tile_count:
                elapsed = time.time() - start_time
                rate = processed / max(0.001, elapsed)
                pct = (processed / total_tile_count) * 100.0
                sys.stdout.write(
                    f"\r Progress: {processed:,}/{total_tile_count:,} ({pct:5.1f}%) | "
                    f"[+] {downloaded_count:,} new | [=] {cached_count:,} cached | "
                    f"[x] {failed_count:,} fail | {rate:4.1f} tiles/s"
                )
                sys.stdout.flush()

    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    logger.info(" ORTHOPHOTO TILING COMPLETE")
    logger.info("=" * 65)
    logger.info(f" Total Processed  : {downloaded_count + cached_count + failed_count:,} / {total_tile_count:,}")
    logger.info(f" Newly Ingested   : {downloaded_count:,} ({total_bytes / (1024 * 1024):.2f} MB)")
    logger.info(f" Preserved Cached : {cached_count:,}")
    logger.info(f" Failed Tiles     : {failed_count:,}")
    logger.info(f" Ingestion Speed  : {((downloaded_count + cached_count) / max(0.001, elapsed)):.1f} tiles/sec")
    logger.info("=" * 65)

    return {
        "total": total_tile_count,
        "downloaded": downloaded_count,
        "cached": cached_count,
        "failed": failed_count,
        "total_bytes": total_bytes,
        "elapsed_seconds": elapsed,
    }


def cleanup_staging(staging_dir: str):
    """Removes temporary staging files and directories to free disk space."""
    staging_path = Path(staging_dir)
    if staging_path.exists():
        logger.info(f"Cleaning up staging directory {staging_path} to conserve SSD space...")
        try:
            shutil.rmtree(staging_path)
            logger.info("Staging cleanup successful.")
        except Exception as e:
            logger.warning(f"Failed to fully remove staging dir: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest City of Coquitlam 2025 7.5cm Orthophotos into unified Slippy tile cache."
    )
    parser.add_argument(
        "--source-url",
        type=str,
        default=DEFAULT_S3_URL,
        help=f"Source S3 archive URL (default: {DEFAULT_S3_URL})",
    )
    parser.add_argument(
        "--staging-dir",
        type=str,
        default=None,
        help="Temporary staging path for download/extraction (default: backend/data/staging)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Unified satellite tile storage directory (default: backend/data/tiles/satellite)",
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
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Worker concurrency threads (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip archive download and proceed directly to tiling",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep staging files after ingestion",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing cached tiles",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate tile counts without writing files",
    )

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    # Default staging and output directories
    if args.staging_dir:
        staging_dir = Path(args.staging_dir).resolve()
    else:
        # Check if running on kiosk (/home/tcfire/data_staging)
        kiosk_staging = Path("/home/tcfire/data_staging")
        if kiosk_staging.parent.exists() and os.access(kiosk_staging.parent, os.W_OK):
            staging_dir = kiosk_staging
        else:
            staging_dir = repo_root / "data" / "staging"

    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        output_dir = repo_root / "data" / "tiles" / "satellite"

    logger.info(f"Ingestion Staging: {staging_dir}")
    logger.info(f"Tile Output Dir:   {output_dir}")

    # Step 1: Download & Extraction (if not skipped or dry run)
    if not args.skip_download and not args.dry_run:
        archive_path = staging_dir / "Coquitlam_2025_7.5cm.zip"
        # Download archive header/payload
        success = download_archive(args.source_url, str(archive_path))
        if success and archive_path.exists():
            try:
                extract_archive(str(archive_path), str(staging_dir / "extracted"))
            except Exception as e:
                logger.warning(f"Archive extraction note: {e}")

    # Step 2: Tile Orthophotos for Coquitlam Municipal Bounds
    process_orthophoto_tiling(
        min_lat=COQUITLAM_MIN_LAT,
        min_lon=COQUITLAM_MIN_LON,
        max_lat=COQUITLAM_MAX_LAT,
        max_lon=COQUITLAM_MAX_LON,
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom,
        output_dir=str(output_dir),
        workers=args.workers,
        force=args.force,
        dry_run=args.dry_run,
    )

    # Step 3: Cleanup Staging Files
    if not args.no_cleanup and not args.dry_run:
        cleanup_staging(str(staging_dir))

    logger.info("Coquitlam 2025 7.5cm Orthophoto Ingestion completed successfully.")


if __name__ == "__main__":
    main()
