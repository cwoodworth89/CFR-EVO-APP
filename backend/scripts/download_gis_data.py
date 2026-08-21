"""
download_gis_data.py - Coquitlam ArcGIS REST API Downloader

Downloads authoritative municipal GIS datasets from geodata.coquitlam.ca:
1. Road Centre Lines (Transportation Layer 16) -> road_centre_lines.geojson (paginated)
2. Road Names (AddressSearch Layer 2) -> road_names.json (paginated/merged)
3. City Boundary (Cadastral Layer 14) -> city_boundary.geojson
4. Emergency Response Zones (Planning Layer 6) -> emergency_zones.geojson

Saves output files to backend/data/staging/.
"""

import os
import sys
import json
import time
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def fetch_with_retry(url: str, params: dict, max_retries: int = 3, timeout: int = 30) -> dict:
    """Performs HTTP GET with exponential backoff retry."""
    headers = {"User-Agent": "CFR-EVO-GIS-Downloader/1.0"}
    backoff = [2, 4, 8]
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"ArcGIS REST Error: {data['error']}")
            return data
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = backoff[attempt] if attempt < len(backoff) else 8
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Request failed after {max_retries} attempts: {e}")
                raise


def download_road_centre_lines(staging_dir: str) -> int:
    """
    Downloads Road Centre Lines from Transportation service (Layer 16).
    Paginates with resultOffset/resultRecordCount to retrieve all records.
    Saves as a single GeoJSON FeatureCollection to road_centre_lines.geojson.
    """
    url = "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Transportation/MapServer/16/query"
    output_file = os.path.join(staging_dir, "road_centre_lines.geojson")
    offset = 0
    limit = 1000
    all_features = []

    logger.info("Downloading Road Centre Lines (Transportation Layer 16)...")
    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "outSR": "4326",
            "returnGeometry": "true",
            "resultOffset": str(offset),
            "resultRecordCount": str(limit),
            "f": "geojson"
        }
        data = fetch_with_retry(url, params)
        features = data.get("features", [])
        if not features:
            break
        all_features.extend(features)
        logger.info(f"  • Road Centre Lines: fetched {len(features)} features (offset {offset}, total: {len(all_features)})")
        if len(features) < limit:
            break
        offset += limit

    fc = {
        "type": "FeatureCollection",
        "features": all_features
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(fc, f, indent=2)

    logger.info(f"✓ Successfully saved {len(all_features)} Road Centre Lines to {output_file}")
    return len(all_features)


def download_road_names(staging_dir: str) -> int:
    """
    Downloads Road Names from AddressSearch service (Layer 2).
    Paginates across records and saves full response to road_names.json.
    """
    url = "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/AddressSearch/MapServer/2/query"
    output_file = os.path.join(staging_dir, "road_names.json")
    offset = 0
    limit = 1000
    all_features = []
    base_response = None

    logger.info("Downloading Road Names (AddressSearch Layer 2)...")
    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "resultOffset": str(offset),
            "resultRecordCount": str(limit),
            "f": "pjson"
        }
        data = fetch_with_retry(url, params)
        if base_response is None:
            base_response = data
        features = data.get("features", [])
        if not features:
            break
        all_features.extend(features)
        logger.info(f"  • Road Names: fetched {len(features)} records (offset {offset}, total: {len(all_features)})")
        if len(features) < limit:
            break
        offset += limit

    if base_response is None:
        base_response = {}
    base_response["features"] = all_features
    if "exceededTransferLimit" in base_response:
        del base_response["exceededTransferLimit"]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(base_response, f, indent=2)

    logger.info(f"✓ Successfully saved {len(all_features)} Road Names to {output_file}")
    return len(all_features)


def download_city_boundary(staging_dir: str) -> int:
    """
    Downloads City Boundary polygon from Cadastral service (Layer 14).
    Saves as GeoJSON FeatureCollection to city_boundary.geojson.
    """
    url = "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Cadastral/MapServer/14/query"
    output_file = os.path.join(staging_dir, "city_boundary.geojson")

    logger.info("Downloading City Boundary (Cadastral Layer 14)...")
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "geojson"
    }
    data = fetch_with_retry(url, params)
    features = data.get("features", [])

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info(f"✓ Successfully saved {len(features)} City Boundary feature(s) to {output_file}")
    return len(features)


def download_emergency_zones(staging_dir: str) -> int:
    """
    Downloads Emergency Response Zones polygons from Planning service (Layer 6).
    Saves as GeoJSON FeatureCollection to emergency_zones.geojson.
    """
    url = "https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Planning/MapServer/6/query"
    output_file = os.path.join(staging_dir, "emergency_zones.geojson")

    logger.info("Downloading Emergency Response Zones (Planning Layer 6)...")
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "geojson"
    }
    data = fetch_with_retry(url, params)
    features = data.get("features", [])

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info(f"✓ Successfully saved {len(features)} Emergency Response Zones to {output_file}")
    return len(features)


def download_all(staging_dir: str = None) -> dict[str, int]:
    """Downloads all 4 municipal GIS datasets into staging directory."""
    if staging_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        staging_dir = os.path.abspath(os.path.join(script_dir, "..", "data", "staging"))

    os.makedirs(staging_dir, exist_ok=True)
    logger.info(f"Starting GIS data download to staging directory: {staging_dir}")

    results = {}
    results["road_centre_lines"] = download_road_centre_lines(staging_dir)
    results["road_names"] = download_road_names(staging_dir)
    results["city_boundary"] = download_city_boundary(staging_dir)
    results["emergency_zones"] = download_emergency_zones(staging_dir)

    logger.info("=" * 60)
    logger.info("GIS DATA DOWNLOAD SUMMARY:")
    for dataset, count in results.items():
        logger.info(f"  • {dataset}: {count} records/features")
    logger.info("=" * 60)
    return results


if __name__ == "__main__":
    try:
        staging_override = sys.argv[1] if len(sys.argv) > 1 else None
        results = download_all(staging_override)
        sys.exit(0)
    except Exception as exc:
        logger.exception(f"GIS Data Download failed: {exc}")
        sys.exit(1)
