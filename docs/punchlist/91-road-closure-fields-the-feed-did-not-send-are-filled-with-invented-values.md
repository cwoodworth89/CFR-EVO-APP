# Punch list #91 — Road closure fields the feed did not send are filled with invented values, including the access level

| | |
|:--|:--|
| **Status** | BACKEND BUILT `ea6151b9` with a migration that **must run before the api rebuild**; frontend half with `frontend-kiosk-architect`; **not deployed, migration not yet run on Postgres.** Text placeholders unruled and untouched; three follow-on rulings below |
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

## Operator rulings

Three follow-ons raised by GIS at `ea6151b9`, **not built, the operator's to say:**

- **(a) Is a content hash "inventing an id"?** `feed_record_key` is derived only from the
  record, never shown, and `id` stays null; GIS holds that it is not. If the operator
  disagrees, the alternative is to insert id-less records fresh each sync and deactivate the
  previous batch's — nothing derived, row ids churn hourly.
- **(b) A present DriveBC severity other than MAJOR still falls through to CAUTION** —
  MODERATE, for one. Whether Open511 enumerates MINOR/MODERATE/MAJOR/UNKNOWN is GIS's
  recollection, **unverified** (§7.3); no project standard covers it. Recorded as a gap in
  [`../standards/README.md`](../standards/README.md).
- **(c) Municipal 511 starts every record at CAUTION** and only raises it from
  `RoadClosureType` bits or "road closed" text, so a municipal record with no type is also
  CAUTION by default — the same defect in the other feed.

1. **Unknown severity — ruled 2026-09-16: "keep the box but add N/A."** A fourth visible
   state. Severity and the derived access level propagate as `null`; the kiosk keeps the access
   box and shows **N/A** in it. Never CAUTION, never NO_ACCESS.
2. **Text placeholders — not yet ruled.** Blank (`--`), or omit the card field? Untouched until
   the operator says.
3. **The `db_{n}` id — ruled 2026-09-16: "keep positional ID as null, but state it."** No id is
   invented from the record's position. The record is kept and the card says the feed sent no
   id. How a record with no id survives the upsert without being invented or duplicated is
   engineering, GIS's to solve and state.

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
