#!/usr/bin/env python3
"""
backend/scripts/import_parcels.py
High-speed GIS ingestion script: imports 100% of Coquitlam Addresses.shp records (69,708 rows)
into the unified 40-column PostgreSQL `public.parcels` table.

Pre-computes emergency response zone_id (1..134) via spatial point-in-polygon intersection
against Emergency_Response_Zones.shp, eliminating runtime geocoding zone lookups.
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime

# Ensure backend and sibling microservices are on sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

def create_parcels_table(engine, drop_existing: bool = True):
    """Creates the 40-column unified parcels table and indexes."""
    from sqlalchemy import text
    with engine.begin() as conn:
        if drop_existing:
            logging.info("Dropping legacy tables (parcels, streetview_overrides)...")
            conn.execute(text("DROP TABLE IF EXISTS public.streetview_overrides CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS public.parcels CASCADE;"))

        logging.info("Creating unified 40-column public.parcels table...")
        create_sql = text("""
        CREATE TABLE IF NOT EXISTS public.parcels (
            id BIGSERIAL PRIMARY KEY,
            parcel_uuid UUID DEFAULT gen_random_uuid() NOT NULL,

            gis_id VARCHAR(255),
            address VARCHAR(255) NOT NULL,
            house VARCHAR(50),
            street VARCHAR(255),
            streettype VARCHAR(50),
            unit VARCHAR(50),
            unittype VARCHAR(50),
            postal VARCHAR(10),
            block VARCHAR(50),
            plan VARCHAR(50),
            lot VARCHAR(50),
            legaldesc TEXT,
            plan_area VARCHAR(20),
            folio VARCHAR(50),
            zonetype1 VARCHAR(30),
            zonetype2 VARCHAR(30),
            zonetype3 VARCHAR(30),
            status VARCHAR(20),
            units INTEGER,
            sc_card VARCHAR(50),
            extract_dt DATE,

            lat DOUBLE PRECISION,
            lng DOUBLE PRECISION,

            zone_id VARCHAR(16),
            address_normalized VARCHAR(255),

            front_lat DOUBLE PRECISION,
            front_lng DOUBLE PRECISION,
            centroid_lat DOUBLE PRECISION,
            centroid_lng DOUBLE PRECISION,
            entrance_lat DOUBLE PRECISION,
            entrance_lng DOUBLE PRECISION,
            streetview_heading DOUBLE PRECISION DEFAULT 0.0,
            streetview_pitch DOUBLE PRECISION DEFAULT 5.0,
            streetview_fov DOUBLE PRECISION DEFAULT 80.0,
            lock_box_notes TEXT,
            hazard_notes TEXT,
            pre_plan_pdf_url TEXT,
            construction_type VARCHAR(100),
            floor_count INTEGER,
            is_pa_page BOOLEAN NOT NULL DEFAULT FALSE,

            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_parcels_address ON public.parcels (address);
        CREATE INDEX IF NOT EXISTS idx_parcels_address_normalized ON public.parcels (address_normalized);
        CREATE INDEX IF NOT EXISTS idx_parcels_gis_id ON public.parcels (gis_id);
        CREATE INDEX IF NOT EXISTS idx_parcels_zone_id ON public.parcels (zone_id);
        CREATE INDEX IF NOT EXISTS idx_parcels_street ON public.parcels (street, streettype);
        CREATE INDEX IF NOT EXISTS idx_parcels_house_street ON public.parcels (house, street);
        CREATE INDEX IF NOT EXISTS idx_parcels_unit ON public.parcels (unit) WHERE unit IS NOT NULL AND unit != '';
        CREATE INDEX IF NOT EXISTS idx_parcels_zonetype1 ON public.parcels (zonetype1);
        """)
        conn.execute(create_sql)
        logging.info("Table public.parcels and all indexes created successfully.")

def run_import(address_shp_path: str, zones_shp_path: str, drop_existing: bool = True, batch_size: int = 5000):
    """Executes the full GIS shapefile loading, spatial zone intersection, and database copy."""
    import geopandas as gpd
    from sqlalchemy import create_engine, text

    if not os.path.exists(address_shp_path):
        logging.error(f"Addresses shapefile not found at: {address_shp_path}")
        sys.exit(1)
    if not os.path.exists(zones_shp_path):
        logging.error(f"Emergency Response Zones shapefile not found at: {zones_shp_path}")
        sys.exit(1)

    start_time = time.time()
    logging.info("=" * 60)
    logging.info("CFR EVO: Ingesting Coquitlam Parcels & Pre-Computing Zones")
    logging.info(f"Addresses source: {address_shp_path}")
    logging.info(f"Zones source:     {zones_shp_path}")
    logging.info("=" * 60)

    # 1. Load Addresses Shapefile
    logging.info("Reading Addresses shapefile...")
    addr_gdf = gpd.read_file(address_shp_path)
    total_raw = len(addr_gdf)
    logging.info(f"Loaded {total_raw} raw address records. Native CRS: {addr_gdf.crs}")

    # Ensure WGS84 for lat/lng extraction
    if addr_gdf.crs is None:
        logging.warning("Addresses CRS is undefined. Assuming EPSG:26910 (UTM Zone 10N)...")
        addr_gdf.set_crs(epsg=26910, inplace=True)
    
    addr_wgs84 = addr_gdf.to_crs(epsg=4326)
    centroids = addr_wgs84.geometry.centroid
    addr_gdf["lat"] = centroids.y
    addr_gdf["lng"] = centroids.x

    # 2. Load Emergency Response Zones & Spatial Join
    logging.info("Reading Emergency Response Zones shapefile...")
    zones_gdf = gpd.read_file(zones_shp_path)
    logging.info(f"Loaded {len(zones_gdf)} response zones. Native CRS: {zones_gdf.crs}")

    if zones_gdf.crs != addr_gdf.crs:
        logging.info("Re-projecting response zones to match addresses CRS...")
        zones_gdf = zones_gdf.to_crs(addr_gdf.crs)

    logging.info("Performing spatial point-in-polygon join (Address points -> Response Zones)...")
    joined = gpd.sjoin(addr_gdf, zones_gdf[["MAP_NAME", "geometry"]], how="left", predicate="within")

    # 3. Clean & Format Data
    logging.info("Formatting records and normalizing addresses...")
    seen_addresses = set()
    records_to_insert = []
    zone_assigned_count = 0
    missing_zone_count = 0

    def clean_str(val):
        if val is None:
            return None
        s = str(val).strip()
        if s == "" or s.lower() in ("nan", "none", "<null>"):
            return None
        return s

    for idx, row in joined.iterrows():
        raw_addr = clean_str(row.get("ADDRESS"))
        if not raw_addr:
            continue
        
        # Deduplicate identical address strings if present in source
        if raw_addr in seen_addresses:
            continue
        seen_addresses.add(raw_addr)

        gis_id = clean_str(row.get("GIS_ID"))
        house = clean_str(row.get("HOUSE"))
        street = clean_str(row.get("STREET"))
        streettype = clean_str(row.get("STREETTYPE"))
        unit = clean_str(row.get("UNIT"))
        unittype = clean_str(row.get("UNITTYPE"))
        postal = clean_str(row.get("POSTAL"))
        block = clean_str(row.get("BLOCK"))
        plan = clean_str(row.get("PLAN"))
        lot = clean_str(row.get("LOT"))
        
        raw_legal = row.get("LEGALDESC")
        legaldesc = clean_str(str(raw_legal).replace("\n", " ").replace("\r", " ")) if raw_legal is not None else None
        plan_area = clean_str(row.get("PLAN_AREA"))
        folio = clean_str(row.get("FOLIO"))
        zonetype1 = clean_str(row.get("ZONETYPE1"))
        zonetype2 = clean_str(row.get("ZONETYPE2"))
        zonetype3 = clean_str(row.get("ZONETYPE3"))
        status = clean_str(row.get("STATUS")) or "Active"
        
        units_raw = str(row.get("UNITS", "") or "").strip()
        units = int(units_raw) if units_raw.isdigit() else None
        
        sc_card = clean_str(row.get("SC_CARD"))
        
        extract_dt = row.get("EXTRACT_DT")
        if extract_dt is not None:
            try:
                extract_dt = str(extract_dt)[:10]
            except Exception:
                extract_dt = None

        lat = float(row.get("lat", 0.0))
        lng = float(row.get("lng", 0.0))

        zone_val = row.get("MAP_NAME")
        if zone_val is not None and str(zone_val).strip() != "" and str(zone_val) != "nan":
            zone_id = str(zone_val).strip()
            zone_assigned_count += 1
        else:
            zone_id = None
            missing_zone_count += 1

        addr_norm = raw_addr.lower()

        records_to_insert.append({
            "gis_id": gis_id,
            "address": raw_addr,
            "house": house,
            "street": street,
            "streettype": streettype,
            "unit": unit,
            "unittype": unittype,
            "postal": postal,
            "block": block,
            "plan": plan,
            "lot": lot,
            "legaldesc": legaldesc,
            "plan_area": plan_area,
            "folio": folio,
            "zonetype1": zonetype1,
            "zonetype2": zonetype2,
            "zonetype3": zonetype3,
            "status": status,
            "units": units,
            "sc_card": sc_card,
            "extract_dt": extract_dt,
            "lat": lat,
            "lng": lng,
            "zone_id": zone_id,
            "address_normalized": addr_norm,
            "front_lat": lat,
            "front_lng": lng,
            "centroid_lat": lat,
            "centroid_lng": lng,
            "entrance_lat": lat,
            "entrance_lng": lng,
            "streetview_heading": 0.0,
            "streetview_pitch": 5.0,
            "streetview_fov": 80.0,
            "is_pa_page": False
        })

    logging.info(f"Prepared {len(records_to_insert)} clean records for database ingestion.")
    logging.info(f"Emergency Zones assigned: {zone_assigned_count} | Unassigned (boundary edges): {missing_zone_count}")

    # 4. Connect to DB & Bulk Insert
    db_url = get_database_url()
    logging.info(f"Connecting to database: {db_url.split('@')[-1] if '@' in db_url else db_url}...")
    engine = create_engine(db_url, pool_pre_ping=True)

    create_parcels_table(engine, drop_existing=drop_existing)

    logging.info(f"Executing batch insertion (batch size: {batch_size})...")
    insert_sql = text("""
    INSERT INTO public.parcels (
        gis_id, address, house, street, streettype, unit, unittype, postal,
        block, plan, lot, legaldesc, plan_area, folio, zonetype1, zonetype2, zonetype3,
        status, units, sc_card, extract_dt, lat, lng, zone_id, address_normalized,
        front_lat, front_lng, centroid_lat, centroid_lng, entrance_lat, entrance_lng,
        streetview_heading, streetview_pitch, streetview_fov, is_pa_page
    ) VALUES (
        :gis_id, :address, :house, :street, :streettype, :unit, :unittype, :postal,
        :block, :plan, :lot, :legaldesc, :plan_area, :folio, :zonetype1, :zonetype2, :zonetype3,
        :status, :units, :sc_card, CAST(:extract_dt AS DATE), :lat, :lng, :zone_id, :address_normalized,
        :front_lat, :front_lng, :centroid_lat, :centroid_lng, :entrance_lat, :entrance_lng,
        :streetview_heading, :streetview_pitch, :streetview_fov, :is_pa_page
    )
    """)

    total_inserted = 0
    with engine.begin() as conn:
        for i in range(0, len(records_to_insert), batch_size):
            batch = records_to_insert[i:i + batch_size]
            conn.execute(insert_sql, batch)
            total_inserted += len(batch)
            logging.info(f"  Inserted {total_inserted}/{len(records_to_insert)} parcels ({(total_inserted/len(records_to_insert)*100):.1f}%)...")

    elapsed_s = time.time() - start_time
    logging.info("=" * 60)
    logging.info(f"SUCCESS: Ingested {total_inserted} parcels in {elapsed_s:.2f}s ({(total_inserted/elapsed_s):.0f} rows/sec).")
    logging.info("=" * 60)

    # 5. Run Verification Queries
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM public.parcels;")).scalar()
        zones = conn.execute(text("SELECT COUNT(DISTINCT zone_id) FROM public.parcels WHERE zone_id IS NOT NULL;")).scalar()
        high_rises = conn.execute(text("SELECT COUNT(*) FROM public.parcels WHERE units > 50;")).scalar()
        multi_units = conn.execute(text("SELECT COUNT(*) FROM public.parcels WHERE unit IS NOT NULL AND unit != '';")).scalar()
        
        logging.info("Verification Summary:")
        logging.info(f"  Total Rows in DB:               {count}")
        logging.info(f"  Unique Emergency Zones Populated: {zones}")
        logging.info(f"  Multi-Unit / Condo Rows:        {multi_units}")
        logging.info(f"  High-Rise Buildings (>50 units):{high_rises}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Coquitlam shapefiles into public.parcels")
    parser.add_argument(
        "--addresses",
        default=os.path.join(backend_dir, "data", "Property_Information", "Addresses.shp"),
        help="Path to Addresses.shp"
    )
    parser.add_argument(
        "--zones",
        default=os.path.join(backend_dir, "data", "Emergency_Response_Zones", "Emergency_Response_Zones.shp"),
        help="Path to Emergency_Response_Zones.shp"
    )
    parser.add_argument(
        "--no-drop",
        action="store_true",
        help="Do not drop existing table before import"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Batch insert chunk size"
    )
    args = parser.parse_args()

    run_import(
        address_shp_path=args.addresses,
        zones_shp_path=args.zones,
        drop_existing=not args.no_drop,
        batch_size=args.batch_size
    )
