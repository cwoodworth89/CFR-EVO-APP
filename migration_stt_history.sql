-- Migration: Create evaluation_history table for STT metrics tracking
CREATE TABLE IF NOT EXISTS public.evaluation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    model_version TEXT NOT NULL,
    total_samples INTEGER NOT NULL,
    wer NUMERIC(5,2) NOT NULL,
    cer NUMERIC(5,2) NOT NULL,
    perfect_percent NUMERIC(5,2) NOT NULL,
    operational_percent NUMERIC(5,2) NOT NULL,
    failed_percent NUMERIC(5,2) NOT NULL
);

-- Manage Realtime settings for evaluation_history
DO $$
BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.evaluation_history;
EXCEPTION
    WHEN OTHERS THEN
        NULL;
END $$;

-- Enable Row-Level Security (RLS)
ALTER TABLE public.evaluation_history ENABLE ROW LEVEL SECURITY;

-- RLS Policies
DROP POLICY IF EXISTS "Allow public select on evaluation_history" ON public.evaluation_history;
CREATE POLICY "Allow public select on evaluation_history" 
ON public.evaluation_history FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow authenticated insert on evaluation_history" ON public.evaluation_history;
CREATE POLICY "Allow authenticated insert on evaluation_history" 
ON public.evaluation_history FOR INSERT TO authenticated WITH CHECK (true);
