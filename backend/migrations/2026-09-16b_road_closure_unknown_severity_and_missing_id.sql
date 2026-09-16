-- Let a road closure carry an unknown severity and a missing road name as NULL, instead of
-- the invented values the ingestion used to fill them with.
--
-- WHY
-- ---
-- Punch list #91, operator rulings 2026-09-16.
--
-- 1. Unknown severity -> N/A. A DriveBC event with no severity was stored as MINOR/CAUTION,
--    a Municipal 511 record with no stated closure type started at CAUTION ("for all I know
--    it's purely informational alerts"), and a row with no closure_type was served as
--    FULL_CLOSURE. All are now NULL, so emergency_access must allow NULL. closure_type
--    already does.
--
-- 2. Text the feed did not send -> NULL, shown as "--" ("If we don't get a title don't make
--    one up"). street_name was filled with "Regional Corridor" / "Local Road"; it is now
--    NULL when the feed sends none, so street_name must allow NULL. headline and description
--    already do.
--
-- Not in this file, by ruling: a record with no feed id is skipped at ingestion, not stored,
-- so closure_id stays NOT NULL. (The first draft of this file, never run, dropped that NOT
-- NULL and added a content-key column; the operator reversed that ruling before deploy.)
--
-- ORDER: apply this BEFORE rebuilding the api container.
--   * Rebuild first, migration late: the old table is fine for reads, so the kiosk list keeps
--     drawing, but the first sync that meets an unstated severity or a missing road name
--     fails its INSERT on the NOT NULL. The whole sync rolls back, #89 records FAILED and
--     the banner shows, and every hourly tick fails the same way until this runs.
--   * Migration first, old code still running: harmless. The old code always writes both
--     columns.
-- Base.metadata.create_all does not alter an existing table, so the rebuild will not do this.
--
-- Falsifier from #91, run on the kiosk 2026-09-16: 0 of 177 rows had a NULL closure_type,
-- description, street_name or headline, or a db_% / muni_None% id. After this migration and
-- before the next sync, `SELECT count(*) FROM public.road_closures WHERE emergency_access IS
-- NULL OR street_name IS NULL;` is 0 -- the migration changes no data.
--
-- Apply on the kiosk:
--   docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch \
--     < backend/migrations/2026-09-16b_road_closure_unknown_severity_and_missing_id.sql

BEGIN;

ALTER TABLE public.road_closures
    ALTER COLUMN emergency_access DROP NOT NULL,
    ALTER COLUMN street_name DROP NOT NULL;

COMMENT ON COLUMN public.road_closures.emergency_access IS
    'NO_ACCESS / ACCESS_ONLY / CAUTION, or NULL when the feed stated no severity (#91). The kiosk shows N/A.';
COMMENT ON COLUMN public.road_closures.street_name IS
    'Road name as the feed sent it, or NULL when it sent none (#91). The kiosk shows --.';

COMMIT;
