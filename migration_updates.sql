-- Migration: Rename simulation_requests to dispatch_uploads and configure policies & realtime

-- 1. Rename the table
ALTER TABLE IF EXISTS public.simulation_requests RENAME TO dispatch_uploads;

-- 2. Create the table fresh if running on a clean database setup
CREATE TABLE IF NOT EXISTS public.dispatch_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    audio_url TEXT NOT NULL,
    verified_transcript TEXT,
    status TEXT DEFAULT 'pending' NOT NULL, -- 'pending', 'processing', 'completed', 'failed'
    result JSONB,
    error_message TEXT
);

-- 3. Manage Realtime settings
-- Remove old table from publication if it exists
DO $$
BEGIN
    ALTER PUBLICATION supabase_realtime DROP TABLE public.simulation_requests;
EXCEPTION
    WHEN OTHERS THEN
        -- Catch if table is already dropped or is not a member of publication
        NULL;
END $$;

-- Add renamed/new table to publication
DO $$
BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.dispatch_uploads;
EXCEPTION
    WHEN OTHERS THEN
        -- Catch if table is already a member of publication
        NULL;
END $$;

-- 4. Enable Row-Level Security (RLS)
ALTER TABLE public.dispatch_uploads ENABLE ROW LEVEL SECURITY;

-- 5. Create RLS Policies for dispatch_uploads (Restricting access to authenticated users to prevent public leaks)
DROP POLICY IF EXISTS "Allow public select on dispatch_uploads" ON public.dispatch_uploads;
DROP POLICY IF EXISTS "Allow authenticated select on dispatch_uploads" ON public.dispatch_uploads;
CREATE POLICY "Allow authenticated select on dispatch_uploads" 
ON public.dispatch_uploads FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Allow public insert on dispatch_uploads" ON public.dispatch_uploads;
DROP POLICY IF EXISTS "Allow authenticated insert on dispatch_uploads" ON public.dispatch_uploads;
CREATE POLICY "Allow authenticated insert on dispatch_uploads" 
ON public.dispatch_uploads FOR INSERT TO authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public update on dispatch_uploads" ON public.dispatch_uploads;
DROP POLICY IF EXISTS "Allow authenticated update on dispatch_uploads" ON public.dispatch_uploads;
CREATE POLICY "Allow authenticated update on dispatch_uploads" 
ON public.dispatch_uploads FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
