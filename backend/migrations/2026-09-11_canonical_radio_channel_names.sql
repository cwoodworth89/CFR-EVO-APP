-- Radio channels: one canonical name, used by the parser, the operator picker and the kiosk
--
-- WHY
-- Two names existed for every channel and neither side agreed with the other.
-- public.vocabulary held "Talk Group 10 Combined Response Coquitlam"; the parser ran every
-- match through clean_channel_name_for_output(), which stripped "Talk Group" and
-- "Coquitlam" and stored "10 Combined Response" -- a string in no vocabulary. So:
--
--   * 575 of 576 stored dispatches.target->>'radio_channel' values matched nothing in the
--     list the operator picks from, and the HITL picker appended each as a stray extra
--     <option> (VerificationSidebar.jsx, the "saved value stays choosable" branch). That
--     extra row at the bottom of the talk group dropdown was this, on nearly every call.
--   * The drift reached ground truth: 396 verified_talkgroup rows hold "10 Combined
--     Response" (prefilled from the system value) against 1 holding a real vocabulary term.
--   * Two spellings of one channel accumulated -- "Combined Response" (38) and "10 Combined
--     Response" (385) -- from successive versions of the cleaner.
--
-- PROVENANCE (CLAUDE.md 6.3, tier 4 -- department operational policy):
-- The canonical spoken form is the operator's ruling, 2026-09-11: the "Talk Group" prefix
-- is not part of a channel's name. Locution announces "use talk group" as the carrier
-- phrase and the channel name follows it, so the vocabulary term is now exactly what is
-- spoken after that phrase -- "5 Coquitlam", "10 Combined Response Coquitlam", "Combined
-- Venue Port Mann". Nothing rewrites it on the way in or out.
--
-- The matching fix that goes with this is in cfr_dispatch/parser/channels.py; the venue
-- channels were unreachable before it (DISP-2026-07CC85, DISP-2026-B772D2).
--
-- Idempotent: the renames are keyed on the old term and the backfill on the old values.

BEGIN;

-- 1. The vocabulary is the list. Drop the prefix; the two venue channels never carried it.
UPDATE public.vocabulary v
SET term = c.new_term,
    term_normalized = lower(c.new_term),
    updated_at = NOW()
FROM (VALUES
    ('Talk Group 5 Coquitlam',                    '5 Coquitlam'),
    ('Talk Group 6 Coquitlam',                    '6 Coquitlam'),
    ('Talk Group 7 Coquitlam',                    '7 Coquitlam'),
    ('Talk Group 8 Coquitlam',                    '8 Coquitlam'),
    ('Talk Group 9 Coquitlam',                    '9 Coquitlam'),
    ('Talk Group 10 Combined Response Coquitlam', '10 Combined Response Coquitlam')
) AS c(old_term, new_term)
WHERE v.category = 'radio_channel' AND v.term = c.old_term;

-- 2. Every stored channel becomes the term it was derived from. "Combined Response" and
--    "10 Combined Response" are both channel 10 under earlier versions of the cleaner;
--    "Talk Group 10 Combined Response Coquitlam" is the one row picked from the old list.
CREATE TEMP TABLE _channel_canon(old_val TEXT PRIMARY KEY, new_val TEXT NOT NULL) ON COMMIT DROP;
INSERT INTO _channel_canon VALUES
    ('5',                                         '5 Coquitlam'),
    ('6',                                         '6 Coquitlam'),
    ('7',                                         '7 Coquitlam'),
    ('8',                                         '8 Coquitlam'),
    ('9',                                         '9 Coquitlam'),
    ('10 Combined Response',                      '10 Combined Response Coquitlam'),
    ('Combined Response',                         '10 Combined Response Coquitlam'),
    ('Talk Group 10 Combined Response Coquitlam', '10 Combined Response Coquitlam'),
    ('Talk Group 5 Coquitlam',                    '5 Coquitlam'),
    ('Talk Group 6 Coquitlam',                    '6 Coquitlam'),
    ('Talk Group 7 Coquitlam',                    '7 Coquitlam'),
    ('Talk Group 8 Coquitlam',                    '8 Coquitlam'),
    ('Talk Group 9 Coquitlam',                    '9 Coquitlam');

UPDATE public.dispatches d
SET target = jsonb_set(d.target, '{radio_channel}', to_jsonb(c.new_val), FALSE)
FROM _channel_canon c
WHERE d.target->>'radio_channel' = c.old_val;

UPDATE public.dispatches d
SET verified_talkgroup = c.new_val
FROM _channel_canon c
WHERE d.verified_talkgroup = c.old_val;

-- sanitized_transcript is deliberately NOT rewritten. It records what the system produced
-- at the time and is read as evidence in review; correcting it would erase the defect from
-- the corpus the backtest scores against (CLAUDE.md 6.6).

COMMIT;

-- Verify: every stored channel is now a vocabulary term, and nothing is orphaned.
--   SELECT d.target->>'radio_channel' AS stored, count(*),
--          bool_or(v.term IS NOT NULL) AS in_vocabulary
--   FROM public.dispatches d
--   LEFT JOIN public.vocabulary v
--     ON v.category = 'radio_channel' AND v.term = d.target->>'radio_channel'
--   WHERE d.target->>'radio_channel' IS NOT NULL
--   GROUP BY 1 ORDER BY 2 DESC;
