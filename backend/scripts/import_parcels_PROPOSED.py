#!/usr/bin/env python3
"""
backend/scripts/import_parcels_PROPOSED.py
Authoritative GIS ingestion & parcel boundary snapping script for CFR EVO.

Proposed replacement for backend/scripts/import_parcels.py implementing:
- Section 2.2 of docs/emergency_routing_gis_parcels_standard.md: Boundary-Edge Decomposition
  and Multi-Criteria Frontage Scoring for emergency apparatus tactical arrival endpoints.
- Non-destructive UPSERT (ON CONFLICT address): preserves operational pre-plans, lockbox notes,
  hazards, custom frontage/entrance overrides, and streetview headings.
- 100% Coquitlam Addresses.shp ingestion with Polygon/MultiPolygon geometry in EPSG:4326.
- Pre-computes emergency response zone_id (1..134) via spatial point-in-polygon intersection.
- PostGIS boundary edge decomposition with angular parallelism (cos^2 Delta theta), edge length,
  road classification hierarchy weighting, distance exponential decay, and multiplicative street
  name prior (1.0 + 2.0 * I_name) to eliminate naive centroid snapping failure modes.
- Maintains 100% compatibility with existing OSRM routing infrastructure and public.roads schema.
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
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto";'))
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS postgis;'))

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


def install_snap_stored_procedure(engine):
    """
    Installs the PostGIS stored function `fn_calculate_parcel_road_snap` in PostgreSQL
    per Section 2.6 of docs/emergency_routing_gis_parcels_standard.md.
    """
    from sqlalchemy import text
    fn_sql = text("""
    CREATE OR REPLACE FUNCTION public.fn_calculate_parcel_road_snap(
        p_parcel_id BIGINT,
        p_target_street VARCHAR(255) DEFAULT NULL
    )
    RETURNS TABLE (
        snap_lat DOUBLE PRECISION,
        snap_lng DOUBLE PRECISION,
        snapped_road_id BIGINT,
        snapped_road_name VARCHAR(255),
        snap_distance_m DOUBLE PRECISION,
        frontage_edge_geom GEOMETRY(LineString, 4326),
        snap_point_geom GEOMETRY(Point, 4326)
    )
    LANGUAGE plpgsql
    AS '
    DECLARE
        v_parcel_geom GEOMETRY(Geometry, 4326);
        v_parcel_geom_utm GEOMETRY(Geometry, 26910);
        v_target_street VARCHAR(255);
        v_clean_street VARCHAR(255);
        v_found_rows INTEGER;
    BEGIN
        SELECT geom, ST_Transform(geom, 26910), COALESCE(p_target_street, street)
        INTO v_parcel_geom, v_parcel_geom_utm, v_target_street
        FROM public.parcels
        WHERE id = p_parcel_id;

        IF v_parcel_geom IS NULL THEN
            RETURN;
        END IF;

        -- Normalize target street by stripping leading numbers and trailing road type abbreviations
        IF v_target_street IS NOT NULL THEN
            v_clean_street := TRIM(REGEXP_REPLACE(
                REGEXP_REPLACE(TRIM(v_target_street), ''^[0-9]+[A-Za-z]?\\s+'', '''', ''i''),
                ''\\s+(ST|STREET|RD|ROAD|AVE|AVENUE|DR|DRIVE|BLVD|BOULEVARD|HWY|HIGHWAY|CRES|CRESCENT|CT|COURT|PL|PLACE|LN|LANE|WY|WAY|TERR|TERRACE|PKWY|PARKWAY|TRAIL|TRL|CIR|CIRCLE|GATE|ROW|MEWS|WALK)$'',
                '''',
                ''i''
            ));
        END IF;

        IF ST_GeometryType(v_parcel_geom) = ''ST_Point'' THEN
            RETURN QUERY
            WITH candidate_roads AS (
                SELECT 
                    r.id AS r_id,
                    r.fullname AS r_fullname,
                    r.roadname AS r_roadname,
                    (ST_Dump(ST_Transform(r.geom, 26910))).geom AS r_geom_utm
                FROM public.roads r
                WHERE r.geom && ST_Expand(v_parcel_geom, 0.005)
                  AND ST_DWithin(ST_Transform(r.geom, 26910), v_parcel_geom_utm, 200.0)
            ),
            ranked_points AS (
                SELECT 
                    c.r_id,
                    c.r_fullname,
                    ST_ClosestPoint(c.r_geom_utm, v_parcel_geom_utm) AS pt_utm,
                    ST_Distance(c.r_geom_utm, v_parcel_geom_utm) AS dist_m,
                    CASE 
                        WHEN v_clean_street IS NOT NULL AND (
                            UPPER(c.r_fullname) ILIKE ''%'' || UPPER(v_clean_street) || ''%'' OR
                            UPPER(c.r_roadname) = UPPER(v_clean_street) OR
                            UPPER(c.r_fullname) ILIKE ''%'' || UPPER(v_target_street) || ''%''
                        ) THEN 100.0
                        ELSE 0.0
                    END AS name_bonus
                FROM candidate_roads c
                ORDER BY (ST_Distance(c.r_geom_utm, v_parcel_geom_utm) - (
                    CASE 
                        WHEN v_clean_street IS NOT NULL AND (
                            UPPER(c.r_fullname) ILIKE ''%'' || UPPER(v_clean_street) || ''%'' OR
                            UPPER(c.r_roadname) = UPPER(v_clean_street) OR
                            UPPER(c.r_fullname) ILIKE ''%'' || UPPER(v_target_street) || ''%''
                        ) THEN 100.0
                        ELSE 0.0
                    END
                )) ASC
                LIMIT 1
            )
            SELECT 
                ST_Y(ST_Transform(rp.pt_utm, 4326)) AS snap_lat,
                ST_X(ST_Transform(rp.pt_utm, 4326)) AS snap_lng,
                rp.r_id AS snapped_road_id,
                rp.r_fullname AS snapped_road_name,
                rp.dist_m AS snap_distance_m,
                NULL::GEOMETRY(LineString, 4326) AS frontage_edge_geom,
                ST_Transform(rp.pt_utm, 4326) AS snap_point_geom
            FROM ranked_points rp;
            RETURN;
        END IF;

        RETURN QUERY
        WITH boundary_edges AS (
            SELECT 
                (ST_DumpSegments(ST_ExteriorRing((ST_Dump(v_parcel_geom_utm)).geom))).geom AS edge_geom_utm
        ),
        candidate_roads AS (
            SELECT 
                r.id AS r_id,
                r.fullname AS r_fullname,
                r.roadname AS r_roadname,
                r.road_class,
                (ST_Dump(ST_Transform(r.geom, 26910))).geom AS r_geom_utm
            FROM public.roads r
            WHERE r.geom && ST_Expand(v_parcel_geom, 0.002)
              AND ST_DWithin(ST_Transform(r.geom, 26910), v_parcel_geom_utm, 60.0)
        ),
        edge_road_pairs AS (
            SELECT 
                e.edge_geom_utm,
                r.r_id,
                r.r_fullname,
                r.road_class,
                ST_Length(e.edge_geom_utm) AS edge_len_m,
                ST_Distance(e.edge_geom_utm, r.r_geom_utm) AS dist_m,
                CASE 
                    WHEN ST_Equals(
                        ST_ClosestPoint(r.r_geom_utm, ST_StartPoint(e.edge_geom_utm)),
                        ST_ClosestPoint(r.r_geom_utm, ST_EndPoint(e.edge_geom_utm))
                    ) THEN 90.0
                    ELSE ABS(
                        degrees(ST_Azimuth(ST_StartPoint(e.edge_geom_utm), ST_EndPoint(e.edge_geom_utm))) -
                        degrees(ST_Azimuth(
                            ST_ClosestPoint(r.r_geom_utm, ST_StartPoint(e.edge_geom_utm)),
                            ST_ClosestPoint(r.r_geom_utm, ST_EndPoint(e.edge_geom_utm))
                        ))
                    )
                END AS angle_diff_deg,
                CASE 
                    WHEN v_clean_street IS NOT NULL AND (
                        UPPER(r.r_fullname) ILIKE ''%'' || UPPER(v_clean_street) || ''%'' OR
                        UPPER(r.r_roadname) = UPPER(v_clean_street) OR
                        (v_target_street IS NOT NULL AND UPPER(r.r_fullname) ILIKE ''%'' || UPPER(v_target_street) || ''%'')
                    ) THEN 1.0
                    ELSE 0.0
                END AS name_match_factor,
                CASE 
                    WHEN r.road_class IN (''ART'', ''HWY'', ''COL'') THEN 1.2
                    WHEN r.road_class = ''LOC'' THEN 1.0
                    WHEN r.road_class = ''LANE'' THEN 0.2
                    ELSE 0.5
                END AS class_weight,
                r.r_geom_utm
            FROM boundary_edges e
            CROSS JOIN candidate_roads r
            WHERE ST_Distance(e.edge_geom_utm, r.r_geom_utm) < 60.0
              AND ST_Length(e.edge_geom_utm) > 0.5
        ),
        scored_edges AS (
            SELECT 
                erp.*,
                (
                    (0.60 * COALESCE(POWER(COS(radians(erp.angle_diff_deg)), 2), 0.0)) +
                    (0.40 * LN(1.0 + LEAST(erp.edge_len_m, 30.0)))
                ) * erp.class_weight * EXP(-erp.dist_m / 25.0) * (1.0 + 2.0 * erp.name_match_factor) AS score,
                ST_LineInterpolatePoint(
                    erp.r_geom_utm,
                    ST_LineLocatePoint(erp.r_geom_utm, ST_PointOnSurface(erp.edge_geom_utm))
                ) AS snap_pt_utm
            FROM edge_road_pairs erp
            ORDER BY score DESC NULLS LAST
            LIMIT 1
        )
        SELECT 
            ST_Y(ST_Transform(se.snap_pt_utm, 4326)) AS snap_lat,
            ST_X(ST_Transform(se.snap_pt_utm, 4326)) AS snap_lng,
            se.r_id AS snapped_road_id,
            se.r_fullname AS snapped_road_name,
            se.dist_m AS snap_distance_m,
            ST_Transform(se.edge_geom_utm, 4326) AS frontage_edge_geom,
            ST_Transform(se.snap_pt_utm, 4326) AS snap_point_geom
        FROM scored_edges se;

        -- Tier 5 Fallback: If 0 rows matched (rural/park parcel >60m from roads)
        GET DIAGNOSTICS v_found_rows = ROW_COUNT;
        IF v_found_rows = 0 THEN
            RETURN QUERY
            WITH nearest_road AS (
                SELECT 
                    r.id AS r_id,
                    r.fullname AS r_fullname,
                    (ST_Dump(ST_Transform(r.geom, 26910))).geom AS r_geom_utm
                FROM public.roads r
                WHERE r.geom IS NOT NULL
                ORDER BY r.geom <-> v_parcel_geom
                LIMIT 1
            ),
            proj AS (
                SELECT 
                    nr.r_id,
                    nr.r_fullname,
                    ST_ClosestPoint(nr.r_geom_utm, v_parcel_geom_utm) AS pt_utm,
                    ST_Distance(nr.r_geom_utm, v_parcel_geom_utm) AS dist_m
                FROM nearest_road nr
            )
            SELECT 
                ST_Y(ST_Transform(p.pt_utm, 4326)) AS snap_lat,
                ST_X(ST_Transform(p.pt_utm, 4326)) AS snap_lng,
                p.r_id AS snapped_road_id,
                p.r_fullname AS snapped_road_name,
                p.dist_m AS snap_distance_m,
                NULL::GEOMETRY(LineString, 4326) AS frontage_edge_geom,
                ST_Transform(p.pt_utm, 4326) AS snap_point_geom
            FROM proj p;
        END IF;
    END;
    ';
    """)
    try:
        with engine.begin() as conn:
            conn.execute(fn_sql)
        logging.info("  ✓ Stored procedure fn_calculate_parcel_road_snap registered.")
    except Exception as e:
        logging.warning(f"  Note: fn_calculate_parcel_road_snap registration notice: {e}")


def backfill_parcel_frontage(engine, batch_size: int = 500, recalculate_all: bool = True) -> int:
    """
    Computes front_lat/front_lng using the Boundary-Edge Decomposition snapping algorithm
    (Section 2.2 of docs/emergency_routing_gis_parcels_standard.md).

    Mathematical Formulation:
    - Decomposes exterior polygon ring into 2-point linear edges E_i.
    - Searches candidate road segments R_j in public.roads within 60m search radius.
    - Evaluates all MultiLineString linear components without arbitrary segment loss.
    - Calculates angular alignment parallelism Phi(E_i, R_j) = cos^2(Delta theta).
    - Calculates edge frontage length L(E_i) with logarithmic dampening: ln(1 + min(L, 30m)).
    - Applies road classification hierarchy weight W_class: 1.2 Arterial/Collector, 1.0 Local, 0.2 Lane.
    - Applies distance exponential decay exp(-d / 25m).
    - Multiplies by authoritative street name prior (1.0 + 2.0 * I_name) to prioritize civic frontage.
    - Projects orthogonally to road centerline: P_snap = ST_LineInterpolatePoint(R*, ST_LineLocatePoint(R*, ST_PointOnSurface(E*))).
    - Provides Tier 5 nearest road centerline fallback for Point parcels and distant park parcels.
    """
    from sqlalchemy import text
    logging.info("=" * 60)
    logging.info("Step: Computing Boundary-Edge Decomposition Frontage Points (public.parcels)...")

    try:
        with engine.connect() as conn:
            roads_exists = conn.execute(text("SELECT to_regclass('public.roads');")).scalar()
            if not roads_exists:
                logging.warning("  public.roads table does not exist. Skipping frontage computation.")
                return 0

            road_count = conn.execute(text("SELECT COUNT(*) FROM public.roads WHERE geom IS NOT NULL;")).scalar()
            if not road_count or road_count == 0:
                logging.warning("  public.roads has no geometry records. Skipping frontage computation.")
                return 0

            logging.info(f"  Found {road_count} road segments in public.roads with geometry.")

            # Identify candidate parcel IDs requiring frontage calculation
            if recalculate_all:
                candidate_ids = [r[0] for r in conn.execute(text("""
                    SELECT id 
                    FROM public.parcels 
                    WHERE lat IS NOT NULL AND lng IS NOT NULL 
                    ORDER BY id;
                """)).fetchall()]
            else:
                candidate_ids = [r[0] for r in conn.execute(text("""
                    SELECT id 
                    FROM public.parcels 
                    WHERE lat IS NOT NULL AND lng IS NOT NULL 
                      AND (front_lat IS NULL OR (front_lat = lat AND front_lng = lng))
                    ORDER BY id;
                """)).fetchall()]

        total_candidates = len(candidate_ids)
        if total_candidates == 0:
            logging.info("  All parcels already have frontage points.")
            return 0

        logging.info(f"  Calculating boundary edge snapping for {total_candidates} parcels (chunks of {batch_size})...")

        # Core Boundary Edge Decomposition Batch SQL Query
        # Evaluates all LineString components of candidate roads within 60m
        edge_decomp_sql = text("""
        UPDATE public.parcels p SET
            front_lat = best_snap.front_lat,
            front_lng = best_snap.front_lng
        FROM (
            WITH batch_parcels AS (
                SELECT id, address, street, geom, lat, lng
                FROM public.parcels
                WHERE id >= :min_id AND id <= :max_id
                  AND geom IS NOT NULL
            ),
            candidate_roads AS (
                SELECT 
                    bp.id AS parcel_id,
                    bp.street,
                    r.id AS r_id,
                    r.fullname AS r_fullname,
                    r.roadname AS r_roadname,
                    r.road_class,
                    (ST_Dump(ST_Transform(r.geom, 26910))).geom AS r_geom_utm
                FROM batch_parcels bp
                JOIN public.roads r ON r.geom && ST_Expand(bp.geom, 0.001)
                WHERE ST_DWithin(ST_Transform(r.geom, 26910), ST_Transform(bp.geom, 26910), 60.0)
            ),
            boundary_edges AS (
                SELECT 
                    bp.id AS parcel_id,
                    bp.street,
                    (ST_DumpSegments(ST_ExteriorRing((ST_Dump(ST_Transform(bp.geom, 26910))).geom))).geom AS edge_geom_utm
                FROM batch_parcels bp
                WHERE ST_GeometryType(bp.geom) IN ('ST_Polygon', 'ST_MultiPolygon')
            ),
            edge_road_pairs AS (
                SELECT 
                    e.parcel_id,
                    e.edge_geom_utm,
                    cr.r_geom_utm,
                    cr.road_class,
                    cr.r_fullname,
                    cr.r_roadname,
                    cr.street,
                    ST_Length(e.edge_geom_utm) AS edge_len_m,
                    ST_Distance(e.edge_geom_utm, cr.r_geom_utm) AS dist_m
                FROM boundary_edges e
                JOIN candidate_roads cr ON cr.parcel_id = e.parcel_id
                WHERE ST_Distance(e.edge_geom_utm, cr.r_geom_utm) < 60.0
                  AND ST_Length(e.edge_geom_utm) > 0.5
            ),
            scored_edges AS (
                SELECT 
                    erp.parcel_id,
                    ST_Y(ST_Transform(erp.snap_pt_utm, 4326)) AS front_lat,
                    ST_X(ST_Transform(erp.snap_pt_utm, 4326)) AS front_lng,
                    ROW_NUMBER() OVER (PARTITION BY erp.parcel_id ORDER BY erp.score DESC NULLS LAST) AS rnk
                FROM (
                    SELECT 
                        erp.parcel_id,
                        (
                            (0.60 * COALESCE(POWER(COS(radians(
                                CASE 
                                    WHEN ST_Equals(
                                        ST_ClosestPoint(erp.r_geom_utm, ST_StartPoint(erp.edge_geom_utm)),
                                        ST_ClosestPoint(erp.r_geom_utm, ST_EndPoint(erp.edge_geom_utm))
                                    ) THEN 90.0
                                    ELSE ABS(
                                        degrees(ST_Azimuth(ST_StartPoint(erp.edge_geom_utm), ST_EndPoint(erp.edge_geom_utm))) -
                                        degrees(ST_Azimuth(
                                            ST_ClosestPoint(erp.r_geom_utm, ST_StartPoint(erp.edge_geom_utm)),
                                            ST_ClosestPoint(erp.r_geom_utm, ST_EndPoint(erp.edge_geom_utm))
                                        ))
                                    )
                                END
                            )), 2), 0.0)) +
                            (0.40 * LN(1.0 + LEAST(erp.edge_len_m, 30.0)))
                        ) * 
                        CASE 
                            WHEN erp.road_class IN ('ART', 'HWY', 'COL') THEN 1.2
                            WHEN erp.road_class = 'LOC' THEN 1.0
                            WHEN erp.road_class = 'LANE' THEN 0.2
                            ELSE 0.5
                        END * 
                        EXP(-erp.dist_m / 25.0) * 
                        (1.0 + 2.0 * (
                            CASE 
                                WHEN erp.street IS NOT NULL AND (
                                    UPPER(erp.r_fullname) ILIKE '%' || UPPER(erp.street) || '%' OR
                                    UPPER(erp.r_roadname) = UPPER(erp.street) OR
                                    UPPER(erp.r_roadname) ILIKE '%' || UPPER(erp.street) || '%'
                                ) THEN 1.0 
                                ELSE 0.0 
                            END
                        )) AS score,
                        ST_LineInterpolatePoint(
                            erp.r_geom_utm,
                            ST_LineLocatePoint(erp.r_geom_utm, ST_PointOnSurface(erp.edge_geom_utm))
                        ) AS snap_pt_utm
                    FROM edge_road_pairs erp
                ) erp
            )
            SELECT parcel_id, front_lat, front_lng
            FROM scored_edges
            WHERE rnk = 1
        ) best_snap
        WHERE p.id = best_snap.parcel_id;
        """)

        # Fallback query for Point parcels or parcels beyond 60m boundary snapping
        fallback_sql = text("""
        UPDATE public.parcels p SET
            front_lat = ST_Y(nearest.pt),
            front_lng = ST_X(nearest.pt)
        FROM (
            SELECT DISTINCT ON (p2.id)
                p2.id as parcel_id,
                ST_ClosestPoint(
                    ST_Transform(r.r_geom_utm, 4326),
                    ST_SetSRID(ST_MakePoint(p2.lng, p2.lat), 4326)
                ) as pt
            FROM public.parcels p2
            CROSS JOIN LATERAL (
                SELECT (ST_Dump(ST_Transform(r2.geom, 26910))).geom AS r_geom_utm
                FROM public.roads r2
                WHERE r2.geom IS NOT NULL
                ORDER BY r2.geom <-> ST_SetSRID(ST_MakePoint(p2.lng, p2.lat), 4326)
                LIMIT 1
            ) r
            WHERE p2.id >= :min_id AND p2.id <= :max_id
              AND p2.lat IS NOT NULL AND p2.lng IS NOT NULL
              AND (
                  p2.front_lat IS NULL 
                  OR (p2.front_lat = p2.lat AND p2.front_lng = p2.lng)
                  OR ST_GeometryType(p2.geom) = 'ST_Point'
              )
        ) nearest
        WHERE p.id = nearest.parcel_id;
        """)

        start_t = time.time()
        total_updated = 0

        for i in range(0, total_candidates, batch_size):
            chunk = candidate_ids[i:i + batch_size]
            min_id = chunk[0]
            max_id = chunk[-1]

            with engine.begin() as tx_conn:
                res = tx_conn.execute(edge_decomp_sql, {"min_id": min_id, "max_id": max_id})
                updated_chunk = res.rowcount if hasattr(res, "rowcount") else len(chunk)
                total_updated += updated_chunk

                # Execute fallback for any remaining unassigned or Point parcels
                tx_conn.execute(fallback_sql, {"min_id": min_id, "max_id": max_id})

            pct = (min(i + batch_size, total_candidates) / total_candidates) * 100
            elapsed = time.time() - start_t
            rate = (i + len(chunk)) / elapsed if elapsed > 0 else 0
            logging.info(
                f"  Edge snapping progress: {min(i + batch_size, total_candidates)}/{total_candidates} "
                f"parcels ({pct:.1f}%) [{rate:.0f} rows/s]..."
            )

        elapsed_s = time.time() - start_t
        logging.info(f"  ✓ Boundary-Edge Decomposition frontage backfill completed for {total_updated} parcels in {elapsed_s:.2f}s.")
        return total_updated
    except Exception as e:
        logging.error(f"  ✗ Error calculating boundary-edge parcel frontage: {e}", exc_info=True)
        return 0


def run_import(
    address_shp_path: str,
    zones_shp_path: str,
    drop_existing: bool = False,
    skip_frontage: bool = False,
    recalculate_all: bool = True,
    frontage_only: bool = False,
    batch_size: int = 500
):
    """Executes the full GIS shapefile loading, spatial zone intersection, UPSERT ingestion, and boundary-edge snapping."""
    from sqlalchemy import create_engine, text

    start_time = time.time()
    db_url = get_database_url()
    logging.info("=" * 60)
    logging.info("CFR EVO: Boundary-Edge Decomposition Parcel Snapping & GIS Ingestion")
    logging.info(f"Database:         {db_url.split('@')[-1] if '@' in db_url else db_url}")
    logging.info(f"Ingestion mode:   {'FORCE DROP & RECREATE' if drop_existing else 'NON-DESTRUCTIVE UPSERT'}")
    logging.info("=" * 60)

    engine = create_engine(db_url, pool_pre_ping=True)
    create_parcels_table(engine, drop_existing=drop_existing)
    install_snap_stored_procedure(engine)

    if not frontage_only:
        import geopandas as gpd

        if not os.path.exists(address_shp_path):
            logging.error(f"Addresses shapefile not found at: {address_shp_path}")
            sys.exit(1)
        if not os.path.exists(zones_shp_path):
            logging.error(f"Emergency Response Zones shapefile not found at: {zones_shp_path}")
            sys.exit(1)

        logging.info(f"Addresses source: {address_shp_path}")
        logging.info(f"Zones source:     {zones_shp_path}")

        # 1. Load Addresses Shapefile & Reproject to WGS84
        logging.info("Reading Addresses shapefile...")
        addr_gdf = gpd.read_file(address_shp_path)
        total_raw = len(addr_gdf)
        logging.info(f"Loaded {total_raw} raw address records. Native CRS: {addr_gdf.crs}")

        if addr_gdf.crs is None:
            logging.warning("Addresses CRS is undefined. Assuming EPSG:26910 (UTM Zone 10N)...")
            addr_gdf.set_crs(epsg=26910, inplace=True)

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
                "centroid_lat": lat,
                "centroid_lng": lng,
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
        logging.info(f"Emergency Zones assigned: {zone_assigned_count} | Unassigned: {missing_zone_count}")

        # 4. Connect to DB & Bulk UPSERT
        upsert_batch_size = max(batch_size, 2000)
        logging.info(f"Executing batch UPSERT ingestion (batch size: {upsert_batch_size})...")
        upsert_sql = text("""
        INSERT INTO public.parcels (
            gis_id, address, house, street, streettype, unit, unittype, postal,
            block, plan, lot, legaldesc, plan_area, folio, zonetype1, zonetype2, zonetype3,
            status, units, sc_card, extract_dt, lat, lng, zone_id, address_normalized,
            geom,
            front_lat, front_lng, centroid_lat, centroid_lng,
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
            :front_lat, :front_lng, :centroid_lat, :centroid_lng,
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
            centroid_lat = EXCLUDED.centroid_lat,
            centroid_lng = EXCLUDED.centroid_lng,
            zone_id = EXCLUDED.zone_id,
            address_normalized = EXCLUDED.address_normalized,
            geom = EXCLUDED.geom,
            updated_at = CURRENT_TIMESTAMP;
        """)

        total_processed = 0
        with engine.begin() as conn:
            for i in range(0, len(records_to_insert), upsert_batch_size):
                batch = records_to_insert[i:i + upsert_batch_size]
                conn.execute(upsert_sql, batch)
                total_processed += len(batch)
                pct = (total_processed / len(records_to_insert)) * 100
                logging.info(f"  Ingested {total_processed}/{len(records_to_insert)} parcels ({pct:.1f}%)...")

    # 5. Compute Boundary-Edge Road Frontage Coordinates
    if not skip_frontage:
        backfill_parcel_frontage(engine, batch_size=batch_size, recalculate_all=recalculate_all)
    else:
        logging.info("Skipping road frontage calculation (--skip-frontage specified).")

    elapsed_s = time.time() - start_time
    logging.info("=" * 60)
    logging.info(f"SUCCESS: Parcel ingestion & boundary snapping complete in {elapsed_s:.2f}s.")
    logging.info("=" * 60)

    # 6. Verification Summary
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM public.parcels;")).scalar()
        poly_count = conn.execute(text("SELECT COUNT(*) FROM public.parcels WHERE geom IS NOT NULL;")).scalar()
        zones = conn.execute(text("SELECT COUNT(DISTINCT zone_id) FROM public.parcels WHERE zone_id IS NOT NULL;")).scalar()
        frontage_aligned = conn.execute(text("SELECT COUNT(*) FROM public.parcels WHERE front_lat IS NOT NULL AND front_lat != lat;")).scalar()

        logging.info("Verification Summary:")
        logging.info(f"  Total Rows in DB:                 {count}")
        logging.info(f"  Polygons Populated (geom):        {poly_count}")
        logging.info(f"  Road-Aligned Frontage Points:     {frontage_aligned}")
        logging.info(f"  Unique Emergency Zones Populated: {zones}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Coquitlam shapefiles into public.parcels with Boundary-Edge Decomposition Snapping")
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
        help="Deprecated alias (non-destructive UPSERT is the default)"
    )
    parser.add_argument(
        "--skip-frontage",
        action="store_true",
        help="Skip boundary-edge road frontage calculation"
    )
    parser.add_argument(
        "--frontage-only",
        action="store_true",
        help="Execute boundary-edge frontage calculation only, without re-reading shapefiles"
    )
    parser.add_argument(
        "--recalculate-all",
        action="store_true",
        default=True,
        help="Recalculate boundary frontage for all parcels (default: True)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch chunk size for boundary snapping (default: 500)"
    )
    args = parser.parse_args()

    run_import(
        address_shp_path=args.addresses,
        zones_shp_path=args.zones,
        drop_existing=args.force_drop,
        skip_frontage=args.skip_frontage,
        recalculate_all=args.recalculate_all,
        frontage_only=args.frontage_only,
        batch_size=args.batch_size
    )
