-- Drop public.parcels.access_far_corner_m. Compute it at report time instead.
--
-- WHY
-- ---
-- Operator decision 2026-08-31: do not store values that have no perpetual use. This one is
-- wanted occasionally, to find properties worth an access review -- that is a report, not an
-- attribute of a parcel.
--
-- It is derived from the arrival point, so it is only true until the arrival point moves, and
-- keeping it correct means remembering to recompute it every time. That is not hypothetical:
-- the migration that added it (2026-08-29_flag_sites_needing_access_review.sql) says
-- "Recompute this after any run of backfill_parcel_frontage", and nothing ever did. When
-- punch-list #58 cleared 56 stale front points on 2026-08-31, those same 56 rows kept a
-- far-corner distance measured from the point that had just been removed -- a stored number
-- describing a position that no longer existed.
--
-- Nothing read the column. Its only consumers were the migration that wrote it and, briefly, a
-- recompute added the same day it was removed.
--
-- WHAT REPLACES IT
-- ----------------
-- The measurement itself is still wanted and its reasoning still holds -- see the original
-- migration for why two simpler detectors failed, notably that all 265 pads at 201 Cayer St
-- share one 122,923 m2 footprint and so agree perfectly, making a 12-hectare site look
-- healthy. Agreement is not correctness.
--
-- Run it when a report is wanted (add `AND p.is_base_site` once #48 is applied, so a property
-- is measured once rather than once per legal lot):
--
--   SELECT p.address,
--          round(ST_Length(ST_LongestLine(
--              ST_SetSRID(ST_MakePoint(
--                  COALESCE(p.entrance_lng, p.front_lng),
--                  COALESCE(p.entrance_lat, p.front_lat)), 4326),
--              p.geom)::geography)::numeric, 1) AS far_corner_m,
--          round(ST_Area(p.geom::geography)::numeric, 0)                    AS lot_m2
--     FROM public.parcels p
--    WHERE p.geom IS NOT NULL
--      AND COALESCE(p.entrance_lat, p.front_lat) IS NOT NULL
--    ORDER BY far_corner_m DESC NULLS LAST
--    LIMIT 100;
--
-- NOT DESTRUCTIVE OF ANYTHING OPERATOR-ENTERED. The column held a computed measurement only;
-- no human ever set it, and it can be reproduced exactly by the query above.

BEGIN;

DROP INDEX IF EXISTS public.idx_parcels_access_far_corner;

ALTER TABLE public.parcels
    DROP COLUMN IF EXISTS access_far_corner_m;

COMMIT;

-- VERIFY (expect 0 rows)
--   SELECT column_name FROM information_schema.columns
--    WHERE table_schema='public' AND table_name='parcels'
--      AND column_name='access_far_corner_m';
