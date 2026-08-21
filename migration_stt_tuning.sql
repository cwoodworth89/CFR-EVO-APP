-- Migration: Add model_updated and quality_rating to dispatches for STT feedback tracking
ALTER TABLE public.dispatches ADD COLUMN IF NOT EXISTS model_updated BOOLEAN DEFAULT FALSE;
ALTER TABLE public.dispatches ADD COLUMN IF NOT EXISTS quality_rating TEXT DEFAULT 'PENDING';
