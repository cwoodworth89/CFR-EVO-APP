# Punch list #61 — The API silently falls back to an empty SQLite file when Postgres is unreachable

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🗄️ API & Database |
| **Blocks** | 1 |
| **Origin** | Found 2026-09-04 while repairing `tools/inspect_dispatch.py` (staleness audit follow-up) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 61. The API silently falls back to an empty SQLite file when Postgres is unreachable

> **Status**: 🔴 **Open — found 2026-09-04 by reading the code; the fallback file on the kiosk
> proves the path has executed at least once.** Not fixed here: it is the production API's own
> startup behaviour and removing it is a design change, so it is the operator's call (§6.1).

### What the code does

`backend/api/database.py:15-40` binds the SQLAlchemy engine at import time. It opens a test
connection to `DATABASE_URL` with a 2-second timeout and, if that raises for any reason, creates
`backend/data/cfr_dispatch.db` and binds a SQLite engine to it instead. `ensure_sqlite_compatibility()`
(`database.py:47-58`) then adds any recently added columns to the SQLite `dispatches` table, so the
fallback is designed in, not accidental.

Everything downstream is silent about it:

* The agent persists every real dispatch **through the API**: `services/dispatch_notifications/src/notification_service/dispatch_persistence.py:10-13`
  POSTs to `/api/dispatches`. An API on the fallback writes those rows into the SQLite file, and
  they never reach `public.dispatches`.
* The kiosk and the review console read `/api/dispatches`. On the fallback they get an empty list,
  which is indistinguishable from "no calls today". That is the §7.1 test: a crew cannot tell.
* No log line reaches a person. The only trace is inside the container log.

### What guards it, and what does not

`docker-compose.yml:115-117` makes `api` depend on `postgres` with `condition: service_healthy`,
so at **stack start** the API waits for Postgres. But `api` has `restart: always`: if the API
container restarts while Postgres is down or restarting, it binds SQLite and **stays there until
its next restart**, however long Postgres has been back.

### Evidence, 2026-09-04

Checked on the kiosk, read-only:

| Check | Result |
|:--|:--|
| `backend/data/cfr_dispatch.db` on the host | **exists**, 73,728 bytes, last modified 2026-08-21 20:38 |
| Tables inside it | `dispatches`, `evaluation_history`, `dispatch_uploads`, `road_closures`, `streetview_overrides`, `parcels` |
| Rows in its `dispatches` | **0** |
| Same file inside the container | present at `/app/backend/data/cfr_dispatch.db` (bind mount) |

So the fallback fired at least once, on 2026-08-21 (the PostGIS migration day), created the
schema, and captured nothing that time. Whether the API is on Postgres **right now** was not
measured: two attempts to import `api.database` inside the container failed on the module path
(`/app` layout), and §7.7 says stop after two. The file evidence stands on its own.

### What would falsify this (§7.6)

* `engine.dialect.name` inside the running container printing `postgresql` shows the fallback
  is not active today; it does not show it cannot activate tomorrow.
* The file's modification time never advancing past 2026-08-21 shows it has not re-fired.
* A dispatch that a crew heard but the review console never listed, with a matching row inside
  the SQLite file, would be the failure itself.

### Recommended action

Remove the fallback: if Postgres is unreachable at import, log the reason and **exit non-zero**,
so `restart: always` keeps retrying until Postgres answers and the API is never up on the wrong
database. Then delete `backend/data/cfr_dispatch.db` and `ensure_sqlite_compatibility()`. Test
files that relied on the SQLite path, if any, should use an explicit SQLite URL rather than the
fallback. This is a §6.1 decision: an API that is down is a visible unknown; an API serving an
empty database is a plausible wrong answer.

`tools/inspect_dispatch.py` already refuses to run without a Postgres `DATABASE_URL` for this
reason, so a developer cannot be misled the same way.
