-- Recover dispatches written to the orphaned public.live_calls table, then drop it.
--
-- Sequence of events on 2026-08-21:
--   16:24 PDT  2026-08-21_rename_live_calls_to_dispatches.sql renamed the table.
--   16:36 PDT  DISP-2026-01DCBC (Lift Assist, 1142 Dufferin St, M1) arrived while the
--              cfr_api container was still running the pre-rename image. Its models.py
--              still declared __tablename__ = "live_calls", so SQLAlchemy's create_all
--              recreated the table and the dispatch was written there instead.
--   17:30 PDT  The container was rebuilt and began writing to public.dispatches again.
--
-- A `docker restart` reuses the existing image; only a rebuild picks up code changes.
-- The rename migration should have been paired with an image rebuild in the same step.
--
-- This moves any rows that exist only in live_calls into dispatches, preserving
-- dispatch_id, then drops the orphan table. Idempotent.

BEGIN;

DO $$
DECLARE
    moved INT := 0;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = 'live_calls') THEN

        INSERT INTO public.dispatches (
            dispatch_id, timestamp, incident_type, responding_units, target,
            raw_transcript, sanitized_transcript, confidence_score, verify_location,
            origins, audio_url, audio_duration, verified_transcript, verified_address,
            verified_incident, verified_units, feedback_submitted, quality_rating,
            model_updated, review_notes, routing_metrics
        )
        SELECT
            lc.dispatch_id, lc.timestamp, lc.incident_type, lc.responding_units, lc.target,
            lc.raw_transcript, lc.sanitized_transcript, lc.confidence_score, lc.verify_location,
            lc.origins, lc.audio_url, lc.audio_duration, lc.verified_transcript, lc.verified_address,
            lc.verified_incident, lc.verified_units, lc.feedback_submitted, lc.quality_rating,
            lc.model_updated, lc.review_notes, lc.routing_metrics
        FROM public.live_calls lc
        WHERE NOT EXISTS (
            SELECT 1 FROM public.dispatches d WHERE d.dispatch_id = lc.dispatch_id
        );

        GET DIAGNOSTICS moved = ROW_COUNT;
        RAISE NOTICE 'Recovered % dispatch(es) from public.live_calls', moved;

        DROP TABLE public.live_calls;
        RAISE NOTICE 'Dropped orphaned public.live_calls';
    ELSE
        RAISE NOTICE 'public.live_calls does not exist; nothing to recover';
    END IF;
END $$;

COMMIT;
