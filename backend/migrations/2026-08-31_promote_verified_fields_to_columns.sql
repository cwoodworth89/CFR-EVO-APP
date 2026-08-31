-- Promote the operator-verified fields out of target JSON into real columns.
--
-- WHY
-- ---
-- `verified_*` was split across two storage mechanisms, and the only thing deciding
-- which a field got was WHEN it was added:
--
--     verified_transcript, verified_address, verified_incident, verified_units
--         -> real columns
--     verified_map_grid, verified_talkgroup, verified_response_type, verified_x_street_*
--         -> keys inside the `target` JSON blob
--
-- Nothing about the data justifies that. These are eight fixed things a human types
-- into eight fixed boxes during review, not a variable-shaped answer.
--
-- What the split costs, concretely:
--
--   * A JSON key cannot be type-checked or constrained. A misspelled key, or a value
--     of the wrong type, is accepted silently and returns empty forever. That is how
--     `.claude/skills/hitl-log-analysis` came to ship a triage query selecting
--     `feedback_notes`, a field that has never existed -- against a column it would
--     have errored on first run (docs/briefings/skills_audit_2026-08-30.md).
--   * A JSON key cannot be indexed usefully. `target->>'verified_map_grid'` opens every
--     row; a column does not.
--   * A JSON key is invisible in the schema. Nothing tells a reader the field exists;
--     you find out by reading application code, or by counting keys as this migration's
--     author had to.
--
-- This is the operator's own ground truth -- the data every harness in
-- docs/qa_harnesses.md measures against. It should be the best-described data in the
-- system, not the least.
--
-- WHAT STAYS IN `target`, AND WHY THAT IS CORRECT
-- -----------------------------------------------
-- `target` holds the GEOCODER'S ANSWER, which legitimately varies in shape: a parcel
-- with polygon `rings`, a junction with `candidates`, a street section with `length_m`,
-- or an amber `resolution_note` saying why it could not place the address. Forcing that
-- into fixed columns would mean dozens, mostly NULL on any given call. A JSON blob is
-- the right choice for a variable-shaped answer from one subsystem. It is the wrong
-- choice for a fixed set of human-entered fields.
--
-- DATA
-- ----
-- Measured 2026-08-31 before running: verified_map_grid on 458 records (428 non-empty),
-- verified_talkgroup on 458 (429 non-empty). verified_response_type and
-- verified_x_street_1/2 are written by the review panel but carry no records yet, so
-- they are created empty rather than copied.
--
-- The `target` keys are dropped in the same transaction, so there is exactly one home
-- for each field afterwards and no reader can silently keep using the stale one.
-- Safe to re-run.

BEGIN;

ALTER TABLE public.dispatches
    ADD COLUMN IF NOT EXISTS verified_map_grid      TEXT,
    ADD COLUMN IF NOT EXISTS verified_talkgroup     TEXT,
    ADD COLUMN IF NOT EXISTS verified_response_type TEXT,
    ADD COLUMN IF NOT EXISTS verified_x_street_1    TEXT,
    ADD COLUMN IF NOT EXISTS verified_x_street_2    TEXT;

-- Copy across. NULLIF keeps an empty string out of the column: the review panel wrote
-- '' for "not answered", and an unanswered field is NULL, not blank (CLAUDE.md §6.1).
UPDATE public.dispatches
SET verified_map_grid      = NULLIF(target->>'verified_map_grid', ''),
    verified_talkgroup     = NULLIF(target->>'verified_talkgroup', ''),
    verified_response_type = NULLIF(target->>'verified_response_type', ''),
    verified_x_street_1    = NULLIF(target->>'verified_x_street_1', ''),
    verified_x_street_2    = NULLIF(target->>'verified_x_street_2', '')
WHERE target IS NOT NULL
  AND (target ? 'verified_map_grid' OR target ? 'verified_talkgroup'
       OR target ? 'verified_response_type'
       OR target ? 'verified_x_street_1' OR target ? 'verified_x_street_2');

-- One home per field: remove the JSON keys now the columns hold them.
UPDATE public.dispatches
SET target = target - 'verified_map_grid' - 'verified_talkgroup'
                    - 'verified_response_type'
                    - 'verified_x_street_1' - 'verified_x_street_2'
WHERE target IS NOT NULL
  AND (target ? 'verified_map_grid' OR target ? 'verified_talkgroup'
       OR target ? 'verified_response_type'
       OR target ? 'verified_x_street_1' OR target ? 'verified_x_street_2');

COMMIT;

-- Verification (expect target_keys_remaining = 0, and the column counts to match the
-- non-empty figures recorded above -- 428 and 429):
--
--   SELECT count(*) FILTER (WHERE target ? 'verified_map_grid'
--                             OR target ? 'verified_talkgroup') AS target_keys_remaining,
--          count(verified_map_grid)  AS grid_col,
--          count(verified_talkgroup) AS talkgroup_col
--   FROM public.dispatches;
