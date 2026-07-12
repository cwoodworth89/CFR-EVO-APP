-- Migration: Add model_updated and quality_rating to live_calls for STT feedback tracking
ALTER TABLE public.live_calls ADD COLUMN IF NOT EXISTS model_updated BOOLEAN DEFAULT FALSE;
ALTER TABLE public.live_calls ADD COLUMN IF NOT EXISTS quality_rating TEXT DEFAULT 'PENDING';
