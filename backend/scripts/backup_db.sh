#!/usr/bin/env bash
#
# backup_db.sh -- scheduled PostgreSQL backup for the CFR EVO kiosk.
#
# Context (PROJECT_IDEAS.md #9): until now no backup existed anywhere in the
# project, and that was defensible -- every table derived from the City of
# Coquitlam Open Data Portal and could be rebuilt by re-running an import
# script. That stopped being true once HITL corrections began accumulating in
# public.dispatches, and `docker compose down -v` destroys the postgres_data
# volume in a single command.
#
# TWO TIERS, because the risk is not evenly distributed. Measured on the kiosk
# database 2026-08-27:
#
#   public.parcels      135 MB   87% of the database, fully re-importable
#   public.dispatches   3.2 MB   464 rows, IRREPLACEABLE (verified_* HITL data)
#
# The irreplaceable half is ~2% of the bytes, so it is kept far longer than the
# bulk. The full dump is still the safety net: it contains every table, so a
# table mis-classified as replaceable below loses retention depth, never data.
#
# Deliberately does NOT back up dispatch audio (backend/audio_files/, *.wav).
# That is the other half of the ground-truth corpus and is tracked separately
# as PROJECT_IDEAS.md #9 step 4.
#
# Usage:
#   backend/scripts/backup_db.sh              # both tiers
#   backend/scripts/backup_db.sh --critical   # small tier only
#   BACKUP_DIR=/mnt/x backend/scripts/backup_db.sh
#
# Restore: see docs/briefings/database_backup_runbook.md

set -euo pipefail

CONTAINER="${CONTAINER:-cfr_postgres}"
BACKUP_DIR="${BACKUP_DIR:-/home/tcfire/cfr-backups}"

# Retention counts, not days: a machine that was powered off for a week should
# still keep the last N good backups rather than expiring them by wall clock.
KEEP_FULL="${KEEP_FULL:-7}"
KEEP_CRITICAL="${KEEP_CRITICAL:-90}"

# Tables no import script can rebuild. Everything here is small; the whole set
# is under 4 MB, so a 90-deep retention costs well under a gigabyte.
#   dispatches          HITL verified_* corrections -- the ground-truth corpus
#   dispatch_sessions   pipeline session records
#   dispatch_uploads    manual upload provenance
#   evaluation_history  STT/parser MLOps metrics over time
#   streetview_overrides hand-set panorama orientations
#   vocabulary          units, call types, radio channels (hand-normalised)
#   gate_keys           hand-curated with Coquitlam SAR (PROJECT_IDEAS #8, not
#                       yet created -- absent tables are skipped, not fatal)
CRITICAL_TABLES=(
  dispatches
  dispatch_sessions
  dispatch_uploads
  evaluation_history
  streetview_overrides
  vocabulary
  gate_keys
)

log() { printf '%s [backup_db] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { printf '%s [backup_db] ERROR: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2; exit 1; }

docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true \
  || die "container '$CONTAINER' is not running -- no backup taken"

mkdir -p "$BACKUP_DIR"
STAMP="$(date '+%Y%m%d-%H%M%S')"

# Credentials come from the container's own environment rather than a parsed
# copy of backend/.env, so this cannot drift from what Postgres actually runs
# with and no password is duplicated into a second file.
in_pg() {
  docker exec "$CONTAINER" sh -c \
    'PGPASSWORD="$POSTGRES_PASSWORD" '"$1"' -U "$POSTGRES_USER" -d "$POSTGRES_DB" '"${2:-}"
}

# Write to .part and rename only on success. A truncated dump that looks like a
# valid backup is precisely the plausible-wrong-answer failure this project
# treats as a defect (CLAUDE.md 6.1); an interrupted run must leave no file
# that a future restore could mistake for a good one.
dump_to() {
  local out="$1" args="$2" label="$3"
  if in_pg pg_dump "$args" | gzip -9 > "${out}.part"; then
    mv "${out}.part" "$out"
    log "$label -> $(basename "$out") ($(du -h "$out" | cut -f1))"
  else
    rm -f "${out}.part"
    die "$label dump failed"
  fi
}

# Keep the newest N of a prefix, delete the rest.
rotate() {
  local prefix="$1" keep="$2"
  local -a old
  mapfile -t old < <(ls -1t "$BACKUP_DIR/${prefix}"-*.sql.gz 2>/dev/null | tail -n +"$((keep + 1))")
  if [ "${#old[@]}" -gt 0 ]; then
    rm -f "${old[@]}"
    log "rotated ${#old[@]} old ${prefix} backup(s), keeping $keep"
  fi
}

backup_critical() {
  # Ask the database which of the critical tables exist rather than assuming.
  # gate_keys is listed above before it has been created, and pg_dump's
  # behaviour when a -t pattern matches nothing is not something to guess at
  # (CLAUDE.md 7.3a) -- so resolve the list first and pass only real tables.
  local list present args=""
  list="$(printf "'%s'," "${CRITICAL_TABLES[@]}" | sed 's/,$//')"
  present="$(in_pg psql "-tAc \"SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ($list) ORDER BY tablename\"")" \
    || die "could not enumerate critical tables"

  [ -n "$present" ] || die "none of the critical tables exist -- refusing to write an empty backup"

  local t
  while IFS= read -r t; do
    [ -n "$t" ] && args="$args -t public.$t"
  done <<< "$present"

  log "critical tables: $(echo "$present" | tr '\n' ' ')"
  dump_to "$BACKUP_DIR/cfr-critical-${STAMP}.sql.gz" "$args" "critical"
  rotate "cfr-critical" "$KEEP_CRITICAL"
}

backup_full() {
  dump_to "$BACKUP_DIR/cfr-full-${STAMP}.sql.gz" "" "full"
  rotate "cfr-full" "$KEEP_FULL"
}

main() {
  log "starting (container=$CONTAINER dir=$BACKUP_DIR)"
  backup_critical
  if [ "${1:-}" != "--critical" ]; then
    backup_full
  fi
  log "done; $(ls -1 "$BACKUP_DIR"/*.sql.gz 2>/dev/null | wc -l) archive(s), $(du -sh "$BACKUP_DIR" | cut -f1) total"
}

main "$@"
