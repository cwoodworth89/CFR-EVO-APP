-- Drop public.custom_places
--
-- The table was seeded from backend/data/vocabulary/custom_places.json, a
-- script-generated file whose coordinates were never validated. Measured against
-- public.parcels, three secondary schools were 309 m, 537 m and 1,774 m from their
-- municipal parcel coordinates.
--
-- It backed step 7 of the geocoder cascade (fuzzy match on place name). That step had
-- no reachable use case: Locution always speaks the civic address before the place
-- name -- "1240 lansdowne drive Scott Creek Middle School" -- so step 1 resolves the
-- address against public.parcels and the parser already captures the name as the
-- sub-address. A dispatch naming only a place does not occur.
--
-- Named-location support going forward belongs on the address record itself:
-- public.parcels already carries entrance_lat/entrance_lng, front_lat/front_lng,
-- lock_box_notes, hazard_notes and pre_plan_pdf_url. Naming is sub-address semantics.

BEGIN;
DROP TABLE IF EXISTS public.custom_places;
COMMIT;
