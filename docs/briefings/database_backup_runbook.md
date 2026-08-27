# Database Backup & Restore Runbook

Covers [`backend/scripts/backup_db.sh`](../../backend/scripts/backup_db.sh) on the kiosk
(`tcfire@100.95.146.94`). Background and the wider gap analysis are in
[`PROJECT_IDEAS.md`](../PROJECT_IDEAS.md) #9.

> **An untested backup is a hypothesis.** Run the restore drill in §4 at least once, and
> again after any change to the schema or the container setup.

**Drill status: ✅ PASSED 2026-08-27.** `cfr-critical-20260827-120023.sql.gz` was restored
into a scratch database with `psql -v ON_ERROR_STOP=1` (exit 0, no errors). All six
critical tables matched live row counts except `dispatches`, which was one row short —
confirmed as expected point-in-time drift, not data loss: restored `max(id)` was 528
against a live 529, i.e. one dispatch arrived after the 12:00:23 snapshot. Scratch
database dropped afterwards.

---

## 1. What is protected, and what is not

| | Retention | Contents |
|:--|:--|:--|
| `cfr-critical-*.sql.gz` | 90 runs | Tables no import script can rebuild — see the header of `backup_db.sh` |
| `cfr-full-*.sql.gz` | 7 runs | Every table, including the 135 MB re-importable `parcels` |

The split follows the risk, not the bytes. Measured 2026-08-27: `parcels` is 135 MB and
87% of the database but is re-importable from the City of Coquitlam Open Data Portal;
`dispatches` is 3.2 MB / 464 rows and is **irreplaceable** — it holds the `verified_*`
HITL corrections that the STT backtest and parser regression suites are built on.

The full dump contains every table, so a table wrongly classed as replaceable loses
retention depth, never data.

**Not covered by this script:**

* **Dispatch audio** (`backend/audio_files/`, `frontend/public/recordings/`, all `*.wav`).
  This is the other half of the ground-truth corpus — the recordings and the `verified_*`
  columns are one dataset in two stores, and losing either half destroys the pair.
  Tracked as PROJECT_IDEAS #9 step 4. **Still outstanding.**
* **Fine-tuned Whisper model** (`backend/models/whisper-base-cfr-ct2/`).
* **`backend/.env`** — deliberately never in any repository or dump.
* **MBTiles archives** — re-crawlable, slowly.

## 2. Schedule

Runs daily at 03:15 on the kiosk via the `tcfire` crontab:

```bash
ssh tcfire@100.95.146.94 "crontab -l | grep backup_db"
```

Backups are written to `/home/tcfire/cfr-backups/`, deliberately **outside** the repo so
that multi-megabyte dumps can never be swept into a `git add .`, and so repository
operations cannot disturb them.

## 3. Operating it

```bash
ssh tcfire@100.95.146.94 "/home/tcfire/CFR-EVO-APP/backend/scripts/backup_db.sh"
```

```bash
ssh tcfire@100.95.146.94 "ls -lht /home/tcfire/cfr-backups | head"
```

```bash
ssh tcfire@100.95.146.94 "tail -40 /home/tcfire/cfr-backups/backup.log"
```

The script fails loudly and exits non-zero if the `cfr_postgres` container is not
running, if `pg_dump` fails, or if none of the critical tables exist. It writes each dump
to a `.part` file and renames only on success, so an interrupted run leaves no file that
a later restore could mistake for a good one.

Environment overrides: `CONTAINER`, `BACKUP_DIR`, `KEEP_FULL`, `KEEP_CRITICAL`.

## 4. Restore drill

**Verify an archive is readable and complete** — gzip integrity plus a look at the tail,
since a truncated SQL dump will still decompress up to the truncation point:

```bash
ssh tcfire@100.95.146.94 "gunzip -t /home/tcfire/cfr-backups/cfr-critical-*.sql.gz && echo GZIP_OK"
```

A complete `pg_dump` ends with `-- PostgreSQL database dump complete`:

```bash
ssh tcfire@100.95.146.94 "gunzip -c \$(ls -t /home/tcfire/cfr-backups/cfr-critical-*.sql.gz | head -1) | tail -3"
```

**Rehearse into a scratch database** — never restore over the live one to test:

```bash
ssh tcfire@100.95.146.94 "docker exec cfr_postgres sh -c 'PGPASSWORD=\$POSTGRES_PASSWORD createdb -U \$POSTGRES_USER restore_drill'"
```

```bash
ssh tcfire@100.95.146.94 "gunzip -c \$(ls -t /home/tcfire/cfr-backups/cfr-critical-*.sql.gz | head -1) | docker exec -i cfr_postgres sh -c 'PGPASSWORD=\$POSTGRES_PASSWORD psql -U \$POSTGRES_USER -d restore_drill'"
```

Confirm the row count matches production, then drop the scratch database:

```bash
ssh tcfire@100.95.146.94 "docker exec cfr_postgres sh -c 'PGPASSWORD=\$POSTGRES_PASSWORD psql -U \$POSTGRES_USER -d restore_drill -c \"SELECT count(*) FROM dispatches\"'"
```

```bash
ssh tcfire@100.95.146.94 "docker exec cfr_postgres sh -c 'PGPASSWORD=\$POSTGRES_PASSWORD dropdb -U \$POSTGRES_USER restore_drill'"
```

**Real recovery** after losing the volume: bring the stack up so `init_db.sql` creates a
clean database, then load the newest full dump, then the newest critical dump on top —
in that order, so the freshest irreplaceable data wins.

## 5. Pulling copies off the kiosk

Everything in §1–4 lives on the same SSD as the database it protects. That defends
against `docker compose down -v`, a bad migration, and accidental deletion — **not
against hardware failure**, which is the failure most likely to take the irreplaceable
HITL corpus with it.

[`backend/scripts/pull_backups.ps1`](../../backend/scripts/pull_backups.ps1) is the
off-kiosk half. Run it on the developer laptop:

```powershell
.\backend\scripts\pull_backups.ps1
```

It copies down any archive not already held, verifies each transfer against the remote
byte size before accepting it, and rotates local full dumps while keeping **every**
critical archive — those are a few megabytes each and are the data that cannot be
regenerated.

Default destination is `~\Nextcloud\Documents\Projects\Coding\CFR-EVO-Backups` — a
sibling of the repository, never inside it, so multi-megabyte dumps cannot be swept into
a `git add .`. Because that path is under Nextcloud, syncing carries the archives off the
laptop too, making three copies in total.

Override with `-Destination` (e.g. an external drive) and `-KeepFull`.

### Still open

This depends on someone running the laptop. It is an interim measure, not scheduled
off-site storage, and PROJECT_IDEAS #9 step 2 stays open until something runs unattended.
If the laptop sits unopened for a month, the off-kiosk copy is a month stale.

**Dispatch audio remains unprotected entirely** (#9 step 4) — the recordings and the
`verified_*` columns are one dataset in two stores, and this covers only one of them.
