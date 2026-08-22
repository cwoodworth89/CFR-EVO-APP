-- Manual intersection: LOUGHEED HWY & MARINER WAY
--
-- Lougheed Hwy and Mariner Way do not intersect. It is a grade-separated interchange:
-- the two centrelines never meet, and their closest approach is 221.6 m. The derived
-- table therefore holds HIGHWAY RAMP & LOUGHEED HWY (3 candidates) and
-- MARINER WAY & UNITED BLVD there instead, which is geometrically correct.
--
-- Crews nevertheless refer to the place as "Lougheed and Mariner", so it needs to be
-- dispatchable under that name. source='manual' exists exactly for this: a row a person
-- decided on, which backend/scripts/derive_intersections.py will never delete or
-- overwrite when it rebuilds the derived rows.
--
-- COORDINATE PROVENANCE AND ITS LIMIT
-- The point below is the midpoint of the shortest line between the two centrelines in
-- public.roads -- the geometric centre of the gap between them, in map grid 49. That is
-- a defensible derivation, but it is NOT an operational decision: nobody has confirmed
-- that the centre of the gap is where apparatus should be sent, rather than a specific
-- ramp head or the Mariner Way overpass. The notes column records that, and the row
-- should be corrected by whoever owns response geography.

INSERT INTO public.intersections
    (street_a, street_b, intersection_key, lat, lng, geom, candidate_index,
     source, notes, updated_at)
VALUES (
    'LOUGHEED HWY', 'MARINER WAY', 'LOUGHEED HWY & MARINER WAY',
    49.240487, -122.816114,
    ST_SetSRID(ST_MakePoint(-122.816114, 49.240487), 4326),
    0,
    'manual',
    'Grade-separated interchange, not a junction: the Lougheed Hwy and Mariner Way '
    || 'centrelines never meet (closest approach 221.6 m). Added manually because crews '
    || 'use this name. Coordinate is the midpoint of the shortest line between the two '
    || 'centrelines (map grid 49), derived 2026-08-22 -- NOT operationally confirmed. '
    || 'Needs review by response geography: the correct dispatch point may be a specific '
    || 'ramp head or the overpass rather than the centre of the gap.',
    now()
)
ON CONFLICT (intersection_key, candidate_index) DO UPDATE SET
    source = 'manual',
    notes = EXCLUDED.notes,
    updated_at = now();
