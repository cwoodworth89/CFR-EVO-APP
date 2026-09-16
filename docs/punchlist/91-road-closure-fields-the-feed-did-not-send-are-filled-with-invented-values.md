# Punch list #91 — Road closure fields the feed did not send are filled with invented values, including the access level

| | |
|:--|:--|
| **Status** | DEPLOYED 2026-09-16 20:07Z, confirmed on the kiosk (HEAD `0d17989a`, migration, bundle and api all in). First sync forced 20:08Z: 67 of 71 active closures N/A. **Open:** ERROR log volume (141 lines / 3 min, measured); the admin panel row is BUILT `e0514fe4` and **needs a frontend build**; the DriveBC pass-through question waits on `roads[].state` values from the operator's browser |
| **Severity** | 🔴 crew-visible — crews read the access level off a severity the feed never sent |
| **Area** | ⚙️ API · 🖥️ Kiosk |
| **Origin** | Found by `gis-spatial-engineer` while fixing #90 ("hardcoded failsafes concern me, it needs to fail loudly" — operator, 2026-09-16); every line verified by lead against the working tree at `e3009d6a` |
| **Related** | #89 · #90 · CLAUDE.md §6.1 (no default incident type, no placeholder that reads as real data) · §6.3 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

#90 removed one invented value — a coordinate. The same two files fill every other gap the
feeds leave with a value that reads as real. The two that set the **access level** matter
most, and they default in **opposite directions**:

| Where | Default | What a crew sees |
|:--|:--|:--|
| `backend/api/road_closure_service.py:243` | `(evt.get('severity') or 'MINOR')` — an unknown DriveBC severity becomes MINOR | A closure of unknown severity is filed as **CAUTION**, the mildest tier |
| `backend/api/routers/road_closures.py:175` | `r.closure_type or "FULL_CLOSURE"` — an unknown stored type is served as a full closure | The same unknown, one step later, is drawn as **NO_ACCESS**, the most severe |

Neither carries a source (§6.3). Which one a crew sees depends on which field happened to be
empty. Both are the "default incident type" §6.1 names outright.

The rest, same defect, lower stakes:

| Where | Default |
|:--|:--|
| `routers/road_closures.py:177` | `r.description or "Active traffic event."` |
| `road_closure_service.py:278` | street name `or "Regional Corridor"` |
| `road_closure_service.py:282` | headline `or "TRAFFIC ALERT"` |
| `road_closure_service.py:367` | municipal location `or "Local Road"` |
| `road_closure_service.py:369` | description `or "Local road construction or restriction."` |
| `road_closure_service.py:277` | `closure_id` falls back to `f"db_{len(raw_notices)}"` when the feed sends no id — the same id can be produced on a later sync for a different closure and **overwrite it** |

## What it should do

An unknown severity is an unknown, not a tier: propagate `null`, and let the sidebar and the
marker show a closure whose access level is **not stated** — distinct from CAUTION, ACCESS
ONLY and NO ACCESS — rather than pick one. Text fields render as absent (`--`), not as prose
that reads as a description. A record with no id from the feed gets an id derived from the
record (source + stable fields), never from the position in the list.

## Operator rulings (as they stand, 2026-09-16 evening)

1. **Unknown severity → N/A.** "Keep the box but add N/A." A fourth visible state; severity and
   access level propagate as `null`. Never CAUTION, never NO_ACCESS. *Built in `ea6151b9` /
   `776b52e5`, stands.*
2. **Text placeholders → `--`.** "If we don't get a title don't make one up. Approved with `--`
   or N/A for those fields." Description, street name, headline, municipal location propagate
   `null`; the kiosk renders `--`. `street_name` is NOT NULL on the kiosk, so the migration
   must drop it. *In rework.*
3. **A record with no feed id → skipped.** First ruled "keep as null, but state it"; **reversed**
   on seeing the content-key solution: "likely needs to be flagged for an admin and not
   displayed, and just skipped… so we [don't] end up with a bunch of no feed_calls." Not stored,
   not served, logged at ERROR with the raw record, counted per attempt in the sync status. The
   content key (`feed_record_key`, CHECK, partial index, `idMissing`) is **removed**; `closure_id`
   stays NOT NULL. What the console shows an admin is GIS's to propose, not build. *In rework.*
4. **Municipal 511 must not start at CAUTION.** "For all I know it's purely informational
   alerts." A municipal record with no stated type is null → N/A; only a stated type raises
   it. *In rework.*
5. **DriveBC's present severities — verified 2026-09-16 from DriveBC's own documentation**
   (`api.open511.gov.bc.ca/help`, read with the operator's permission; the fetch is registered in
   [`../external_calls.md`](../external_calls.md) Part B). The enumeration is **MINOR / MODERATE /
   MAJOR / UNKNOWN**, and every definition is about *traffic impact*: MINOR "very limited impact on
   traffic"; MODERATE "a visible impact on traffic but should not create significant delay"; MAJOR
   "a significant impact on traffic, probably on a large scale"; UNKNOWN "the impact is unknown".
   **None of them says anything about whether a road is passable**, so MAJOR → NO_ACCESS was an
   invention, not a translation. The field that *is* about passability is `roads[].state` — DriveBC
   supports it (`name`, `from`, `to`, `state`, `direction`, plus a custom `delay` in minutes) and
   shows `"state": "CLOSED"` as its only example. **No reachable document enumerates it:** the
   Open511 spec site refuses with a self-signed certificate (lead and the operator both hit it),
   and BC's own OpenAPI specs — found through the Government of Canada open data record the
   operator supplied — define query parameters and no response schema. So it was **measured on
   the live feed instead, 2026-09-16, 306 active events in one request:** `roads[].state` is
   `ALL_LANES_OPEN` (238), absent (52) or `CLOSED` (16); `severity` is MINOR (274) or MAJOR (32),
   with MODERATE and UNKNOWN not in use; `event_type` is CONSTRUCTION (273), INCIDENT (18) or
   ROAD_CONDITION (15). **The two fields are independent: 18 MAJOR events had every lane open,
   and 5 MINOR events were CLOSED.** Under the deployed code those 18 drew as NO_ACCESS and those 5
   as CAUTION — wrong in both directions, measured. The feed is Open Government Licence – BC
   (from the spec's `license`). Recorded in the standards index and the register.
   **The specification itself was then read** — Open511 v1.0 `event.html` from the maintainer's
   repository, found through the operator's `datastandards.directory` link — so `roads[].state` is
   now HELD, verbatim: `CLOSED` "road closed in the given direction", `SOME_LANES_CLOSED` "but the
   road remains open", `SINGLE_LANE_ALTERNATING`, `ALL_LANES_OPEN`; with `roads[].direction`
   (N…NE, NONE, BOTH). Municipal 511's own legend was read too: it distinguishes "Road Closed -
   No Emergency Access / Emergency Access Unspecified", "Road Closed - Emergency Access Only",
   "Road Closed - Local Traffic Only", "Lane(s) Closed", "Alternating Traffic", "Intermittently
   Blocked", "Bike Lane Closure", "Sidewalk Closure". Both in the standards index.
   **Proposal for the operator, sourced, not built:**
   - **DriveBC:** the access box reads `roads[].state`, not `severity`. `CLOSED` → NO ACCESS —
     but the spec says *in the given direction*, so a closure with `direction` N and the crew
     approaching S is his to rule on. `SOME_LANES_CLOSED` and `SINGLE_LANE_ALTERNATING` → the
     road is passable with a restriction: which of our tiers, if any, is a domain call.
     `ALL_LANES_OPEN` → no restriction, informational. Absent → N/A. A value outside the four →
     N/A and one ERROR line naming it. `severity` shown as the feed's word (MINOR / MODERATE /
     MAJOR / UNKNOWN), never as a tier.
   - **Municipal 511:** the tiers already mirror its legend, but the `RoadClosureType` bit values
     in `road_closure_service.py` have no document behind them. Before any tier is trusted, GIS
     should verify each bit against the legend by measurement — pull one municipal record of
     each legend type and read its bits — and record the table. "Emergency Access Unspecified"
     shares an icon with "No Emergency Access" on the vendor's map; whether it shares a tier on
     ours is the operator's.
   - **Licence:** Municipal 511 states none. Recorded in the register; the operator decides.
   **Ruled, operator 2026-09-16, in his words:** "Closed -> No access (and we might need to alter
   the routing table about that, or know when we cross road events a driver should be flagged.
   Future work). All_lanes_open -> Info. Some_lanes/alternating (Caution - Restrictions). Closed
   per direction -> Caution - Restrictions, and state the road closure direction. We often can go
   counterflow with the help of flaggers." **Lead's reading, sent to GIS to build and to
   challenge:** `CLOSED` with direction BOTH / NONE / absent → NO_ACCESS; `CLOSED` with a
   compass direction → CAUTION with the direction carried and stated; `SOME_LANES_CLOSED` and
   `SINGLE_LANE_ALTERNATING` → CAUTION; `ALL_LANES_OPEN` → informational; absent → null; a value
   outside the four → null and one ERROR line. `severity` is never a tier; carried as the feed's
   word. Whether "Caution - Restrictions" is the CAUTION tier relabelled or a new tier is the
   frontend's question once the contract exists. **Municipal 511:** the operator ordered the bit
   verification and a complete list of current Coquitlam records for his review ("maybe decide
   if we need to filter out some items"); the municipal tier mapping and "Emergency Access
   Unspecified" are not ruled until he has read it. **Licence: "Backlog the license"** — done,
   not an item. The routing-table and cross-event-flag idea is a backlog line.
6. **No hover-only information**, anywhere on the kiosk or the console: "it won't benefit a
   touchscreen setup or mobile." Standing convention, going into `kiosk-responsive-ergonomics`;
   an audit of existing hover-only content is a backlog line, not freeze work.

## Falsifier

`SELECT count(*) FROM public.road_closures WHERE closure_type IS NULL OR description IS NULL
OR street_name IS NULL OR headline IS NULL OR closure_id LIKE 'db_%';` — if zero today, the
defect is latent like #90 was; it still goes, for the same reason.

## Log

| Date | Event |
|:--|:--|
| 2026-09-16 | Found by `gis-spatial-engineer` during #90, out of its scope, not built. Verified by lead line by line. Promoted under §7.1: the severity pair is crew-visible. Rulings above are the operator's |
| 2026-09-16 | Operator ruled severity (N/A, a fourth state) and the id (null, stated on the card). Backend sent to `gis-spatial-engineer`: stop both severity defaults and the positional id, define the response contract for unknown severity and missing id, solve the upsert, leave the text placeholders alone. Frontend half (the N/A box, the "no id" line) waits on that contract. Text placeholders still need a ruling |
| 2026-09-16 | **Backend built, `ea6151b9`.** `_drivebc_severity` (`road_closure_service.py:172`) replaces `or 'MINOR'`: missing, blank or UNKNOWN → `(None, None)`. `_feed_id` (`:160`) → `None` for missing/None/blank, which also closes one not listed: `str(evt.get('id', …))` turned a present-but-null id into the string **"None"**, shared by every such record. `db_{n}` gone at `:328`; Municipal 511's `muni_None_{n}` — the same positional defect in the other feed — gone at `:436`. Serializer `or "FULL_CLOSURE"` gone (`routers/road_closures.py:175–194`), ERROR logs at ingestion and at serve. **Contract:** `severity` and `emergencyAccess` null together when unknown; `id` null with `idMissing: true`; new `rowId` (integer, stable) for keys and selection, never displayed. **Model** (`models.py:92–115`): `closure_id` and `emergency_access` nullable, `closure_type` loses its default, new `feed_record_key`, CHECK `closure_id IS NOT NULL OR feed_record_key IS NOT NULL`, partial unique index on the key `WHERE closure_id IS NULL`. **Migration** `backend/migrations/2026-09-16b_road_closure_unknown_severity_and_missing_id.sql`, one transaction, **apply before the rebuild**: `create_all` does not alter an existing table, and the new code maps the column, so rebuild-first 500s every `road_closures` query until it runs. Lead read the migration and checked it against the live schema by a single `information_schema` SELECT: `closure_id` and `emergency_access` are the two NOT NULLs and are the two it drops; `closure_type` is already nullable; `feed_record_key` absent. Sufficient; **not executed**. **Match solution for an id-less record:** `feed_record_key = sha256` over canonical JSON of raw feed fields a feed does not edit in place (DriveBC: source, road_name, geography, schedule, created; Municipal: Source, LocationName, decoded path, ProposedStart), set only when `closure_id` is null, never served. Upsert matches id'd rows on `closure_id`, id-less on `closure_id IS NULL AND feed_record_key = key`; deactivation gained a second branch because `NOT IN` is never true for NULL. **Failure modes stated:** a feed editing a keyed field makes a new row and the old one deactivates only by the existing rules (id'd rows had the same gap); two id-less records identical in every key field → first kept, second dropped, ERROR logged — the one place a record is not kept. **Verified:** `FeedGapTests` in `test_road_closure_sync_status.py` (8 tests, 9 subtests, real ingestion on SQLite, no network) — nulls and logs for every unknown form, an id-less record synced three times with an in-place edit stays one row with one row id, identical pair → one row + ERROR, id-less record leaving the feed deactivates, Municipal issue without IssueId → one row over two syncs; served contract in `test_road_closures_cache.py`; road closure tests 19 passed. `test_api_routers.py::test_road_closures_router` hits the kiosk and **fails until the migration runs** — expected. **Falsifier on the kiosk:** 0 of 177 rows null in any of the four fields, 0 `db_%`, 0 `muni_None%` — latent, like #90. Frontend half sent with the contract. **Deploy-window note:** the current bundle's access filters do not match a null `emergencyAccess`, so such a closure would still show, in the marker's default colour; latent today |
| 2026-09-16 | **Operator rulings on seeing the build** (numbered list above): id-less records **skipped, not kept** — reversing the content-key solution before its migration ran; text placeholders `--`; Municipal 511 default null, not CAUTION; DriveBC present-severity pass-through is a question pending a permitted spec read; no hover-only information as a standing rule; `rules-of-hooks` joins `lint:crash`. Backend rework sent to `gis-spatial-engineer` (remove the content key, keep `closure_id` NOT NULL, count skips in the sync status, null the five text defaults with a `street_name` migration, municipal default null, leave DriveBC's present mapping alone). Frontend rework held for the new contract; the `lint:crash` and runbook changes sent now |
| 2026-09-16 | **Backend reworked, `c8dc474d`.** Migration replaced in place: one transaction, `ALTER COLUMN emergency_access DROP NOT NULL, ALTER COLUMN street_name DROP NOT NULL`, two column comments, no data change — **lead read it and it matches the two NOT NULLs the earlier `information_schema` read showed**; not executed. Model: `closure_id` NOT NULL again (`models.py:91`), `street_name` and `emergency_access` nullable, `feed_record_key`, CHECK and index gone. **Contract vs `ea6151b9`:** `id` never null (id-less records are not served); `idMissing` removed (the deployed bundle's branches at `RightSidebar.jsx:301`, `RoadClosureMarker.jsx:83` are dead, harmless, to be removed); `rowId` unchanged; `severity`/`emergencyAccess` null when unstated **and now null for a Municipal 511 record with no stated type** (bit 262144 → NO_ACCESS; bits 65536/32768/16384 or closed text → ACCESS_ONLY; otherwise null); `street`/`headline`/`description` null when the feed sent nothing → `--`. Two fallbacks remain, both real data from the same record: headline ← street name; municipal location ← LocationName → TableViewInfo.Location → BaseLocationDescription. **Skips:** `_skip_id_less_record` (`road_closure_service.py:215`) logs ERROR with source and raw record (2000-char cap) and counts; `sync.skipped = {count, bySource} | null` — last attempt only, resets each sync, `null` = no attempt has recorded one (not zero); also `sync.sources.<feed>.skippedNoId`; counted **after** the city and zone filters, so it is id-less records that would have shown in Coquitlam. **Deploy order:** migration then rebuild. Rebuild-first no longer 500s (no new column) but the first sync meeting an unstated severity or a missing road name fails its INSERT on NOT NULL, the whole sync rolls back, #89 records FAILED and the banner shows every tick until the migration runs — and 166 of today's 177 rows are municipal CAUTION, how many from the old default the table cannot say, so that is likely on the first sync. Migration-first with the old code running is harmless. **Falsifier:** after the migration, before the next sync, `SELECT count(*) FROM public.road_closures WHERE emergency_access IS NULL OR street_name IS NULL;` → 0; non-zero after the first sync on the new code is the ruling working. **Verified:** `FeedGapTests` reworked, 21 road closure tests + 10 subtests on SQLite, no network — skips not stored, logged, counted, outcome still SUCCEEDED; count resets; old status row → `skipped` null; text nulls; municipal untyped → null/null, 262144 → NO_ACCESS, "Road closed" → ACCESS_ONLY; served contract. `test_road_closures_router` passes against the live kiosk (old schema readable by new code); the same two unrelated failures as before. **Flagged, no action:** (1) the router logs ERROR per null-severity closure on every uncached serve (60 s cache, kiosk polls 5 min, console more) — if most municipal records are untyped that is ~100+ lines per serve and buries the skip errors; GIS suggests, after the first live sync shows the number, ERROR for skips and #90 only and one summary line for unknown severity — operator's call; (2) `sync.skipped` counts id-less records only; a closure dropped for unusable geometry or falling outside the city/zones is not counted, pre-existing and unchanged. **Admin surface, proposed only:** one "Road closure feed" row in `frontend/src/components/admin/SystemMetricsPanel.jsx` (rendered from `DispatchReview.jsx:662`, polls `/api/metrics/summary` every 10 s, already uses `--` for unmeasured) — last outcome and time, "N records skipped — no feed id" by source shown only when `count > 0`, a pointer to `journalctl`; data from `GET /api/road-closures` → `sync`, no new endpoint; alternative is `/api/metrics/summary` carrying `roadClosureSync`. Not the hall display, no banner. Frontend rework sent with the contract |
| 2026-09-16 | **Frontend reworked, `bbfc393e`**, five files, contract read at `road_closures.py:188–206` of `c8dc474d`. `closureText` (`closureAccess.js:100`, `NO_TEXT = '--'` at `:92`) returns `--` for null, undefined, empty or whitespace; everything that renders closure text goes through it — sidebar street `RightSidebar.jsx:285` and headline `:301`; popup headline `RoadClosureMarker.jsx:81`, street `:82`, description `:103`; nothing else renders closure text (searched). Hall grouping uses `zoneId`, never street. `idMissing` branches and the NO ID line removed from both files; `rowId` keying unchanged. **A card with all three text fields null, top to bottom:** `--` in the access colour (slate for N/A) with the source; the #90 location line only if it also has no point; `--` where the headline goes, with the access pill; the date range and ACTIVE/FUTURE pill. Popup: pill and source, `--` headline, `--` street, zones and dates if present, `--` description. `sync.skipped` not read anywhere; #89 banner unchanged. Verified: `lint:crash` (three rules), full eslint on the four `src` files, `build`, `npm run test:node` 56/56 with a new `closureText` test. Not seen rendered; no null-text record exists and none was made (§6.5). Committed with `git commit -- <paths>` |
| 2026-09-16 | **Deployed, confirmed by lead over SSH:** kiosk HEAD `0d17989a`, bundle 20:07 local, api image 20:07:25Z; migration applied (the forced sync below wrote nulls, so the NOT NULLs are gone). **Sync forced 20:08:24Z** (`POST /api/road-closures/sync`, the operator's word): `SUCCEEDED`, 78 synced, both feeds reached, `skipped.count` 0 both sources. Served list 71 closures: **67 null access (N/A), 2 null street, 2 null headline.** Table: 181 rows, 74 null access, 71 active of which 67 null access. So Municipal 511 states a type on almost none of its records — the old CAUTION default was invented for ~94% of what crews saw. **Log volume measured, not guessed: 141 ERROR lines in the three minutes around the sync**, one `has no known severity` line per null-severity closure per uncached serve — GIS's flag is real. Operator ruled the admin panel row ("monitor for now… possibly create rules around patterns"); sent to `frontend-kiosk-architect` with these numbers. DriveBC vocabulary verified (ruling 5 above) |
| 2026-09-16 | Operator ruled the `roads[].state` mapping (ruling 5 above, verbatim) and ordered the Municipal 511 bit verification plus a complete record list for his review. Both sent to `gis-spatial-engineer` as one job: Piece A the DriveBC contract (`roadState`, `roadDirection`, `feedSeverity`), Piece B the bit → legend → tier table marked measured or inferred, and `docs/briefings/municipal511_coquitlam_records_2026-09-16.md` with every current record grouped by label, nothing filtered. Frontend display waits on the contract |
| 2026-09-16 | **Operator ruled the log volume: "Collapse the severity errors to one summary line per serve."** The per-record `has no known severity` line at serve time (141 in three minutes, measured) becomes one line per uncached serve with the count by source; the id-less skip and #90's unusable coordinate stay ERROR per record, since the collapse exists so those are not buried. Sent to `gis-spatial-engineer` as Piece C, queued behind Pieces A and B; level (WARNING vs ERROR) is GIS's to choose and state |
| 2026-09-16 | **Admin panel row built, `e0514fe4`**, console only, three files by name; frontend build only, no api change. `SystemMetricsPanel.jsx:306` the block under the STT and container sections; `:8` `fetchClosureFeed`, one `apiClient.roadClosures.fetchAll()` on the panel's existing 10 s tick (`:59`) — no second loop, no new endpoint; `useRoadClosures` was not reachable without threading props through `MapBoard` and `DispatchReview` and would lag a forced sync by up to 5 min. `closureFeedCounts` at `closureAccess.js:113`. Three cards under "🚧 Road Closure Feed": **last sync attempt** (outcome coloured, `At --` when null, backend `error` when present); **sources · skipped, no feed id** (Reached / Not reached per source, `skipped N` per source and total, `--` when `sync.skipped` is null — not 0; above zero turns amber with a `journalctl` / `docker logs cfr_api` pointer); **served list** (closures served, access N/A, no street, no headline, each with its share, e.g. `67 (94%)`, counted with the same `accessKey` / `closureText` the cards render with). A failed read says so in red and every figure goes to `--`; stale numbers are never left on screen as current. Nothing hover-only. Verified: `lint:crash`, full eslint 0/0 on both `src` files, `build`, `test:node` 57/57, and **one read-only GET against the live kiosk** run through the helper: `SUCCEEDED` 20:08:24Z, both reached, skipped 0/0, 71 served / 67 N/A / 2 / 2 — matches lead's reading. Not seen rendered: the panel sits behind the admin unlock; the amber skipped state has never existed |
| 2026-09-16 | **Frontend built, `776b52e5`.** Contract checked against `routers/road_closures.py` at `ea6151b9`. Access labels and colours were three hand-copied ternaries, so they are now one module, `frontend/src/utils/closureAccess.js`, with `ACCESS_UNKNOWN` beside the three levels (`:43`, map line `#94a3b8` slate-400; the 🚧 icon was amber for every level already and is unchanged). **N/A** shows for null, absent or unrecognised `emergencyAccess` — sidebar pill `RightSidebar.jsx:310–311`, street colour `:285`, marker popup `RoadClosureMarker.jsx:76–77`, line `:32`; before this the same unknown drew NO_ACCESS red on the map and LANE CLOSURE yellow in the sidebar. **`⚠️ NO ID IN FEED RECORD`** under the street line (`RightSidebar.jsx:301–303`, popup `RoadClosureMarker.jsx:83–84`), stacked with the #90 location line; `rowId` never displayed. **Keys and selection** on `closureKey` (`rowId`, or `id` against an older api) at `RightSidebar.jsx:267` and `RoadClosuresLayer.jsx:23`, `sameClosure` at `:25` false when either side has no key, so two unidentified closures never both highlight; no other closure keyed on `id` anywhere in the frontend. **Filters:** map (`useRoadClosures.js:80`) and list (`RightSidebar.jsx:96`) both through `passesAccessFilter` (`closureAccess.js:66`); N/A passes unconditionally, since no toggle names it and switching off a known level should not hide an unknown one; timeframe toggles still apply. Verified: `lint:crash` and full eslint clean on every touched file (three pre-existing errors in `MapBoard.jsx` on untouched lines, same count with the change stashed), `build` clean, `npm run test:node` 55/55 with 6 new `closureAccess` tests. Not seen rendered; no such closure exists on the kiosk and none was created |
