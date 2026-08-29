-- Make entrance_lat / entrance_lng mean what their name says.
--
-- WHAT THEY HOLD TODAY. An exact copy of the parcel centroid. Measured 2026-08-29 across
-- 65,400 populated rows: 0 match the front point, 65,400 match lat/lng, averaging 57 m from
-- the actual street frontage. The column is named "entrance" and has never contained one.
--
-- AND IT IS UNREACHABLE. services/gis/src/gis_service/address_resolver.py reads
--
--     dest_lat = front_lat or entrance_lat or lat
--
-- front_lat is populated on all 65,401 parcels, so entrance_lat is never consulted -- and if
-- it ever were, it would return the centroid, which is the same as the third fallback. A
-- field promising something it does not hold, that nothing reads: the same shape as the
-- library-naming defects in docs/standards/dependency-behaviour.md, in our own schema.
--
-- WHAT THIS MIGRATION DOES. Clears the copied centroids and re-establishes the column as the
-- OPERATOR-VERIFIED access point -- the gate, lobby door or driveway apron a company officer
-- has confirmed, for sites where the computed frontage point is not where crews should stop.
--
-- The computed value stays in front_lat / front_lng. The two are then cleanly separated:
--
--     entrance_*   human, authoritative, rare, never overwritten by an import
--     front_*      computed, regenerated on every parcel import
--
-- Resolution precedence becomes  entrance -> front -> approximate, changed in the same commit.
--
-- WHY REUSE THESE COLUMNS rather than add a parcel_access_overrides table: the convention
-- already exists here alongside lock_box_notes and hazard_notes (both present, both empty),
-- which is plainly where operator knowledge was intended to live. Adding a table for data
-- that already has a home is how one fact ends up in two places -- the defect this project
-- has already hit with street suffixes and TALK_GROUPS.
--
-- SCALE. docs/complex_sites_for_review.csv lists 1,421 sites where the property extends more
-- than 100 m beyond the computed arrival point. 252 of them carry 20+ unit addresses covering
-- 23,516 units; reviewing the top 100 sites covers 64% of affected addresses. This is a
-- review queue in the hundreds, not a per-parcel data-entry burden.
--
-- Safe to re-run.

BEGIN;

-- 1. Clear the copied centroids. Nothing reads this column today, so nothing breaks.
UPDATE public.parcels
   SET entrance_lat = NULL,
       entrance_lng = NULL
 WHERE entrance_lat IS NOT NULL
   AND entrance_lat = lat
   AND entrance_lng = lng;

-- 2. Attribution. An override that cannot be traced to a person and a date is not
--    operator-verified, it is just another unexplained number (CLAUDE.md §6.3).
ALTER TABLE public.parcels
    ADD COLUMN IF NOT EXISTS entrance_set_by   VARCHAR(120),
    ADD COLUMN IF NOT EXISTS entrance_set_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS entrance_note     TEXT;

-- 3. An entrance is only meaningful with both coordinates.
ALTER TABLE public.parcels
    DROP CONSTRAINT IF EXISTS parcels_entrance_pair_complete;
ALTER TABLE public.parcels
    ADD CONSTRAINT parcels_entrance_pair_complete
    CHECK ((entrance_lat IS NULL) = (entrance_lng IS NULL));

-- 4. Find the reviewed sites quickly; the vast majority of rows stay NULL.
CREATE INDEX IF NOT EXISTS idx_parcels_entrance_set
    ON public.parcels (id) WHERE entrance_lat IS NOT NULL;

COMMENT ON COLUMN public.parcels.entrance_lat IS
    'Operator-verified access point (gate/lobby/apron), latitude. NULL for the great majority '
    'of parcels, which use the computed front_lat. Set by human review; never written by any '
    'import. Takes precedence over front_lat when resolving a destination.';
COMMENT ON COLUMN public.parcels.entrance_lng IS
    'Operator-verified access point, longitude. See entrance_lat.';
COMMENT ON COLUMN public.parcels.entrance_note IS
    'Why the access point is where it is, shown to crews: "gated, keypad at Glen Dr west end".';
COMMENT ON COLUMN public.parcels.front_lat IS
    'COMPUTED frontage point: closest point on the road named by parcels.street to the parcel '
    'polygon. Regenerated on every parcel import. Overridden by entrance_lat where set.';

COMMIT;
