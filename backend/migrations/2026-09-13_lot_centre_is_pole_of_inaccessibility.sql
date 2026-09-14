-- A lot's centre point becomes its pole of inaccessibility, and its map grid the zone at that point
--
-- Operator ruling, 2026-09-13 (docs/standards/operator_data.md, ruling 12 and the grid item in §5):
-- approved after the diff below was shown.
--
-- Before: centroid_lat/lng was the GeoPandas centroid, which fell OUTSIDE 233 City lots, and a
-- City lot's zone_id was the June Emergency_Response_Zones.shp polygon containing that centroid.
-- Base sites used ST_PointOnSurface. So some lots carried the grid of a point outside them, and
-- the grid came from a different copy of the zones than everything else reads.
--
-- After: every row with an outline gets the interior point furthest from any edge, computed in
-- metres because ST_MaximumInscribedCircle measures in the geometry's units
-- (docs/standards/dependency-behaviour.md). zone_id is public.zone_for_point() at that point,
-- reading public.zones. One copy of the zones, one point for both values.
--
-- Diff measured on the kiosk before applying:
--   centre points  inside the outline on all 71,212 rows (was outside on 233 City lots)
--                  City lots move median 7.2 m, p90 30.6 m, max 611.6 m
--                  base sites move median 9.0 m, p90 42.4 m, max 758.4 m
--   map grids      11 of 69,541 City lots change, 5 addressed (1046 United Blvd 14->31,
--                  1085 Falcon Dr 64->69, 3305 David Ave 102->96, 4124 Cedar Dr 116->118,
--                  4300 Oliver Rd 117->118); 2 unaddressed lots fall in no zone
--                  3 of 1,671 base sites change (1331 Gabriola Dr 100->102,
--                  2885 Lansdowne Dr 79->78, 2995 Robson Dr 88->90)
--                  no dispatch in the corpus went to any of the 14
--
-- Not touched: front_lat/lng (measured from the outline to the named street, not from this
-- point), entrance_* and streetview_* (the operator's).
--
-- Rollback: /home/tcfire/cfr-backups/operator-data-20260913/parcels_centre_and_grid_before_2026-09-13.csv
-- on the kiosk holds id, centroid_lat, centroid_lng and zone_id for all 71,213 rows as they were.
--
-- The import computes the same values (import_parcels.py set_lot_centres_and_grids and
-- build_base_site_rows), so the next import cannot revert this. Idempotent: safe to re-run.

BEGIN;

UPDATE public.parcels p SET
    centroid_lat = ST_Y(c.pt),
    centroid_lng = ST_X(c.pt),
    zone_id      = public.zone_for_point(c.pt),
    updated_at   = now()
FROM (
    SELECT id, ST_Transform((ST_MaximumInscribedCircle(ST_Transform(geom, 26910))).center, 4326) AS pt
    FROM public.parcels
    WHERE geom IS NOT NULL
) c
WHERE p.id = c.id;

COMMENT ON COLUMN public.parcels.centroid_lat IS
  'Latitude of the lot''s centre point: its pole of inaccessibility, the interior point furthest from any edge. Not a centroid despite the name (operator ruling 2026-09-13, docs/standards/operator_data.md).';
COMMENT ON COLUMN public.parcels.centroid_lng IS
  'Longitude of the lot''s centre point: its pole of inaccessibility, the interior point furthest from any edge. Not a centroid despite the name (operator ruling 2026-09-13, docs/standards/operator_data.md).';
COMMENT ON COLUMN public.parcels.zone_id IS
  'Map grid: public.zone_for_point() at the centre point (centroid_lat/lng), from public.zones (operator ruling 2026-09-13).';

COMMIT;
