# Punch list #89 — A failed road closure sync leaves the last list on screen, with no warning

| | |
|:--|:--|
| **Status** | OPEN — design ruled 2026-09-16; not built |
| **Severity** | 🔴 crew-visible — a two-week-old closure list looks exactly like today's |
| **Area** | 🖥️ Kiosk · ⚙️ API |
| **Origin** | External call audit, 2026-08-31 (`post_freeze_backlog.md`, the §2.1 row); promoted when the operator ruled the design on 2026-09-16 |
| **Related** | [`../external_calls.md`](../external_calls.md) §2.1 · `road-closure-management` skill |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

1. **The sync fails silently.** `run_periodic_road_closure_sync`
   (`backend/api/routers/road_closures.py:156`) wakes hourly and calls
   `check_and_sync_if_stale` (`backend/api/road_closure_service.py:369`), which syncs from
   `open511.gov.bc.ca` when the local data is older than 24 h. A failure is caught, logged and
   swallowed (`:395`), and the function returns `False` — **the same value it returns when no
   sync was needed** (`:398`). The caller cannot tell "nothing to do" from "could not reach
   the source".
2. **The kiosk keeps drawing the last set.** `useRoadClosures`
   (`frontend/src/hooks/useRoadClosures.js`) polls `GET /api/road-closures` every five
   minutes and gets the list, only the list. The sidebar (`RightSidebar.jsx`) groups it by
   hall. Nothing on screen says when it was last true.
3. **An empty list is unreadable.** No closures on screen means either the City has none or
   the source was never reached. Today those look identical.

## What was ruled out, and why

A staleness indicator built on the age of the data. Measured 2026-09-16:
`check_and_sync_if_stale` reads `max(RoadClosureModel.updated_at)`, and `updated_at` is
stamped on every row a sync touches (`road_closure_service.py:308`) — so it tracks contact
only while at least one closure comes back. A sync that succeeds and returns zero closures
leaves the timestamp untouched, and the indicator would warn on a healthy quiet day. A warning
crews learn to ignore is worse than none.

## The ruling — operator, 2026-09-16

**Raise a warning flag when the previous attempt to sync failed. Clear it the next time one
succeeds.** No threshold, no derived value.

It also closes point 3 above: no flag and no closures means the source was reached and the
City has none; a flag and no closures means we could not reach it.

## What it needs

1. **Backend — three-state outcome, persisted.** The sync records its last attempt's result
   in Postgres (not process memory: the API container restarts, and the daemon only re-attempts
   at startup when the data is already stale — `check_and_sync_if_stale`'s 24 h gate — so an
   in-memory flag would clear on restart and stay clear for up to an hour with the link still
   down). States: not attempted / succeeded / failed, with the time of the last attempt.
   `check_and_sync_if_stale` stops returning `False` for two different things.
2. **API — expose it.** `GET /api/road-closures` returns the outcome beside the list.
3. **Kiosk — the flag.** Operator ruling 2026-09-16: **a banner in the closure sidebar,
   shown only while the last sync attempt failed, absent otherwise.** Not a persistent status
   line. Rendered by `RightSidebar.jsx` from the field the API returns in piece 2; the sidebar
   keeps drawing the last list beneath it, since a stale list with a warning beats an empty
   one.

Falsifier, before building on it (§7.6): pull the kiosk's network for one hourly tick with the
data older than 24 h, and confirm the flag raises; restore it and confirm the flag clears on
the next successful tick, including when the source returns zero closures.

## Log

| Date | Event |
|:--|:--|
| 2026-08-31 | Found by the external call audit; parked in the backlog as "§6.1 question, not a coding fix" |
| 2026-09-16 | Age-based indicator measured and ruled out (see above). Operator ruled the failed-attempt flag. Promoted here |
| 2026-09-16 | Operator: backend half to `gis-spatial-engineer` (sent by lead, three bounded pieces); element ruled — a banner in the closure sidebar, only while the last attempt failed. Frontend half goes to `frontend-kiosk-architect` once the API field's shape is returned |
