-- Rename public.parcels.lat/lng -> centroid_lat/centroid_lng.
--
-- WHY
-- ---
-- The column has always held the PARCEL POLYGON CENTROID, computed by us with
-- `.centroid` on geom -- it is not a value the City supplies. Nothing in the name said
-- so, and that silence cost a real defect: the import contained
--
--     "entrance_lat": lat
--
-- which seeded the OPERATOR-VERIFIED access point with a centroid on every new row
-- (punch-list #50). Written as `"entrance_lat": centroid_lat` it would have looked
-- wrong on sight. This is the §7.3a failure -- the name not matching the contract --
-- applied to a column instead of a function.
--
-- The name was only free because centroid_lat/centroid_lng were dropped earlier the
-- same day: they were a byte-identical duplicate of lat/lng on all 65,400 polygon rows
-- (backend/migrations/2026-08-31_drop_duplicate_centroid_columns.sql).
--
-- THE THREE POSITIONS, after this. address_resolver takes the first that is set:
--
--     entrance_*  operator-verified access point, written only by a human
--     front_*     computed arrival point on the road the address NAMES
--     centroid_*  polygon centroid: zone point-in-polygon input, map centring, simple
--                 per-parcel script work, and the last-resort arrival position
--
-- WHAT DOES NOT CHANGE
-- --------------------
-- The API still publishes these as "lat" / "lng" in its parcel responses
-- (backend/api/routers/parcels.py). That is a reasonable thing for an API to call a
-- point, and holding it stable keeps the frontend and any map work off this rename.
-- Only the column is renamed.
--
-- public.intersections.lat/lng and public.hydrants.lat/lng are NOT touched -- on those
-- tables the row IS a point, so lat/lng is already the accurate name.
--
-- Safe to re-run.

BEGIN;

ALTER TABLE public.parcels RENAME COLUMN lat TO centroid_lat;
ALTER TABLE public.parcels RENAME COLUMN lng TO centroid_lng;

COMMIT;

-- Verification (expect old=0, new=2, and 65,401 populated):
--   SELECT count(*) FILTER (WHERE column_name IN ('lat','lng'))                   AS old_names,
--          count(*) FILTER (WHERE column_name IN ('centroid_lat','centroid_lng')) AS new_names
--   FROM information_schema.columns WHERE table_name = 'parcels';
