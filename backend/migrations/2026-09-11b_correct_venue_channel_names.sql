-- The venue channels are "Combined Response Venue <X>", not "Combined Venue <X>"
--
-- WHY
-- The vocabulary was missing a word. Earlier the same day, 2026-09-11_canonical_radio_
-- channel_names.sql treated "combined response venue port man" on DISP-2026-07CC85 as
-- Whisper inserting "response" into "Combined Venue Port Mann". That was wrong, and it was
-- asserted without being checked against the audio (CLAUDE.md 7.3, 7.7).
--
-- The operator listened to the recording: the dispatcher says "use talk group combined
-- response venue port mann". His own verified transcript of DISP-2026-B772D2, corrected by
-- hand on 2026-08-02, says the same:
--
--   use talk group combined response venue port mann, map grid 52
--
-- The spoken template across 584 calls is invariably "use talk group <name> map grid <n>",
-- so what sits in that slot IS the channel name. The STT was right and the list was wrong.
--
-- PROVENANCE (CLAUDE.md 6.3, tier 4 -- department operational policy):
-- Operator, 2026-09-11, from the audio: the Port Mann channel is "Combined Response Venue
-- Port Mann". He rules the transit channel follows the same pattern -- "Combined Response
-- Venue Transit System" -- which no call in the corpus has ever exercised, so the rename
-- rests on his knowledge of the roster and not on a measurement.
--
-- CONSEQUENCE, and the ruling that goes with it
-- "Combined Response" now belongs to three channels, so channel 10 has no distinguishing
-- word left but its digit -- and Whisper drops that digit on ~9 % of channel-10 calls (39
-- of 434, confirmed against the operator's own verified transcripts, plus 2 calls that lost
-- it in one round and kept it in the other). match_radio_channel therefore stops requiring
-- a word no other channel carries and scores plain word overlap instead: "combined response
-- coquitlam" still names channel 10, three words to Port Mann's two.
--
-- A fragment degraded to bare "combined response" names both equally and becomes
-- NO_TALK_GROUP. Operator ruling, 2026-09-11: 10 calls of 584, taken over a frequency
-- tiebreak, because channel 10 outnumbering Port Mann 460 to 2 is not evidence about the
-- call in hand (6.1).
--
-- Those 10 historical rows are NOT rewritten. They record what the system produced, and
-- re-deciding a stored dispatch is a re-parse, not a canonicalisation (6.6).
--
-- Idempotent: keyed on the old terms and the old stored value.

BEGIN;

UPDATE public.vocabulary v
SET term = c.new_term,
    term_normalized = lower(c.new_term),
    updated_at = NOW()
FROM (VALUES
    ('Combined Venue Port Mann',     'Combined Response Venue Port Mann'),
    ('Combined Venue Transit System', 'Combined Response Venue Transit System')
) AS c(old_term, new_term)
WHERE v.category = 'radio_channel' AND v.term = c.old_term;

UPDATE public.dispatches
SET target = jsonb_set(target, '{radio_channel}',
                       to_jsonb('Combined Response Venue Port Mann'::text), FALSE)
WHERE target->>'radio_channel' = 'Combined Venue Port Mann';

UPDATE public.dispatches
SET verified_talkgroup = 'Combined Response Venue Port Mann'
WHERE verified_talkgroup = 'Combined Venue Port Mann';

COMMIT;

-- Verify: every stored channel is still a vocabulary term.
--   SELECT d.target->>'radio_channel' AS stored, count(*),
--          bool_or(v.term IS NOT NULL) AS in_vocabulary
--   FROM public.dispatches d
--   LEFT JOIN public.vocabulary v
--     ON v.category = 'radio_channel' AND v.term = d.target->>'radio_channel'
--   WHERE d.target->>'radio_channel' IS NOT NULL
--   GROUP BY 1 ORDER BY 2 DESC;
