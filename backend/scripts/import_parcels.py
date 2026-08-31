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

            centroid_lat DOUBLE PRECISION,
            centroid_lng DOUBLE PRECISION,

            zone_id VARCHAR(16),
            address_normalized VARCHAR(255),

            geom geometry(Geometry, 4326),

            -- THE THREE POSITIONS A PARCEL CAN RESOLVE TO -------------------------
            -- address_resolver takes the first that is set:
            --     entrance -> front -> centroid
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
            -- centroid_*  PARCEL POLYGON CENTROID, computed by us from geom -- it is
            --             not supplied by the City. Used for the zone point-in-polygon
            --             join, for map centring, and for simple script work that just
            --             needs one point per parcel. It is ALSO the last-resort
            --             arrival position, and a poor one: on 177 parcels it falls
            --             outside the parcel entirely, and on 2865 Glen Dr it sits
            --             135.6 m from Glen Drive. Never copy it into front_* or
            --             entrance_* -- that is exactly the defect #50 fixed.
            --
            -- There used to be a fourth pair, centroid_lat/centroid_lng. It was a
            -- byte-identical duplicate of these on all 65,400 polygon rows, selected
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

            -- TRUE on CFR-derived rows standing for a whole multi-parcel property and
            -- carrying its operator context; FALSE on rows imported verbatim from the City
            -- address layer. One civic address can span many legal parcels -- 523 Gatensbury
            -- St spans 392 -- and rather than choose between them the import keeps every
            -- City row and adds one base site that speaks for them all (punch-list #48).
            is_base_site BOOLEAN NOT NULL DEFAULT FALSE,

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
        -- address is UNIQUE only among base sites: there must be exactly one per address so
        -- the upsert protecting operator columns has a key. City rows repeat freely, which is
        -- the point -- each keeps its own folio, legaldesc, gis_id and geometry (#48).
        CREATE UNIQUE INDEX IF NOT EXISTS parcels_base_site_address_uniq
            ON public.parcels (address) WHERE is_base_site;
        CREATE INDEX IF NOT EXISTS idx_parcels_address ON public.parcels (address);
        CREATE INDEX IF NOT EXISTS idx_parcels_base_grouping
            ON public.parcels (house, street, streettype) WHERE NOT is_base_site;
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
                WHERE centroid_lat IS NOT NULL AND centroid_lng IS NOT NULL
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
              AND p2.centroid_lat IS NOT NULL AND p2.centroid_lng IS NOT NULL
              AND p2.geom IS NOT NULL
              AND p2.street IS NOT NULL AND btrim(p2.street) <> ''
        ) nearest
        WHERE p.id = nearest.parcel_id;
        """)
        # Parcels whose addressed street has no matching road get NO front point at all.
        #
        # They are not snapped to the nearest road of another name -- that is the defect this
        # whole function was rewritten to remove. But "not snapped" is not sufficient on its
        # own: leaving them untouched means they KEEP whatever the previous any-road
        # algorithm wrote, which is a front point on someone else's street. Measured
        # 2026-08-31: 56 parcels were carrying exactly that, silently, months after the
        # any-road behaviour was removed (punch-list #58).
        #
        # So the unmatched set is explicitly nulled below. A missing arrival point surfaces
        # as the Tier 1 amber card; a stale one routes a crew confidently to the wrong
        # street, and nothing on the kiosk says so. An unknown reported as unknown is a
        # correct answer (§6.1).
        #
        # Every one of these streets is a municipal data gap tracked in
        # docs/city_gis_data_register.md, and they are the natural first entries in the
        # operator entrance queue (punch-list #49), being precisely the properties where no
        # automatic answer exists.
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

        # Clear any front point left behind by an earlier run on a street that has no road.
        with engine.begin() as tx_conn:
            cleared = tx_conn.execute(text("""
                UPDATE public.parcels p
                   SET front_lat = NULL, front_lng = NULL, updated_at = now()
                 WHERE (p.front_lat IS NOT NULL OR p.front_lng IS NOT NULL)
                   AND NOT EXISTS (
                       SELECT 1 FROM public.roads r
                        WHERE r.geom IS NOT NULL
                          AND upper(replace(r.roadname, '''', ''))
                              = upper(replace(p.street, '''', ''))
                   );
            """)).rowcount

        # NOTE: nothing derived from the arrival point is stored alongside it. There was an
        # access_far_corner_m column -- metres from the arrival point to the furthest corner
        # of the parcel -- and it went stale the moment a front point moved, because keeping
        # it correct depended on remembering to recompute it. Nobody did: when #58 cleared 56
        # stale front points on 2026-08-31, those rows kept a distance measured from a point
        # that no longer existed. It was dropped rather than maintained (operator decision:
        # do not store values with no perpetual use). The measurement is still wanted
        # occasionally and is a report, not an attribute -- the query lives in
        # backend/migrations/2026-08-31_drop_access_far_corner.sql.

        elapsed_s = time.time() - start_t
        logging.info(f"  ✓ Road frontage backfill completed for {total_updated} parcels in {elapsed_s:.2f}s.")
        if cleared:
            logging.warning(
                f"  ⚠ Cleared {cleared} stale front point(s) on parcels whose addressed street "
                f"has no road in public.roads. These now report an unknown arrival point "
                f"rather than one on another street (punch-list #58)."
            )
        return total_updated
    except Exception as e:
        logging.error(f"  ✗ Error calculating parcel frontage coordinates: {e}", exc_info=True)
        return 0


def build_base_site_rows(engine) -> int:
    """
    Derives one CFR-owned `base_site` row per multi-parcel property.

    A civic address can span several legal parcels -- 1,508 do, and 523 Gatensbury St spans
    392. The import used to collapse those to one row by keeping whichever the shapefile
    listed first (punch-list #48). Every tiebreak rule considered was wrong in a different
    way, so none is applied: all City rows are kept, and this row is added to speak for the
    whole property.

    The base site holds the CFR context -- entrance point, lockbox, hazard notes, pre-plans --
    and applies to every City row at that address. One entrance set on `2865 Glen Dr` serves
    all 76 of its units, so which City row a lookup happens to return stops mattering.

    Deliberate choices, each with a reason:

    * Grouped on (house, street, streettype), so units group with their base address.
      `2865 Glen Dr 1..76` and `2865 Glen Dr` are one property.
    * Records with no house number are EXCLUDED. Those are street-only right-of-way
      entries -- `Harper Rd` appears 61 times spread over 3.9 km -- and a union of them is
      a multipolygon whose centre means nothing. They resolve at street level anyway.
    * Geometry is ST_Union of the members: the true property extent, which is also what
      fixes the kiosk outlining one lot of eight.
    * ST_PointOnSurface, not ST_Centroid: the point is guaranteed to lie inside the
      polygon. On 177 parcels citywide a centroid falls outside its own parcel, which is
      how zone lookups and frontage snapping went wrong before.
    * The City's MASTER record is NOT used as the base site. Measured first: across 517
      properties it averages 10.3% of the summed unit area while spanning the whole site,
      because it is strata COMMON PROPERTY -- driveways and walkways between the units --
      not the building and not the envelope. See docs/briefings/base_site_rows_decision.md.
    * The ON CONFLICT list carries no operator column. entrance_*, lock_box_notes,
      hazard_notes, pre_plan_pdf_url, construction_type and floor_count are protected by
      omission, exactly as they are on City rows. Human knowledge must survive the pipeline
      that regenerates computed values.

    Front points are not set here -- backfill_parcel_frontage runs afterwards and treats a
    base site like any other row, snapping it to the street its address names.
    """
    from sqlalchemy import text
    logging.info("=" * 60)
    logging.info("Step: Deriving base_site rows for multi-parcel properties...")

    sql = text("""
        INSERT INTO public.parcels (
            address, house, street, streettype, address_normalized,
            geom, centroid_lat, centroid_lng, zone_id, is_base_site
        )
        SELECT
            btrim(concat_ws(' ', p.house, p.street, p.streettype)),
            p.house, p.street, p.streettype,
            lower(btrim(concat_ws(' ', p.house, p.street, p.streettype))),
            ST_Multi(ST_Union(p.geom)),
            ST_Y(ST_PointOnSurface(ST_Union(p.geom))),
            ST_X(ST_PointOnSurface(ST_Union(p.geom))),
            public.zone_for_point(ST_PointOnSurface(ST_Union(p.geom))),
            TRUE
        FROM public.parcels p
        WHERE NOT p.is_base_site
          AND p.house  IS NOT NULL AND btrim(p.house)  <> ''
          AND p.street IS NOT NULL AND btrim(p.street) <> ''
          AND p.geom   IS NOT NULL
        GROUP BY p.house, p.street, p.streettype
        HAVING count(*) > 1
        ON CONFLICT (address) WHERE is_base_site DO UPDATE SET
            house              = EXCLUDED.house,
            street             = EXCLUDED.street,
            streettype         = EXCLUDED.streettype,
            address_normalized = EXCLUDED.address_normalized,
            geom               = EXCLUDED.geom,
            centroid_lat       = EXCLUDED.centroid_lat,
            centroid_lng       = EXCLUDED.centroid_lng,
            zone_id            = EXCLUDED.zone_id,
            updated_at         = now();
    """)

    try:
        with engine.begin() as conn:
            written = conn.execute(sql).rowcount
        with engine.connect() as conn:
            total = conn.execute(text(
                "SELECT count(*) FROM public.parcels WHERE is_base_site;")).scalar()
            no_zone = conn.execute(text(
                "SELECT count(*) FROM public.parcels WHERE is_base_site AND zone_id IS NULL;")).scalar()
        logging.info(f"  ✓ {written} base_site rows written; {total} exist in total.")
        if no_zone:
            logging.warning(
                f"  ⚠ {no_zone} base site(s) resolve to no emergency zone. A unioned property "
                f"can straddle a zone boundary or fall in a gap; these need review.")
        return total
    except Exception as e:
        logging.error(f"  ✗ Error deriving base_site rows: {e}", exc_info=True)
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
    duplicate_addresses = 0
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

        # EVERY City record is kept, duplicates included.
        #
        # This previously skipped any address string already seen, which collapsed 1,508
        # groups and discarded 4,141 records -- keeping whichever the shapefile happened to
        # list first, in file order, with no rule. 631 of those groups have members more than
        # 25 m apart, so the survivor was frequently not the lot a crew arrives at, and the
        # discarded rows took their own folio, legaldesc and geometry with them.
        #
        # Nothing chooses between them now. A CFR-owned base site row is derived afterwards
        # and speaks for the whole property (build_base_site_rows below, punch-list #48).
        duplicate_addresses += raw_addr in seen_addresses
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
            "centroid_lat": lat,
            "centroid_lng": lng,
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

    logging.info(f"Prepared {len(records_to_insert)} City records for ingestion "
                 f"({duplicate_addresses} share an address with another record and are all kept).")
    logging.info(f"Emergency Zones assigned: {zone_assigned_count} | Unassigned (boundary edges): {missing_zone_count}")

    # 4. Connect to DB & Bulk UPSERT
    db_url = get_database_url()
    logging.info(f"Connecting to database: {db_url.split('@')[-1] if '@' in db_url else db_url}...")
    engine = create_engine(db_url, pool_pre_ping=True)

    create_parcels_table(engine, drop_existing=drop_existing)

    # City address rows are replaced wholesale rather than upserted.
    #
    # `address` is no longer unique among them -- 1,508 civic addresses legitimately span
    # several legal parcels -- so ON CONFLICT (address) has nothing to key on, and if it did
    # it would collapse precisely what #48 stopped collapsing.
    #
    # Replacing them is safe because City rows carry NO operator data. Every piece of CFR
    # knowledge -- entrance point, lockbox, hazard notes, pre-plans -- lives on a base_site
    # row, which is preserved here and upserted separately below. That separation is what
    # makes the City half disposable, and it is the whole reason this design works.
    #
    # If single-parcel properties ever need notes of their own, the answer is to give that
    # address a base_site row too, NOT to write context onto a City row (operator decision
    # 2026-08-31, docs/briefings/base_site_rows_decision.md).
    logging.info("Replacing City address rows (base sites are preserved)...")
    with engine.begin() as conn:
        removed = conn.execute(text(
            "DELETE FROM public.parcels WHERE NOT is_base_site;"
        )).rowcount
        preserved = conn.execute(text(
            "SELECT count(*) FROM public.parcels WHERE is_base_site;"
        )).scalar()
    logging.info(f"  Removed {removed} City rows; {preserved} base site rows preserved.")

    logging.info(f"Executing batch ingestion (batch size: {batch_size})...")
    insert_sql = text("""
    INSERT INTO public.parcels (
        gis_id, address, house, street, streettype, unit, unittype, postal,
        block, plan, lot, legaldesc, plan_area, folio, zonetype1, zonetype2, zonetype3,
        status, units, sc_card, extract_dt, centroid_lat, centroid_lng, zone_id, address_normalized,
        geom,
        front_lat, front_lng,
        streetview_heading, streetview_pitch, streetview_fov, is_pa_page
    ) VALUES (
        :gis_id, :address, :house, :street, :streettype, :unit, :unittype, :postal,
        :block, :plan, :lot, :legaldesc, :plan_area, :folio, :zonetype1, :zonetype2, :zonetype3,
        :status, :units, :sc_card, CAST(:extract_dt AS DATE), :centroid_lat, :centroid_lng, :zone_id, :address_normalized,
        CASE 
            WHEN :geom_wkt IS NOT NULL AND :geom_wkt != '' 
            THEN ST_GeomFromText(:geom_wkt, 4326) 
            ELSE NULL 
        END,
        :front_lat, :front_lng,
        :streetview_heading, :streetview_pitch, :streetview_fov, :is_pa_page
    );
    """)

    total_processed = 0
    with engine.begin() as conn:
        for i in range(0, len(records_to_insert), batch_size):
            batch = records_to_insert[i:i + batch_size]
            conn.execute(insert_sql, batch)
            total_processed += len(batch)
            pct = (total_processed / len(records_to_insert)) * 100
            logging.info(f"  Ingested {total_processed}/{len(records_to_insert)} parcels ({pct:.1f}%)...")

    # 5. Derive base_site rows -- must run before frontage, so each base site gets a front
    #    point of its own from the street its address names.
    build_base_site_rows(engine)

    # 6. Compute Road-Facing Frontage Coordinates
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
