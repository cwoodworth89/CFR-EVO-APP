-- Carry DriveBC's roads[].state, roads[].direction and severity on each road closure, so
-- the access level is read from passability and not from traffic impact.
--
-- WHY
-- ---
-- Punch list #91 ruling 5, operator 2026-09-16. The access level for a DriveBC event came
-- from `severity` (MAJOR -> NO_ACCESS, anything else -> CAUTION). Open511 v1.0 defines
-- severity as traffic impact, not passability, and the live feed measured the same day had
-- 18 MAJOR events with every lane open and 5 MINOR events CLOSED. The passability field is
-- roads[].state (with roads[].direction), now HELD in docs/standards/README.md.
--
--   road_state      CLOSED / SOME_LANES_CLOSED / SINGLE_LANE_ALTERNATING / ALL_LANES_OPEN
--   road_direction  N NW W SW S SE E NE NONE BOTH -- lets a one-direction closure be stated
--   feed_severity   MINOR / MODERATE / MAJOR / UNKNOWN as sent -- information, never a tier
--
-- All three are NULL for Municipal 511, and NULL on DriveBC rows until the next sync
-- rewrites them. No CHECK on the values: an unrecognised feed value is logged and stored as
-- NULL by the code, and a CHECK would turn a vocabulary change into a failed sync.
--
-- ORDER: apply this BEFORE rebuilding the api container. The new model maps these columns,
-- so without them every query on road_closures fails: GET /api/road-closures returns 500
-- and the kiosk list goes empty. Base.metadata.create_all does not add columns to an existing
-- table. The old code runs unchanged against the migrated table.
--
-- Apply on the kiosk:
--   docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch \
--     < backend/migrations/2026-09-16c_road_closure_open511_road_state.sql

BEGIN;

ALTER TABLE public.road_closures
    ADD COLUMN IF NOT EXISTS road_state VARCHAR(32),
    ADD COLUMN IF NOT EXISTS road_direction VARCHAR(8),
    ADD COLUMN IF NOT EXISTS feed_severity VARCHAR(16);

COMMENT ON COLUMN public.road_closures.road_state IS
    'DriveBC roads[].state (Open511 v1.0). emergency_access is derived from it. NULL for Municipal 511 or when not sent.';
COMMENT ON COLUMN public.road_closures.road_direction IS
    'DriveBC roads[].direction (Open511 v1.0) of the road the access level was taken from.';
COMMENT ON COLUMN public.road_closures.feed_severity IS
    'DriveBC severity as sent (traffic impact). Information only; never used as an access tier.';

COMMIT;
