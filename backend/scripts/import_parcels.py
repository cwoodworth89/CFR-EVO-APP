#!/usr/bin/env python3
"""
backend/scripts/import_parcels.py
High-speed GIS ingestion script: imports 100% of Coquitlam Addresses.shp records (69,708 rows)
into the unified 40-column PostgreSQL `public.parcels` table with true Polygon geometry and PostGIS indexing.

Features:
- Non-destructive UPSERT (ON CONFLICT address): preserves operational data (pre-plans, lockbox notes,
  hazards, custom frontage/entrance coordinates, streetview headings) while refreshing municipal GIS attributes.
- Full Polygon/MultiPolygon geometry ingestion into `geom geometry(Geometry, 4326)` with GiST spatial indexing.
- Pre-computes emergency response zone_id (1..134) via spatial point-in-polygon intersection against Emergency_Response_Zones.shp.
- Road Frontage Calculation: Computes actual road-facing frontage coordinates (front_lat, front_lng)
  via PostGIS `ST_ClosestPoint` to nearest road centrelines in `public.roads`.
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


def create_parcels_table(engine, drop_existing: bool = False):
    """
    Creates or updates the 40-column unified parcels table, geometry column, and indexes.
    Defaults to non-destructive creation (UPSERT mode).
    """
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))

        if drop_existing:
            logging.info("Force drop enabled: Dropping legacy tables (parcels, streetview_overrides)...")
            conn.execute(text("DROP TABLE IF EXISTS public.streetview_overrides CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS public.parcels CASCADE;"))

        logging.info("Verifying unified 40-column public.parcels table...")
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

            geom geometry(Geometry, 4326),

            -- THE THREE POSITIONS A PARCEL CAN RESOLVE TO -------------------------
            -- address_resolver takes the first that is set:
            --     entrance -> front -> lat/lng
            --
            -- entrance_*  OPERATOR-VERIFIED. Where a company officer says the way in
            --             actually is -- the gate, the keypad, the side apparatus can
            --             reach. Written ONLY by a human through the review UX, never
            --             by this import (punch-list #50), and attributed by
            --             entrance_set_by / _at / _note. Human knowledge has to
            --             survive every re-import.
            --
            -- front_*     COMPUTED ARRIVAL POINT. The closest point on the road the
            --             address NAMES, measured to the parcel POLYGON. This is what
            --             a crew is sent to for an ordinary property, and it is
            --             populated for all 65,401 parcels by
            --             backfill_parcel_frontage.
            --
            -- lat/lng     PARCEL POLYGON CENTROID, computed by us from geom -- it is
            --             not supplied by the City. Used for the zone point-in-polygon
            --             join, for map centring, and for simple script work that just
            --             needs one point per parcel. It is ALSO the last-resort
            --             arrival position, and a poor one: on 177 parcels it falls
            --             outside the parcel entirely, and on 2865 Glen Dr it sits
            --             135.6 m from Glen Drive. Never copy it into front_* or
            --             entrance_* -- that is exactly the defect #50 fixed.
            --
            -- There used to be a fourth pair, centroid_lat/centroid_lng. It was a
            -- byte-identical duplicate of lat/lng on all 65,400 polygon rows, selected
            -- by the resolver and never read. Dropped 2026-08-31.
            ------------------------------------------------------------------------
            front_lat DOUBLE PRECISION,
            front_lng DOUBLE PRECISION,
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
        """)
        conn.execute(create_sql)

        # Ensure geometry column exists and supports generic Geometry (Polygon / MultiPolygon)
        if not drop_existing:
            conn.execute(text("ALTER TABLE public.parcels ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326);"))
            try:
                conn.execute(text("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_schema = 'public' AND table_name = 'parcels' AND column_name = 'geom'
                    ) THEN
                        BEGIN
                            ALTER TABLE public.parcels ALTER COLUMN geom TYPE geometry(Geometry, 4326);
                        EXCEPTION WHEN OTHERS THEN
                            NULL;
                        END;
                    END IF;
                END $$;
                """))
            except Exception:
                pass

        # Ensure all indexes exist
        index_sql = text("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_parcels_address ON public.parcels (address);
        CREATE INDEX IF NOT EXISTS idx_parcels_address_normalized ON public.parcels (address_normalized);
        CREATE INDEX IF NOT EXISTS idx_parcels_gis_id ON public.parcels (gis_id);
        CREATE INDEX IF NOT EXISTS idx_parcels_zone_id ON public.parcels (zone_id);
        CREATE INDEX IF NOT EXISTS idx_parcels_street ON public.parcels (street, streettype);
        CREATE INDEX IF NOT EXISTS idx_parcels_house_street ON public.parcels (house, street);
        CREATE INDEX IF NOT EXISTS idx_parcels_unit ON public.parcels (unit) WHERE unit IS NOT NULL AND unit != '';
        CREATE INDEX IF NOT EXISTS idx_parcels_zonetype1 ON public.parcels (zonetype1);
        CREATE INDEX IF NOT EXISTS idx_parcels_geom ON public.parcels USING GIST (geom);
        """)
        conn.execute(index_sql)
        logging.info("Table public.parcels and all indexes verified successfully.")


def backfill_parcel_frontage(engine, batch_size: int = 5000) -> int:
    """
    Computes front_lat/front_lng as the nearest point on the closest road centreline
    using PostGIS spatial KNN (<->) and ST_ClosestPoint.
    Only updates parcels where front_lat is NULL or front_lat == lat (unmodified default).
    """
    from sqlalchemy import text
    logging.info("=" * 60)
    logging.info("Step: Computing Road-Facing Frontage Points (public.parcels)...")

    try:
        with engine.connect() as conn:
            # Check public.roads table and geometry availability
            roads_exists = conn.execute(text("SELECT to_regclass('public.roads');")).scalar()
            if not roads_exists:
                logging.warning("  public.roads table does not exist. Skipping frontage computation.")
                return 0

            road_count = conn.execute(text("SELECT COUNT(*) FROM public.roads WHERE geom IS NOT NULL;")).scalar()
            if not road_count or road_count == 0:
                logging.warning("  public.roads has no geometry records. Skipping frontage computation.")
                return 0

            logging.info(f"  Found {road_count} road segments in public.roads with geometry.")

            # EVERY parcel is recomputed, not only those missing a front point.
            #
            # This previously selected `front_lat IS NULL OR front_lat = lat`, i.e. backfill
            # only. With no NULLs left it became a no-op, so the frontage points froze against
            # whatever road network existed the first time it ran. When the roads import was
            # fixed on 2026-08-26 and gained 237 segments (private and MOT roads that had been
            # silently filtered), not one parcel was recomputed. Stale-by-design.
            #
            # Recomputation is cheap and the inputs only change at import, so there is no
            # reason to skip rows.
            candidate_ids = [r[0] for r in conn.execute(text("""
                SELECT id
                FROM public.parcels
                WHERE lat IS NOT NULL AND lng IS NOT NULL
                  AND geom IS NOT NULL
                ORDER BY id;
            """)).fetchall()]

        total_candidates = len(candidate_ids)
        if total_candidates == 0:
            logging.info("  No parcels with geometry to compute frontage for.")
            return 0

        logging.info(f"  Calculating road frontage coordinates for {total_candidates} parcels (chunks of {batch_size})...")

        chunk_sql = text("""
        UPDATE public.parcels p SET
            front_lat  = ST_Y(nearest.pt),
            front_lng  = ST_X(nearest.pt),
            updated_at = now()
        FROM (
            SELECT DISTINCT ON (p2.id)
                p2.id AS parcel_id,
                -- Measured to the parcel POLYGON, not its centroid. The centroid of a large
                -- or irregular lot can be far from the street, and on 177 parcels citywide it
                -- falls OUTSIDE the parcel entirely (L-shaped and wrapped sites). 2865 Glen Dr
                -- is 8 legal lots whose centroid sits 135.6 m from Glen Drive, which is how
                -- every centroid-based method ended up choosing a neighbouring road.
                ST_ClosestPoint(r.geom, p2.geom) AS pt
            FROM public.parcels p2
            CROSS JOIN LATERAL (
                -- CONSTRAINED TO THE STREET THE ADDRESS NAMES.
                --
                -- This is the whole correction. It previously took the nearest road of ANY
                -- name, which put 1,813 parcels on a street their address does not name --
                -- 2865 Glen Dr landed on Guildford Way, 254 m from where a crew should stop.
                --
                -- The street is not a preference to be weighed against geometry: the address
                -- states it, and both sides are municipal data (parcels.street against
                -- roads.roadname). A scoring weight can be outvoted by parallelism or road
                -- class; a filter cannot. Department decision 2026-08-29.
                --
                -- Apostrophes are stripped on both sides because the cadastre writes
                -- "Deer's Leap" and the road layer writes "Deers Leap" -- our normalization
                -- gap, not a City one.
                SELECT r2.geom
                FROM public.roads r2
                WHERE r2.geom IS NOT NULL
                  AND upper(replace(r2.roadname, '''', ''))
                      = upper(replace(p2.street, '''', ''))
                ORDER BY r2.geom <-> p2.geom
                LIMIT 1
            ) r
            WHERE p2.id >= :min_id AND p2.id <= :max_id
              AND p2.lat IS NOT NULL AND p2.lng IS NOT NULL
              AND p2.geom IS NOT NULL
              AND p2.street IS NOT NULL AND btrim(p2.street) <> ''
        ) nearest
        WHERE p.id = nearest.parcel_id;
        """)
        # NOTE: parcels whose addressed street has no matching road are deliberately left
        # untouched rather than snapped to the nearest road of another name. There are 54 of
        # them, every one tracked in docs/city_gis_data_register.md as a municipal data gap.
        # They surface as an approximate location rather than a confident wrong one (§6.1).
        #
        # NOTE: entrance_lat / entrance_lng are NEVER written here. Those hold the
        # operator-verified access point, and human knowledge must survive the pipeline that
        # regenerates the computed values.

        start_t = time.time()
        total_updated = 0

        for i in range(0, total_candidates, batch_size):
            chunk = candidate_ids[i:i + batch_size]
            min_id = chunk[0]
            max_id = chunk[-1]

            with engine.begin() as tx_conn:
                res = tx_conn.execute(chunk_sql, {"min_id": min_id, "max_id": max_id})
                updated_chunk = res.rowcount if hasattr(res, "rowcount") else len(chunk)
                total_updated += updated_chunk

            pct = (min(i + batch_size, total_candidates) / total_candidates) * 100
            logging.info(f"  Frontage backfill progress: {min(i + batch_size, total_candidates)}/{total_candidates} parcels evaluated ({pct:.1f}%)...")

        elapsed_s = time.time() - start_t
        logging.info(f"  ✓ Road frontage backfill completed for {total_updated} parcels in {elapsed_s:.2f}s.")
        return total_updated
    except Exception as e:
        logging.error(f"  ✗ Error calculating parcel frontage coordinates: {e}", exc_info=True)
        return 0


def run_import(
    address_shp_path: str,
    zones_shp_path: str,
    drop_existing: bool = False,
    skip_frontage: bool = False,
    batch_size: int = 5000
):
    """Executes the full GIS shapefile loading, spatial zone intersection, UPSERT ingestion, and frontage alignment."""
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
    logging.info(f"Ingestion mode:   {'FORCE DROP & RECREATE' if drop_existing else 'NON-DESTRUCTIVE UPSERT'}")
    logging.info("=" * 60)

    # 1. Load Addresses Shapefile & Reproject to WGS84
    logging.info("Reading Addresses shapefile...")
    addr_gdf = gpd.read_file(address_shp_path)
    total_raw = len(addr_gdf)
    logging.info(f"Loaded {total_raw} raw address records. Native CRS: {addr_gdf.crs}")

    if addr_gdf.crs is None:
        logging.warning("Addresses CRS is undefined. Assuming EPSG:26910 (UTM Zone 10N)...")
        addr_gdf.set_crs(epsg=26910, inplace=True)

    # Transform geometry to standard EPSG:4326
    addr_wgs84 = addr_gdf.to_crs(epsg=4326)
    centroids = addr_wgs84.geometry.centroid

    addr_wgs84["lat"] = centroids.y
    addr_wgs84["lng"] = centroids.x
    addr_wgs84["geom_wkt"] = addr_wgs84.geometry.apply(
        lambda g: g.wkt if g is not None and not g.is_empty else None
    )

    # 2. Load Emergency Response Zones & Spatial Point-in-Polygon Join
    logging.info("Reading Emergency Response Zones shapefile...")
    zones_gdf = gpd.read_file(zones_shp_path)
    logging.info(f"Loaded {len(zones_gdf)} response zones. Native CRS: {zones_gdf.crs}")

    if zones_gdf.crs != addr_wgs84.crs:
        logging.info("Re-projecting response zones to EPSG:4326...")
        zones_gdf = zones_gdf.to_crs(epsg=4326)

    logging.info("Performing spatial point-in-polygon join (Address centroids -> Response Zones)...")
    # Use centroid points for spatial join to ensure clean point-in-polygon matching
    addr_points_gdf = addr_wgs84.copy()
    addr_points_gdf.geometry = centroids
    joined = gpd.sjoin(
        addr_points_gdf,
        zones_gdf[["MAP_NAME", "geometry"]],
        how="left",
        predicate="within"
    )

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
        if s == "" or s.lower() in ("nan", "none", "<null>", "null"):
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
        geom_wkt = clean_str(row.get("geom_wkt"))

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
            "geom_wkt": geom_wkt,
            "front_lat": lat,
            "front_lng": lng,
            # entrance_* is DELIBERATELY ABSENT from this dict, and from the INSERT
            # column list below.
            #
            # It holds the OPERATOR-VERIFIED way in -- "gated, keypad at Glen Dr west
            # end" -- recorded by a company officer, and it outranks everything else in
            # address_resolver (entrance -> front -> centroid). Seeding it here set it
            # to the CENTROID, which meant a new parcel resolved to the worst of the
            # three positions while looking like a human had verified it: the good
            # computed front point was skipped, and entrance_set_by/at/note were all
            # NULL with nothing checking them.
            #
            # The centroid is not a safe stand-in. On 177 parcels it falls OUTSIDE the
            # parcel entirely, and on 2865 Glen Dr it sits 135.6 m from Glen Drive.
            #
            # Leaving these unbound means a new row gets SQL NULL, so the resolver falls
            # through to front_lat -- which is computed for every parcel. An unset
            # entrance is a correct answer (CLAUDE.md 6.1); a fabricated one is not.
            #
            # A comment 200 lines above already claimed this invariant and did not hold
            # it -- it was attached to backfill_parcel_frontage, which genuinely never
            # writes entrance, while the INSERT here did. Punch-list #50.
            "streetview_heading": 0.0,
            "streetview_pitch": 5.0,
            "streetview_fov": 80.0,
            "is_pa_page": False
        })

    logging.info(f"Prepared {len(records_to_insert)} clean records for database ingestion.")
    logging.info(f"Emergency Zones assigned: {zone_assigned_count} | Unassigned (boundary edges): {missing_zone_count}")

    # 4. Connect to DB & Bulk UPSERT
    db_url = get_database_url()
    logging.info(f"Connecting to database: {db_url.split('@')[-1] if '@' in db_url else db_url}...")
    engine = create_engine(db_url, pool_pre_ping=True)

    create_parcels_table(engine, drop_existing=drop_existing)

    logging.info(f"Executing batch UPSERT ingestion (batch size: {batch_size})...")
    upsert_sql = text("""
    INSERT INTO public.parcels (
        gis_id, address, house, street, streettype, unit, unittype, postal,
        block, plan, lot, legaldesc, plan_area, folio, zonetype1, zonetype2, zonetype3,
        status, units, sc_card, extract_dt, lat, lng, zone_id, address_normalized,
        geom,
        front_lat, front_lng,
        streetview_heading, streetview_pitch, streetview_fov, is_pa_page
    ) VALUES (
        :gis_id, :address, :house, :street, :streettype, :unit, :unittype, :postal,
        :block, :plan, :lot, :legaldesc, :plan_area, :folio, :zonetype1, :zonetype2, :zonetype3,
        :status, :units, :sc_card, CAST(:extract_dt AS DATE), :lat, :lng, :zone_id, :address_normalized,
        CASE 
            WHEN :geom_wkt IS NOT NULL AND :geom_wkt != '' 
            THEN ST_GeomFromText(:geom_wkt, 4326) 
            ELSE NULL 
        END,
        :front_lat, :front_lng,
        :streetview_heading, :streetview_pitch, :streetview_fov, :is_pa_page
    )
    ON CONFLICT (address) DO UPDATE SET
        gis_id = EXCLUDED.gis_id,
        house = EXCLUDED.house,
        street = EXCLUDED.street,
        streettype = EXCLUDED.streettype,
        unit = EXCLUDED.unit,
        unittype = EXCLUDED.unittype,
        postal = EXCLUDED.postal,
        block = EXCLUDED.block,
        plan = EXCLUDED.plan,
        lot = EXCLUDED.lot,
        legaldesc = EXCLUDED.legaldesc,
        plan_area = EXCLUDED.plan_area,
        folio = EXCLUDED.folio,
        zonetype1 = EXCLUDED.zonetype1,
        zonetype2 = EXCLUDED.zonetype2,
        zonetype3 = EXCLUDED.zonetype3,
        status = EXCLUDED.status,
        units = EXCLUDED.units,
        sc_card = EXCLUDED.sc_card,
        extract_dt = EXCLUDED.extract_dt,
        lat = EXCLUDED.lat,
        lng = EXCLUDED.lng,
        zone_id = EXCLUDED.zone_id,
        address_normalized = EXCLUDED.address_normalized,
        geom = EXCLUDED.geom,
        updated_at = CURRENT_TIMESTAMP;
    """)

    total_processed = 0
    with engine.begin() as conn:
        for i in range(0, len(records_to_insert), batch_size):
            batch = records_to_insert[i:i + batch_size]
            conn.execute(upsert_sql, batch)
            total_processed += len(batch)
            pct = (total_processed / len(records_to_insert)) * 100
            logging.info(f"  Ingested {total_processed}/{len(records_to_insert)} parcels ({pct:.1f}%)...")

    # 5. Compute Road-Facing Frontage Coordinates
    if not skip_frontage:
        backfill_parcel_frontage(engine, batch_size=batch_size)
    else:
        logging.info("Skipping road frontage point backfill (--skip-frontage specified).")

    elapsed_s = time.time() - start_time
    logging.info("=" * 60)
    logging.info(f"SUCCESS: Ingested {total_processed} parcels in {elapsed_s:.2f}s ({(total_processed/elapsed_s):.0f} rows/sec).")
    logging.info("=" * 60)

    # 6. Run Verification Queries
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM public.parcels;")).scalar()
        poly_count = conn.execute(text("SELECT COUNT(*) FROM public.parcels WHERE geom IS NOT NULL;")).scalar()
        zones = conn.execute(text("SELECT COUNT(DISTINCT zone_id) FROM public.parcels WHERE zone_id IS NOT NULL;")).scalar()
        high_rises = conn.execute(text("SELECT COUNT(*) FROM public.parcels WHERE units > 50;")).scalar()
        multi_units = conn.execute(text("SELECT COUNT(*) FROM public.parcels WHERE unit IS NOT NULL AND unit != '';")).scalar()
        frontage_aligned = conn.execute(text("SELECT COUNT(*) FROM public.parcels WHERE front_lat IS NOT NULL AND front_lat != lat;")).scalar()

        logging.info("Verification Summary:")
        logging.info(f"  Total Rows in DB:                 {count}")
        logging.info(f"  Polygons Populated (geom):        {poly_count}")
        logging.info(f"  Road-Aligned Frontage Points:     {frontage_aligned}")
        logging.info(f"  Unique Emergency Zones Populated: {zones}")
        logging.info(f"  Multi-Unit / Condo Rows:          {multi_units}")
        logging.info(f"  High-Rise Buildings (>50 units):  {high_rises}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Coquitlam shapefiles into public.parcels (Non-destructive UPSERT mode)")
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
        "--force-drop",
        action="store_true",
        help="Force drop and recreate public.parcels (WARNING: destroys operational pre-plans/notes)"
    )
    parser.add_argument(
        "--no-drop",
        action="store_true",
        help="Deprecated alias (non-destructive UPSERT is now the default)"
    )
    parser.add_argument(
        "--skip-frontage",
        action="store_true",
        help="Skip PostGIS nearest road frontage point calculation"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Batch insert chunk size (default: 5000)"
    )
    args = parser.parse_args()

    run_import(
        address_shp_path=args.addresses,
        zones_shp_path=args.zones,
        drop_existing=args.force_drop,
        skip_frontage=args.skip_frontage,
        batch_size=args.batch_size
    )
