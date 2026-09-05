"""The API's one database connection.

There is no fallback. The kiosk's PostgreSQL/PostGIS is the only database this system has,
and since the operator's ruling of 2026-09-04 it is also the test database (backed up nightly
by backend/scripts/backup_db.sh). When Postgres cannot be reached at import, this module
exits non-zero. Under Docker that means the API container stops and `restart: always`
keeps retrying until Postgres answers, which is the behaviour a crew can see: the display
says the API is down. The previous behaviour, kept from 2026-06 until punch-list #61, was to
bind an empty SQLite file under backend/data/ and carry on, so the review console showed
"no dispatches" and the agent's POSTs landed in a file nobody read (CLAUDE.md 6.1: a
plausible wrong answer is worse than a visible unknown).
"""
import logging
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    # docker-compose.yml sets DATABASE_URL inside the container; this default matches its
    # POSTGRES_* defaults for a process running on the kiosk host.
    "postgresql://cfr_user:cfr_password_2026@localhost:5432/cfr_dispatch",
)

# Convert asyncpg/postgresql scheme if needed
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL.startswith("postgresql"):
    sys.exit(
        "api.database: DATABASE_URL must be a PostgreSQL URL, got scheme %r. "
        "There is no SQLite mode (punch-list #61)." % DATABASE_URL.split(":", 1)[0]
    )


def _connect():
    """Probe once with a short timeout, then build the pooled engine. Exit on failure."""
    # 2 s connect timeout: unchanged from before #61 (Postgres is a container on the same
    # host); not re-derived here.
    probe = create_engine(DATABASE_URL, pool_timeout=2, connect_args={"connect_timeout": 2})
    shown = probe.url.render_as_string(hide_password=True)
    try:
        with probe.connect():
            pass
    except Exception as exc:
        logging.critical("api.database: cannot reach PostgreSQL at %s: %s", shown, exc)
        sys.exit(
            "api.database: cannot reach PostgreSQL at %s: %s\n"
            "Refusing to start without the database; there is no fallback (punch-list #61)."
            % (shown, exc)
        )
    finally:
        probe.dispose()
    logging.info("api.database: connected to PostgreSQL at %s", shown)
    return create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        pool_timeout=30,
    )


engine = _connect()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
