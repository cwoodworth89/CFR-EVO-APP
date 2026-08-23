-- public.dispatch_sessions — phase 1 state, survivable across a worker restart.
--
-- WHY
-- The two-phase pipeline kept phase 1 candidates in a plain dict inside the worker
-- process (DispatchSessionManager._phase_1_candidates). Nothing persisted it, so if the
-- worker died every in-flight dispatch lost its phase 1 context.
--
-- That is not a cosmetic loss. Phase 2 reads this state, and when it is missing it takes
-- the "Phase 1 was skipped" single-phase branch (phase2.py) and publishes a second INSERT
-- rather than the UPDATE the correction path uses — producing a duplicate dispatch on the
-- kiosk, which is the mechanism behind punch-list #25.
--
-- It was also the one piece of dispatch state not in PostgreSQL, which is otherwise the
-- single source of truth for dispatches, vocabulary, hydrants, intersections and closures.
--
-- TTL is enforced on created_at, matching the previous in-memory 600 s window. Rows are
-- deleted by cleanup_session on normal phase 2 completion; the TTL sweep only catches
-- dispatches whose phase 2 never ran.

CREATE TABLE IF NOT EXISTS public.dispatch_sessions (
    dispatch_id     VARCHAR(64) PRIMARY KEY,
    buffer_len      INTEGER     NOT NULL DEFAULT 0,
    raw_transcript  TEXT,
    transcript      TEXT,
    -- Serialized DispatchData dataclasses. Phase 2 reconstructs them and reads .address
    -- and .intersection, so the field names must round-trip exactly.
    candidates      JSONB       NOT NULL DEFAULT '[]'::jsonb,
    units           JSONB       NOT NULL DEFAULT '[]'::jsonb,
    target          JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The TTL sweep orders by age, so this is the index that matters.
CREATE INDEX IF NOT EXISTS idx_dispatch_sessions_created_at
    ON public.dispatch_sessions (created_at);

COMMENT ON TABLE public.dispatch_sessions IS
'Phase 1 state for in-flight dispatches, read by phase 2. Rows are short-lived: deleted on
phase 2 completion, or swept after the TTL if phase 2 never ran. A missing row makes phase
2 treat the dispatch as single-phase, which publishes a second INSERT — see punch-list #29.';
