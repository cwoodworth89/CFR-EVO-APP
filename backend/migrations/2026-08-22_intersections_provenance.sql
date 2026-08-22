-- public.intersections: add provenance so human corrections survive a re-derive.
--
-- The table is now DERIVED from public.roads centreline geometry (see
-- backend/scripts/derive_intersections.py). A rebuild must not silently discard a
-- coordinate an operator fixed by hand, so every row records where it came from.
--
--   'derived' -- computed from public.roads geometry. Deleted and rewritten on every
--                rebuild. Do not edit these by hand; the edit would be lost.
--   'manual'  -- entered or corrected by a person. NEVER touched by a rebuild.
--
-- A 'manual' row suppresses the derived row for the same key and candidate_index, so
-- the human answer is the one the geocoder sees.

ALTER TABLE public.intersections
  ADD COLUMN IF NOT EXISTS source VARCHAR(16) NOT NULL DEFAULT 'derived',
  ADD COLUMN IF NOT EXISTS notes TEXT,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE public.intersections
  DROP CONSTRAINT IF EXISTS intersections_source_check;
ALTER TABLE public.intersections
  ADD CONSTRAINT intersections_source_check CHECK (source IN ('derived','manual'));

CREATE INDEX IF NOT EXISTS idx_intersections_source ON public.intersections (source);
