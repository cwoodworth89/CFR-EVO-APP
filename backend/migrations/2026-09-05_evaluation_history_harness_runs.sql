-- Let public.evaluation_history record any harness run, not only a Whisper WER run.
--
-- WHY
-- ---
-- The table was built for one script (backtest_regression.py) and its columns are that
-- script's summary: wer, cer, perfect/operational/failed percent, all NOT NULL. The parser
-- and geocoder harnesses, and the chained recording-to-map harness added 2026-09-05, have
-- different summaries, and forcing them into those columns would mean inventing numbers
-- (CLAUDE.md 6.1). So the STT-shaped columns become nullable, and every run also carries
-- which stage it measured, the code it ran (git hash), the slice of the corpus it replayed,
-- and its own metrics as JSON. Operator ruling 2026-09-04: "I want to see if we improve the
-- system over time." This table is where that is visible; tools/harness_history.py reads it.
--
-- Applied on the kiosk 2026-09-05:
--   docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch \
--     < backend/migrations/2026-09-05_evaluation_history_harness_runs.sql

ALTER TABLE public.evaluation_history
    ALTER COLUMN wer DROP NOT NULL,
    ALTER COLUMN cer DROP NOT NULL,
    ALTER COLUMN perfect_percent DROP NOT NULL,
    ALTER COLUMN operational_percent DROP NOT NULL,
    ALTER COLUMN failed_percent DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS stage TEXT,
    ADD COLUMN IF NOT EXISTS git_hash TEXT,
    ADD COLUMN IF NOT EXISTS period_start DATE,
    ADD COLUMN IF NOT EXISTS period_end DATE,
    ADD COLUMN IF NOT EXISTS metrics JSONB,
    ADD COLUMN IF NOT EXISTS notes TEXT;

-- Every row written before this migration came from backtest_regression.py.
UPDATE public.evaluation_history SET stage = 'stt' WHERE stage IS NULL;
