-- Drop public.parcels.centroid_lat / centroid_lng.
--
-- WHY
-- ---
-- They were a byte-identical duplicate of lat/lng: measured 2026-08-31, 65,400 of the
-- 65,400 polygon rows had centroid_lat = lat AND centroid_lng = lng. The import wrote
-- them from the same variable, address_resolver SELECTed them and never read them, and
-- nothing else touched them.
--
-- Two columns holding the same number under different names is not free. It invites a
-- reader to believe there is a distinction, and this table already had one costly
-- confusion of exactly that kind: `lat` is silently the polygon centroid, which is how
-- `"entrance_lat": lat` came to seed the operator-verified field with a centroid
-- (punch-list #50).
--
-- WHAT REMAINS -- three positions, one meaning each. address_resolver takes the first
-- that is set:
--
--     entrance_*  operator-verified access point, written only by a human
--     front_*     computed arrival point on the road the address NAMES
--     lat/lng     parcel polygon centroid; zone point-in-polygon input, map centring,
--                 simple per-parcel script work, and the last-resort arrival position
--
-- Safe to re-run. No data is lost: every value in these columns also exists in lat/lng.

BEGIN;

ALTER TABLE public.parcels DROP COLUMN IF EXISTS centroid_lat;
ALTER TABLE public.parcels DROP COLUMN IF EXISTS centroid_lng;

COMMIT;

-- Verification (expect 0):
--   SELECT count(*) FROM information_schema.columns
--   WHERE table_name = 'parcels' AND column_name IN ('centroid_lat','centroid_lng');
