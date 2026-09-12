-- Call types: add a term the corpus proved, and settle "smouldering" on the Canadian spelling
--
-- WHY
-- Three corrections, all operator-directed 2026-09-11, found while re-measuring the call-type
-- matcher against the verified corpus.
--
-- 1. `Medical Aid - Confined Space Entrapment` is verified on DISP-2026-7F4878 but was not in
--    public.vocabulary, so the parser could only ever reach the bare "Medical Aid". The spoken
--    call-type list is still being built out: the department holds the CAD codes, not the
--    phrasing the Locution dispatcher actually reads, so terms are added as verified calls
--    reveal them.
--
-- 2. `Wildland Fire - Smoldering` (US spelling) is removed. It was never in the live database
--    -- only in the seed -- but it would come back on any fresh import. **No alias replaces
--    it** (operator ruling: "No alias, I'll do better next time to get it right").
--
--    Checked before removing it, because Whisper writes American English (punch-list #43) and
--    losing a recognition spelling could have cost real calls: of the 8 raw transcripts that
--    contain the word, **7 use the US spelling** -- and all of them already resolve to
--    `Wildland Fire - Smouldering` anyway, through the fuzzy stage, on the one-letter
--    difference. Removing the term costs nothing. Verified by re-parsing those calls.
--
-- 3. Two `verified_incident` rows hold `Wildland Fire - Smoldering`, a term that is not in the
--    vocabulary at all, so the backtest was scoring two correct parses as wrong. Those, and
--    the `verified_transcript` rows carrying the US spelling, move to Canadian.
--
--    This does change the WER reference: faster-whisper currently writes "smoldering", so its
--    output now scores as an error on those calls until a fine-tune teaches the department's
--    spelling. That is the intended direction, not a side effect -- 7 calls of 629.
--
-- `raw_transcript` and `sanitized_transcript` are NOT touched. They record what the STT and
-- the pipeline produced, and correcting them would erase the evidence (CLAUDE.md 6.6).
--
-- PROVENANCE (CLAUDE.md 6.3, tier 4 -- department operational policy): operator, 2026-09-11.
-- Canadian spelling throughout; the department writes "smouldering".
--
-- Idempotent: the insert is ON CONFLICT DO NOTHING, the delete and updates key on the old value.

BEGIN;

INSERT INTO public.vocabulary (category, term, term_normalized, sort_order, source, is_active)
VALUES ('call_type', 'Medical Aid - Confined Space Entrapment',
        'medical aid - confined space entrapment', 999, 'cfr_curated', TRUE)
ON CONFLICT (category, term) DO NOTHING;

DELETE FROM public.vocabulary
WHERE category = 'call_type' AND term = 'Wildland Fire - Smoldering';

UPDATE public.dispatches
SET verified_incident = 'Wildland Fire - Smouldering'
WHERE verified_incident = 'Wildland Fire - Smoldering';

UPDATE public.dispatches
SET verified_transcript = regexp_replace(
        regexp_replace(verified_transcript, 'Smoldering', 'Smouldering', 'g'),
        'smoldering', 'smouldering', 'g')
WHERE verified_transcript ~ 'moldering';

COMMIT;

-- Verify: no US spelling left in anything the operator wrote, and the new term is live.
--   SELECT count(*) FILTER (WHERE verified_incident  ~* 'smoldering') AS incident_us,
--          count(*) FILTER (WHERE verified_transcript ~* 'smoldering') AS transcript_us
--   FROM public.dispatches;
--   SELECT term FROM public.vocabulary
--   WHERE category = 'call_type' AND term ILIKE '%entrapment%' OR term ILIKE '%m%ulder%';
