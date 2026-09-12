-- The Street View camera position becomes its own column — punch list #78
--
-- Operator ruling, 2026-09-11: "I don't want the destination/arrival/calculation to change
-- just because I change the street view. The default calculated point, arrival point, and
-- streetview point should be separate and no change each other."
--
-- Until now there was nowhere to put the camera position, so `save_parcel_streetview` wrote
-- it into `front_lat`/`front_lng` — the computed frontage, which is the destination a truck
-- is routed to when no arrival point is set. Framing a picture moved where the truck stops,
-- by 66 m at 2865 Glen Dr and 65 m at 3030 Lincoln Ave (measured against the values the #77
-- frontage review queue recorded on 2026-09-10).
--
-- After this the three points are independent:
--   front_lat/front_lng          computed, from backfill_parcel_frontage (the polygon and its street)
--   entrance_lat/entrance_lng    the operator's ruling on where the truck stops
--   streetview_lat/streetview_lng  where the camera stands to take the picture
--
-- Idempotent: safe to re-run.

ALTER TABLE public.parcels
  ADD COLUMN IF NOT EXISTS streetview_lat double precision,
  ADD COLUMN IF NOT EXISTS streetview_lng double precision;

COMMENT ON COLUMN public.parcels.streetview_lat IS
  'Street View camera position, not a routing destination (punch list #78, 2026-09-11).';
COMMENT ON COLUMN public.parcels.streetview_lng IS
  'Street View camera position, not a routing destination (punch list #78, 2026-09-11).';

-- Backfill. For a row that already carries a saved view, today's front_lat IS the camera
-- position — that is the defect — so moving it across loses nothing and keeps every saved
-- view pointing where the operator left it. Rows without a saved view are untouched.
UPDATE public.parcels
   SET streetview_lat = front_lat,
       streetview_lng = front_lng
 WHERE streetview_heading IS NOT NULL
   AND streetview_lat IS NULL
   AND front_lat IS NOT NULL;

-- What this migration does NOT do: repair the frontages the old behaviour overwrote.
-- `front_lat` is recomputed for every row by backfill_parcel_frontage, which is the repair;
-- it is a separate, operator-timed run because it moves routing destinations.
