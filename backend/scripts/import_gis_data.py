#!/usr/bin/env python3
"""
backend/scripts/import_gis_data.py
Master GIS Ingestion & PostGIS Data Pipeline for CFR EVO.

Imports authoritative City of Coquitlam GIS layers into containerized PostgreSQL 16 / PostGIS:
  1. PostGIS Extension verification
  2. Road Centre Lines (GeoJSON -> public.roads)
  3. Emergency Response Zones (GeoJSON -> public.zones)
  4. City Boundary (GeoJSON -> public.city_boundary)
  5. Road Names Dictionary (JSON -> public.road_names)
  6. Custom Places (JSON -> public.custom_places)
  7. Radio & Dispatch Vocabulary (.txt -> public.vocabulary)
  8. Topological Road Intersections (Shapely intersection computation -> public.intersections)
  9. Parcel Road Frontage Point Backfill (ST_ClosestPoint)
  10. Parcel Point Geometry Indexing (ST_MakePoint -> public.parcels.geom)
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime
from collections import defaultdict

from sqlalchemy import create_engine, text
from shapely.geometry import shape, Point, MultiPoint, Polygon, MultiPolygon
from shapely.ops import unary_union, transform

# Setup path resolution
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

root_dir = os.path.dirname(backend_dir)
for s in ["gis", "audio", "dispatch_notifications"]:
    p = os.path.join(root_dir, "services", s, "src")
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def get_database_url() -> str:
    """Resolves database URL from environment or default local container."""
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch"
    )
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return db_url


def to_2d(geom):
    """Drops Z/altitude dimension if present, returning standard 2D geometry."""
    if geom is None:
        return None
    if getattr(geom, "has_z", False):
        return transform(lambda x, y, *args: (x, y), geom)
    return geom


def safe_int(val):
    """Safely parses integers from mixed string/float/null values."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "<null>", "null"):
        return None
    if s.isdigit():
        return int(s)
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def safe_bool(val):
    """Safely parses boolean from strings like 'Y', 'YES', 'True', '1'."""
    if val is None:
        return False
    return str(val).strip().upper() in ("YES", "Y", "TRUE", "1")


def ensure_tables(engine):
    """Ensures all required GIS tables and indexes exist prior to import."""
    logging.info("Verifying GIS database schemas...")
    schema_sql = text("""
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";
    CREATE EXTENSION IF NOT EXISTS postgis;

    CREATE TABLE IF NOT EXISTS public.roads (
        id BIGSERIAL PRIMARY KEY,
        fullname VARCHAR(255) NOT NULL,
        roadname VARCHAR(255),
        roadtype VARCHAR(20),
        road_class VARCHAR(10),
        functional_class VARCHAR(10),
        speed INTEGER,
        num_lanes INTEGER,
        truck_route BOOLEAN DEFAULT FALSE,
        bus_route BOOLEAN DEFAULT FALSE,
        status VARCHAR(20) DEFAULT 'OPERATING',
        left_begin INTEGER,
        left_end INTEGER,
        right_begin INTEGER,
        right_end INTEGER,
        geom GEOMETRY(MultiLineString, 4326),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='roads' AND column_name='geom') THEN
            BEGIN
                ALTER TABLE public.roads ALTER COLUMN geom TYPE GEOMETRY(MultiLineString, 4326) USING ST_Multi(geom);
            EXCEPTION WHEN OTHERS THEN
                NULL;
            END;
        END IF;
    END $$;
    CREATE INDEX IF NOT EXISTS idx_roads_fullname ON public.roads (fullname);
    CREATE INDEX IF NOT EXISTS idx_roads_class ON public.roads (road_class);
    CREATE INDEX IF NOT EXISTS idx_roads_geom ON public.roads USING GIST (geom);

    CREATE TABLE IF NOT EXISTS public.intersections (
        id BIGSERIAL PRIMARY KEY,
        street_a VARCHAR(255) NOT NULL,
        street_b VARCHAR(255) NOT NULL,
        intersection_key VARCHAR(511) NOT NULL,
        lat DOUBLE PRECISION NOT NULL,
        lng DOUBLE PRECISION NOT NULL,
        zone_id VARCHAR(16),
        geom GEOMETRY(Point, 4326),
        candidate_index INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_intersections_key ON public.intersections (intersection_key);
    CREATE INDEX IF NOT EXISTS idx_intersections_streets ON public.intersections (street_a, street_b);
    CREATE INDEX IF NOT EXISTS idx_intersections_zone ON public.intersections (zone_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_intersections_unique ON public.intersections (intersection_key, candidate_index);
    CREATE INDEX IF NOT EXISTS idx_intersections_geom ON public.intersections USING GIST (geom);

    CREATE TABLE IF NOT EXISTS public.zones (
        id BIGSERIAL PRIMARY KEY,
        map_name VARCHAR(16) NOT NULL UNIQUE,
        geom GEOMETRY(MultiPolygon, 4326),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_zones_map_name ON public.zones (map_name);
    CREATE INDEX IF NOT EXISTS idx_zones_geom ON public.zones USING GIST (geom);

    CREATE TABLE IF NOT EXISTS public.city_boundary (
        id BIGSERIAL PRIMARY KEY,
        name VARCHAR(100) DEFAULT 'City of Coquitlam',
        geom GEOMETRY(MultiPolygon, 4326),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_city_boundary_geom ON public.city_boundary USING GIST (geom);

    CREATE TABLE IF NOT EXISTS public.road_names (
        id BIGSERIAL PRIMARY KEY,
        road_name VARCHAR(255) NOT NULL UNIQUE,
        road_name_normalized VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_road_names_normalized ON public.road_names (road_name_normalized);

    CREATE TABLE IF NOT EXISTS public.custom_places (
        id BIGSERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        name_normalized VARCHAR(255),
        address VARCHAR(255),
        lat DOUBLE PRECISION NOT NULL,
        lng DOUBLE PRECISION NOT NULL,
        geom GEOMETRY(Point, 4326),
        category VARCHAR(50),
        metadata JSONB,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_custom_places_name ON public.custom_places (name_normalized);
    CREATE INDEX IF NOT EXISTS idx_custom_places_geom ON public.custom_places USING GIST (geom);

    CREATE TABLE IF NOT EXISTS public.vocabulary (
        id BIGSERIAL PRIMARY KEY,
        category VARCHAR(50) NOT NULL,
        term VARCHAR(255) NOT NULL,
        term_normalized VARCHAR(255),
        sort_order INTEGER DEFAULT 0,
        source VARCHAR(20) DEFAULT 'import',
        is_active BOOLEAN DEFAULT TRUE,
        metadata JSONB,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_vocab_category ON public.vocabulary (category);
    CREATE INDEX IF NOT EXISTS idx_vocab_term ON public.vocabulary (term_normalized);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_vocab_unique ON public.vocabulary (category, term);
    """)
    with engine.begin() as conn:
        conn.execute(schema_sql)


def step1_ensure_postgis(engine) -> bool:
    """Step 1: Ensure PostGIS Extension is installed."""
    logging.info("=" * 60)
    logging.info("Step 1: Ensuring PostGIS & pgcrypto extensions...")
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";"))
        logging.info("  ✓ PostGIS extension enabled successfully.")
        return True
    except Exception as e:
        logging.error(f"  ✗ Failed to enable PostGIS extension: {e}")
        return False


def step2_import_roads(engine, roads_geojson_path: str, batch_size: int = 500) -> tuple:
    """Step 2: Import Roads -> public.roads from GeoJSON."""
    logging.info("=" * 60)
    logging.info("Step 2: Importing Road Centre Lines -> public.roads...")
    if not os.path.exists(roads_geojson_path):
        logging.error(f"  ✗ Roads GeoJSON not found at: {roads_geojson_path}")
        return 0, []

    try:
        with open(roads_geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        features = data.get("features", [])
        logging.info(f"  Loaded {len(features)} total road features from GeoJSON.")

        records_to_insert = []
        operating_features = []

        for feature in features:
            props = feature.get("properties", {})
            status = props.get("STATUS")
            if status and str(status).strip().upper() != "OPERATING":
                continue

            fullname = props.get("FULLNAME") or props.get("fullname")
            if not fullname or not str(fullname).strip():
                continue
            fullname = str(fullname).strip()

            geom_obj = shape(feature["geometry"])
            geom_2d = to_2d(geom_obj)
            wkt = geom_2d.wkt

            records_to_insert.append({
                "fullname": fullname,
                "roadname": props.get("ROADNAME") or props.get("roadname"),
                "roadtype": props.get("ROADTYPE") or props.get("roadtype"),
                "road_class": props.get("CLASS") or props.get("road_class"),
                "functional_class": props.get("FUNCTIONAL_CLASS") or props.get("functional_class"),
                "speed": safe_int(props.get("SPEED")),
                "num_lanes": safe_int(props.get("NUM_LANES")),
                "truck_route": safe_bool(props.get("TRUCKROUTE")),
                "bus_route": safe_bool(props.get("BUSROUTE")),
                "status": status or "OPERATING",
                "left_begin": safe_int(props.get("LEFTBEGIN")),
                "left_end": safe_int(props.get("LEFTEND")),
                "right_begin": safe_int(props.get("RIGHTBEGIN")),
                "right_end": safe_int(props.get("RIGHTEND")),
                "wkt": wkt
            })
            operating_features.append(feature)

        insert_sql = text("""
        INSERT INTO public.roads (
            fullname, roadname, roadtype, road_class, functional_class,
            speed, num_lanes, truck_route, bus_route, status,
            left_begin, left_end, right_begin, right_end,
            geom
        ) VALUES (
            :fullname, :roadname, :roadtype, :road_class, :functional_class,
            :speed, :num_lanes, :truck_route, :bus_route, :status,
            :left_begin, :left_end, :right_begin, :right_end,
            ST_Multi(ST_Force2D(ST_GeomFromText(:wkt, 4326)))
        );
        """)

        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE public.roads RESTART IDENTITY CASCADE;"))
            for i in range(0, len(records_to_insert), batch_size):
                batch = records_to_insert[i:i + batch_size]
                conn.execute(insert_sql, batch)

        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM public.roads;")).scalar()

        logging.info(f"  ✓ Successfully imported {count} operating roads into public.roads.")
        return count, operating_features
    except Exception as e:
        logging.error(f"  ✗ Step 2 error importing roads: {e}")
        return 0, []


def step3_import_zones(engine, zones_geojson_path: str, batch_size: int = 500) -> int:
    """Step 3: Import Emergency Response Zones -> public.zones."""
    logging.info("=" * 60)
    logging.info("Step 3: Importing Emergency Zones -> public.zones...")
    if not os.path.exists(zones_geojson_path):
        logging.error(f"  ✗ Emergency Zones GeoJSON not found at: {zones_geojson_path}")
        return 0

    try:
        with open(zones_geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        features = data.get("features", [])

        records = []
        for feat in features:
            props = feat.get("properties", {})
            map_name = str(props.get("MAP_NAME", "")).strip()
            if not map_name:
                continue

            geom_obj = shape(feat["geometry"])
            geom_2d = to_2d(geom_obj)
            wkt = geom_2d.wkt

            records.append({
                "map_name": map_name,
                "wkt": wkt
            })

        insert_sql = text("""
        INSERT INTO public.zones (map_name, geom)
        VALUES (:map_name, ST_Multi(ST_Force2D(ST_GeomFromText(:wkt, 4326))));
        """)

        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE public.zones RESTART IDENTITY CASCADE;"))
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                conn.execute(insert_sql, batch)

        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM public.zones;")).scalar()

        logging.info(f"  ✓ Successfully imported {count} response zones into public.zones (expected: 134).")
        return count
    except Exception as e:
        logging.error(f"  ✗ Step 3 error importing zones: {e}")
        return 0


def step4_import_city_boundary(engine, boundary_geojson_path: str) -> int:
    """Step 4: Import City Boundary -> public.city_boundary."""
    logging.info("=" * 60)
    logging.info("Step 4: Importing City Boundary -> public.city_boundary...")
    if not os.path.exists(boundary_geojson_path):
        logging.error(f"  ✗ City Boundary GeoJSON not found at: {boundary_geojson_path}")
        return 0

    try:
        with open(boundary_geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        features = data.get("features", [])
        if not features:
            logging.error("  ✗ No features found in city boundary GeoJSON.")
            return 0

        feat = features[0]
        props = feat.get("properties", {})
        name = props.get("NAME") or "City of Coquitlam"

        geom_obj = shape(feat["geometry"])
        geom_2d = to_2d(geom_obj)
        wkt = geom_2d.wkt

        insert_sql = text("""
        INSERT INTO public.city_boundary (name, geom)
        VALUES (:name, ST_Multi(ST_Force2D(ST_GeomFromText(:wkt, 4326))));
        """)

        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE public.city_boundary RESTART IDENTITY CASCADE;"))
            conn.execute(insert_sql, {"name": name, "wkt": wkt})

        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM public.city_boundary;")).scalar()

        logging.info(f"  ✓ Successfully imported {count} city boundary row into public.city_boundary.")
        return count
    except Exception as e:
        logging.error(f"  ✗ Step 4 error importing city boundary: {e}")
        return 0


def step5_import_road_names(engine, road_names_json_path: str, batch_size: int = 500) -> int:
    """Step 5: Import Road Names -> public.road_names."""
    logging.info("=" * 60)
    logging.info("Step 5: Importing Road Names -> public.road_names...")
    if not os.path.exists(road_names_json_path):
        logging.error(f"  ✗ Road names JSON not found at: {road_names_json_path}")
        return 0

    try:
        with open(road_names_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        unique_names = set()
        if isinstance(data, dict) and "features" in data:
            for feat in data["features"]:
                attrs = feat.get("attributes", {})
                rn = attrs.get("Road_Name") or attrs.get("ROAD_NAME") or attrs.get("road_name")
                if rn and str(rn).strip():
                    unique_names.add(str(rn).strip())
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, str) and item.strip():
                    unique_names.add(item.strip())
                elif isinstance(item, dict):
                    rn = item.get("Road_Name") or item.get("ROAD_NAME") or item.get("road_name")
                    if rn and str(rn).strip():
                        unique_names.add(str(rn).strip())

        records = [
            {"road_name": n, "road_name_normalized": n.upper()}
            for n in sorted(unique_names)
        ]

        insert_sql = text("""
        INSERT INTO public.road_names (road_name, road_name_normalized)
        VALUES (:road_name, :road_name_normalized)
        ON CONFLICT (road_name) DO NOTHING;
        """)

        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE public.road_names RESTART IDENTITY CASCADE;"))
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                conn.execute(insert_sql, batch)

        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM public.road_names;")).scalar()

        logging.info(f"  ✓ Successfully imported {count} unique road names into public.road_names (expected ~1,079).")
        return count
    except Exception as e:
        logging.error(f"  ✗ Step 5 error importing road names: {e}")
        return 0


def step6_import_custom_places(engine, custom_places_json_path: str, batch_size: int = 500) -> int:
    """Step 6: Import Custom Places -> public.custom_places."""
    logging.info("=" * 60)
    logging.info("Step 6: Importing Custom Places -> public.custom_places...")
    if not os.path.exists(custom_places_json_path):
        logging.error(f"  ✗ Custom places JSON not found at: {custom_places_json_path}")
        return 0

    try:
        with open(custom_places_json_path, "r", encoding="utf-8") as f:
            lm_data = json.load(f)

        records = []
        for name_key, val in lm_data.items():
            name = str(val.get("name") or name_key).strip()
            name_normalized = name_key.strip().upper()
            address = val.get("address")
            lat = float(val["lat"])
            lng = float(val["lng"])
            category = val.get("category", "custom_place")
            meta = json.dumps(val.get("metadata")) if val.get("metadata") else None

            records.append({
                "name": name,
                "name_normalized": name_normalized,
                "address": address,
                "lat": lat,
                "lng": lng,
                "category": category,
                "metadata": meta
            })

        insert_sql = text("""
        INSERT INTO public.custom_places (name, name_normalized, address, lat, lng, geom, category, metadata)
        VALUES (
            :name, :name_normalized, :address, :lat, :lng,
            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
            :category, CAST(:metadata AS JSONB)
        );
        """)

        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE public.custom_places RESTART IDENTITY CASCADE;"))
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                conn.execute(insert_sql, batch)

        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM public.custom_places;")).scalar()

        logging.info(f"  ✓ Successfully imported {count} custom places into public.custom_places.")
        return count
    except Exception as e:
        logging.error(f"  ✗ Step 6 error importing custom places: {e}")
        return 0


def step7_import_vocabulary(engine, vocab_dir: str, batch_size: int = 500) -> dict:
    """Step 7: Import Vocabulary -> public.vocabulary from .txt files."""
    logging.info("=" * 60)
    logging.info("Step 7: Importing Vocabulary -> public.vocabulary...")

    vocab_file_map = {
        "unit": os.path.join(vocab_dir, "units_vocabulary.txt"),
        "call_type": os.path.join(vocab_dir, "call_types.txt"),
        "radio_channel": os.path.join(vocab_dir, "radio_channels.txt"),
        "response_type": os.path.join(vocab_dir, "response_types.txt"),
        "map_grid": os.path.join(vocab_dir, "map_grid_numbers.txt"),
    }

    category_counts = {}
    records = []
    seen = set()

    for cat, filepath in vocab_file_map.items():
        if not os.path.exists(filepath):
            logging.warning(f"  Vocabulary file for {cat} not found: {filepath}")
            category_counts[cat] = 0
            continue

        cat_order = 0
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                term = line.strip()
                if not term or term.startswith("#"):
                    continue
                if (cat, term) in seen:
                    continue
                seen.add((cat, term))
                cat_order += 1
                records.append({
                    "category": cat,
                    "term": term,
                    "term_normalized": term.upper(),
                    "sort_order": cat_order,
                    "source": "import"
                })
        category_counts[cat] = cat_order

    insert_sql = text("""
    INSERT INTO public.vocabulary (category, term, term_normalized, sort_order, source, is_active)
    VALUES (:category, :term, :term_normalized, :sort_order, :source, TRUE)
    ON CONFLICT (category, term) DO UPDATE SET
        term_normalized = EXCLUDED.term_normalized,
        sort_order = EXCLUDED.sort_order,
        updated_at = CURRENT_TIMESTAMP;
    """)

    try:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE public.vocabulary RESTART IDENTITY CASCADE;"))
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                conn.execute(insert_sql, batch)

        logging.info("  ✓ Vocabulary Import Breakdown:")
        for cat, cnt in category_counts.items():
            logging.info(f"    - {cat:15s}: {cnt} terms")
        logging.info(f"    Total Vocabulary Records: {len(records)}")
        return category_counts
    except Exception as e:
        logging.error(f"  ✗ Step 7 error importing vocabulary: {e}")
        return category_counts


def step8_compute_intersections(engine, road_features: list, intersections_json_path: str = None, batch_size: int = 1000) -> int:
    """Step 8: Import or Compute Topological Road Intersections -> public.intersections."""
    logging.info("=" * 60)
    logging.info("Step 8: Importing / Computing Topological Road Intersections...")

    if intersections_json_path and os.path.exists(intersections_json_path):
        logging.info(f"  Loading authoritative intersections from: {intersections_json_path}")
        try:
            with open(intersections_json_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            from gis_service.geocoder import split_intersection_parts, normalize_intersection_key
            records = []
            for key, candidates in raw_data.items():
                parts = split_intersection_parts(key)
                if parts:
                    street_a, street_b = sorted([parts[0], parts[1]])
                    norm_key = normalize_intersection_key(street_a, street_b)
                else:
                    words = key.split('&')
                    if len(words) >= 2:
                        street_a, street_b = sorted([words[0].strip(), words[1].strip()])
                        norm_key = normalize_intersection_key(street_a, street_b)
                    else:
                        street_a = key
                        street_b = key
                        norm_key = key.strip().upper()
                cand_list = candidates if isinstance(candidates, list) else [candidates]
                for idx, c in enumerate(cand_list):
                    records.append({
                        "street_a": street_a,
                        "street_b": street_b,
                        "intersection_key": norm_key,
                        "lat": float(c["lat"]),
                        "lng": float(c["lng"]),
                        "zone_id": str(c.get("grid", "")).strip() if c.get("grid") is not None and str(c.get("grid")).strip() != "" else None,
                        "candidate_index": idx
                    })
            insert_sql = text("""
            INSERT INTO public.intersections (
                street_a, street_b, intersection_key, lat, lng, zone_id, geom, candidate_index
            ) VALUES (
                :street_a, :street_b, :intersection_key, :lat, :lng, :zone_id,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                :candidate_index
            )
            ON CONFLICT (intersection_key, candidate_index) DO UPDATE SET
                street_a = EXCLUDED.street_a,
                street_b = EXCLUDED.street_b,
                lat = EXCLUDED.lat,
                lng = EXCLUDED.lng,
                zone_id = EXCLUDED.zone_id,
                geom = EXCLUDED.geom;
            """)
            with engine.begin() as conn:
                conn.execute(text("TRUNCATE TABLE public.intersections RESTART IDENTITY CASCADE;"))
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    conn.execute(insert_sql, batch)
            with engine.connect() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM public.intersections;")).scalar()
            logging.info(f"  ✓ Successfully imported {count} authoritative intersections into public.intersections.")
            return count
        except Exception as e:
            logging.warning(f"  Failed to import intersections from JSON ({e}), falling back to shape computation.")

    start_t = time.time()

    # 1. Group road segments by normalized road name and merge with unary_union
    road_geoms = {}
    for feature in road_features:
        props = feature.get("properties", {})
        status = props.get("STATUS")
        if status and str(status).strip().upper() != "OPERATING":
            continue
        name = props.get("FULLNAME", "").strip()
        if not name:
            continue
        geom = to_2d(shape(feature["geometry"]))
        name_upper = name.upper()
        if name_upper in road_geoms:
            road_geoms[name_upper] = unary_union([road_geoms[name_upper], geom])
        else:
            road_geoms[name_upper] = geom

    road_names_list = sorted(road_geoms.keys())
    total_roads = len(road_names_list)
    logging.info(f"  Unified {total_roads} unique operating roads for intersection analysis.")

    # Pre-cache bounding boxes for fast candidate filtering
    bounds_dict = {name: road_geoms[name].bounds for name in road_names_list}

    intersection_results = []

    # 2. Pairwise intersection with bounding box pre-filtering
    for i in range(total_roads):
        if i > 0 and i % 100 == 0:
            logging.info(f"  Progress: {i}/{total_roads} roads evaluated ({len(intersection_results)} intersection points found)...")

        name_a = road_names_list[i]
        geom_a = road_geoms[name_a]
        b_a = bounds_dict[name_a]

        for j in range(i + 1, total_roads):
            name_b = road_names_list[j]
            b_b = bounds_dict[name_b]

            # Fast bounding box rejection (minx, miny, maxx, maxy)
            if b_a[0] > b_b[2] or b_a[2] < b_b[0] or b_a[1] > b_b[3] or b_a[3] < b_b[1]:
                continue

            if not geom_a.intersects(geom_b := road_geoms[name_b]):
                continue

            result = geom_a.intersection(geom_b)
            if result.is_empty:
                continue

            points = []
            if result.geom_type == "Point":
                points = [result]
            elif result.geom_type == "MultiPoint":
                points = list(result.geoms)
            elif result.geom_type == "GeometryCollection":
                points = [g for g in result.geoms if g.geom_type == "Point"]

            if not points:
                continue

            sorted_names = sorted([name_a, name_b])
            key = f"{sorted_names[0]} & {sorted_names[1]}"

            # Deduplicate points within ~10m of each other (0.0001 deg)
            unique_points = []
            for pt in points:
                is_dup = False
                for upt in unique_points:
                    if pt.distance(upt) < 0.0001:
                        is_dup = True
                        break
                if not is_dup:
                    unique_points.append(pt)

            for idx, pt in enumerate(unique_points):
                intersection_results.append({
                    "street_a": sorted_names[0],
                    "street_b": sorted_names[1],
                    "intersection_key": key,
                    "lat": pt.y,
                    "lng": pt.x,
                    "candidate_index": idx
                })

    calc_elapsed = time.time() - start_t
    logging.info(f"  Computed {len(intersection_results)} intersection points across {total_roads} roads in {calc_elapsed:.2f}s.")

    # 3. Insert into public.intersections
    insert_sql = text("""
    INSERT INTO public.intersections (
        street_a, street_b, intersection_key, lat, lng, geom, candidate_index
    ) VALUES (
        :street_a, :street_b, :intersection_key, :lat, :lng,
        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
        :candidate_index
    );
    """)

    try:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE public.intersections RESTART IDENTITY CASCADE;"))
            for i in range(0, len(intersection_results), batch_size):
                batch = intersection_results[i:i + batch_size]
                conn.execute(insert_sql, batch)

        # 4. Spatial join to update zone_id from public.zones
        logging.info("  Associating emergency response zone_id to intersections...")
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE public.intersections i
                SET zone_id = z.map_name
                FROM public.zones z
                WHERE ST_Contains(z.geom, i.geom);
            """))

        with engine.connect() as conn:
            total_db = conn.execute(text("SELECT COUNT(*) FROM public.intersections;")).scalar()
            assigned_zones = conn.execute(text("SELECT COUNT(*) FROM public.intersections WHERE zone_id IS NOT NULL;")).scalar()

        logging.info(f"  ✓ Successfully stored {total_db} intersections ({assigned_zones} with zone_id).")

        # 5. Validation checks
        with engine.connect() as conn:
            # Check Christmas Way & Westwood St
            res_xmas = conn.execute(text("""
                SELECT intersection_key, lat, lng, zone_id 
                FROM public.intersections 
                WHERE intersection_key LIKE '%CHRISTMAS WAY%' AND intersection_key LIKE '%WESTWOOD ST%';
            """)).fetchall()

            # Check David Ave & Panorama Dr (parallel roads)
            res_david = conn.execute(text("""
                SELECT intersection_key, lat, lng, zone_id 
                FROM public.intersections 
                WHERE intersection_key LIKE '%DAVID AVE%' AND intersection_key LIKE '%PANORAMA DR%';
            """)).fetchall()

            logging.info("  Intersection Validation Results:")
            if res_xmas:
                logging.info(f"    ✓ Found expected intersection: '{res_xmas[0][0]}' at ({res_xmas[0][1]:.5f}, {res_xmas[0][2]:.5f}), Zone: {res_xmas[0][3]}")
            else:
                logging.warning("    ✗ Expected intersection 'CHRISTMAS WAY & WESTWOOD ST' NOT found!")

            if not res_david:
                logging.info("    ✓ Correctly rejected parallel roads: 'DAVID AVE & PANORAMA DR' (0 intersections)")
            else:
                logging.warning(f"    ✗ Unexpected intersections found for parallel roads 'DAVID AVE & PANORAMA DR': {len(res_david)}")

        return total_db
    except Exception as e:
        logging.error(f"  ✗ Step 8 error computing/storing intersections: {e}")
        return 0


def step9_backfill_parcel_frontage(engine) -> int:
    """Step 9: Backfill Parcel Frontage Points using ST_ClosestPoint to Road Centrelines."""
    logging.info("=" * 60)
    logging.info("Step 9: Backfilling Parcel Frontage Points (public.parcels)...")

    try:
        with engine.connect() as conn:
            table_exists = conn.execute(text("SELECT to_regclass('public.parcels');")).scalar()
            if not table_exists:
                logging.warning("  public.parcels table does not exist. Run import_parcels.py first.")
                return 0
            parcel_count = conn.execute(text("SELECT COUNT(*) FROM public.parcels;")).scalar()
            if parcel_count == 0:
                logging.warning("  public.parcels table is empty (0 rows). Run import_parcels.py first.")
                return 0

        update_sql = text("""
        UPDATE public.parcels p
        SET front_lat = ST_Y(sub.closest_pt),
            front_lng = ST_X(sub.closest_pt)
        FROM (
            SELECT DISTINCT ON (p2.id) p2.id,
                   ST_ClosestPoint(r.geom, ST_SetSRID(ST_MakePoint(p2.lng, p2.lat), 4326)) AS closest_pt
            FROM public.parcels p2
            JOIN public.roads r ON UPPER(r.fullname) = UPPER(p2.street || ' ' || p2.streettype)
            WHERE p2.front_lat IS NULL
              AND p2.lat IS NOT NULL
            ORDER BY p2.id, ST_Distance(r.geom, ST_SetSRID(ST_MakePoint(p2.lng, p2.lat), 4326))
        ) sub
        WHERE p.id = sub.id;
        """)

        with engine.begin() as conn:
            result = conn.execute(update_sql)
            updated = result.rowcount if hasattr(result, "rowcount") else 0

        logging.info(f"  ✓ Backfilled frontage coordinates for {updated} parcels.")
        return updated
    except Exception as e:
        logging.error(f"  ✗ Step 9 error backfilling parcel frontage: {e}")
        return 0


def step10_add_parcel_geom(engine) -> int:
    """Step 10: Ensure Point Geometry column & Spatial Index on public.parcels."""
    logging.info("=" * 60)
    logging.info("Step 10: Ensuring Point Geometry & GIST index on public.parcels...")

    try:
        with engine.connect() as conn:
            table_exists = conn.execute(text("SELECT to_regclass('public.parcels');")).scalar()
            if not table_exists:
                logging.warning("  public.parcels table does not exist. Run import_parcels.py first.")
                return 0

        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE public.parcels ADD COLUMN IF NOT EXISTS geom GEOMETRY(Point, 4326);"))
            try:
                conn.execute(text("ALTER TABLE public.parcels ALTER COLUMN geom TYPE GEOMETRY(Point, 4326) USING ST_Centroid(geom);"))
            except Exception:
                pass

            result = conn.execute(text("""
                UPDATE public.parcels
                SET geom = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
                WHERE geom IS NULL AND lat IS NOT NULL AND lng IS NOT NULL;
            """))
            updated = result.rowcount if hasattr(result, "rowcount") else 0
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_parcels_geom ON public.parcels USING GIST (geom);"))

        logging.info(f"  ✓ Created/updated spatial geom column on {updated} parcels with GIST index.")
        return updated
    except Exception as e:
        logging.error(f"  ✗ Step 10 error configuring parcel geometry: {e}")
        return 0


def run_full_import(
    data_dir: str = None,
    batch_size: int = 500,
    skip_intersections: bool = False,
    skip_parcels: bool = False
):
    """Executes the complete end-to-end GIS import pipeline."""
    total_start = time.time()
    db_url = get_database_url()

    if data_dir is None:
        data_dir = os.path.join(backend_dir, "data")

    staging_dir = os.path.join(data_dir, "staging")
    vocab_dir = os.path.join(data_dir, "vocabulary")

    roads_path = os.path.join(staging_dir, "road_centre_lines.geojson")
    zones_path = os.path.join(staging_dir, "emergency_zones.geojson")
    boundary_path = os.path.join(staging_dir, "city_boundary.geojson")
    road_names_path = os.path.join(staging_dir, "road_names.json")
    custom_places_path = os.path.join(vocab_dir, "custom_places.json")
    intersections_path = os.path.join(data_dir, "gis", "intersections.json")

    logging.info("=" * 70)
    logging.info("  CFR EVO MASTER GIS POSTGIS INGESTION PIPELINE")
    logging.info("=" * 70)
    logging.info(f"Database Target: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    logging.info(f"Staging Dir:     {staging_dir}")
    logging.info(f"Vocabulary Dir:  {vocab_dir}")
    logging.info("=" * 70)

    engine = create_engine(db_url, pool_pre_ping=True)

    # Step 1: Ensure PostGIS & DB Schemas
    ensure_tables(engine)
    step1_ensure_postgis(engine)

    # Step 2: Import Roads
    roads_count, road_features = step2_import_roads(engine, roads_path, batch_size=batch_size)

    # Step 3: Import Emergency Zones
    zones_count = step3_import_zones(engine, zones_path, batch_size=batch_size)

    # Step 4: Import City Boundary
    boundary_count = step4_import_city_boundary(engine, boundary_path)

    # Step 5: Import Road Names
    road_names_count = step5_import_road_names(engine, road_names_path, batch_size=batch_size)

    # Step 6: Import Custom Places
    custom_places_count = step6_import_custom_places(engine, custom_places_path, batch_size=batch_size)

    # Step 7: Import Vocabulary
    vocab_counts = step7_import_vocabulary(engine, vocab_dir, batch_size=batch_size)
    total_vocab = sum(vocab_counts.values())

    # Step 8: Compute Intersections
    if not skip_intersections:
        if not road_features and os.path.exists(roads_path):
            with open(roads_path, "r", encoding="utf-8") as f:
                road_features = json.load(f).get("features", [])
        intersections_count = step8_compute_intersections(
            engine, road_features,
            intersections_json_path=intersections_path,
            batch_size=batch_size
        )
    else:
        logging.info("Step 8: Skipped (--skip-intersections).")
        intersections_count = 0

    # Step 9 & 10: Parcel Operations
    if not skip_parcels:
        parcels_geom_count = step10_add_parcel_geom(engine)
        parcels_front_count = step9_backfill_parcel_frontage(engine)
    else:
        logging.info("Steps 9 & 10: Skipped (--skip-parcels).")
        parcels_geom_count = 0
        parcels_front_count = 0

    elapsed = time.time() - total_start

    # Summary Table
    print("\n" + "=" * 50)
    print("           === Import Summary ===")
    print("=" * 50)
    print(f"roads:         {roads_count:>8d} rows")
    print(f"intersections: {intersections_count:>8d} rows")
    print(f"zones:         {zones_count:>8d} rows")
    print(f"city_boundary: {boundary_count:>8d} row")
    print(f"road_names:    {road_names_count:>8d} rows")
    print(f"custom_places: {custom_places_count:>8d} rows")
    print(f"vocabulary:    {total_vocab:>8d} rows")
    print(f"parcels geom:  {parcels_geom_count:>8d} updated")
    print(f"parcels front: {parcels_front_count:>8d} updated")
    print("=" * 50)
    print(f"Total Pipeline Execution Time: {elapsed:.2f} seconds")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Master GIS Ingestion Script for CFR EVO PostGIS")
    parser.add_argument(
        "--data-dir",
        default=os.path.join(backend_dir, "data"),
        help="Base path to data directory"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch insert chunk size (default: 500)"
    )
    parser.add_argument(
        "--skip-intersections",
        action="store_true",
        help="Skip topological intersection calculation"
    )
    parser.add_argument(
        "--skip-parcels",
        action="store_true",
        help="Skip parcel geometry and frontage backfill"
    )
    args = parser.parse_args()

    run_full_import(
        data_dir=args.data_dir,
        batch_size=args.batch_size,
        skip_intersections=args.skip_intersections,
        skip_parcels=args.skip_parcels
    )
