# Punch list #89 — A failed road closure sync leaves the last list on screen, with no warning

| | |
|:--|:--|
| **Status** | DEPLOYED 2026-09-16, confirmed by lead over SSH (kiosk HEAD `fdfb103e`, bundle and api image built 15:18Z). **`727c297b` carries a hook-order defect that is live on the display; the fix is `776b52e5` and needs a frontend build.** Falsifier not yet run. "Any for now" as built |
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
| 2026-09-16 | **Backend built, `ad339fec`.** New one-row table `public.road_closure_sync_status` (`backend/api/models.py:110`, SQL in `backend/migrations/2026-09-16_road_closure_sync_status.sql`; `create_all` at `server.py:116` makes it, no migration step). Outcome recorded on every exit of `sync_road_closures_to_db` (`road_closure_service.py:155`); `check_and_sync_if_stale` (`:503`) returns three distinct results; `GET /api/road-closures` returns `{closures, sync}` from one cache entry (`routers/road_closures.py:93`, `:161`). **Load-bearing finding:** neither feed's failure propagates as an exception — each `urlopen` is caught and logged (`:296`, `:401`), so an unreachable network produces an empty list and a clean exit, byte-for-byte a quiet day. Reachability is therefore recorded per feed where its block completes (`:294`, `:399`), not inferred from a raise; anything else would have failed the falsifier. Verified by `backend/tests/test_road_closure_sync_status.py` (8 checks, SQLite, no network) including the zero-closure clear; nothing live verified. Two pre-existing unrelated failures in `test_api_routers.py` confirmed at HEAD. **Judgement pending the operator:** any one feed not ingested in full marks the attempt FAILED (conservative; the alternative is a one-line change at `:176`). **Side effect:** the new table already exists on the kiosk, zero rows — a local test run imported `api.server` against `DATABASE_URL` and `create_all` made it. Additive and harmless; recorded because it landed outside the operator's hand |
| 2026-09-16 | Frontend half sent to `frontend-kiosk-architect` with the response contract: fix `useRoadClosures.js:27` (`Array.isArray` guard blanks the list on the new shape) and the banner in `RightSidebar.jsx` on exactly `sync.outcome === "FAILED"`; `NOT_ATTEMPTED` never raises it. #90 opened for the default coordinate GIS found at `routers/road_closures.py:134` |
| 2026-09-16 | **Frontend built, `727c297b`.** `useRoadClosures.js:35` unwraps `payload?.closures ?? payload` — the list draws on the old bare array and the new object, so the bundle and the api container can land in either order without an empty sidebar; `:36` lifts `sync`, returned as `syncStatus` (`:81`). Banner in `RightSidebar.jsx:167` on exactly `syncStatus?.outcome === "FAILED"`, rendered at `:194` between the header and the scroll area so it cannot scroll away; amber, not red, because red already means NO_ACCESS on the closure cards beside it; `error` and `lastAttemptAt` omitted entirely when null (§6.1). Wire through `MapBoard.jsx:108`, `:585`. On a *fetch* failure the hook keeps both the last list and the last flag — the kiosk failing to reach the API says nothing about the feeds. Verified: `lint:crash` and `build` clean; the unwrap and the condition exercised across nine payload shapes at expression level (no React test harness exists). **Not seen rendered**; visual fit at 320 px is reasoned, not looked at |
| 2026-09-16 | Operator reports deployed ("Done"). Recorded as reported, not confirmed (§6.6). Falsifier unrun. Note: #90's `e3009d6a` touches the same api container and will need another `--build api` |
| 2026-09-16 | **Operator ruled the open judgement: "any for now."** Any one feed not ingested in full marks the attempt FAILED, as GIS built it (`road_closure_service.py:176`). Revisable if DriveBC proves flaky; the per-feed detail in `sync.sources` is what would show that |
| 2026-09-16 | **Defect in `727c297b`, found by its author while doing #91:** the `React.useMemo` it added sits after `RightSidebar`'s `if (!isExplore) return null;` (`:158`), so if `appMode` changes while the sidebar is mounted React sees a different number of hooks and throws. `lint:crash` (no-undef, TDZ) cannot see hook order; full eslint on the touched files caught it. Fixed in `776b52e5` as a plain value. The agent assumed it was never deployed; **lead confirmed over SSH that it is** — kiosk HEAD `fdfb103e` includes it, bundle built 15:18Z. Deploying `776b52e5` or later removes it; `727c297b` alone must never be deployed again. Runbook change sent to the frontend agent: full eslint on touched files joins `kiosk-ui-audit` |
