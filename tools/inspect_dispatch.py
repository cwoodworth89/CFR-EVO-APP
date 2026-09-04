#!/usr/bin/env python3
"""Dump one dispatch record from the kiosk database as JSON.

    .venv/bin/python tools/inspect_dispatch.py DISP-2026-55B7B6

Runs on the kiosk host (or the laptop over Tailscale) with the project virtualenv, from the
repository root. Not inside the API container: tools/ is not copied into that image.

Why it insists on a Postgres DATABASE_URL
-----------------------------------------
``backend/api/database.py`` binds its engine at import time and, when it cannot reach
Postgres, silently falls back to an empty SQLite file under backend/data/. A tool built on
that would report a real dispatch as "not found" and look correct doing it (CLAUDE.md 6.1).
So the URL is settled first, from the environment or backend/.env, and the script stops if
it is missing or not Postgres.

History
-------
Rewritten 2026-09-04. The original (2026-08-04) imported ``cfr_dispatch.database``, a module
that has never existed in this repository, and queried an ``incident_number`` column that
``public.dispatches`` does not have. It had never run.
"""
from __future__ import annotations

import json
import os
import sys

from _repo import BACKEND  # tools/_repo.py puts backend/ (the api package) on sys.path


def settle_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        env_path = os.path.join(str(BACKEND), ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if not url.startswith(("postgresql://", "postgres://")):
        sys.exit("DATABASE_URL is not set (environment or backend/.env) or is not Postgres. "
                 "Refusing to run: api/database.py would fall back to an empty SQLite file and "
                 "report a real dispatch as missing.")
    os.environ["DATABASE_URL"] = url
    return url


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: inspect_dispatch.py <dispatch_id>", file=sys.stderr)
        return 2
    settle_database_url()
    from api.database import SessionLocal  # binds at import; must follow settle_database_url()
    from sqlalchemy import text

    dispatch_id = sys.argv[1]
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT * FROM public.dispatches WHERE dispatch_id = :id"), {"id": dispatch_id}
        ).mappings().first()
    if row is None:
        print(f"Dispatch '{dispatch_id}' not found in public.dispatches.")
        return 1
    print(json.dumps(dict(row), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
