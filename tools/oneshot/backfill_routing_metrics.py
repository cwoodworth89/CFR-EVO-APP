#!/usr/bin/env python3
"""
CFR EVO - Historical Routing Metrics Migration & Backfill Script
Adds the routing_metrics JSONB column to public.dispatches and backfills
per-unit driving distance and ETA metrics from Home Fire Halls for all historical dispatches.
"""

import os
import sys
import json
import logging
import psycopg2
from pathlib import Path

# Add backend and sibling service roots to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/, for _repo
from _repo import BACKEND as BACKEND_DIR, SERVICES as SERVICES_DIR
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SERVICES_DIR / "gis" / "src") not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR / "gis" / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        try:
            return psycopg2.connect(db_url)
        except Exception as e:
            logging.warning(f"Failed connecting to DATABASE_URL: {e}")

    # Docker internal vs external fallbacks
    hosts = [
        os.environ.get("DB_HOST", "localhost"),
        "localhost",
        "cfr_postgres",
        "127.0.0.1"
    ]
    for h in hosts:
        try:
            conn = psycopg2.connect(
                dbname=os.environ.get("POSTGRES_DB", "cfr_dispatch"),
                user=os.environ.get("POSTGRES_USER", "cfr_user"),
                password=os.environ.get("POSTGRES_PASSWORD", "cfr_password_2026"),
                host=h,
                port=int(os.environ.get("POSTGRES_PORT", 5432)),
                connect_timeout=3
            )
            logging.info(f"Connected to PostgreSQL database at {h}:5432")
            return conn
        except Exception:
            continue
    raise RuntimeError("Could not connect to PostgreSQL on any known host.")

def main():
    logging.info("Starting CFR EVO historical routing metrics migration & backfill...")

    from gis_service.routing_engine import EVORoutingEngine
    router = EVORoutingEngine()

    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Step 1: Ensure column and index exist
        logging.info("Ensuring 'routing_metrics' column and GIN index exist in public.dispatches...")
        cur.execute("""
            ALTER TABLE public.dispatches 
            ADD COLUMN IF NOT EXISTS routing_metrics JSONB NOT NULL DEFAULT '[]'::jsonb;
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_dispatches_routing_metrics_gin 
            ON public.dispatches USING gin (routing_metrics jsonb_path_ops);
        """)
        conn.commit()
        logging.info("Schema migration verified successfully.")

        # Step 2: Query all records
        cur.execute("""
            SELECT id, dispatch_id, responding_units, verified_units, target 
            FROM public.dispatches 
            ORDER BY id ASC;
        """)
        rows = cur.fetchall()
        logging.info(f"Scanned {len(rows)} historical dispatch records.")

        updated_count = 0
        skipped_count = 0

        for row_id, disp_id, resp_units, ver_units, target_json in rows:
            target = target_json if isinstance(target_json, dict) else {}
            lat = target.get("lat")
            lng = target.get("lng")

            # Resolve unit list
            units = ver_units if (ver_units and len(ver_units) > 0) else resp_units
            if not units:
                units = target.get("units", [])
                if isinstance(units, str):
                    units = [u.strip() for u in units.split(",") if u.strip()]

            if not lat or not lng or not units:
                skipped_count += 1
                continue

            # Calculate routing metrics
            metrics = router.calculate_units_routing(units, float(lat), float(lng))
            if not metrics:
                skipped_count += 1
                continue

            metrics_json = json.dumps(metrics)

            cur.execute("""
                UPDATE public.dispatches 
                SET routing_metrics = %s::jsonb,
                    target = jsonb_set(
                        COALESCE(target, '{}'::jsonb),
                        '{routing_metrics}',
                        %s::jsonb,
                        true
                    )
                WHERE id = %s;
            """, (metrics_json, metrics_json, row_id))

            updated_count += 1
            if updated_count % 25 == 0:
                logging.info(f"Backfilled {updated_count}/{len(rows)} records...")

        conn.commit()
        logging.info(f"✅ Historical Backfill Complete! Updated: {updated_count}, Skipped (no coords/units): {skipped_count}")

    except Exception as e:
        conn.rollback()
        logging.error(f"❌ Error during routing metrics backfill: {e}", exc_info=True)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
