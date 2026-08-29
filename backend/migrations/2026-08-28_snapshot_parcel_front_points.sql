-- Snapshot public.parcels.front_lat / front_lng before any further change.
--
-- WHY. On 2026-08-28 the parcel front points were bulk-rewritten in production by the
-- boundary-edge snapping work, while the accompanying briefing described the change as
-- pending review. `updated_at` was not bumped, so the affected rows cannot be identified
-- from the table itself, and no snapshot of the post-change state exists either.
--
-- Two rollback points to the PRE-change state already exist as database dumps
-- (cfr-full-20260827-120023.sql.gz and cfr-full-20260828-031501.sql.gz, both verified to
-- contain 2865 Glen Dr at 49.285031145392914, -122.80336198032026). What is missing is a
-- record of the CURRENT state, so that whichever way the review goes, both are recoverable.
--
-- This table is that record. It is additive: it creates nothing the application reads and
-- changes no existing row.
--
-- Measured difference between the two states, over a fixed 5,000-parcel sample:
--     front point on the parcel's own addressed street   3,191 (63.8%)  ->  4,897 (97.9%)
--     snapped to a road further than the addressed street    524        ->     75
--
-- Idempotent: re-running replaces the snapshot rather than appending a second copy.

BEGIN;

DROP TABLE IF EXISTS public.parcels_frontpoint_snapshot_20260828;

CREATE TABLE public.parcels_frontpoint_snapshot_20260828 AS
SELECT
    id,
    address,
    street,
    streettype,
    lat,
    lng,
    front_lat,
    front_lng,
    updated_at,
    now() AS snapshot_taken_at
FROM public.parcels;

CREATE UNIQUE INDEX idx_parcels_frontpoint_snap_20260828_id
    ON public.parcels_frontpoint_snapshot_20260828 (id);

COMMENT ON TABLE public.parcels_frontpoint_snapshot_20260828 IS
    'Point-in-time copy of parcels.front_lat/front_lng as of 2026-08-28, taken AFTER the '
    'boundary-edge snapping bulk rewrite and BEFORE any restore. The pre-change state lives '
    'in cfr-full-20260828-031501.sql.gz. Keep both until the snapping proposal is resolved.';

COMMIT;
