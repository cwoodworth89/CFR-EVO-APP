#!/usr/bin/env python3
"""
compile_mbtiles.py
==================
Builds and compiles centralized MBTiles archives for CFR EVO:
1. satellite.mbtiles:
   - Combines City of Coquitlam 2025 7.5cm Orthophoto + surrounding regional base imagery (Zooms 12 through 20).
   - Standard format: JPEG (Quality 85).
2. street.mbtiles:
   - Carto Voyager / OpenStreetMap street basemap with full labels (Zooms 12 through 18).
   - Standard format: PNG.
3. street_nolabels.mbtiles:
   - Tactical light/grey basemap without text labels (Zooms 12 through 18).
   - Standard format: PNG.

Features:
- Fast multi-threaded concurrent downloading (32 workers) with retry backoff
- Ingests existing loose disk tiles directly into MBTiles (zero re-downloads)
- Ingests TMS raw tiles from Coquitlam 2025 7.5cm Orthophoto (converting PNG to JPEG 85)
- SQLite WAL mode + transaction batching for high write throughput
- Resumable (skips already present tiles in the MBTiles archive)
- Standard Slippy XYZ -> TMS coordinate conversion for MBTiles spec
- Tile count & size reporting per zoom level
"""

import os
import sys
import io
import math
import time
import random
import sqlite3
import argparse
import logging
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any, Optional, Set
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("mbtiles_builder")

# Bounding Boxes
# Regional Operational Bounds (Zooms 12-16)
REGIONAL_MIN_LAT = 49.15
REGIONAL_MAX_LAT = 49.48
REGIONAL_MIN_LON = -123.04
REGIONAL_MAX_LON = -122.60

# Coquitlam Core & Emergency Response Corridor (Zooms 17-18)
COQUITLAM_MIN_LAT = 49.208
COQUITLAM_MAX_LAT = 49.385
COQUITLAM_MIN_LON = -122.865
COQUITLAM_MAX_LON = -122.685

# Urban Core & Apparatus Bay Stations 1-4 Corridor (Zooms 19-20)
URBAN_CORE_MIN_LAT = 49.240
URBAN_CORE_MAX_LAT = 49.340
URBAN_CORE_MIN_LON = -122.870
URBAN_CORE_MAX_LON = -122.730

USER_AGENT = "CFR-EVO/1.0 (Coquitlam Fire Rescue Emergency Offline Cache)"

LAYER_CONFIGS = {
    "street": {
        "format": "png",
        "description": "Carto Voyager / OpenStreetMap Basemap with Full Labels",
        "url_template": "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "subdomains": ["a", "b", "c", "d"],
        "min_zoom": 12,
        "max_zoom": 18,
    },
    "street_nolabels": {
        "format": "png",
        "description": "Tactical Light/Grey Basemap without Labels",
        "url_template": "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png",
        "subdomains": ["a", "b", "c", "d"],
        "min_zoom": 12,
        "max_zoom": 18,
    },
    "satellite": {
        "format": "jpg",
        "description": "City of Coquitlam 2025 7.5cm Orthophoto & Regional Satellite Imagery",
        "url_template": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "subdomains": [""],
        "min_zoom": 12,
        "max_zoom": 20,
    }
}


def deg2num(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    """Convert WGS84 lat/lon to Slippy map tile X, Y coordinates."""
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (x, y)


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


def init_mbtiles_db(db_path: str, layer_name: str, config: Dict[str, Any]) -> sqlite3.Connection:
    """Initialize an MBTiles SQLite database with metadata and tile table."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA synchronous = NORMAL;")
    cur.execute("PRAGMA cache_size = -64000;")  # 64MB cache
    
    cur.execute("CREATE TABLE IF NOT EXISTS metadata (name text, value text);")
    cur.execute("CREATE TABLE IF NOT EXISTS tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob);")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS tile_index ON tiles (zoom_level, tile_column, tile_row);")
    
    # Insert or replace metadata
    metadata = {
        "name": layer_name,
        "type": "baselayer",
        "version": "1.0",
        "description": config.get("description", f"{layer_name} offline tile cache"),
        "format": config["format"],
        "bounds": f"{REGIONAL_MIN_LON},{REGIONAL_MIN_LAT},{REGIONAL_MAX_LON},{REGIONAL_MAX_LAT}",
        "minzoom": str(config["min_zoom"]),
        "maxzoom": str(config["max_zoom"]),
        "center": "-122.7907,49.2911,15",
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


def ingest_loose_disk_tiles(conn: sqlite3.Connection, loose_dir: str, target_format: str = "png") -> int:
    """
    Ingests existing loose directory tiles ({loose_dir}/{z}/{x}/{y_xyz}.ext) into MBTiles.
    Converts Slippy XYZ y to TMS tile_row: tile_row = (1 << z) - 1 - y_xyz.
    """
    loose_path = Path(loose_dir)
    if not loose_path.exists():
        return 0
    
    logger.info(f"Scanning loose disk tiles in {loose_dir}...")
    cur = conn.cursor()
    inserted = 0
    batch = []
    
    for z_dir in sorted(loose_path.iterdir()):
        if not z_dir.is_dir() or not z_dir.name.isdigit():
            continue
        z = int(z_dir.name)
        max_y = (1 << z) - 1
        
        for x_dir in sorted(z_dir.iterdir()):
            if not x_dir.is_dir() or not x_dir.name.isdigit():
                continue
            x = int(x_dir.name)
            
            for tile_file in x_dir.iterdir():
                if tile_file.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
                    continue
                stem = tile_file.stem
                if not stem.isdigit():
                    continue
                y_xyz = int(stem)
                y_tms = max_y - y_xyz
                
                try:
                    with open(tile_file, 'rb') as f:
                        data = f.read()
                    
                    if len(data) < 50:
                        continue
                    
                    # Convert PNG to JPEG 85 if target format is jpg and file is png
                    if target_format in ('jpg', 'jpeg') and tile_file.suffix.lower() == '.png':
                        try:
                            im = Image.open(io.BytesIO(data)).convert('RGB')
                            buf = io.BytesIO()
                            im.save(buf, format='JPEG', quality=85)
                            data = buf.getvalue()
                        except Exception:
                            pass
                    
                    batch.append((z, x, y_tms, data))
                    if len(batch) >= 1000:
                        cur.executemany("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?);", batch)
                        conn.commit()
                        inserted += len(batch)
                        batch = []
                except Exception as e:
                    logger.warning(f"Error reading loose tile {tile_file}: {e}")
                    
    if batch:
        cur.executemany("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?);", batch)
        conn.commit()
        inserted += len(batch)
        
    logger.info(f"Ingested {inserted:,} tiles from loose directory {loose_dir}.")
    return inserted


def ingest_tms_ortho_tiles(conn: sqlite3.Connection, tms_dir: str) -> int:
    """
    Ingests TMS tiles generated by gdal2tiles ({tms_dir}/{z}/{x}/{y_tms}.png) into satellite.mbtiles.
    In MBTiles, tile_row is ALREADY TMS, so tile_row = y_tms.
    Converts PNG to JPEG (Quality 85).
    """
    tms_path = Path(tms_dir)
    if not tms_path.exists():
        return 0
    
    logger.info(f"Ingesting Coquitlam 2025 7.5cm Orthophoto TMS tiles from {tms_dir}...")
    cur = conn.cursor()
    inserted = 0
    batch = []
    
    for z_dir in sorted(tms_path.iterdir()):
        if not z_dir.is_dir() or not z_dir.name.isdigit():
            continue
        z = int(z_dir.name)
        
        for x_dir in sorted(z_dir.iterdir()):
            if not x_dir.is_dir() or not x_dir.name.isdigit():
                continue
            x = int(x_dir.name)
            
            for tile_file in x_dir.iterdir():
                if not tile_file.name.endswith('.png') or tile_file.name.endswith('.aux.xml'):
                    continue
                stem = tile_file.stem
                if not stem.isdigit():
                    continue
                y_tms = int(stem)
                
                try:
                    with open(tile_file, 'rb') as f:
                        png_data = f.read()
                    
                    if len(png_data) < 50:
                        continue
                    
                    # Convert to JPEG 85
                    im = Image.open(io.BytesIO(png_data)).convert('RGB')
                    buf = io.BytesIO()
                    im.save(buf, format='JPEG', quality=85)
                    jpg_data = buf.getvalue()
                    
                    batch.append((z, x, y_tms, jpg_data))
                    if len(batch) >= 1000:
                        cur.executemany("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?);", batch)
                        conn.commit()
                        inserted += len(batch)
                        batch = []
                except Exception as e:
                    logger.warning(f"Error converting ortho tile {tile_file}: {e}")
                    
    if batch:
        cur.executemany("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?);", batch)
        conn.commit()
        inserted += len(batch)
        
    logger.info(f"Ingested {inserted:,} Coquitlam 7.5cm Orthophoto tiles into satellite.mbtiles.")
    return inserted


def download_tile(
    tile: Tuple[int, int, int],
    layer_config: Dict[str, Any],
    max_retries: int = 3
) -> Optional[Tuple[int, int, int, bytes]]:
    """
    Download a single Slippy tile (z, x, y) from the configured source.
    Returns (z, x, tile_row, tile_data) or None.
    """
    z, x, y = tile
    y_tms = (1 << z) - 1 - y
    
    url_template = layer_config["url_template"]
    subdomains = layer_config.get("subdomains", [""])
    subdomain = random.choice(subdomains) if subdomains else ""
    
    if "{s}" in url_template:
        url = url_template.format(s=subdomain, z=z, x=x, y=y)
    elif "{y}" in url_template and "{x}" in url_template:
        # ArcGIS MapServer uses {z}/{y}/{x}
        if "MapServer" in url_template:
            url = url_template.format(z=z, y=y, x=x)
        else:
            url = url_template.format(z=z, x=x, y=y)
    else:
        url = url_template.format(z=z, x=x, y=y)
    
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/jpeg,image/png,image/*;q=0.9,*/*;q=0.8"
        }
    )
    
    target_format = layer_config["format"]
    
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = resp.read()
                    if len(data) < 50:
                        return None
                    
                    # Convert PNG to JPEG 85 if target format is jpg/jpeg
                    if target_format in ('jpg', 'jpeg') and (data[:8] == b'\x89PNG\r\n\x1a\n'):
                        try:
                            im = Image.open(io.BytesIO(data)).convert('RGB')
                            buf = io.BytesIO()
                            im.save(buf, format='JPEG', quality=85)
                            data = buf.getvalue()
                        except Exception:
                            pass
                    
                    return (z, x, y_tms, data)
        except Exception:
            if attempt < max_retries:
                time.sleep(0.2 * (2 ** (attempt - 1)))
                
    return None


def compile_layer(
    layer_name: str,
    output_mbtiles: str,
    loose_dir: Optional[str] = None,
    raw_ortho_dir: Optional[str] = None,
    workers: int = 32,
    skip_downloads: bool = False
):
    """Compiles the complete MBTiles archive for a specific layer."""
    config = LAYER_CONFIGS[layer_name]
    logger.info("=" * 70)
    logger.info(f" COMPILING MBTILES ARCHIVE: {layer_name}.mbtiles")
    logger.info("=" * 70)
    logger.info(f" Target Path  : {output_mbtiles}")
    logger.info(f" Format       : {config['format'].upper()}")
    logger.info(f" Zoom Levels  : {config['min_zoom']} -> {config['max_zoom']}")
    logger.info("=" * 70)
    
    conn = init_mbtiles_db(output_mbtiles, layer_name, config)
    
    # 1. Ingest loose tiles if directory provided
    if loose_dir and os.path.exists(loose_dir):
        ingest_loose_disk_tiles(conn, loose_dir, target_format=config["format"])
        
    # 2. Ingest ortho tiles if satellite layer and raw_ortho_dir provided
    if layer_name == "satellite" and raw_ortho_dir and os.path.exists(raw_ortho_dir):
        ingest_tms_ortho_tiles(conn, raw_ortho_dir)
        
    existing_keys = get_existing_tile_keys(conn)
    logger.info(f"Current existing tiles in database: {len(existing_keys):,}")
    
    if skip_downloads:
        logger.info("Skip downloads requested. Finalizing archive...")
        conn.close()
        return
        
    # 3. Calculate missing tiles to download
    tiles_to_download = []
    min_z, max_z = config["min_zoom"], config["max_zoom"]
    
    for z in range(min_z, max_z + 1):
        if z <= 16:
            # Full regional bounds for Zooms 12-16
            z_tiles = calculate_tiles(REGIONAL_MIN_LAT, REGIONAL_MIN_LON, REGIONAL_MAX_LAT, REGIONAL_MAX_LON, z)
        elif z <= 18:
            # Coquitlam operational corridor for Zooms 17-18
            z_tiles = calculate_tiles(COQUITLAM_MIN_LAT, COQUITLAM_MIN_LON, COQUITLAM_MAX_LAT, COQUITLAM_MAX_LON, z)
        else:
            # Urban Core & Apparatus Bay Stations 1-4 Corridor for Zooms 19-20
            z_tiles = calculate_tiles(URBAN_CORE_MIN_LAT, URBAN_CORE_MIN_LON, URBAN_CORE_MAX_LAT, URBAN_CORE_MAX_LON, z)
            
        for t in z_tiles:
            tz, tx, ty = t
            t_tms = (1 << tz) - 1 - ty
            if (tz, tx, t_tms) not in existing_keys:
                tiles_to_download.append(t)
                
    logger.info(f"Missing tiles to fetch from remote: {len(tiles_to_download):,}")
    
    if not tiles_to_download:
        logger.info("All target tiles already present in MBTiles archive!")
    else:
        logger.info(f"Downloading {len(tiles_to_download):,} tiles using {workers} concurrent workers...")
        start_t = time.time()
        downloaded = 0
        failed = 0
        batch = []
        cur = conn.cursor()
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_tile = {
                executor.submit(download_tile, t, config): t
                for t in tiles_to_download
            }
            
            for future in as_completed(future_to_tile):
                res = future.result()
                if res is not None:
                    batch.append(res)
                    downloaded += 1
                    if len(batch) >= 500:
                        cur.executemany("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?);", batch)
                        conn.commit()
                        batch = []
                else:
                    failed += 1
                    
                total_done = downloaded + failed
                if total_done % 200 == 0 or total_done == len(tiles_to_download):
                    elapsed = time.time() - start_t
                    rate = total_done / elapsed if elapsed > 0 else 0
                    pct = (total_done / len(tiles_to_download)) * 100
                    sys.stdout.write(
                        f"\r Progress: {total_done:,}/{len(tiles_to_download):,} ({pct:5.1f}%) | "
                        f"[+] {downloaded:,} ok | [x] {failed:,} fail | {rate:4.1f} tiles/s"
                    )
                    sys.stdout.flush()
                    
        if batch:
            cur.executemany("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?);", batch)
            conn.commit()
            
        elapsed = time.time() - start_t
        print(f"\nDownload phase complete: {downloaded:,} downloaded in {elapsed:.1f}s ({downloaded/elapsed:.1f} tiles/s).")
        
    # Final database summary & vacuum
    cur = conn.cursor()
    cur.execute("SELECT zoom_level, count(*) FROM tiles GROUP BY zoom_level ORDER BY zoom_level;")
    zoom_stats = cur.fetchall()
    
    logger.info("=" * 70)
    logger.info(f" MBTILES COMPILATION SUMMARY [{layer_name}.mbtiles]")
    logger.info("=" * 70)
    total_db_tiles = 0
    for z, cnt in zoom_stats:
        total_db_tiles += cnt
        logger.info(f"  * Zoom {z:>2}: {cnt:>7,} tiles")
        
    file_size_mb = os.path.getsize(output_mbtiles) / (1024 * 1024)
    logger.info(f" Total Tiles in Archive : {total_db_tiles:,}")
    logger.info(f" Final Archive File Size: {file_size_mb:.2f} MB")
    logger.info("=" * 70)
    
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Compile centralized MBTiles archives for CFR EVO.")
    parser.add_argument(
        "--layer",
        choices=["all", "satellite", "street", "street_nolabels"],
        default="all",
        help="Layer(s) to compile (default: all)"
    )
    parser.add_argument(
        "--tiles-dir",
        type=str,
        default=None,
        help="Base tiles directory (default: backend/data/tiles)"
    )
    parser.add_argument(
        "--raw-ortho-dir",
        type=str,
        default="/home/tcfire/data_staging/raw_tiles",
        help="Directory with raw TMS orthophoto tiles from gdal2tiles"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=32,
        help="Number of concurrent worker threads (default: 32)"
    )
    parser.add_argument(
        "--skip-downloads",
        action="store_true",
        help="Only compile from local files without downloading missing tiles"
    )
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    tiles_base = Path(args.tiles_dir).resolve() if args.tiles_dir else repo_root / "data" / "tiles"
    tiles_base.mkdir(parents=True, exist_ok=True)
    
    layers = ["street", "street_nolabels", "satellite"] if args.layer == "all" else [args.layer]
    
    for layer in layers:
        output_file = str(tiles_base / f"{layer}.mbtiles")
        loose_dir = str(tiles_base / layer)
        compile_layer(
            layer_name=layer,
            output_mbtiles=output_file,
            loose_dir=loose_dir,
            raw_ortho_dir=args.raw_ortho_dir,
            workers=args.workers,
            skip_downloads=args.skip_downloads
        )
        

if __name__ == "__main__":
    main()
