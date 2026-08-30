-- Drop confidence_score from public.dispatches. Punch-list #45.
--
-- WHY IT IS GOING, not just moving: it was a metadata-completeness score labelled as
-- confidence. The geocoder's score minus 30 for no coordinates, 20 for no units, 15
-- for no map grid, 15 for no talk group. A call with a perfectly correct address but
-- an untranscribed talk group scored 85; a call resolved confidently to the WRONG
-- address scored 100. The penalties had no provenance and were not commensurable,
-- and the score destroyed the information it consumed -- by the time an operator saw
-- "85", which field was missing had been thrown away.
--
-- Named flags in target.review_flags replace it, with target.review_flag_count as
-- the total. Those keep the reasons, so a reviewer can confirm or refute each one.
--
-- THIS IS IRREVERSIBLE AND DISCARDS 507 ROWS OF HISTORICAL VALUES.
-- Operator decision 2026-08-29, made after the alternative (retain the column, stop
-- writing to it) was raised and declined.
--
-- The values are recoverable from the verified backup taken the same evening:
--     /home/tcfire/cfr-backups/cfr-critical-20260829-200615.sql.gz
-- confirmed at the time to contain 507 dispatches with gzip integrity OK.
--
-- Run:
--   docker exec -i cfr_postgres psql -U <user> -d cfr_dispatch \
--     < backend/migrations/2026-08-29_drop_confidence_score.sql

BEGIN;

-- verify_location is KEPT. It survives as the operator-facing "check this location"
-- marker, but is now set from a named condition (LOCATION_UNRESOLVED or
-- LOCATION_SUBSTITUTED) rather than an arithmetic threshold of 90.
ALTER TABLE public.dispatches DROP COLUMN IF EXISTS confidence_score;

COMMIT;

-- Backfill note: existing rows have no target.review_flags, so the review panel
-- shows no flag count for calls dispatched before this change. That is honest --
-- the flags were never computed for them. They can be backfilled from the stored
-- target fields if the history is ever wanted.
