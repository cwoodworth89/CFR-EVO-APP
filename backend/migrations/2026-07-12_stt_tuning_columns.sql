-- WHY: adds the STT feedback-loop columns (model_updated, quality_rating) to public.dispatches.
-- Applied on the kiosk (both columns present, checked 2026-09-03) and also created by
-- backend/api/init_db.sql L43-44, so a fresh stack does not need it. Lived at the repository
-- root as migration_stt_tuning.sql from 2026-07-12 (8d06229) until 2026-09-03; moved here so
-- the migrations directory is the complete record.
-- Migration: Add model_updated and quality_rating to dispatches for STT feedback tracking
ALTER TABLE public.dispatches ADD COLUMN IF NOT EXISTS model_updated BOOLEAN DEFAULT FALSE;
ALTER TABLE public.dispatches ADD COLUMN IF NOT EXISTS quality_rating TEXT DEFAULT 'PENDING';
