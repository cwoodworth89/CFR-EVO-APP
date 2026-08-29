-- Record, per parcel, how much property lies beyond its computed arrival point.
--
-- WHY A MEASUREMENT AND NOT A FLAG. "Needs review" depends on where the department chooses to
-- draw the line, and that is a workload decision, not a fact to be derived. Storing a boolean
-- would bake an invented threshold into the data (CLAUDE.md §6.3). Storing the measured
-- distance lets the queue be a query at whatever cutoff is wanted, and lets that cutoff move
-- without a migration.
--
-- WHAT IT MEASURES. Distance from the arrival point to the FURTHEST corner of the parcel: once
-- the apparatus stops, how much property is left to search.
--
-- Two earlier detectors were tried and both failed, which is why this one is stored:
--
--   "spread between the unit arrival points" -- missed every trailer park. All 265 pads at
--       201 Cayer St share one 122,923 m2 footprint and so agree perfectly on one point,
--       making a 12-hectare site look healthy. Agreement is not correctness.
--   "many distinct footprints per address" -- missed the parks for the same reason, and missed
--       the Booth Ave group entirely because those are separate house numbers, not one address.
--
-- DISTRIBUTION at the time of writing (27,380 distinct footprints):
--     > 500 m     82 sites
--     200-500 m  460 sites
--     100-200 m  879 sites
-- and 252 sites carry 20 or more unit addresses, covering 23,516 units. Reviewing the top 100
-- sites by address count covers 64% of affected addresses -- this is a queue in the hundreds.
--
-- Recompute this after any run of backfill_parcel_frontage, since the arrival point moves.
-- Safe to re-run.

BEGIN;

ALTER TABLE public.parcels
    ADD COLUMN IF NOT EXISTS access_far_corner_m DOUBLE PRECISION;

COMMENT ON COLUMN public.parcels.access_far_corner_m IS
    'Metres from the resolved arrival point (entrance_lat if set, else front_lat) to the '
    'furthest corner of the parcel: how much property a crew must still search after '
    'arriving. Measured, not thresholded -- the review cutoff is a departmental decision. '
    'Recompute after backfill_parcel_frontage.';

UPDATE public.parcels p
   SET access_far_corner_m = ST_Length(
           ST_LongestLine(
               ST_SetSRID(ST_MakePoint(
                   COALESCE(p.entrance_lng, p.front_lng),
                   COALESCE(p.entrance_lat, p.front_lat)), 4326),
               p.geom
           )::geography)
 WHERE p.geom IS NOT NULL
   AND COALESCE(p.entrance_lat, p.front_lat) IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_parcels_access_far_corner
    ON public.parcels (access_far_corner_m DESC NULLS LAST);

COMMIT;
