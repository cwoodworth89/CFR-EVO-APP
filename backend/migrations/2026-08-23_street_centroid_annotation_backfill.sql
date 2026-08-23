-- Move the "(Street Centroid)" annotation out of the address and into resolution_note.
--
-- Eight historical dispatches carry display text inside target.address:
--     "2915 Lougheed Hwy (Street Centroid)"
-- That is a UI annotation stored as data. It matches no real address, so anything
-- keying on target.address has to special-case it, and it propagates: an operator
-- using "Prefill Defaults" copied it into verified_address on DISP-2026-80CE24,
-- contaminating ground truth (corrected separately).
--
-- Current code keeps the address clean and puts the explanation in resolution_note,
-- which the kiosk's amber "APPROXIMATE LOCATION" banner reads. These records predate
-- that field, so stripping the annotation alone would leave them displaying as
-- ordinary exact addresses with no warning at all -- worse than the clumsy annotation.
-- The strip and the backfill therefore happen together, in one statement.
--
-- The note names the geocoder version rather than claiming a distance, because the
-- historical pin cannot be re-derived: the resolvers that produced it have since been
-- rewritten, and re-running today's code would yield a different answer.
--
-- Idempotent: the WHERE clause matches only rows still carrying the annotation.
-- Read-modify-write of a jsonb column; no schema change, no coordinate is touched.

BEGIN;

UPDATE public.dispatches
SET target = target || jsonb_build_object(
        'address',
            btrim(regexp_replace(target->>'address', '\s*\(Street Centroid\)\s*$', '')),
        'requested_address',
            btrim(regexp_replace(target->>'address', '\s*\(Street Centroid\)\s*$', '')),
        'resolution_note',
            btrim(regexp_replace(target->>'address', '\s*\(Street Centroid\)\s*$', ''))
            || ' had no matching parcel in City of Coquitlam records. The location shown'
            || ' is a street centroid — the average position of that street, not a'
            || ' specific address. Recorded by the geocoder in use at the time of this'
            || ' call; annotation migrated 2026-08-23.'
    )
WHERE target->>'address' ILIKE '%(Street Centroid)%';

COMMIT;
