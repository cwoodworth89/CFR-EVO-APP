-- Rename public.live_calls -> public.dispatches
--
-- The table held dispatch records but was named live_calls, while every document,
-- skill file, and API route called them dispatches. docs/development_freeze_summary.md
-- even listed "public.dispatches" as if it existed. This aligns the schema with the
-- terminology used everywhere else.
--
-- Idempotent: safe to re-run. Data, column types, and row identities are preserved --
-- ALTER TABLE ... RENAME is a catalog-only operation.

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = 'live_calls')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'public' AND table_name = 'dispatches')
    THEN
        ALTER TABLE public.live_calls RENAME TO dispatches;

        -- Indexes and constraints keep their old names through a table rename;
        -- rename them too so nothing still reads "live_calls".
        ALTER INDEX IF EXISTS live_calls_pkey                     RENAME TO dispatches_pkey;
        ALTER INDEX IF EXISTS live_calls_dispatch_id_key          RENAME TO dispatches_dispatch_id_key;
        ALTER INDEX IF EXISTS idx_live_calls_dispatch_id          RENAME TO idx_dispatches_dispatch_id;
        ALTER INDEX IF EXISTS idx_live_calls_feedback             RENAME TO idx_dispatches_feedback;
        ALTER INDEX IF EXISTS idx_live_calls_feedback_verified    RENAME TO idx_dispatches_feedback_verified;
        ALTER INDEX IF EXISTS idx_live_calls_timestamp            RENAME TO idx_dispatches_timestamp;
        ALTER INDEX IF EXISTS idx_live_calls_target_gin           RENAME TO idx_dispatches_target_gin;
        ALTER INDEX IF EXISTS idx_live_calls_routing_metrics_gin  RENAME TO idx_dispatches_routing_metrics_gin;

        RAISE NOTICE 'Renamed public.live_calls -> public.dispatches';
    ELSE
        RAISE NOTICE 'No rename performed (live_calls absent or dispatches already present)';
    END IF;
END $$;

COMMIT;
