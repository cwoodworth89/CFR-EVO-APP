-- One canonical "which emergency response zone is this point in" definition.
--
-- THE BUG THIS FIXES
-- The containment predicate was inconsistent across the codebase:
--
--   spatial_queries.get_map_grid_for_point   ST_Contains
--   closure_spatial (affected zones)         ST_Intersects
--   closure_spatial (primary zone)           ST_Contains
--   derive_intersections                     ST_Intersects
--   test_zone_spatial_query                  ST_Contains
--
-- ST_Contains tests the STRICT INTERIOR. Emergency response zone polygons are bounded
-- BY the road network, so a road intersection lies exactly ON a zone boundary and
-- ST_Contains rejects it. Measured against the 1,784 derived intersections on
-- 2026-08-22: ST_Contains resolves a zone for 1,605 of them, ST_Intersects for 1,760.
-- 155 real intersections (8.7%) were therefore returning NO map grid from the live
-- geocoder path -- not because the data was missing, but because of the predicate.
--
-- This also explains why the old parcel-derived intersection points appeared to have
-- better zone coverage: they sat inside blocks, away from the boundaries.
--
-- TIE-BREAK
-- A junction at the corner of several zones genuinely lies in all of them. Any adjacent
-- zone locates it correctly, so the lowest-numbered zone is returned to make the answer
-- deterministic and reproducible rather than dependent on scan order.
--
-- A point outside every zone returns NULL. It is NOT snapped to a nearest zone: an
-- unknown grid must read as unknown (CLAUDE.md 6.1).

-- EDGE TOLERANCE
-- The zone polygons do not perfectly tile: adjacent polygon edges leave hairline slivers.
-- MEASURED 2026-08-22: five real intersections sit inside the city boundary but outside
-- the union of all zone polygons, by 0.0, 0.8, 1.7, 2.3 and 2.3 metres. One of them is
-- GORDON AVE & WESTWOOD ST, an intersection that appears twice in the live dispatch
-- record. Those are polygon-edge artifacts, not points genuinely outside the zone system.
--
-- A 2 m sliver is closed by falling back to the nearest zone within 5 m. Zones are
-- hundreds of metres across, so 5 m cannot reach past an adjacent zone -- and a point in
-- a sliver lies on the boundary BETWEEN two zones anyway, so either is a correct answer,
-- exactly as for the corner tie-break above.
--
-- Beyond 5 m the answer is NULL. Metrotown does not silently acquire a Coquitlam grid.
CREATE OR REPLACE FUNCTION public.zone_for_point(pt geometry)
RETURNS varchar
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
    SELECT COALESCE(
        -- Exact: the point is in (or on the boundary of) a zone.
        (SELECT z.map_name
         FROM public.zones z
         WHERE ST_Intersects(z.geom, pt)
         ORDER BY
             CASE WHEN z.map_name ~ '^[0-9]+$' THEN z.map_name::int ELSE 2147483647 END,
             z.map_name
         LIMIT 1),
        -- Sliver: within 5 m of a zone edge, take the nearest.
        (SELECT z.map_name
         FROM public.zones z
         WHERE ST_DWithin(z.geom::geography, pt::geography, 5.0)
         ORDER BY ST_Distance(z.geom::geography, pt::geography),
             CASE WHEN z.map_name ~ '^[0-9]+$' THEN z.map_name::int ELSE 2147483647 END,
             z.map_name
         LIMIT 1)
    );
$$;

COMMENT ON FUNCTION public.zone_for_point(geometry) IS
'Canonical emergency response zone (map grid) for a point. Uses ST_Intersects so a point
on a zone boundary -- i.e. on a road, where intersections live -- resolves. Returns the
lowest-numbered zone for corner points, NULL outside every zone. Every caller must use
this rather than writing its own containment query.';

-- public.intersections.zone_id is dropped: it was a denormalized copy of exactly this
-- function's result, free to drift from the geometry it was derived from. The geocoder
-- now calls zone_for_point(geom) when it loads the table.
ALTER TABLE public.intersections DROP COLUMN IF EXISTS zone_id;
