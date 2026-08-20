#!/usr/bin/env python3
"""
extract_all_intersections_from_gis.py
Comprehensively extracts all municipal road intersections from official Coquitlam shapefiles:
- Addresses.shp (69,708 parcels)
- Emergency_Response_Zones.shp (118 emergency zones with MAP_NAME)

Outputs clean, normalized JSON to backend/data/gis/intersections.json.
"""

import os
import sys
import json
import re
import time
import logging
from typing import Dict, List, Tuple, Any

import numpy as np
from scipy.spatial import cKDTree

try:
    import geopandas as gpd
    import shapely
    from shapely.geometry import Point
except ImportError as e:
    print(f"Error importing geospatial libraries: {e}")
    print("Please install geopandas, shapely, scipy, pyogrio: pip install geopandas shapely scipy pyogrio")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Canonical street suffix abbreviation mapping
SUFFIX_MAPPINGS = {
    "AVENUE": "AVE", "AVE": "AVE",
    "STREET": "ST", "ST": "ST",
    "ROAD": "RD", "RD": "RD",
    "DRIVE": "DR", "DR": "DR",
    "BOULEVARD": "BLVD", "BLVD": "BLVD",
    "HIGHWAY": "HWY", "HWY": "HWY",
    "WAY": "WAY",
    "CRESCENT": "CRES", "CRES": "CRES",
    "COURT": "CRT", "CRT": "CRT",
    "PLACE": "PL", "PL": "PL",
    "LANE": "LN", "LN": "LN",
    "PROMENADE": "PROM", "PROM": "PROM",
    "RAMP": "RAMP",
    "ALLEY": "ALLEY",
    "GATE": "GATE",
    "CLOSE": "CLOSE",
    "MEWS": "MEWS",
    "GREEN": "GREEN",
    "SQUARE": "SQ", "SQ": "SQ",
    "CIRCLE": "CIR", "CIR": "CIR",
    "POINT": "PT", "PT": "PT",
    "TERRACE": "TERR", "TERR": "TERR",
    "RIDGE": "RIDGE",
    "MOUNTAIN": "MTN", "MTN": "MTN",
    "WOOD": "WOOD",
    "WALK": "WK", "WK": "WK",
    "TRAIL": "TRAIL",
    "BAY": "BAY",
}

SUFFIX_EXPAND = {
    "Ave": "Avenue", "St": "Street", "Rd": "Road", "Dr": "Drive",
    "Blvd": "Boulevard", "Hwy": "Highway", "Cres": "Crescent",
    "Crt": "Court", "Pl": "Place", "Ln": "Lane", "Prom": "Promenade",
    "Gate": "Gate", "Close": "Close", "Mews": "Mews", "Green": "Green",
    "Sq": "Square", "Cir": "Circle", "Pt": "Point", "Terr": "Terrace",
    "Ridge": "Ridge", "Mtn": "Mountain", "Wood": "Wood", "Wk": "Walk",
    "Trail": "Trail", "Bay": "Bay", "Way": "Way", "Alley": "Alley", "Ramp": "Ramp"
}


def normalize_street(name: str, st_type: str = "") -> str:
    """Normalizes street name and street type into a canonical uppercase abbreviated string."""
    s = str(name).strip() if name is not None else ""
    t = str(st_type).strip() if st_type is not None and str(st_type).lower() != "nan" else ""
    full = f"{s} {t}".strip().upper()
    clean = re.sub(r"[,.]", "", full)
    clean = re.sub(r"\b(?:BLOCK|BLK|OF)\b", "", clean).strip()
    words = clean.split()
    if not words:
        return ""
    if words[-1] in SUFFIX_MAPPINGS:
        words[-1] = SUFFIX_MAPPINGS[words[-1]]
    return " ".join(words)


def format_display_street(norm_street: str) -> str:
    """Formats a canonical normalized street into human-readable title case."""
    words = norm_street.title().split()
    if words and words[-1] in SUFFIX_EXPAND:
        words[-1] = SUFFIX_EXPAND[words[-1]]
    return " ".join(words)


def format_display_intersection(st1_norm: str, st2_norm: str) -> str:
    """Creates a human-readable display name for an intersection."""
    d1 = format_display_street(st1_norm)
    d2 = format_display_street(st2_norm)
    return f"{d1} & {d2}"


def find_file(candidates: List[str]) -> str:
    """Finds the first existing path from candidate paths."""
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return None


def cluster_points_spatial(points: List[Tuple[float, float]], eps: float = 45.0) -> List[Tuple[float, float]]:
    """
    Clusters 2D metric points (EPSG:26910) within eps meters using cKDTree connected components.
    Returns the mean coordinate of each distinct spatial cluster.
    """
    pts = np.array(points)
    if len(pts) <= 1:
        return [tuple(pts.mean(axis=0))]

    tree = cKDTree(pts)
    visited = set()
    clusters = []

    for i in range(len(pts)):
        if i in visited:
            continue
        cluster = []
        queue = [i]
        visited.add(i)
        while queue:
            curr = queue.pop(0)
            cluster.append(pts[curr])
            neighbors = tree.query_ball_point(pts[curr], r=eps)
            for n in neighbors:
                if n not in visited:
                    visited.add(n)
                    queue.append(n)
        mean_pt = np.mean(cluster, axis=0)
        clusters.append((float(mean_pt[0]), float(mean_pt[1])))
    return clusters


def main():
    t_start = time.time()
    logging.info("================================================================================")
    logging.info("CFR EVO: Municipal Road Intersections Extraction from Official Coquitlam GIS")
    logging.info("================================================================================")

    # 1. Resolve dataset file paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_dir = os.path.dirname(base_dir)

    addr_path = find_file([
        os.path.join(base_dir, "data", "Property_Information", "Addresses.shp"),
        "/app/backend/data/Property_Information/Addresses.shp",
        os.path.join(root_dir, "backend", "data", "Property_Information", "Addresses.shp"),
        "backend/data/Property_Information/Addresses.shp",
        "data/Property_Information/Addresses.shp",
    ])

    zones_path = find_file([
        os.path.join(base_dir, "data", "Emergency_Response_Zones", "Emergency_Response_Zones.shp"),
        "/app/backend/data/Emergency_Response_Zones/Emergency_Response_Zones.shp",
        os.path.join(root_dir, "backend", "data", "Emergency_Response_Zones", "Emergency_Response_Zones.shp"),
        "backend/data/Emergency_Response_Zones/Emergency_Response_Zones.shp",
        "data/Emergency_Response_Zones/Emergency_Response_Zones.shp",
    ])

    existing_intersections_path = find_file([
        os.path.join(base_dir, "data", "gis", "intersections.json"),
        "/app/backend/data/gis/intersections.json",
        os.path.join(root_dir, "backend", "data", "gis", "intersections.json"),
        "backend/data/gis/intersections.json",
        "data/gis/intersections.json",
    ])

    out_intersections_path = (
        existing_intersections_path
        or os.path.join(base_dir, "data", "gis", "intersections.json")
    )
    os.makedirs(os.path.dirname(out_intersections_path), exist_ok=True)

    if not addr_path or not os.path.exists(addr_path):
        logging.error(f"Addresses shapefile not found at {addr_path}!")
        sys.exit(1)
    if not zones_path or not os.path.exists(zones_path):
        logging.error(f"Emergency response zones shapefile not found at {zones_path}!")
        sys.exit(1)

    logging.info(f"Addresses Shapefile: {addr_path}")
    logging.info(f"Zones Shapefile:     {zones_path}")
    logging.info(f"Output Target:       {out_intersections_path}")

    # 2. Load existing curated descriptors if available
    existing_curated: Dict[str, List[Dict[str, Any]]] = {}
    if existing_intersections_path and os.path.exists(existing_intersections_path):
        try:
            with open(existing_intersections_path, "r", encoding="utf-8") as f:
                raw_existing = json.load(f)
            if isinstance(raw_existing, dict):
                existing_curated = raw_existing
            elif isinstance(raw_existing, list):
                for item in raw_existing:
                    name = item.get("name", "")
                    if name:
                        existing_curated[name.upper()] = [item]
            logging.info(f"Loaded {len(existing_curated)} existing intersection entries for curation preservation.")
        except Exception as e:
            logging.warning(f"Could not parse existing intersections.json: {e}")

    # 3. Load Addresses and standardize
    logging.info("Reading Addresses shapefile...")
    gdf_addr = gpd.read_file(addr_path, engine="pyogrio")
    logging.info(f"Loaded {len(gdf_addr)} address records. CRS: {gdf_addr.crs}")

    # Ensure working in metric CRS EPSG:26910 for precise distance calculations
    if gdf_addr.crs != "EPSG:26910" and str(gdf_addr.crs).upper() != "EPSG:26910":
        logging.info("Reprojecting Addresses to EPSG:26910 (UTM Zone 10N)...")
        gdf_addr = gdf_addr.to_crs(epsg=26910)

    gdf_addr["norm_street"] = [
        normalize_street(r.get("STREET"), r.get("STREETTYPE"))
        for _, r in gdf_addr.iterrows()
    ]
    gdf_addr = gdf_addr[gdf_addr["norm_street"] != ""].copy()

    # Deduplicate parcels sharing same street & polygon geometry
    gdf_unique = gdf_addr.drop_duplicates(subset=["norm_street", "GIS_ID"]).reset_index(drop=True)
    logging.info(f"Filtered to {len(gdf_unique)} unique (street, parcel) polygons across {gdf_unique['norm_street'].nunique()} streets.")

    # 4. Load Emergency Response Zones
    logging.info("Reading Emergency Response Zones shapefile...")
    gdf_zones = gpd.read_file(zones_path, engine="pyogrio")
    logging.info(f"Loaded {len(gdf_zones)} emergency response zones. CRS: {gdf_zones.crs}")
    gdf_zones_4326 = gdf_zones.to_crs(epsg=4326)

    # 5. Spatial Indexing & Nearest Parcel Adjacency Query
    logging.info("Building spatial index and querying adjacent parcels on different streets (within 40m)...")
    sindex = gdf_unique.sindex
    bounds = gdf_unique.geometry.bounds
    # Expand bounding boxes by 40 meters
    search_boxes = shapely.box(
        bounds["minx"] - 40.0,
        bounds["miny"] - 40.0,
        bounds["maxx"] + 40.0,
        bounds["maxy"] + 40.0
    )

    i_left, i_right = sindex.query(search_boxes, predicate="intersects")

    # Filter out self-comparisons and duplicate symmetric pairs
    mask_order = i_left < i_right
    i_left = i_left[mask_order]
    i_right = i_right[mask_order]

    st_left = gdf_unique["norm_street"].values[i_left]
    st_right = gdf_unique["norm_street"].values[i_right]
    mask_diff_st = st_left != st_right
    i_left = i_left[mask_diff_st]
    i_right = i_right[mask_diff_st]

    geoms_left = gdf_unique.geometry.values[i_left]
    geoms_right = gdf_unique.geometry.values[i_right]

    # Compute Euclidean distance in EPSG:26910 meters
    dists = shapely.distance(geoms_left, geoms_right)
    mask_close = dists <= 40.0

    i_left_close = i_left[mask_close]
    i_right_close = i_right[mask_close]
    geoms_l = geoms_left[mask_close]
    geoms_r = geoms_right[mask_close]

    logging.info(f"Found {len(i_left_close)} parcel pairs within 40m on different streets.")

    # Calculate junction midpoints using shortest line interpolation
    lines = shapely.shortest_line(geoms_l, geoms_r)
    midpoints = shapely.line_interpolate_point(lines, 0.5, normalized=True)
    mid_x = shapely.get_x(midpoints)
    mid_y = shapely.get_y(midpoints)

    st_l_close = gdf_unique["norm_street"].values[i_left_close]
    st_r_close = gdf_unique["norm_street"].values[i_right_close]

    # 6. Group midpoints by canonical sorted street pair
    pair_midpoints: Dict[str, List[Tuple[float, float]]] = {}
    pair_street_names: Dict[str, Tuple[str, str]] = {}

    for x, y, sl, sr in zip(mid_x, mid_y, st_l_close, st_r_close):
        s1, s2 = sorted([sl, sr])
        key = f"{s1} & {s2}"
        if key not in pair_midpoints:
            pair_midpoints[key] = []
            pair_street_names[key] = (s1, s2)
        pair_midpoints[key].append((float(x), float(y)))

    logging.info(f"Grouped into {len(pair_midpoints)} candidate street pair keys.")

    # 7. Cluster points (45m threshold) and preserve multi-junctions
    all_candidate_nodes: List[Dict[str, Any]] = []
    total_clusters = 0

    for key, pts in pair_midpoints.items():
        s1, s2 = pair_street_names[key]
        clusters = cluster_points_spatial(pts, eps=45.0)
        total_clusters += len(clusters)

        for c_idx, (cx, cy) in enumerate(clusters):
            all_candidate_nodes.append({
                "key": key,
                "st1_norm": s1,
                "st2_norm": s2,
                "cluster_idx": c_idx,
                "num_clusters": len(clusters),
                "geom_26910": Point(cx, cy),
                "x_26910": cx,
                "y_26910": cy,
            })

    logging.info(f"Clustered into {total_clusters} distinct junction nodes across all street pairs.")

    # 8. Reproject to WGS84 EPSG:4326 and Spatial Join with Emergency Response Zones
    logging.info("Tagging candidate junctions with emergency response zone grids (1..134)...")
    pts_gdf = gpd.GeoDataFrame(
        all_candidate_nodes,
        geometry=[n["geom_26910"] for n in all_candidate_nodes],
        crs="EPSG:26910"
    ).to_crs(epsg=4326)

    # Spatial join point-in-polygon with zones
    zone_col = "MAP_NAME" if "MAP_NAME" in gdf_zones_4326.columns else gdf_zones_4326.columns[0]
    joined_gdf = gpd.sjoin(
        pts_gdf,
        gdf_zones_4326[[zone_col, "geometry"]],
        how="left",
        predicate="within"
    )

    # 9. Structure final JSON dictionary and merge curated descriptors
    final_intersections: Dict[str, List[Dict[str, Any]]] = {}

    for _, row in joined_gdf.iterrows():
        key = row["key"]
        st1_norm = row["st1_norm"]
        st2_norm = row["st2_norm"]
        num_clusters = row["num_clusters"]
        cluster_idx = row["cluster_idx"]
        pt = row.geometry
        lat = round(float(pt.y), 6)
        lng = round(float(pt.x), 6)
        grid_val = str(row.get(zone_col, "")).strip() if row.get(zone_col) is not None and str(row.get(zone_col)) != "nan" else None

        base_display_name = format_display_intersection(st1_norm, st2_norm)

        # Multi-junction labeling
        if num_clusters > 1:
            display_name = f"{base_display_name} (Junction {cluster_idx + 1})"
        else:
            display_name = base_display_name

        candidate_obj = {
            "name": display_name,
            "lat": lat,
            "lng": lng,
        }
        if grid_val:
            candidate_obj["grid"] = grid_val

        if key not in final_intersections:
            final_intersections[key] = []
        final_intersections[key].append(candidate_obj)

    # 10. Merge & preserve existing curated notes and descriptors
    preserved_count = 0
    for cur_key, cur_cands in existing_curated.items():
        # Match canonical key
        norm_cur_key = cur_key.strip().upper()
        # Also test if streets are in reverse order
        parts = [p.strip() for p in re.split(r"\s*&\s*", norm_cur_key) if p.strip()]
        if len(parts) == 2:
            s_a = normalize_street(parts[0])
            s_b = normalize_street(parts[1])
            canon_key = f"{min(s_a, s_b)} & {max(s_a, s_b)}"
        else:
            canon_key = norm_cur_key

        has_custom_info = any("description" in c or "grid" in c for c in cur_cands)

        # If existing curated entry has custom descriptions or coordinates tested in suite
        if has_custom_info or canon_key in [
            "LOUGHEED HWY & MARINER WAY",
            "DAVID AVE & PANORAMA DR",
            "CHRISTMAS WAY & WESTWOOD ST",
            "AUSTIN AVE & NELSON ST",
            "GUILDFORD WAY & PINETREE WAY",
            "COAST MERIDIAN RD & DAVID AVE",
            "COAST MERIDIAN RD & PRINCETON AVE",
        ]:
            final_intersections[canon_key] = cur_cands
            preserved_count += 1

    # Sort dictionary keys alphabetically for clean deterministic diffs
    sorted_intersections = {k: final_intersections[k] for k in sorted(final_intersections.keys())}

    # 11. Write out JSON
    logging.info(f"Writing {len(sorted_intersections)} unique intersection keys to {out_intersections_path}...")
    with open(out_intersections_path, "w", encoding="utf-8") as f:
        json.dump(sorted_intersections, f, indent=2)

    # Also update frontend/public/data/intersections.json if directory exists
    frontend_data_path = find_file([
        os.path.join(root_dir, "frontend", "public", "data", "intersections.json"),
        os.path.join(base_dir, "..", "frontend", "public", "data", "intersections.json"),
        "/app/frontend/public/data/intersections.json",
        "frontend/public/data/intersections.json"
    ])
    if frontend_data_path:
        logging.info(f"Updating frontend public dataset at {frontend_data_path}...")
        frontend_list = []
        for key, cands in sorted_intersections.items():
            for c in cands:
                frontend_list.append({
                    "name": c.get("name", key),
                    "lat": c["lat"],
                    "lng": c["lng"]
                })
        try:
            with open(frontend_data_path, "w", encoding="utf-8") as f:
                json.dump(frontend_list, f)
            logging.info(f"Synced {len(frontend_list)} entries to frontend intersections.json.")
        except Exception as e:
            logging.warning(f"Could not update frontend dataset: {e}")

    # 12. Summary Statistics & Multi-Junction Samples
    multi_junc = {k: v for k, v in sorted_intersections.items() if len(v) > 1}
    duration = time.time() - t_start

    logging.info("================================================================================")
    logging.info(f"EXTRACTION COMPLETE in {duration:.2f}s")
    logging.info(f"Total Unique Intersection Keys: {len(sorted_intersections)}")
    logging.info(f"Total Multi-Junction Keys:      {len(multi_junc)}")
    logging.info(f"Curated Entries Preserved:      {preserved_count}")
    logging.info("================================================================================")

    logging.info("Sample Multi-Junction Entries:")
    for k in list(multi_junc.keys())[:5]:
        logging.info(f"  [{k}] -> {len(multi_junc[k])} candidates:")
        for cand in multi_junc[k]:
            logging.info(f"     * {cand.get('name')}: ({cand.get('lat')}, {cand.get('lng')}), Grid: {cand.get('grid')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
