# Punch list #91 — Road closure fields the feed did not send are filled with invented values, including the access level

| | |
|:--|:--|
| **Status** | REWORK — the operator reversed the id ruling and ruled the rest after seeing `ea6151b9`. **`ea6151b9` + `776b52e5` and their migration must not be deployed as they stand**; the migration never ran. Backend rework with `gis-spatial-engineer`; frontend rework held for the new contract. DriveBC present-severity pass-through pending |
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
5. **DriveBC's present severities — open question from the operator:** "What present severities
   are offered through DriveBC? Should we just pass them through?" The MAJOR → NO_ACCESS /
   other → CAUTION mapping has no source. Answering needs the Open511 spec read — an external
   fetch from the dev laptop, **permission asked, not yet given** — after which the mapping is
   either sourced or replaced by pass-through. Untouched until then.
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
| 2026-09-16 | **Frontend built, `776b52e5`.** Contract checked against `routers/road_closures.py` at `ea6151b9`. Access labels and colours were three hand-copied ternaries, so they are now one module, `frontend/src/utils/closureAccess.js`, with `ACCESS_UNKNOWN` beside the three levels (`:43`, map line `#94a3b8` slate-400; the 🚧 icon was amber for every level already and is unchanged). **N/A** shows for null, absent or unrecognised `emergencyAccess` — sidebar pill `RightSidebar.jsx:310–311`, street colour `:285`, marker popup `RoadClosureMarker.jsx:76–77`, line `:32`; before this the same unknown drew NO_ACCESS red on the map and LANE CLOSURE yellow in the sidebar. **`⚠️ NO ID IN FEED RECORD`** under the street line (`RightSidebar.jsx:301–303`, popup `RoadClosureMarker.jsx:83–84`), stacked with the #90 location line; `rowId` never displayed. **Keys and selection** on `closureKey` (`rowId`, or `id` against an older api) at `RightSidebar.jsx:267` and `RoadClosuresLayer.jsx:23`, `sameClosure` at `:25` false when either side has no key, so two unidentified closures never both highlight; no other closure keyed on `id` anywhere in the frontend. **Filters:** map (`useRoadClosures.js:80`) and list (`RightSidebar.jsx:96`) both through `passesAccessFilter` (`closureAccess.js:66`); N/A passes unconditionally, since no toggle names it and switching off a known level should not hide an unknown one; timeframe toggles still apply. Verified: `lint:crash` and full eslint clean on every touched file (three pre-existing errors in `MapBoard.jsx` on untouched lines, same count with the change stashed), `build` clean, `npm run test:node` 55/55 with 6 new `closureAccess` tests. Not seen rendered; no such closure exists on the kiosk and none was created |
