#!/usr/bin/env bash
# Is the dispatch agent in the middle of a call? Run ON the kiosk before any restart of cfr-agent.
#
#   ssh tcfire@100.95.146.94 "bash /home/tcfire/CFR-EVO-APP/tools/kiosk_capture_state.sh"
#
# Exit 0: safe to restart. Exit 1: a broadcast is being captured, or its phase 2 is still
# running; a restart now loses the call and its recording. On 2026-09-05 at 11:42 an unasked
# restart landed 50 s into a structure-fire capture (DISP-2026-33D8C2, punch list #70): no
# audio was saved and the address never reached the kiosk.
#
# The markers are the agent's own log lines, read from the systemd journal because the worker
# process (phase 2) logs there and not to backend/dispatch.log:
#   listener  "STATE: CAPTURING DISPATCH (ID: X)"                    a capture started
#   listener  "[X] Queueing finalized dispatch for background..."     the capture ended
#   worker    "[METRICS] [X] Phase 2 Finalized"                       the recording is saved and the record final
# A capture runs at most 75 s ("MAX DURATION (75s) REACHED", the listener's own cap) and phase 2
# took 6 s on 2026-09-05; a capture older than 195 s with no finalisation is a dead one, not a
# live one, and does not block a restart.
#
# JOURNAL_FILE=<path> reads that file instead of journalctl; NOW_EPOCH=<seconds> fixes "now".
# Both exist so the script can be tested against a saved journal.
set -u

LOOKBACK="${LOOKBACK:-30 min ago}"
if [ -n "${JOURNAL_FILE:-}" ]; then
  LINES=$(cat "$JOURNAL_FILE")
else
  LINES=$(journalctl -u cfr-agent --since "$LOOKBACK" --no-pager 2>/dev/null) || { echo "CANNOT TELL: journalctl failed"; exit 2; }
fi

last_start=$(printf '%s\n' "$LINES" | grep -E 'STATE: CAPTURING DISPATCH \(ID: DISP-[A-Z0-9-]+\)' | tail -1)
if [ -z "$last_start" ]; then
  echo "SAFE TO RESTART: no capture started since $LOOKBACK"
  exit 0
fi

id=$(printf '%s' "$last_start" | grep -oE 'DISP-[A-Z0-9-]+' | tail -1)
ts=$(printf '%s' "$last_start" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' | tail -1)
now=${NOW_EPOCH:-$(date +%s)}
age=$(( now - $(date -d "$ts" +%s) ))

after=$(printf '%s\n' "$LINES" | sed -n "/CAPTURING DISPATCH (ID: $id)/,\$p")
ended=$(printf '%s\n' "$after" | grep -c "\[$id\] Queueing finalized dispatch")
final=$(printf '%s\n' "$after" | grep -c "\[METRICS\] \[$id\] Phase 2 Finalized")

if [ "$final" -gt 0 ]; then
  echo "SAFE TO RESTART: last capture $id is finalised (phase 2 done), tones were ${age}s ago"
  exit 0
fi
if [ "$age" -gt 195 ]; then
  echo "SAFE TO RESTART: last capture $id started ${age}s ago and never finalised; that is a dead capture (#70), not a live one"
  exit 0
fi
if [ "$ended" -gt 0 ]; then
  echo "DO NOT RESTART: $id capture ended, phase 2 still running (${age}s since the tones)"
  exit 1
fi
echo "DO NOT RESTART: $id is being captured (${age}s since the tones; a broadcast runs up to 75 s, then phase 2)"
exit 1
