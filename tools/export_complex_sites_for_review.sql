-- Every site where a crew arriving at the computed point still has property to search.
--
-- WHY THIS EXISTS. Parcel front points are computed as the nearest point on the addressed
-- street. For an ordinary lot that is the driveway. For a large or multi-unit site it is a
-- point on the street edge of something much bigger, and the crew has to find the rest.
--
-- Detector: distance from the arrival point to the FURTHEST corner of the property. This was
-- chosen after two weaker detectors missed real sites (operator knowledge, 2026-08-29):
--
--   "spread between unit arrival points" -- missed every trailer park, because all 265 pads
--       at 201 Cayer St share one footprint and therefore agree perfectly on one point.
--       Agreement is not correctness.
--   "many distinct footprints per address" -- missed 4200 Dewdney Trunk Rd and 201 Cayer St
--       for the same reason, and missed Booth Ave entirely because those are separate house
--       numbers rather than one address.
--
-- Far-corner distance catches all three shapes, because it asks the operational question --
-- after the apparatus stops, how much property is left? -- rather than an internal
-- consistency one.
--
-- SITE = one distinct footprint. Addresses sharing a footprint are one site, listed together.
-- No threshold is applied here; the full distribution is exported and the department decides
-- where to draw the review line.
--
-- Read-only.

\pset pager off
\timing off

COPY (
    WITH site AS (
        SELECT ST_AsBinary(geom)            AS gkey,
               min(geom)                    AS geom,
               min(front_lat)               AS front_lat,
               min(front_lng)               AS front_lng,
               count(*)                     AS address_rows,
               count(*) FILTER (WHERE unit IS NOT NULL AND btrim(unit) <> '') AS unit_rows,
               count(DISTINCT house)        AS distinct_house_numbers,
               count(DISTINCT upper(street)) AS distinct_streets,
               min(street)                  AS street,
               min(address)                 AS example_address,
               max(address)                 AS example_address_last
        FROM public.parcels
        WHERE geom IS NOT NULL
          AND front_lat IS NOT NULL
          AND ST_GeometryType(geom) IN ('ST_Polygon', 'ST_MultiPolygon')
        GROUP BY ST_AsBinary(geom)
    )
    SELECT
        round(ST_Length(ST_LongestLine(
            ST_SetSRID(ST_MakePoint(front_lng, front_lat), 4326), geom)::geography)::numeric, 1)
                                                   AS arrival_to_far_corner_m,
        round(ST_Area(geom::geography)::numeric)   AS area_m2,
        address_rows,
        unit_rows,
        distinct_house_numbers,
        street,
        example_address,
        example_address_last,
        round(front_lat::numeric, 6)               AS arrival_lat,
        round(front_lng::numeric, 6)               AS arrival_lng,
        round(ST_Y(ST_PointOnSurface(geom))::numeric, 6) AS site_centre_lat,
        round(ST_X(ST_PointOnSurface(geom))::numeric, 6) AS site_centre_lng
    FROM site
    WHERE ST_Length(ST_LongestLine(
              ST_SetSRID(ST_MakePoint(front_lng, front_lat), 4326), geom)::geography) > 100
    ORDER BY 1 DESC
) TO STDOUT WITH CSV HEADER;
