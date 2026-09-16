-- Let a road closure carry an unknown severity and a missing feed id as NULL, instead of the
-- invented values the ingestion used to fill them with.
--
-- WHY
-- ---
-- Punch list #91, operator rulings 2026-09-16.
--
-- 1. Unknown severity -> "keep the box but add N/A". A DriveBC event with no severity was
--    stored as MINOR/CAUTION, and a row with no closure_type was served as FULL_CLOSURE,
--    so the same unknown reached crews as the mildest or the most severe tier depending on
--    which field was empty. Both are now NULL, so emergency_access must allow NULL.
--
-- 2. Missing feed id -> "keep as null, but state it". A record without an id was given
--    db_<position in the list> (DriveBC) or muni_None_<n> (Municipal 511), which a later
--    sync can hand to a different closure and overwrite it. closure_id is now NULL for those
--    records, so it must allow NULL. Postgres UNIQUE permits any number of NULLs.
--
--    closure_id is what the upsert matches on, so an id-less record needs another way to be
--    found on the next sync without inventing an id or inserting a duplicate every hour:
--    feed_record_key, a sha256 over the raw fields the feed sent (see
--    road_closure_service._content_record_key). It is set only when closure_id is NULL, is
--    unique among those rows, and is never served as an id. The CHECK guarantees every row
--    is matchable one way or the other.
--
-- ORDER MATTERS. Apply this BEFORE rebuilding the api container. The new code maps
-- feed_record_key, so without the column every query on road_closures fails and
-- GET /api/road-closures returns 500 (the kiosk list goes empty; #89's banner would show,
-- since the sync status lives in its own table). Base.metadata.create_all does not alter an
-- existing table, so the rebuild will not do this for you. The old code runs unchanged
-- against the migrated table: it always writes both columns and never reads the new one.
--
-- Falsifier from #91, run on the kiosk 2026-09-16 before this was written: 0 rows with a
-- NULL closure_type, description, street_name or headline, 0 with a db_% id, 0 with a
-- muni_None% id. 177 rows. The defect was latent.
--
-- Apply on the kiosk:
--   docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch \
--     < backend/migrations/2026-09-16b_road_closure_unknown_severity_and_missing_id.sql

BEGIN;

ALTER TABLE public.road_closures
    ALTER COLUMN closure_id DROP NOT NULL,
    ALTER COLUMN emergency_access DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS feed_record_key TEXT;

ALTER TABLE public.road_closures
    DROP CONSTRAINT IF EXISTS ck_road_closures_id_or_record_key;
ALTER TABLE public.road_closures
    ADD CONSTRAINT ck_road_closures_id_or_record_key
    CHECK (closure_id IS NOT NULL OR feed_record_key IS NOT NULL);

CREATE UNIQUE INDEX IF NOT EXISTS ux_road_closures_feed_record_key
    ON public.road_closures (feed_record_key)
    WHERE closure_id IS NULL;

COMMENT ON COLUMN public.road_closures.closure_id IS
    'The feed''s own id; NULL when the feed record carried none. Never derived from position. Punch list #91.';
COMMENT ON COLUMN public.road_closures.feed_record_key IS
    'Only when closure_id IS NULL: sha256 over raw feed fields, so the next sync can match the record. Not an id; never served as one.';
COMMENT ON COLUMN public.road_closures.emergency_access IS
    'NO_ACCESS / ACCESS_ONLY / CAUTION, or NULL when the feed sent no usable severity (#91). The kiosk shows N/A.';

COMMIT;
