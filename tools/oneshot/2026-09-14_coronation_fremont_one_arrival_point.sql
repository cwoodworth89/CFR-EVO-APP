-- Give the numbered Coronation Cres and Fremont St addresses the one arrival point the operator set on each
--
-- Operator ruling, 2026-09-14: the same treatment as Pinecone Burke Mtn
-- (2026-09-14_pinecone_burke_mtn_one_arrival_point.sql), "for now". Each street has one way in, so
-- its numbered addresses share one arrival point, set once by the operator and copied here.
--
--   Coronation Cres  set on 1138, copied to the other 6. Reached through Port Moody; the crescent
--                    itself has not opened. Operator note: "2026-09-14 Coronation Cres under heavy
--                    construction. General location set until finished."
--   Fremont St       set on 1165, copied to the other 4. City-addressed on Fremont, reached from Devon
--                    through Port Coquitlam. Operator note: "General response area. No roads into back
--                    properties."
--
-- Checked against the kiosk's OSRM before copying, 2026-09-14: the Coronation pin snaps 1 m and every
-- hall's route ends 1 m from it, via Guildford Way, Balmoral Drive and Guildford Drive; the Fremont pin
-- snaps 2 m onto Devon Road (as the routing data names it) and every hall's route ends 2 m from it, via
-- Prairie Avenue. Neither street's addresses had a front point: no City road carries either name
-- (docs/briefings/needs_attention_design.md).
--
-- Arrival point only. Neither source address had a Street View view saved, so there is no view to copy;
-- the Pinecone copy carried one because the operator had saved one there.
--
-- Differs from Pinecone Burke Mtn in one respect: there all 28 addresses shared one City lot; here every
-- address is its own lot, so one point serves 7 lots and 5 lots. The operator's ruling, recorded.
--
-- Scope: numbered rows only. Fremont St has 9 City rows, 4 with no civic number; they are left alone,
-- as the unnumbered lease lots on Burke Mountain were. A row with its own arrival point is never
-- overwritten. Copies the five columns the placer sets, verbatim, keeping the operator's initials and time.
--
-- Guards, per street: exactly one numbered row with an arrival point, and the copy lands on exactly 6
-- (Coronation) or 4 (Fremont) rows. Each block stands alone; re-running one already applied stops with an
-- error and changes nothing.
--
-- City rows: backend/scripts/import_parcels.py deletes and re-inserts them, so a parcel re-import loses
-- these (docs/standards/operator_data.md section 3). Re-set one point per street and re-run until the
-- cfr schema exists.

-- block: Coronation Cres
DO $$
DECLARE placed int; copied int; src public.parcels%ROWTYPE;
BEGIN
    SELECT count(*) INTO placed FROM public.parcels
     WHERE NOT is_base_site AND street = 'Coronation' AND streettype = 'Cres'
       AND NULLIF(btrim(house), '') IS NOT NULL AND entrance_lat IS NOT NULL;
    IF placed <> 1 THEN
        RAISE EXCEPTION 'Coronation Cres: expected exactly one placed arrival point, found %', placed;
    END IF;
    SELECT * INTO src FROM public.parcels
     WHERE NOT is_base_site AND street = 'Coronation' AND streettype = 'Cres'
       AND NULLIF(btrim(house), '') IS NOT NULL AND entrance_lat IS NOT NULL;
    UPDATE public.parcels
       SET entrance_lat = src.entrance_lat, entrance_lng = src.entrance_lng, entrance_note = src.entrance_note,
           entrance_set_by = src.entrance_set_by, entrance_set_at = src.entrance_set_at
     WHERE NOT is_base_site AND street = 'Coronation' AND streettype = 'Cres'
       AND NULLIF(btrim(house), '') IS NOT NULL AND id <> src.id AND entrance_lat IS NULL;
    GET DIAGNOSTICS copied = ROW_COUNT;
    IF copied <> 6 THEN
        RAISE EXCEPTION 'Coronation Cres: copy would land on % rows, expected 6; rolled back', copied;
    END IF;
    RAISE NOTICE 'Coronation Cres: copied the arrival point from % to 6 rows', src.address;
END $$;

-- block: Fremont St
DO $$
DECLARE placed int; copied int; src public.parcels%ROWTYPE;
BEGIN
    SELECT count(*) INTO placed FROM public.parcels
     WHERE NOT is_base_site AND street = 'Fremont' AND streettype = 'St'
       AND NULLIF(btrim(house), '') IS NOT NULL AND entrance_lat IS NOT NULL;
    IF placed <> 1 THEN
        RAISE EXCEPTION 'Fremont St: expected exactly one placed arrival point, found %', placed;
    END IF;
    SELECT * INTO src FROM public.parcels
     WHERE NOT is_base_site AND street = 'Fremont' AND streettype = 'St'
       AND NULLIF(btrim(house), '') IS NOT NULL AND entrance_lat IS NOT NULL;
    UPDATE public.parcels
       SET entrance_lat = src.entrance_lat, entrance_lng = src.entrance_lng, entrance_note = src.entrance_note,
           entrance_set_by = src.entrance_set_by, entrance_set_at = src.entrance_set_at
     WHERE NOT is_base_site AND street = 'Fremont' AND streettype = 'St'
       AND NULLIF(btrim(house), '') IS NOT NULL AND id <> src.id AND entrance_lat IS NULL;
    GET DIAGNOSTICS copied = ROW_COUNT;
    IF copied <> 4 THEN
        RAISE EXCEPTION 'Fremont St: copy would land on % rows, expected 4; rolled back', copied;
    END IF;
    RAISE NOTICE 'Fremont St: copied the arrival point from % to 4 rows', src.address;
END $$;
