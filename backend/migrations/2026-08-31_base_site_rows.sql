-- Add `is_base_site` to public.parcels, and make `address` unique only among those rows.
--
-- WHY
-- ---
-- One civic address can span several legal parcels -- 1,508 of them do, and 523 Gatensbury
-- St spans 392. The import collapsed those to one row by keeping whichever the shapefile
-- listed first, in file order, with no rule (punch-list #48). Measured against the source
-- geometry, 631 of those groups have members more than 25 m apart, so the row that won was
-- frequently not the one a crew arrives at.
--
-- Every tiebreak rule considered was wrong in a different way: largest area favours a vacant
-- rear lot over the building that fronts the street; nearest frontage picks one lot of a
-- 76-unit townhome complex; unioning scattered right-of-way records produces a polygon whose
-- centroid means nothing.
--
-- Operator decision 2026-08-31: DO NOT CHOOSE. Keep every City row exactly as published, and
-- add a CFR-owned `base_site` row that speaks for the whole property. There is then no
-- tiebreak to get wrong.
--
-- `base_site` rather than `base_building`: the latter is fire-prevention vocabulary for a
-- highrise or commercial structure and stops meaning anything for a trailer park or a
-- townhome complex, which is exactly where this problem is worst.
--
-- WHAT THIS ENABLES
-- -----------------
-- CFR context -- entrance point, lockbox, hazard notes, pre-plans -- lives on the base_site
-- row and applies to every City row at that address. One entrance set on `2865 Glen Dr`
-- serves all 76 of its units, so which City row a lookup happens to return stops mattering.
--
-- It also re-sizes punch-list #49 from "set entrances on 65,401 parcels", which is why that
-- item never moved, to 1,671 sites.
--
-- WHY THE UNIQUE INDEX BECOMES PARTIAL
-- ------------------------------------
-- `idx_parcels_address` is UNIQUE, and that is the thing forcing the collapse. It only needs
-- to hold for base_site rows: there must be exactly one per address, so the upsert that
-- protects operator columns has something to key on. City rows must be free to repeat,
-- because that is the whole point -- each keeps its own folio, legaldesc, gis_id and geometry.
--
-- The City's own MASTER record is NOT used as the base site. It was measured first: across
-- 517 properties holding both a MASTER row and unit rows, MASTER averages 10.3% of the summed
-- unit area while its bounding box spans the whole site. It is strata COMMON PROPERTY --
-- driveways and walkways threading between the units -- not the building and not the
-- property envelope. Adopting it as "the property" would have had the kiosk outline a
-- driveway network. See docs/briefings/base_site_rows_decision.md.
--
-- NOT DESTRUCTIVE. Adds a column defaulted FALSE, so every existing row remains a City row
-- and behaviour is unchanged until the import populates base sites.

BEGIN;

ALTER TABLE public.parcels
    ADD COLUMN IF NOT EXISTS is_base_site BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN public.parcels.is_base_site IS
    'TRUE on CFR-derived rows that represent a whole multi-parcel property and carry its '
    'operator context. FALSE on rows imported verbatim from the City address layer. '
    'See docs/briefings/base_site_rows_decision.md.';

-- address is unique only among base sites; City rows may repeat.
DROP INDEX IF EXISTS public.idx_parcels_address;

CREATE UNIQUE INDEX IF NOT EXISTS parcels_base_site_address_uniq
    ON public.parcels (address) WHERE is_base_site;

-- non-unique replacement for ordinary address lookups
CREATE INDEX IF NOT EXISTS idx_parcels_address
    ON public.parcels (address);

-- grouping key used to derive base sites from their member City rows
CREATE INDEX IF NOT EXISTS idx_parcels_base_grouping
    ON public.parcels (house, street, streettype) WHERE NOT is_base_site;

COMMIT;

-- VERIFY (expect: column present, exactly one unique index and it is partial,
-- and 0 base sites until the import creates them)
--
--   SELECT count(*) FILTER (WHERE is_base_site) AS base_sites,
--          count(*) FILTER (WHERE NOT is_base_site) AS city_rows
--     FROM public.parcels;
--
--   SELECT indexname, indexdef FROM pg_indexes
--    WHERE schemaname='public' AND tablename='parcels' AND indexdef ILIKE '%UNIQUE%';
