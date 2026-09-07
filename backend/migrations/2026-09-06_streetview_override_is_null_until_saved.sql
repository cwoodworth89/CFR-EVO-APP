-- WHY
-- Every parcel row carried streetview_heading 0.0 / pitch 5.0 / fov 80.0 from the column
-- DEFAULTs of the original schema extension, so the API's "an override exists when heading
-- is not null" test was true for all 71,210 parcels and the kiosk showed SAVED PREFERRED VIEW
-- (0°) on every address nobody had ever saved (operator, 2026-09-06, DISP-2026-5317C5).
-- Measured before this ran: 71,210 rows at the exact defaults with updated_at <= created_at
-- (never touched), 0 default rows ever updated, 3 non-default rows -- the operator's two
-- real saves that day and one test address.
--
-- Also: the panel saved the SDK's ZOOM (0-4) into streetview_fov, so the two real saves hold
-- fov 1 where they mean 90 degrees. Google's relation is fov = 180 / 2^zoom. Converted here.
--
-- And a column for the panorama ID, which the Maps Platform Service Specific Terms A.3 allow
-- storing indefinitely and which pins the exact camera position, not just the heading
-- (docs/standards/google-maps-platform-terms-excerpts.md, punch-list #35a).
--
-- Apply on the kiosk:
--   docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch < backend/migrations/2026-09-06_streetview_override_is_null_until_saved.sql

BEGIN;

-- 1. Untouched defaults become NULL: no override.
UPDATE public.parcels
   SET streetview_heading = NULL, streetview_pitch = NULL, streetview_fov = NULL
 WHERE streetview_heading = 0 AND streetview_pitch = 5 AND streetview_fov = 80
   AND (updated_at IS NULL OR updated_at <= created_at + interval '1 minute');

-- 2. Saves that stored a zoom level (0-4) in the fov column: convert to degrees.
UPDATE public.parcels
   SET streetview_fov = round((180.0 / power(2, streetview_fov))::numeric, 1)
 WHERE streetview_fov IS NOT NULL AND streetview_fov <= 4;

-- 3. No more defaults: a row without a save has nothing in these columns.
ALTER TABLE public.parcels
  ALTER COLUMN streetview_heading DROP DEFAULT,
  ALTER COLUMN streetview_pitch DROP DEFAULT,
  ALTER COLUMN streetview_fov DROP DEFAULT;

-- 4. The panorama the operator was looking at when they saved.
ALTER TABLE public.parcels ADD COLUMN IF NOT EXISTS streetview_pano_id TEXT;

COMMIT;

-- Check afterwards: expect a handful of rows, none with fov <= 4.
-- SELECT address, streetview_heading, streetview_pitch, streetview_fov, streetview_pano_id, updated_at
--   FROM public.parcels WHERE streetview_heading IS NOT NULL ORDER BY updated_at DESC;
