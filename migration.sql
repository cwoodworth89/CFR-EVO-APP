-- Migration: Setup simulation_requests table and update live_calls columns

-- 1. Add missing columns to public.live_calls if they do not exist
ALTER TABLE public.live_calls ADD COLUMN IF NOT EXISTS audio_url TEXT;
ALTER TABLE public.live_calls ADD COLUMN IF NOT EXISTS audio_duration NUMERIC(6,2);
ALTER TABLE public.live_calls ADD COLUMN IF NOT EXISTS origins TEXT[] DEFAULT '{}';

-- 2. Create the simulation_requests table
CREATE TABLE IF NOT EXISTS public.simulation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    audio_url TEXT NOT NULL,
    verified_transcript TEXT,
    status TEXT DEFAULT 'pending' NOT NULL, -- 'pending', 'processing', 'completed', 'failed'
    result JSONB,
    error_message TEXT
);

-- 3. Enable Realtime on simulation_requests
ALTER publication supabase_realtime ADD TABLE public.simulation_requests;

-- 4. Enable Row-Level Security (RLS) on simulation_requests
ALTER TABLE public.simulation_requests ENABLE ROW LEVEL SECURITY;

-- 5. Create RLS Policies for simulation_requests (Explicitly granting to anon and authenticated roles)
DROP POLICY IF EXISTS "Allow public select on simulation_requests" ON public.simulation_requests;
CREATE POLICY "Allow public select on simulation_requests" 
ON public.simulation_requests FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "Allow public insert on simulation_requests" ON public.simulation_requests;
CREATE POLICY "Allow public insert on simulation_requests" 
ON public.simulation_requests FOR INSERT TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public update on simulation_requests" ON public.simulation_requests;
CREATE POLICY "Allow public update on simulation_requests" 
ON public.simulation_requests FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);
