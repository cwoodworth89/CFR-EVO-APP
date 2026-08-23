"""Phase 1 dispatch session state, persisted in PostgreSQL.

Replaces the in-memory dict that `DispatchSessionManager` used to keep inside the worker
process. If the worker died, every in-flight dispatch lost its phase 1 context, and phase 2
then took the "Phase 1 was skipped" branch and published a second INSERT instead of an
UPDATE — a duplicate dispatch on the kiosk (punch-list #25, #29).

It was also the only piece of dispatch state not in PostgreSQL, which is the single source
of truth for everything else in this system.

The `candidates` list holds `DispatchData` dataclasses. They are stored as JSON and
reconstructed on read, because phase 2 reads `.address` and `.intersection` off them as
attributes.
"""
import os
import time
import json
import logging
from dataclasses import asdict, fields

from sqlalchemy import create_engine, text

from cfr_dispatch.config.models import DispatchData

DEFAULT_TTL_SECONDS = 600

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        db_url = os.environ.get(
            'DATABASE_URL',
            'postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch'
        )
        _engine = create_engine(db_url, pool_pre_ping=True, pool_size=3)
    return _engine


def _serialize_candidates(candidates) -> str:
    out = []
    for c in candidates or []:
        if hasattr(c, '__dataclass_fields__'):
            out.append(asdict(c))
        elif isinstance(c, dict):
            out.append(c)
        else:
            logging.warning("Skipping non-serializable phase 1 candidate: %r", type(c))
    return json.dumps(out)


def _deserialize_candidates(raw) -> list:
    """Rebuild DispatchData objects, tolerating schema drift in either direction.

    Unknown keys are dropped and missing ones default, so a session written by an older
    build does not crash a newer worker reading it -- these rows outlive a deploy.
    """
    if not raw:
        return []
    rows = json.loads(raw) if isinstance(raw, str) else raw
    known = {f.name for f in fields(DispatchData)}
    rebuilt = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        extra = set(r) - known
        if extra:
            logging.debug("Dropping unknown phase 1 candidate fields: %s", sorted(extra))
        rebuilt.append(DispatchData(**{k: v for k, v in r.items() if k in known}))
    return rebuilt


class PostgresSessionStore:
    """Phase 1 session state, keyed by dispatch_id, with a TTL sweep."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds

    # ---------------------------------------------------------------- writes

    def record_phase_1(self, dispatch_id, buffer_len, raw_transcript, transcript,
                       candidates, units, target):
        try:
            with _get_engine().begin() as conn:
                conn.execute(text("""
                    INSERT INTO public.dispatch_sessions
                        (dispatch_id, buffer_len, raw_transcript, transcript,
                         candidates, units, target, created_at)
                    VALUES
                        (:dispatch_id, :buffer_len, :raw_transcript, :transcript,
                         CAST(:candidates AS jsonb), CAST(:units AS jsonb),
                         CAST(:target AS jsonb), now())
                    ON CONFLICT (dispatch_id) DO UPDATE SET
                        buffer_len     = EXCLUDED.buffer_len,
                        raw_transcript = EXCLUDED.raw_transcript,
                        transcript     = EXCLUDED.transcript,
                        candidates     = EXCLUDED.candidates,
                        units          = EXCLUDED.units,
                        target         = EXCLUDED.target,
                        created_at     = now();
                """), {
                    "dispatch_id": dispatch_id,
                    "buffer_len": int(buffer_len or 0),
                    "raw_transcript": raw_transcript or '',
                    "transcript": transcript or '',
                    "candidates": _serialize_candidates(candidates),
                    "units": json.dumps(list(units or [])),
                    "target": json.dumps(target or {}),
                })
            return True
        except Exception as e:
            # Loud: without this row phase 2 will treat the dispatch as single-phase and
            # publish a duplicate INSERT.
            logging.error("[%s] Could not persist phase 1 session: %s. Phase 2 will treat "
                          "this dispatch as single-phase and may publish a duplicate.",
                          dispatch_id, e, exc_info=True)
            return False

    def cleanup(self, dispatch_id):
        try:
            with _get_engine().begin() as conn:
                conn.execute(text("DELETE FROM public.dispatch_sessions WHERE dispatch_id = :d"),
                             {"d": dispatch_id})
        except Exception as e:
            logging.warning("[%s] Could not clean up phase 1 session: %s", dispatch_id, e)

    def evict_stale(self):
        """Delete sessions whose phase 2 never ran. Normal completion deletes its own row."""
        try:
            with _get_engine().begin() as conn:
                result = conn.execute(text("""
                    DELETE FROM public.dispatch_sessions
                    WHERE created_at < now() - make_interval(secs => :ttl)
                    RETURNING dispatch_id
                """), {"ttl": self.ttl_seconds})
                stale = [r[0] for r in result]
            if stale:
                logging.warning("Evicted %d phase 1 session(s) whose phase 2 never ran: %s",
                                len(stale), ', '.join(stale))
            return stale
        except Exception as e:
            logging.warning("Phase 1 session TTL sweep failed: %s", e)
            return []

    # ---------------------------------------------------------------- reads

    def get_phase_1(self, dispatch_id):
        try:
            with _get_engine().connect() as conn:
                row = conn.execute(text("""
                    SELECT raw_transcript, transcript, candidates, units, target
                    FROM public.dispatch_sessions WHERE dispatch_id = :d
                """), {"d": dispatch_id}).mappings().fetchone()
            if not row:
                return None
            return {
                "raw_transcript": row["raw_transcript"],
                "transcript": row["transcript"],
                "candidates": _deserialize_candidates(row["candidates"]),
                "units": row["units"] or [],
                "target": row["target"] or {},
            }
        except Exception as e:
            logging.error("[%s] Could not read phase 1 session: %s", dispatch_id, e,
                          exc_info=True)
            return None

    def is_triggered(self, dispatch_id) -> bool:
        try:
            with _get_engine().connect() as conn:
                return bool(conn.execute(text(
                    "SELECT 1 FROM public.dispatch_sessions WHERE dispatch_id = :d"
                ), {"d": dispatch_id}).fetchone())
        except Exception as e:
            logging.warning("[%s] Could not check phase 1 trigger state: %s", dispatch_id, e)
            return False
