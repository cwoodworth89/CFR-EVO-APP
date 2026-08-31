-- Migrate target.cross_streets (JSON array) to target.x_street_1 / x_street_2.
--
-- WHY
-- ---
-- Operator ruling 2026-08-30: XStreet1 / XStreet2 is the terminology on the printed run
-- sheet and the CAD terminal, and it is now the name used across the whole system --
-- database, pipeline, kiosk and review panel.
--
-- The shape changes too, and that half is a defect fix rather than a rename. The payload
-- built the value as:
--
--     [s for s in [cross_street_1, cross_street_2] if s]
--
-- and that filter destroyed position. Locution announces
--
--     [address] NEAR [x_street_1] AND [x_street_2]
--
-- with either omittable, so a call naming only the SECOND street produced a one-element
-- array whose single entry every reader took for the first.
--
-- WHAT THIS CANNOT RECOVER
-- ------------------------
-- For a one-element array the original position is NOT recorded anywhere -- that is the
-- bug. This migration therefore assigns a single value to x_street_1, which is the
-- majority case but is a guess for any record where only the second was announced.
--
-- Those records are marked with `x_streets_migration_ambiguous: true` rather than being
-- silently normalised, so a later reader can tell a known value from an assumed one
-- (CLAUDE.md §6.1 -- an unknown reported as unknown is a correct answer). Re-deriving the
-- true position needs a re-parse of raw_transcript, which is a separate exercise.
--
-- Safe to re-run: it only touches rows still carrying the old key.

BEGIN;

-- 1. Two announced streets: position is preserved exactly.
UPDATE public.dispatches
SET target = (target - 'cross_streets')
           || jsonb_build_object(
                'x_street_1', target->'cross_streets'->>0,
                'x_street_2', target->'cross_streets'->>1)
WHERE jsonb_typeof(target->'cross_streets') = 'array'
  AND jsonb_array_length(target->'cross_streets') >= 2;

-- 2. One announced street: assigned to x_street_1 and flagged as an assumption.
UPDATE public.dispatches
SET target = (target - 'cross_streets')
           || jsonb_build_object(
                'x_street_1', target->'cross_streets'->>0,
                'x_street_2', NULL,
                'x_streets_migration_ambiguous', true)
WHERE jsonb_typeof(target->'cross_streets') = 'array'
  AND jsonb_array_length(target->'cross_streets') = 1;

-- 3. Empty array: carried no XStreets. Drop the key rather than store two nulls --
--    absent and "announced as empty" are the same thing here.
UPDATE public.dispatches
SET target = target - 'cross_streets'
WHERE jsonb_typeof(target->'cross_streets') = 'array'
  AND jsonb_array_length(target->'cross_streets') = 0;

COMMIT;

-- Verification (expect old_key_remaining = 0):
--
--   SELECT count(*) FILTER (WHERE target ? 'cross_streets')                  AS old_key_remaining,
--          count(*) FILTER (WHERE target ? 'x_street_1')                     AS migrated,
--          count(*) FILTER (WHERE target ? 'x_streets_migration_ambiguous')  AS position_assumed
--   FROM public.dispatches;
