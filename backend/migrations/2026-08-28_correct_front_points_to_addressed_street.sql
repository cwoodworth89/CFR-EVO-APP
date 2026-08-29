-- Correct parcel front points that sit on a street the address does not name.
--
-- CONTEXT. On 2026-08-28 the boundary-edge snapping work bulk-rewrote
-- public.parcels.front_lat / front_lng. That change is a large net improvement and is being
-- KEPT, not reverted: measured over a fixed 5,000-parcel sample, front points landing on the
-- parcel's own addressed street went from 3,191 (63.8%) to 4,897 (97.9%), and points snapped
-- to a road further away than the addressed street fell from 524 to 75.
--
-- Reverting would reintroduce 524 defects in order to remove 90. That would make emergency
-- routing worse, so this migration corrects the residual instead.
--
-- BOTH prior states are preserved before this runs:
--   pre-snapping   -> cfr-full-20260827-120023.sql.gz and cfr-full-20260828-031501.sql.gz
--                     (verified: 2865 Glen Dr at 49.285031145392914, -122.80336198032026)
--   post-snapping  -> public.parcels_frontpoint_snapshot_20260828 (65,401 rows)
--
-- WHAT THIS CORRECTS. 1,813 parcels citywide have a front point whose nearest road carries a
-- different name than the street the address names. For 1,759 of them a road with the
-- addressed street name exists, so the correct frontage is computable. The remaining 54 are
-- the known missing-street cases (see docs/city_gis_data_register.md) and are left alone --
-- there is no road to snap them to, and inventing one is precisely what §6.1 forbids.
--
-- THE RULE. The closest point, on the road whose name matches the parcel's addressed street,
-- to the parcel POLYGON. Two properties make this a constraint rather than a heuristic:
--
--   * The street is not chosen -- the address names it. public.parcels.street is municipal
--     data, matched against public.roads.roadname, also municipal data.
--   * Measuring to the polygon rather than the centroid is what fixes large properties.
--     2865 Glen Dr is 8 legal lots; its centroid is 135.6 m from Glen Drive, which is why
--     every centroid-based method picked a neighbouring road.
--
-- No distance threshold, no scoring weights, no tuned constants. Nothing here is invented.
--
-- Apostrophes are stripped on both sides because the cadastre spells "Deer's Leap" with one
-- and the road layer spells it without -- our own normalization gap, not a City data gap.
--
-- Idempotent: re-running matches nothing, because corrected rows now sit on their own street.

BEGIN;

WITH candidate AS (
    SELECT p.id,
           p.geom,
           upper(replace(p.street, '''', '')) AS addressed_street,
           (SELECT upper(replace(r.roadname, '''', ''))
              FROM public.roads r
             ORDER BY r.geom <-> ST_SetSRID(ST_MakePoint(p.front_lng, p.front_lat), 4326)
             LIMIT 1) AS road_at_front_point
    FROM public.parcels p
    WHERE p.front_lat IS NOT NULL
      AND p.street IS NOT NULL
      AND btrim(p.street) <> ''
), wrong_street AS (
    SELECT c.id, c.geom, c.addressed_street
    FROM candidate c
    WHERE c.road_at_front_point IS DISTINCT FROM c.addressed_street
), corrected AS (
    SELECT w.id,
           (SELECT ST_ClosestPoint(r.geom, w.geom)
              FROM public.roads r
             WHERE upper(replace(r.roadname, '''', '')) = w.addressed_street
             ORDER BY r.geom <-> w.geom
             LIMIT 1) AS pt
    FROM wrong_street w
)
UPDATE public.parcels p
   SET front_lat  = ST_Y(c.pt),
       front_lng  = ST_X(c.pt),
       updated_at = now()
  FROM corrected c
 WHERE p.id = c.id
   AND c.pt IS NOT NULL;

COMMIT;
