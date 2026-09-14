-- Give all 28 Pinecone Burke Mtn addresses the one arrival point and Street View view the operator set
--
-- Operator ruling, 2026-09-14: the 28 numbered Pinecone Burke Mtn addresses share one access, so they
-- carry the same arrival point and the same Street View placement. He set both once, on
-- "12 Pinecone Burke Mtn"; this copies them to the other 27.
--
-- The point is the gate on Upper Harper Road. Note, verbatim from the operator: "GATE ACCESS - CABINS
-- LOCATED 30MIN PAST GATE + WALK". Measured against the kiosk's OSRM the same day:
--   * the gate pin snaps 0 m onto Upper Harper Road, so a route ends at the gate;
--   * the cabin parking area he first pinned is not on the routing graph (nearest routable road 2,320 m
--     away, an unnamed road to the south-east), so it was moved to the gate;
--   * before any pin, these addresses routed to the lot's centre, which snaps 2,142 m onto Quarry Road
--     on the east side of the mountain -- a different approach entirely.
--
-- Why a copy: the placer and the Street View save each write one parcel row
-- (backend/api/routers/parcels.py), and public.parcels is one row per civic address, so a pin on
-- "12 Pinecone Burke Mtn" leaves a call to "157 Pinecone Burke Mtn" with none. The resolver reads
-- entrance -> front -> centroid per row, and these rows have no front point: no City road carries the
-- street (docs/briefings/needs_attention_design.md, the No City road list).
--
-- What it copies, verbatim, the columns those two saves set:
--   arrival point  entrance_lat, entrance_lng, entrance_note, entrance_set_by, entrance_set_at
--   Street View    streetview_heading, streetview_pitch, streetview_fov, streetview_pano_id,
--                  streetview_lat, streetview_lng
-- The placement is the operator's, made once; the copy keeps his initials and his time.
--
-- Scope, measured 2026-09-14: City lot !8180021 carries 49 rows. Besides these 28 it holds 19 "Harper
-- Rd" and 2 "Burke Mountain St" lease lots with no civic number; they are left alone, so the filter is
-- the street, not the lot. Only rows with no arrival point and no Street View of their own are written.
--
-- Guards: it refuses unless exactly one Pinecone Burke Mtn row has an arrival point, unless that row
-- also has a saved Street View view, and unless the copy lands on exactly 27 rows. Re-running after it
-- has been applied stops with an error and changes nothing.
--
-- These are City rows, not base sites. backend/scripts/import_parcels.py deletes and re-inserts every
-- City row, so a parcel re-import loses all 28 (docs/standards/operator_data.md section 3). The planned
-- cfr schema is what fixes that; until then, re-set the point and view on one address and re-run this.

DO $$
DECLARE
    placed  int;
    copied  int;
    src     public.parcels%ROWTYPE;
BEGIN
    SELECT count(*) INTO placed
      FROM public.parcels
     WHERE gis_id = '!8180021' AND NOT is_base_site
       AND street = 'Pinecone Burke' AND streettype = 'Mtn'
       AND entrance_lat IS NOT NULL;

    IF placed <> 1 THEN
        RAISE EXCEPTION 'expected exactly one placed arrival point on Pinecone Burke Mtn, found %', placed;
    END IF;

    SELECT * INTO src
      FROM public.parcels
     WHERE gis_id = '!8180021' AND NOT is_base_site
       AND street = 'Pinecone Burke' AND streettype = 'Mtn'
       AND entrance_lat IS NOT NULL;

    IF src.streetview_pano_id IS NULL AND src.streetview_heading IS NULL THEN
        RAISE EXCEPTION '% has an arrival point but no saved Street View view to copy', src.address;
    END IF;

    UPDATE public.parcels
       SET entrance_lat       = src.entrance_lat,
           entrance_lng       = src.entrance_lng,
           entrance_note      = src.entrance_note,
           entrance_set_by    = src.entrance_set_by,
           entrance_set_at    = src.entrance_set_at,
           streetview_heading = src.streetview_heading,
           streetview_pitch   = src.streetview_pitch,
           streetview_fov     = src.streetview_fov,
           streetview_pano_id = src.streetview_pano_id,
           streetview_lat     = src.streetview_lat,
           streetview_lng     = src.streetview_lng
     WHERE gis_id = '!8180021' AND NOT is_base_site
       AND street = 'Pinecone Burke' AND streettype = 'Mtn'
       AND id <> src.id
       AND entrance_lat IS NULL
       AND streetview_heading IS NULL AND streetview_pano_id IS NULL AND streetview_lat IS NULL;

    GET DIAGNOSTICS copied = ROW_COUNT;
    IF copied <> 27 THEN
        RAISE EXCEPTION 'copy would land on % rows, expected 27; rolled back', copied;
    END IF;

    RAISE NOTICE 'copied the arrival point and Street View view from % to 27 rows', src.address;
END $$;
