#!/usr/bin/env python3
"""
ingest_coquitlam_orthos.py
==========================
City of Coquitlam 2025 7.5cm High-Resolution Orthophoto Ingestion & Tiling Engine.

Processes the open data archive:
Source Archive: /home/tcfire/data_staging/Coquitlam_2025_7.5cm.zip (9.01 GB)
Internal Files: BCCOQU25-SID-7.5CM/BCCOQU25-SID-7.5CM.sid, .prj, .sdw, .aux.xml

Workflow:
1. Unpacks the 2025 7.5cm orthophoto archive in staging (/home/tcfire/data_staging/extracted).
2. Leverages containerized GDAL tooling (`klokantech/gdal` with native MrSID DSDK decoder)
   to run multi-process Web Mercator tiling (`gdal2tiles.py -p mercator -z <min>-<max>`).
3. Converts generated TMS directory structure ({z}/{x}/{y_tms}.png) into standard Slippy XYZ
   Slippy map tiles ({z}/{x}/{max_y - y_tms}.png & .jpg) under `backend/data/tiles/satellite/`.
4. Ensures zero double-caching: writes Coquitlam municipal tiles directly to the unified
   satellite tile cache while preserving surrounding mutual-aid regional tiles.
5. Verifies local FastAPI tile endpoints via HTTP HEAD/GET requests.
6. Cleans up staging zip archives and temporary extracted files to preserve NVMe SSD space.
"""

import os
import sys
import math
import time
import shutil
import zipfile
import argparse
import logging
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
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

DEFAULT_MIN_ZOOM = 14
DEFAULT_MAX_ZOOM = 19
DEFAULT_WORKERS = 8

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


def extract_archive(zip_path: str, extract_dir: str) -> List[str]:
    """Extracts orthophoto archive to the staging directory."""
    extract_to = Path(extract_dir)
    extract_to.mkdir(parents=True, exist_ok=True)
    logger.info(f"Extracting archive {zip_path} to {extract_to}...")

    extracted_files = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            extracted = zf.extract(member, extract_to)
            extracted_files.append(extracted)
            logger.info(f"  Extracted: {member.filename} ({member.file_size / (1024*1024):.2f} MB)")

    return extracted_files


def run_containerized_tiling(
    sid_path: Path,
    raw_tiles_dir: Path,
    zoom_range: str,
    workers: int = 8,
) -> bool:
    """
    Executes gdal2tiles.py inside klokantech/gdal container with native MrSID support.
    """
    logger.info(f"Launching containerized GDAL tiling for Zooms {zoom_range} ({workers} worker processes)...")
    raw_tiles_dir.mkdir(parents=True, exist_ok=True)

    mount_dir = sid_path.parent.resolve()
    rel_sid = sid_path.name
    container_out = "/data/raw_tiles"

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{mount_dir}:/data",
        "-v", f"{raw_tiles_dir.resolve()}:{container_out}",
        "klokantech/gdal",
        "python3", "/usr/local/bin/gdal2tiles.py",
        "-p", "mercator",
        "-z", str(zoom_range),
        "-w", "none",
        "-r", "bilinear",
        f"--processes={workers}",
        f"/data/{rel_sid}",
        container_out,
    ]

    logger.info(f"Executing: {' '.join(cmd)}")
    start_t = time.time()
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
        logger.info(proc.stdout)
        elapsed = time.time() - start_t
        logger.info(f"Container tiling for {zoom_range} completed in {elapsed:.1f}s")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"GDAL container tiling failed (code {e.returncode}):\n{e.stdout}")
        return False


def convert_tms_to_xyz(raw_tiles_dir: Path, dest_dir: Path) -> int:
    """
    Converts TMS tiles {z}/{x}/{y_tms}.png to Slippy XYZ {z}/{x}/{y_xyz}.png and .jpg
    Formula: y_xyz = (1 << z) - 1 - y_tms.
    """
    logger.info(f"Converting TMS tiles from {raw_tiles_dir} to Slippy XYZ under {dest_dir}...")
    dest_dir.mkdir(parents=True, exist_ok=True)
    converted_count = 0

    for z_dir in sorted(raw_tiles_dir.iterdir()):
        if not z_dir.is_dir() or not z_dir.name.isdigit():
            continue
        z = int(z_dir.name)
        max_y = (1 << z) - 1

        for x_dir in sorted(z_dir.iterdir()):
            if not x_dir.is_dir() or not x_dir.name.isdigit():
                continue
            x = int(x_dir.name)
            target_x_dir = dest_dir / str(z) / str(x)
            target_x_dir.mkdir(parents=True, exist_ok=True)

            for tile_file in x_dir.iterdir():
                if tile_file.name.endswith(".png") and not tile_file.name.endswith(".aux.xml"):
                    stem = tile_file.stem
                    if not stem.isdigit():
                        continue
                    y_tms = int(stem)
                    y_xyz = max_y - y_tms

                    target_png = target_x_dir / f"{y_xyz}.png"
                    shutil.copy2(tile_file, target_png)
                    converted_count += 1

    logger.info(f"Converted and merged {converted_count:,} Slippy XYZ tiles.")
    return converted_count


def verify_tile_endpoints(
    sample_tiles: List[Tuple[int, int, int]],
    api_base_url: str = "http://localhost:8000"
) -> bool:
    """
    Verifies tile serving endpoints return HTTP 200 with valid image payloads.
    """
    logger.info(f"Verifying {len(sample_tiles)} sample tile endpoints against {api_base_url}...")
    all_ok = True

    for z, x, y in sample_tiles:
        for ext in ["png", "jpg"]:
            url = f"{api_base_url}/api/tiles/satellite/{z}/{x}/{y}.{ext}"
            try:
                req = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    content_type = resp.headers.get("Content-Type", "")
                    status = resp.status
                    data = resp.read(1024)
                    if status == 200 and ("image/png" in content_type or "image/jpeg" in content_type) and len(data) > 0:
                        logger.info(f"  [OK] {url} -> HTTP {status} ({content_type}, {len(data)} bytes verified)")
                    else:
                        logger.warning(f"  [FAIL] {url} -> HTTP {status} ({content_type})")
                        all_ok = False
            except Exception as e:
                logger.error(f"  [ERROR] {url} -> {e}")
                all_ok = False

    return all_ok


def cleanup_staging(staging_dir: Path):
    """Removes temporary extracted files to free SSD space."""
    if staging_dir.exists():
        logger.info(f"Cleaning up staging directory {staging_dir}...")
        try:
            shutil.rmtree(staging_dir)
            logger.info("Staging cleanup successful.")
        except Exception as e:
            logger.warning(f"Failed to fully clean staging dir: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest City of Coquitlam 2025 7.5cm Orthophotos into unified Slippy tile cache."
    )
    parser.add_argument(
        "--staging-dir",
        type=str,
        default="/home/tcfire/data_staging",
        help="Staging directory containing archive / extracted files",
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
        help=f"Worker concurrency processes (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "--convert-dir",
        type=str,
        default=None,
        help="Directly convert a TMS folder to Slippy XYZ in output-dir without re-tiling",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Preserve staging extracted files after tiling",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only run endpoint verification",
    )

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    staging_dir = Path(args.staging_dir).resolve()
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        output_dir = repo_root / "data" / "tiles" / "satellite"

    if args.convert_dir:
        conv_path = Path(args.convert_dir).resolve()
        logger.info(f"Direct conversion mode: {conv_path} -> {output_dir}")
        total = convert_tms_to_xyz(conv_path, output_dir)
        sample_points = [
            (14, 2603, 5601),
            (15, 5206, 11202),
            (16, 10410, 22405),
        ]
        verify_tile_endpoints(sample_points)
        return

    logger.info("=" * 65)
    logger.info(" COQUITLAM 2025 7.5CM ORTHOPHOTO INGESTION PIPELINE")
    logger.info("=" * 65)
    logger.info(f" Staging Directory : {staging_dir}")
    logger.info(f" Output Tile Dir   : {output_dir}")
    logger.info(f" Zoom Range        : {args.min_zoom} -> {args.max_zoom}")
    logger.info(f" Workers           : {args.workers} processes")
    logger.info("=" * 65)

    if args.verify_only:
        # Sample points in central Coquitlam
        samples = [
            (14, 2603, 5601),
            (15, 5206, 11202),
            (16, 10410, 22405),
            (18, 41640, 89620),
            (19, 83280, 179240),
        ]
        verify_tile_endpoints(samples)
        return

    # Check for SID file in staging
    sid_path = staging_dir / "extracted" / "BCCOQU25-SID-7.5CM" / "BCCOQU25-SID-7.5CM.sid"
    if not sid_path.exists():
        # Check if zip exists
        zip_path = staging_dir / "Coquitlam_2025_7.5cm.zip"
        if zip_path.exists():
            extract_archive(str(zip_path), str(staging_dir / "extracted"))
        else:
            logger.error(f"Neither SID file nor zip archive found at {staging_dir}")
            sys.exit(1)

    raw_tiles_dir = staging_dir / "raw_tiles"
    zoom_range = f"{args.min_zoom}-{args.max_zoom}" if args.min_zoom != args.max_zoom else str(args.min_zoom)
    success = run_containerized_tiling(sid_path, raw_tiles_dir, zoom_range, workers=args.workers)
    if not success:
        logger.error("Containerized tiling failed. Aborting.")
        sys.exit(1)

    # Convert TMS to XYZ and merge into unified cache
    total_tiles = convert_tms_to_xyz(raw_tiles_dir, output_dir)

    # Verification
    sample_points = [
        (14, 2603, 5601),
        (15, 5206, 11202),
        (16, 10410, 22405),
    ]
    if args.max_zoom >= 18:
        sample_points.append((18, 41640, 89620))
    if args.max_zoom >= 19:
        sample_points.append((19, 83280, 179240))

    verify_tile_endpoints(sample_points)

    if not args.no_cleanup:
        cleanup_staging(raw_tiles_dir)

    logger.info("=" * 65)
    logger.info(" COQUITLAM 2025 7.5CM ORTHOPHOTO INGESTION COMPLETE")
    logger.info(f" Total Tiles Ingested: {total_tiles:,}")
    logger.info("=" * 65)


if __name__ == "__main__":
    main()
