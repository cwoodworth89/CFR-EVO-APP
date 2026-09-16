-- Record the outcome of the last road closure sync attempt, so a failed sync can raise a
-- flag on the kiosk instead of leaving the previous list on screen looking current.
--
-- WHY
-- ---
-- Punch list #89. run_periodic_road_closure_sync wakes hourly and calls
-- check_and_sync_if_stale, which syncs when the local data is past 24 h. Nothing recorded
-- whether that attempt worked, so a two-week-old closure list looked exactly like today's,
-- and an empty list could mean either "the City has none" or "we never got through".
--
-- Operator ruling 2026-09-16: the flag is the *failed attempt*, raised when the previous
-- sync failed and cleared on the next success. Explicitly NOT a staleness indicator --
-- that was measured and ruled out, because road_closures.updated_at is stamped only on
-- rows a sync touches, so a healthy sync returning zero closures leaves it untouched and
-- an age-based flag would warn on a quiet day.
--
-- Why its own table rather than a column on road_closures: the outcome of an attempt is
-- not a property of any closure, and the case the flag exists to report -- a successful
-- sync that returns zero closures -- touches no closure row at all.
--
-- Why persisted rather than a module-level variable: the API container restarts, and the
-- daemon only re-attempts once the data is already past the 24 h gate, so an in-memory
-- flag would clear on restart and then read "all clear" for up to an hour with the link
-- still down.
--
-- ALREADY APPLIED, unintentionally. backend/api/server.py:116 runs
-- Base.metadata.create_all(bind=engine) at import, which creates any missing *table* (it
-- does not add columns to an existing one). Running backend/tests/test_road_closures_cache.py
-- locally on 2026-09-16 imports api.server against DATABASE_URL -- which points at the
-- kiosk -- and so created this table there before the api container was rebuilt. Verified
-- present with both CHECK constraints and zero rows, 2026-09-16.
--
-- That means rebuilding the api container is by itself enough to bring this table into
-- being, on this kiosk or on a fresh one. This file is the written record of the shape and
-- the reasoning, and is idempotent if run.
--
-- Deliberately no column DEFAULT on last_outcome: create_all does not emit SQLAlchemy's
-- client-side defaults, so putting one here would make this file and the table the
-- container creates differ. The code writes last_outcome on every insert.
--
-- Apply on the kiosk (optional, see above):
--   docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch \
--     < backend/migrations/2026-09-16_road_closure_sync_status.sql

CREATE TABLE IF NOT EXISTS public.road_closure_sync_status (
    id              INTEGER PRIMARY KEY,
    last_outcome    VARCHAR(16) NOT NULL,
    last_attempt_at TIMESTAMPTZ,
    last_error      TEXT,
    sources         JSONB,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT ck_road_closure_sync_status_singleton CHECK (id = 1),
    CONSTRAINT ck_road_closure_sync_status_outcome
        CHECK (last_outcome IN ('NOT_ATTEMPTED', 'SUCCEEDED', 'FAILED'))
);

COMMENT ON TABLE public.road_closure_sync_status IS
    'Single row (id = 1). Outcome of the most recent road closure sync attempt. Punch list #89.';
COMMENT ON COLUMN public.road_closure_sync_status.last_outcome IS
    'NOT_ATTEMPTED / SUCCEEDED / FAILED. NOT_ATTEMPTED is the state before any sync has run and is not a failure.';
COMMENT ON COLUMN public.road_closure_sync_status.sources IS
    'Per-feed reachability for that attempt. Any feed not ingested in full makes the whole attempt FAILED, because a partial closure list is indistinguishable from a complete one on the kiosk.';

-- No seed row. road_closure_service.record_sync_outcome inserts id = 1 on the first
-- attempt, and read_sync_status reports NOT_ATTEMPTED while the row is absent -- which is
-- the truthful answer, not a failure (CLAUDE.md 6.1).
