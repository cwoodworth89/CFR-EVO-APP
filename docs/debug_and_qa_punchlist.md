# CFR EVO: Final Phase Debug & QA Punch List

This document tracks identified bugs, routing anomalies, edge cases, and feature refinements to investigate and resolve during the final bug squashing and testing phase.

> [!NOTE]
> **Status key (reconciled 2026-08-21, commit `0db0b75`)**: ✅ = verified against the
> current working tree *and*, where the item touches data, the running kiosk database.
> ⚠️ = confirmed still open. Each status line states what was checked, so a later reader
> can tell **reported** from **confirmed** (CLAUDE.md §6.6).
>
> Items closed at the 2026-08-21 reconciliation: **#7** (obsolete — the cascade step was
> removed), **#11** (fixed and re-synced). Item **#2** was reopened, then closed the same
> day once both surviving coordinate fallbacks were removed.
>
> Closed 2026-08-22 by the intersection rebuild: **#8** (test suite), **#9** and **#13**
> (`public.intersections` derived from road geometry), plus new items **#15** (fuzzy
> substitution) and **#16** (`<street> and <street>` CAD artifact) found and fixed in the
> same pass.
>
> Still open: **#1**, **#10**, **#12**, **#14**, **#17**, **#19**, **#20**, **#21**,
> **#22**.
>
> **Found from live operation 2026-08-22**, none of them reachable from the test corpus —
> all three came from one operator screenshot of a real dispatch: **#24** (an invented
> hydrant shown on every call, closed), **#25** (a corrected re-broadcast queueing itself
> as a second call, closed on the kiosk side with a latent backend ordering defect
> recorded), **#26** (the pipeline's INFO logging is discarded, closed — and the reason #25
> could not be diagnosed from logs).
>
> Closed 2026-08-22 during decomposition: **#22** (closure timeframe filters matched nothing).

---

## 🧭 Routing Engine & Pathfinding Anomalies

### 1. Erratic Routing Loops & Intra-Municipal Path Preference
> **Status**: ⚠️ **Still open — not re-examined at the 2026-08-21 reconciliation.** Turn-by-turn
> routing functions, but the OSRM Lua profile arterial-vs-alleyway weighting has not been
> re-tuned. No new evidence was gathered this pass; the description below is as originally
> reported and the loops have **not** been re-observed since routing moved to stock OSRM.
> Re-confirm the behaviour still reproduces before spending time on profile tuning.
* **Incident / Path**: `1300 Pinetree Way` (Town Centre Fire Hall / Hall 1) $\rightarrow$ `428 Nelson St`.
* **Reported Behavior**:
  * The calculated apparatus route exhibits erratic pathing with unnatural loops, parking lot / back-alley cut-throughs, and unnecessary detours (see visual trace below).
  * The route leaves optimal arterial corridors and may exit municipal bounds unnecessarily.
* **Root Cause Investigation Needed**:
  * Inspect OSRM Lua emergency profile weighting (`osrm/profiles/emergency.lua` or local OSRM graph).
  * Check OSM road classification weights (e.g. `service`, `parking_aisle`, `residential` vs `primary`/`secondary`/`tertiary`).
  * Check snap distance / nearest-road snapping logic for origins and destinations near complex driveways or hall aprons.
  * Evaluate weighting penalty for crossing municipal boundaries: prioritize staying inside Coquitlam city limits on intra-city calls where possible.
* **Visual Reference Trace**:
  ```
  Origin: 1300 Pinetree Way (Hall 1 Apron)
  Target: 428 Nelson St
  Issue: Bizarre loops, erratic turns, sub-optimal road class snapping
  ```

---

### 2. Intersection Geocoding & Hardcoded Port Moody Fallback (`DISP-2026-F1F345`)
> **Status**: ✅ **Closed 2026-08-21 (second pass).** Reopened during the reconciliation,
> then fixed — see the resolution note at the end of this item. **Two** fallbacks had
> survived the sweep, not one. Original reopening follows.
>
> ⚠️ **REOPENED 2026-08-21.** Mostly fixed, but **one fallback survived the
> sweep** — and it is on the live new-dispatch path. `frontend/src/components/MapBoard.jsx:471`:
>
> ```js
> const target = newCall.target || (newCall.address
>   ? { address: newCall.address, lat: newCall.lat || COQUITLAM_CENTER[0],
>                                 lng: newCall.lng || COQUITLAM_CENTER[1] } : null);
> ```
>
> This is the exact defect this item describes, one commit short of closed: a null
> coordinate silently becomes `49.2838, -122.7907` (City Centre), inside the §5 bounds
> check, so tiles render and routing proceeds and nothing warns. It is the same shape as
> the bug that routed **every live MQTT call** to Town Centre.
>
> The claim "all hardcoded coordinate fallbacks have now been removed frontend-wide" was
> **reported, not verified**, and is wrong.
>
> ~~The other four `COQUITLAM_CENTER` uses in `MapBoard.jsx` were checked and are
> legitimate — initial map view (`:176`, `:836`), a distance comparison (`:380–381`), and
> an idle "reset view" `flyTo` (`:998`). **Only line 471 needs to change.**~~
>
> **That was wrong, and it is worth recording why.** `:176` is *not* an initial map view —
> it is inside `RoadClosureMarker`, and it was a **second fabrication of the same class**:
>
> ```js
> const markerPos = Array.isArray(closure.coordinates) && closure.coordinates.length >= 2
>   ? [parseFloat(closure.coordinates[0]), parseFloat(closure.coordinates[1])]
>   : COQUITLAM_CENTER;      // <- a road closure with no coordinate drawn at City Centre
> ```
>
> A closure whose point coordinate is missing or malformed was rendered as a closure
> **across City Centre that the municipal feed never reported** — an invented road closure
> on the tactical map, which could push crews off a route that is actually open. It was
> mis-assessed on the first pass because the enclosing function was identified from a grep
> line number rather than by reading the surrounding code.
>
> The remaining three uses were re-read in full and *are* legitimate: initial map centre
> (`:836`), an off-default-view distance comparison (`:380–381`), and the idle "reset
> view" button (`:998`). None substitutes for real data.
>
> ---
>
> **Resolution (2026-08-21).** Both fabrications removed in `MapBoard.jsx`:
>
> 1. **Dispatch target** — the `|| COQUITLAM_CENTER[...]` defaults are gone; `lat`/`lng`
>    now propagate as `null`, so the §5 Tier 1 card fires and routing stays suppressed.
>    Downstream was already safe: `updateTargetAddress` branches only on `address` and
>    `rings`, and the `flyTo` is guarded by `if (map && target.lat && target.lng)`.
> 2. **Road closure marker** — falls back only to the first vertex of the closure's *own*
>    polyline (real data from the same record), and renders **no marker** when there is
>    neither a point nor a polyline. The polyline alone still shows the closure.
>
> Both carry provenance comments citing §6.1. `npm run lint:crash` and `npm run build`
> both pass.
>
> **Note for #6**: the backend already drops closures with unparseable geometry rather
> than pinning them, so the marker path should rarely fire — but the frontend no longer
> depends on that being true.
* **Incident**: `CHRISTMAS WAY AND WESTWOOD ST` (Grid 68, Motor Vehicle Incident).
* **Observed Problem**:
  * The call routed from Hall 1 all the way out into **Port Moody** (`49.27305, -122.88452`).
  * The Cadastral Block & Satellite PIPs were blank (outside Coquitlam municipal tile boundary).
  * Street View was unable to resolve facade.
* **Root Cause Identified**:
  * The dispatch target had `target.lat: null, target.lng: null` because intersection geocoding did not resolve `Christmas Way and Westwood St`.
  * When `lat`/`lng` is null, `App.jsx` (`handleSimulateCall`) and `SimulationControl.jsx` fell back to hardcoded coordinates `49.27305, -122.88452` (Port Moody).
  * OSRM faithfully routed to the Port Moody coordinates, and tile servers have no data outside Coquitlam.
* **Action Required**:
  1. Add authoritative Coquitlam arterial intersection coordinates for `Christmas Way & Westwood St` (`49.2783, -122.7935`) and audit intersection dictionary.
  2. Fix `App.jsx` and `SimulationControl.jsx` fallback coordinates to use verified City Center coordinates (`49.2838, -122.7907`), never out-of-city coordinates.

---

### 3. Missing `responding_units` in Replayed Dispatches
> **Status**: ✅ **Confirmed fixed (re-verified 2026-08-21).** A tree-wide `SQ1` grep now
> returns exactly one hit — `EVORoutingEngine.js:27`, a descriptive subtitle string in the
> staged `APPARATUS_TIERS` seed data (§6.4), not a fallback. Originally verified in `App.jsx`; `verified_units` → `responding_units` → `[]` resolution is passed through explicitly. The `['SQ1','E1','L1']` invented-apparatus fallbacks have additionally been removed from `EVORoutingEngine.js`, `RouteOverviewPanel.jsx`, and `MapBoard.jsx`.
* **Observed Problem**: Simulated calls in Kiosk view display `SQ1, E1, L1` regardless of what units were dispatched (e.g. `DISP-2026-F1F345` had `E1, E2, R2, C8`).
* **Root Cause**: `handleSimulateCall` in `frontend/src/App.jsx` omitted `responding_units: call.verified_units || call.responding_units || []` when building `mockCall`, causing `EVORoutingEngine.js` to trigger its `['SQ1', 'E1', 'L1']` fallback.
* **Fix**: Pass `responding_units` explicitly in `App.jsx`.

---

## 🎨 Kiosk & Review Panel UI/UX Refinements

### 4. Remove Satellite View from Call Review Panel
> **Status**: ✅ **Fixed, but the record was wrong.** The defect is gone: `SatelliteMiniMap`
> is no longer in `VerificationSidebar.jsx`, and the Burlington & Pinetree pin is
> impossible — the component early-returns `null` on falsy `lat`/`lng`
> (`hud/SatelliteMiniMap.jsx:7`) and its one caller guards as well, rendering
> "Coordinates missing" instead (`hud/ActiveDispatchPanel.jsx:120–126`).
>
> **The claim "deleted entirely" is false.** The file exists at
> `frontend/src/components/hud/SatelliteMiniMap.jsx` and is used by
> `ActiveDispatchPanel.jsx` — a different, intended surface. It was removed from the
> review panel, not from the codebase.
>
> Cosmetic follow-up, not a data defect: that panel is labelled
> `🛰️ GOOGLE SATELLITE VIEW`, but the layer is the local offline MBTiles service
> (`TILE_BASE_URL/services/satellite/...`). The label names a cloud provider this
> architecture deliberately does not use.

* **Observed Problem**: `VerificationSidebar.jsx` includes a `<SatelliteMiniMap />` component that was never intended in the plan. When target coordinates are missing, it persistently defaults to pinning at Burlington Ave & Pinetree Way (`49.2838, -122.7932`).
* **Fix**: Remove `SatelliteMiniMap` from `VerificationSidebar.jsx`.

### 5. Audio Player Simplification in Call Review Panel
> **Status**: ✅ **Confirmed fixed (verified 2026-08-21).** A tree-wide grep for
> `AudioWaveformPlayer` returns no hits; the file and every reference are gone. Reverted to
> native audio controls (removed alongside commit `d5fbdcc`).

* **Observed Problem**: The custom canvas-based `AudioWaveformPlayer` is overly complex; user prefers a simple, clean, dependable native audio player.
* **Fix**: Revert to the clean, streamlined audio player in `VerificationSidebar.jsx`.

---

## 🛣️ Road Closure Ingestion

### 6. Verify first live ingest through the new PostGIS path
> **Status**: ✅ **Closed 2026-08-22 — verified, every pass criterion met.**
>
> | Pass criterion | Result |
> |:--|:--|
> | `last_sync` age < 24h | 12h ✅ |
> | Active closures, same magnitude as the previous 103 | **94** ✅ |
> | `with_geometry` equals `closures` | **94 / 94** ✅ |
> | `hall_id` populated 1–4 on most rows | 93 of 94 ✅ |
>
> Distribution: hall 1 → 13, hall 2 → 22, hall 3 → 40, hall 4 → 18, null → 1. The single
> null is a boundary-straddling closure whose centroid falls outside every zone, which is
> exactly the case this item's "watch for" note anticipated — `is_within_city` admits it
> via `ST_Intersects` while centroid containment cannot place it.
>
> The 2026-08-21 snapshot that read as a total failure (0 rows with `geom`, 103 with a null
> `hall_id`) was pre-rewrite residue, as recorded below. A sync has since run against the
> new code and populates both columns.
>
> Original entry follows.
>
> ⚠️ **Open — still unverified (re-checked 2026-08-21).** Correct as written.
> The rewrite **is** live in the running container — `docker exec cfr_api grep -c
> resolve_zones_and_hall /app/backend/api/road_closure_service.py` returns 4 — but no
> ingest cycle has run against it yet.
>
> **Read the current table with care — it is pre-rewrite residue, not a failed new run.**
> Today's snapshot looks like a total failure of the new path and is not:
>
> | Measure | Now | Pass criterion |
> |:--|--:|:--|
> | `last_sync` | 2026-08-21 01:39 PDT (20 h) | < 24 h ✅ |
> | active closures | 103 | ~103 ✅ |
> | rows with `geom` | **0** | should equal 103 ❌ |
> | active rows with `hall_id IS NULL` | **103** | should be mostly 1–4 ❌ |
>
> The two failures are explained by timing, not by a bug: the `cfr_api` image was rebuilt
> at **21:21 PDT**, and the last sync ran at **01:39 PDT** — twenty hours *before* the new
> code existed on the box. Every current row was written by the old service, which had no
> `geom`/`hall_id` logic. The columns themselves exist and the new code writes them
> (`road_closure_service.py:123`, `:175`, `:355–361`).
>
> **The first sync after 2026-08-21 21:21 PDT is the real test.** Until then these two
> columns carry no information about the rewrite. Re-run the queries below afterwards.

* **What changed**: `road_closure_service.py` now resolves zones and municipal
  containment via `ST_Intersects` / `ST_Contains` against `public.city_boundary` and
  `public.zones`, instead of ray-casting over `zones.json`. Closures with unparseable
  geometry are now **dropped** rather than pinned to a placeholder coordinate.
* **How to verify** — check the ingest actually ran and succeeded:
  ```bash
  # 1. Did a sync run, and when?
  ssh tcfire@100.95.146.94 "docker logs cfr_api 2>&1 | grep -i 'differentials-synced' | tail -5"

  # 2. Freshness: updated_at should be within the last 24h (check_and_sync_if_stale
  #    uses max_age_seconds=86400)
  ssh tcfire@100.95.146.94 "docker exec cfr_postgres sh -c 'psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"
    SELECT max(updated_at) AS last_sync,
           now() - max(updated_at) AS age,
           count(*) FILTER (WHERE active) AS active_closures
    FROM public.road_closures;\"'"

  # 3. Did the new columns populate? hall_id and geom should be non-null on
  #    freshly-synced active rows.
  ssh tcfire@100.95.146.94 "docker exec cfr_postgres sh -c 'psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"
    SELECT hall_id, count(*) AS closures,
           count(geom) AS with_geometry
    FROM public.road_closures WHERE active
    GROUP BY hall_id ORDER BY hall_id NULLS LAST;\"'"
  ```
* **Pass criteria**:
  - `last_sync` age < 24h, and a `differentials-synced` line appears in the API log.
  - Active closure count is non-zero and in the same order of magnitude as the previous
    103 — a large drop would suggest the new containment check is over-filtering.
  - `hall_id` is populated (1–4) on most rows; a large `NULL` group means centroid
    containment is failing and needs review.
  - `with_geometry` equals `closures` — a shortfall means the `geom` mirror UPDATE is
    not firing.
* **Watch for**: closures legitimately spanning the city edge. `is_within_city` uses
  `ST_Intersects` (touching counts), not `ST_Contains`, so a boundary-straddling closure
  should still be admitted. If those disappear, the check is too strict.

---

## 📍 Custom Places Data Quality

### 7. `custom_places.json` coordinates are hand-entered and some are badly wrong
> **Status**: ✅ **Closed 2026-08-21 — obsolete, resolved by removal.** The problem was not
> fixed by correcting the coordinates; **the entire cascade step was deleted** (commit
> `2ef12b7`), which moots the item. Verified on all four surfaces:
>
> * `backend/data/vocabulary/custom_places.json` — deleted.
> * `public.custom_places` — dropped (`to_regclass` returns `NULL` on the kiosk).
> * The geocoder cascade no longer has a custom-places step; `geocoder.py` documents the
>   removal in place, citing the ≤1.8 km error and the fact that Locution always speaks
>   the civic address first, so the step was effectively unreachable anyway.
> * The competing hardcoded school list in `MapLayers.jsx` is gone — the "two
>   hand-maintained lists disagreeing" defect no longer has two lists.
>
> No references to `custom_places` remain anywhere in the tree.
>
> **What this does not resolve**: the underlying need. A dispatch that names a place rather
> than an address now returns `None` and surfaces the §5 Tier 1 card instead of resolving
> ~1.8 km off. That is the correct failure under §6.1 — visibly unknown beats confidently
> wrong — but it is a *capability gap*, not a capability. If place-name dispatches turn out
> to matter operationally, the fix is authoritative records in `public.parcels`, per §6.2 —
> never a re-imported hand-keyed list.
>
> The original analysis is kept below as the rationale for the removal.

**Original finding (2026-08-21, measured against `public.parcels`):**

* **What it is**: `backend/data/vocabulary/custom_places.json` holds 152 named places
  (parks, schools, civic buildings) keyed by lowercase name. It seeds
  `public.custom_places`, which is **Step 7 of the 8-step geocoder cascade** — the
  fallback used when a dispatch names a place rather than an address.
* **The problem**: coordinates appear hand-entered and are not validated against any
  authoritative source. Three secondary schools, cross-checked against `public.parcels`
  (municipal `Addresses.shp`):

  | Place | `custom_places.json` error | `MapLayers.jsx` error |
  |:--|--:|--:|
  | Centennial Secondary | **1,774 m** | 92 m |
  | Gleneagle Secondary | 537 m | 14 m |
  | Pinetree Secondary | 309 m | 28 m |

* **Operational impact**: a dispatch naming "Centennial Secondary" that falls through to
  Step 7 resolves ~1.8 km from the actual school. Apparatus routes to the wrong place,
  and nothing flags it — the coordinates are inside Coquitlam, so the §5 bounds check
  passes and tiles render normally.
* **Scope of the sample**: 140 of 152 entries carry a civic address in parentheses.
  Only **14** matched a parcel on exact address string (formats differ), so the
  distribution below is indicative, not a full audit: 8 within 50 m, 1 at 50–200 m,
  2 at 200–500 m, 3 over 500 m.
* **Second source of truth**: `MapLayers.jsx` carries its own hardcoded school list with
  *different* coordinates for the same schools. It is consistently closer to the parcel
  data (14–92 m). Two hand-maintained lists disagreeing is itself the defect.

* **Do NOT blind-snap to parcels.** For a school or civic building the parcel centroid is
  right. For a park, a lake, or a trailhead the useful dispatch point may deliberately be
  an entrance or muster point rather than the parcel centroid — some hand-placed values
  may be intentional. This needs a per-category decision:
  - **Buildings** (schools, hospitals, civic): resolve through the geocoder cascade
    against `public.parcels` and replace.
  - **Open spaces** (parks, lakes, trails): confirm with operations whether the stored
    point is a deliberate access point; if so, record that in `public.custom_places` as
    provenance rather than leaving it looking like an unverified guess.
  - Reconcile `MapLayers.jsx`'s school list against `public.custom_places` so there is
    one source.
* **Suggested check** — run the 140 addresses through the geocoder rather than exact
  string match, which will resolve far more than 14 and give a real error distribution.

---

## 🧪 Test Suite Debt

### 8. The 11 test failures are NOT environmental — correcting the record
> **Status**: ✅ **Closed 2026-08-21.** All 11 failures fixed and verified on the kiosk:
> **82 passed, 1 xfailed, 0 failed** (from 11 failed / 72 passed). See the resolution at
> the end of this item. The diagnosis below was re-confirmed before any fix was made.
>
> ⚠️ **Open — every stated cause re-confirmed 2026-08-21 against the kiosk
> database and the working tree.** Run on the kiosk with PostGIS reachable, `librosa`
> present and `XDG_RUNTIME_DIR` set: **identical 11 failures, 72 passed.** Earlier commit
> messages this session described all 11 as "pre-existing and environmental". The
> pre-existing half was verified by stashing; **the environmental half was inferred and
> is wrong.**
>
> Confirmation of each cause below, so this can be picked up without re-deriving it:
>
> | Claim | Check | Result |
> |:--|:--|:--|
> | `public.landmarks` is gone | `to_regclass('public.landmarks')` | `NULL` — dropped ✅ |
> | a test still queries it | `test_postgis_migration.py:52–54` | still `SELECT COUNT(*) FROM public.landmarks` ✅ |
> | intersection bound is stale | `SELECT count(*) FROM public.intersections` | **6,499** vs asserted 400–2,500 ✅ |
> | shapefile constants removed | `test_fault_injection.py:65` | still imports `ADDRESS_SHAPEFILE_PATH` / `ZONES_SHAPEFILE_PATH` ✅ |
>
> `test_database_integration.py:29–30` defines those two shapefile paths as **module-level
> literals** rather than importing them, so it fails differently from `test_fault_injection.py`
> — it will not raise `ImportError`, it will look for files that the PostGIS migration
> removed. Worth fixing in the same pass.
>
> Note the ordering trap on the cascade: the six `InFailedSqlTransaction` failures are
> collateral from `test_landmarks_count` aborting the shared connection's transaction. Fix
> that one test first, then re-run before judging the rest — the remaining count will drop
> before any of them are touched.
>
> ---
>
> **Resolution (2026-08-21) — 11 failed / 72 passed → 82 passed, 1 xfailed, 0 failed.**
>
> The root cause of the cascade was **not** the stale test; it was the fixture. `conn` was
> `scope='module'`, so all 16 tests shared one connection and therefore one transaction —
> any single failing statement aborted it and every later test died with
> `InFailedSqlTransaction`. Making it function-scoped means one bad test can no longer
> manufacture six more. That is the structural fix; fixing only `test_landmarks_count`
> would have cleared the symptom and left the amplifier in place.
>
> Per test:
>
> | Test | Change |
> |:--|:--|
> | `test_landmarks_count` | Replaced by `test_dropped_tables_stay_dropped`, asserting `landmarks` **and** `custom_places` are absent, so a reintroduction is caught |
> | 6 × `InFailedSqlTransaction` | Not touched — they were never broken. Cleared by the fixture scope |
> | `test_intersections_count` | Bound relaxed to a populated-table sanity floor, **not** re-pinned to 6,499 (see below) |
> | `test_no_false_intersections` | `xfail(strict=False)` — the test is right and the *data* is wrong |
> | `test_04_unknown_address_fallback_safety` | Rebuilt on the database-backed validator; the shapefile constants are gone |
> | `test_build_dispatch_payload_option2` | `MockValidator.local_geocode` signature tracks the real one (`target_map_grid`, `cross_street_*`) |
>
> **Two judgement calls worth stating plainly, because both could have been "fixed" the
> dishonest way:**
>
> 1. **`test_intersections_count` was not re-pinned to 6,499.** Updating the bound to
>    match whatever the table currently holds would encode unaudited data as the expected
>    answer — and #13 records that this table has at least one confirmed false row and
>    apparent duplicates. There is no source for a correct count, so asserting a precise
>    one would be an unsourced constant (§6.3). It now asserts only that the import did not
>    fail or empty, with a comment saying to restore a real bound after the #13 audit.
> 2. **`test_no_false_intersections` was marked `xfail`, not weakened.** It is a *true
>    positive* — it detects the real defect in item #9. Relaxing the assertion would have
>    turned the suite green by deleting the alarm. `xfail` reports the true state, and
>    `strict=False` means it XPASSes the moment the data is fixed, so the fix will not go
>    unnoticed. **Item #9 remains open; this changed nothing about the underlying data.**
>
> One further finding: the run also needs `DATABASE_URL`, which is **not** in
> `backend/.env`. Without it `test_04` *skips* rather than passes, which reads as green in
> the summary line. Take it from the container (see the environment notes in
> `review_status_handoff.md`). With it set: 82 passed, 1 xfailed, **0 skipped**.

Actual causes:

* **1 stale test causing ~6 cascading failures.** `test_landmarks_count` queries
  `public.landmarks`, renamed to `custom_places` in Phase D and dropped entirely on
  2026-08-21. The `UndefinedTable` error aborts the transaction, so every later test on
  that connection fails with `InFailedSqlTransaction` — `test_vocabulary_units`,
  `test_vocabulary_call_types`, `test_zone_spatial_query`,
  `test_city_boundary_contains_coquitlam`, `test_city_boundary_excludes_burnaby`,
  `test_parcels_have_geometry`. Fixing the one stale test likely clears all of them.
* **`test_intersections_count`**: asserts 400–2500, actual is **6,499**. Either the
  bound is stale or the intersection set grew. `docs/development_freeze_summary.md`
  documents 3,947, which matches neither.
* **`test_fault_injection::test_04_unknown_address_fallback_safety`**: imports
  `ADDRESS_SHAPEFILE_PATH` / `ZONES_SHAPEFILE_PATH` from `cfr_dispatch.config`. Removed
  in the Phase A PostGIS migration. Stale test, not a product bug.
* **`test_pipeline_unit::test_build_dispatch_payload_option2`**: its `MockValidator`
  lacks the `target_map_grid` keyword the real `local_geocode` gained in the geocoder 2.0
  work. Stale mock signature.

### 9. False intersection: DAVID AVE & PANORAMA DR
> **Status**: ✅ **Closed 2026-08-22 — resolved structurally.** `public.intersections` is
> now DERIVED from `public.roads` centreline geometry
> ([`backend/scripts/derive_intersections.py`](../backend/scripts/derive_intersections.py)),
> so a pair of streets that never meet cannot be stored. 6,499 rows → **1,784**; the
> `DAVID AVE & PANORAMA DR` rows are gone, and
> `test_every_intersection_is_geometrically_real` now asserts the invariant over the whole
> table rather than that one pair.
>
> **The scope question is answered, and it was not a handful of bad rows.** The old table
> came from `extract_all_intersections_from_gis.py`, which never read a road centreline:
> it paired PARCEL address points within 40 m of each other on differently-named streets,
> took the midpoint of the shortest line between the two parcels, and clustered those with
> a 45 m epsilon. Its working definition of "intersection" was *two houses on different
> streets happen to be within 40 m*. Measured against road geometry:
>
> | Measure | Count |
> |:--|--:|
> | Rows whose two streets never meet | **3,086** (1,777 of those pairs >60 m apart) |
> | Rows where the streets do meet, median coordinate error | **63 m** (only 129 of 2,863 within 10 m) |
> | Stored points not within 20 m of *any* road | **3,413** |
> | Rows on a street literally named `NAN` | **113** |
>
> Verified against the 24 real intersection dispatches: **kept 20, gained 1, lost 0**, and
> against the five operator-verified coordinates the error fell from 879 m → 5 m,
> 471 m → 1 m, 107 m → 15 m, 41 m → 7 m, and 8 m → 9 m.
>
> The original finding is kept below.

**Original finding (2026-08-21):** the two rows were
> still present on the kiosk: `SELECT count(*) FROM public.intersections WHERE
> intersection_key = 'DAVID AVE & PANORAMA DR'` returns **2**, against a table of **6,499**.

`test_no_false_intersections` asserts these parallel streets never meet. `public.intersections`
holds **2 rows** for them, and PostGIS confirms the road geometries do **not** intersect:

```sql
SELECT EXISTS (SELECT 1 FROM public.roads a, public.roads b
  WHERE a.fullname ILIKE 'DAVID AVE%' AND b.fullname ILIKE 'PANORAMA DR%'
    AND ST_Intersects(a.geom, b.geom));   -- returns false
```

A dispatch to that intersection geocodes to a fabricated point with no warning.

**Scope is not established.** A bulk check comparing every stored intersection against
road geometry was attempted and is invalid: `intersections.street_a/street_b` use
abbreviated suffixes (`ABBEY LN`) while `roads.fullname` uses full words
(`Waterford Place`), so only 317 of 6,499 join at all. A real audit must normalise
suffixes first — reuse `normalize_street_suffix` from `parser/location.py` rather than
joining raw strings.

Also observed: duplicate rows (`ABBEY LN & GLENBROOK ST` twice). May be legitimate
multi-candidate entries distinguished by `candidate_index`, or may be duplicates —
not yet determined.

### 10. Three test modules have never run in review
> **Status**: ⚠️ **Open — unchanged 2026-08-21.** No attempt was made to run them this pass;
> the missing dependencies have not been installed.

`test_database_integration`, `test_listener` and `test_keyword_spotter` were excluded all
session with `--ignore` because `librosa` (local) and `pvporcupine` (kiosk) are missing.
"72 passed" therefore does not represent the full suite. `pvporcupine` is a Picovoice
wake-word dependency that is not installed on the kiosk at all — worth deciding whether
that feature is live before keeping a test for it.

---

## 🚰 Hydrant Data

### 11. Private hydrants defaulted to NFPA 291 class AA — fabricated flow rating
> **Status**: ✅ **Closed 2026-08-21 — fixed, re-synced and verified end to end**
> (commits `7b684eb`, `4122628`). All three required steps were completed and each was
> checked independently:
>
> | Required step | Verification | Result |
> |:--|:--|:--|
> | 1. Remove the `or "AA"` default | `sync_hydrants.py:77` | now `"flowClass": attribs.get("flow_class")` ✅ |
> | 2. Re-sync — a code fix alone changes nothing | `public.hydrants` on the kiosk | **853 of 3,390** rows carry `flow_class IS NULL` ✅ |
> | 3. Explicit unknown rendering | hydrant layer | renders `⚠️ UNRATED`, distinct from all four NFPA colours ✅ |
>
> Step 2 is the one that mattered and it is the one that is easy to skip: the fabricated
> values lived in cached data, not in code. **853 unrated hydrants** is the direct
> counterpart of the 462 + 68 + 9 + 8 = 547 non-OPERATING AA rows plus the OPERATING
> unrated remainder — they now read as unknown instead of as the best available supply.
>
> The stale `frontend/public/data/hydrants.json` cache was deleted rather than
> regenerated; the kiosk now reads `/api/hydrants` from `public.hydrants`, so there is one
> source and no cache to drift.
>
> The `sync_hydrants.py:77` fix carries a provenance comment (`:72`) explaining why the
> default was dangerous, per §6.3.

**Historical record of the defect (as originally found):**

`backend/scripts/sync_hydrants.py:80` substituted the highest flow class when the
municipal source had none:

```python
"flowClass": attribs.get("flow_class") or "AA",
```

`backend/scripts/update_gis_data.py:207` does the same lookup honestly:

```python
"flowClass": attribs.get("flow_class") or "",
```

The two scripts disagree, and the fabricating one produced the cached data.

Distribution in the since-deleted `frontend/public/data/hydrants.json` (3,387 hydrants),
which is what made the default visible:

| status | AA | A | B | C |
|:--|--:|--:|--:|--:|
| OPERATING | 2322 | 333 | 123 | 60 |
| **PRIVATE** | **462** | 2 | 0 | 0 |
| OPERATING NON-TCA | 68 | 0 | 0 | 0 |
| NOT READY | 9 | 0 | 0 | 0 |
| METRO | 8 | 0 | 0 | 0 |

OPERATING shows a real spread (≈82% AA). PRIVATE is **99.6% AA**, and NON-TCA, NOT READY
and METRO are **100% AA**. That pattern is a default, not a measurement — consistent with
the operator's report that private hydrants have no recorded flow value.

**The direction of the error matters.** Under NFPA 291, AA is the *highest* class
(light blue, 1500+ GPM). Defaulting unknown hydrants to AA tells crews an unrated
hydrant is the best available supply. For a working fire that is the most dangerous
possible substitution — the opposite of failing safe, and a direct CLAUDE.md §6.1
violation.

**Fix**: `flow_class` should propagate as null and render as an explicit unknown
(grey/unclassified marker, "flow not rated"), never as a colour-coded class. Requires:
1. Change the `or "AA"` default in `sync_hydrants.py`.
2. Re-sync hydrant data — the cached JSON already carries the fabricated values, so a
   code fix alone changes nothing.
3. Give the kiosk hydrant layer an explicit unknown rendering, distinct from all four
   NFPA colours.

---

## 🧭 Geocoder Honesty Gaps

### 12. Street centroid reports the requested address as though exact
> **Status**: ⚠️ **Open — re-confirmed in the working tree 2026-08-21.** Both overwrites are
> still present: `geocoder.py:170–174` (step 5, street centroid) and `:177–181` (step 6,
> road centroid). Unchanged since the item was written.

`geocoder.py` step 5 overwrites the result address with the address that was asked for:

```python
result = self.address.resolve_street_centroid(parsed.street, parsed.street_type)
if result:
    result['address'] = f"{parsed.house} {parsed.raw}".strip().title() if parsed.house else result['address']
```

So a whole-street average is displayed as "3080 Gordon Ave" — indistinguishable on
screen from an exact parcel match apart from the confidence score. Step 6 (road centroid)
does the same.

The step 4b nearest-civic resolver added 2026-08-21 deliberately does **not** do this: it
reports the parcel actually used, keeps the dispatched string in `requested_address`, and
explains the substitution in `resolution_note`. Steps 5 and 6 should follow that pattern.

### 13. `public.intersections` needs the same data-integrity pass
> **Status**: ✅ **Closed 2026-08-22.** This item proposed deriving intersections from
> `public.roads` via `ST_Intersects` "so false entries become structurally impossible".
> That is what was done — see #9 for the measured before/after.
>
> Three further defects were found and fixed in the same pass:
>
> * **Suffix vocabulary was hardcoded in two places that disagreed.** The extractor wrote
>   `SUNSET SQ` while the geocoder normalized a dispatch to `SUNSET SQUARE`, so those
>   intersections were unreachable; `normalization.py` was also missing 10 suffix types
>   present in `public.roads.roadtype`, covering 26 real streets. Suffixes now live in
>   `public.vocabulary` (category `street_suffix`) and are read by both, with a migration
>   guard that fails loudly if the municipal data gains a suffix nothing maps.
> * **Five inconsistent zone-containment queries.** `ST_Contains` tests the strict
>   interior, and zone polygons are bounded by roads, so junctions sit exactly on a
>   boundary and were rejected: 155 of 1,784 intersections got no map grid for that reason
>   alone. There is now one `public.zone_for_point()`, and `intersections.zone_id` — a
>   denormalized copy of it — was dropped.
> * **Fuzzy intersection matching substituted silently.** See #15.

The nearest-civic work fixed the *address* side of unresolvable locations. The
intersection side has had no equivalent review:

* At least one confirmed false intersection (`DAVID AVE & PANORAMA DR`, item #9), where
  PostGIS confirms the road geometries never meet.
* 6,499 rows against 3,947 documented in `docs/development_freeze_summary.md`.
* Apparent duplicates (`ABBEY LN & GLENBROOK ST` twice) that may or may not be legitimate
  `candidate_index` entries.
* No validation that a stored intersection point actually lies on both named roads.

A proper audit must normalise street suffixes first — `intersections.street_a` uses
abbreviations (`ABBEY LN`) while `roads.fullname` uses full words (`Waterford Place`),
so a raw string join matches only 317 of 6,499. Reuse `normalize_street_suffix` from
`parser/location.py`.

Worth considering whether intersections should be *derived* from `public.roads` geometry
via `ST_Intersects` rather than imported as a separate list — that would make false
intersections structurally impossible.

---

## 📢 PA Page Leakage

### 14. PA announcements are being captured as dispatches
> **Status**: ⚠️ **Open — mechanism identified; blocked on corpus.** Re-checked 2026-08-21:
> **0 of 408** dispatches carry the `[PA]` tag
> (`count(*) FILTER (WHERE review_notes LIKE '%[PA]%')`).
>
> The negative-control suite described below cannot start until the operator has tagged
> some captures, so this item is **waiting on data, not on engineering**. The
> post-transcription retraction option is the one that can be designed in the meantime,
> since it depends on the Locution template rather than on audio fingerprints.

Several PA (station paging) announcements have been captured and persisted as real
dispatches. The likely mechanism is in `audio_listener.py`:

```python
pa_matches        = [m for m in all_matches if m[0] == "PA Tone"]
apparatus_matches = [m for m in all_matches if m[0] in ("Chief Tone", "Engine Tone", "Rescue Tone")]

if pa_matches and not apparatus_matches:
    # disregard, reset listener
elif apparatus_matches:
    # CAPTURE
```

A PA page is only discarded when it matches the PA tone **and no apparatus tone**. The
operator has confirmed that PA announcements can themselves carry apparatus tones. Any
such page satisfies `apparatus_matches` and is captured as a dispatch — the `elif`
branch wins.

That ordering is deliberate for the opposite case (a real dispatch preceded by a PA
chime must not be discarded), so the fix is not simply reversing the precedence. Options
worth evaluating against real audio:

* Whether a PA page's apparatus tones differ measurably from a dispatch's — the DSP
  already logs peak frequencies and Z-scores per capture.
* Whether the announcement that follows the tones can disambiguate: a dispatch always
  states units, an address and a map grid in the Locution template, a PA page does not.
  A post-transcription check could retract a capture that parses to nothing.
* Tightening `FREQUENCY_TOLERANCE_HZ` (currently 8 Hz) — but note item #1.4, where an
  event matched PA Tone on peaks 588/647 against golden 595/647, inside tolerance by a
  single hertz. Tolerance is implicated in **both** directions.

**Tagging convention (current, no code change needed)**: accidental PA captures are
marked by putting `[PA]` in the HITL **review notes** field. That field is already wired
end to end — editable in `VerificationSidebar.jsx`, submitted by `DispatchReview.jsx`,
accepted by `DispatchUpdateSchema`, returned by the API. A dedicated checkbox was
considered and rejected as not worth the UI weight for how rare these are.

Once a corpus of `[PA]`-tagged dispatches exists, their audio can be pulled from
`backend/audio_files/recordings/` by dispatch_id and run against the fingerprinting code
as a negative-control suite:

```sql
SELECT dispatch_id, audio_url FROM public.dispatches WHERE review_notes LIKE '%[PA]%';
```

As of 2026-08-21 no dispatches carry the tag yet, and the single
`pa_page_DISP-2026-AB76A8.wav` fixture was deleted rather than kept as a separate file —
its dispatch had no row in `public.dispatches`, and the corpus will come from tagged
captures instead.


---

## 🔎 Geocoder Substitution

### 15. Fuzzy matching silently substituted a different intersection
> **Status**: ✅ **Closed 2026-08-22.** Found while verifying the #9 rebuild.

`intersection_resolver.lookup` resolved an unmatched intersection by fuzzy-matching the
whole normalized key against every other key and returning the best hit above 80.

Observed live:

| Requested | Returned | Reported as |
|:--|:--|:--|
| `Lougheed Hwy & Mariner Way` | `Lougheed Hwy & Pinetree Way` — **4,301 m away** | conf 86, `is_ambiguous: false`, no note |
| `Lougheed Hwy & Lougheed Hwy` | `Alderson Ave & Lougheed Hwy` | **conf 100** |

Two independent causes:

1. **The `token_set_ratio` subset trap.** It returns 100 when one token set is a subset of
   the other, so `token_set_ratio('LOUGHEED HWY', 'ALDERSON AVE & LOUGHEED HWY')` = 100.
   Any key containing the requested street scored a perfect match.
2. **No safe threshold exists.** Measured across all 1,079 road names, genuinely different
   streets score `HAMBER CRT`/`AMBER CRT` **96**, `WESTWOOD ST`/`EASTWOOD ST` **93**,
   `BURKE MOUNTAIN ST`/`BLUE MOUNTAIN ST` **93** — while the transcription errors worth
   recovering score `TASIS→TAHSIS` **95** and `JOHNSON→JOHNSTON` **98**. The correct
   corrections sit *below* the dangerous collisions. No cutoff separates them, and
   confusing Westwood with Eastwood sends apparatus across the city.

**Fix.** Fuzzy matching is now a *candidate generator only*, never a resolution. Each
street is scored independently (whole-key scoring let the shared half inflate the result —
that is how `MARINER WAY`→`PINETREE WAY` reached 86), only combinations that correspond to
a real existing junction are offered, and any non-exact match comes back
`is_ambiguous: true` with `requested_address` and `resolution_note` so the operator sees
and confirms it. The street-type alias swap (`RD↔AVE`, `ST↔WAY`, `BLVD↔DR`, returning
confidence 95) was deleted outright — renaming a street is not a match.

The real fix for transcription noise is upstream: Whisper already receives
`COQUITLAM_STREETS` from `public.road_names`, and biasing transcription toward the real
vocabulary stops "Lowheed" reaching the geocoder at all.

### 16. `<street> and <street>` is a CAD artifact, not a self-intersection
> **Status**: ✅ **Closed 2026-08-22.**

`DISP-2026-546B9E` transcribed as *"lougheed highway and lougheed highway, near lougheed
highway and lougheed highway ... map grid 49"* — Locution filled both the address slot and
the "near" cross-street slot with the same street because the CAD record had no cross
street. It is not a junction: `ST_IsSimple` is true for Lougheed Hwy, so the centreline
never crosses itself.

Resolved as a **street section** rather than a point: the stretch of that street inside
the announced map grid (533 m of Lougheed Hwy in grid 49). The kiosk highlights the
section in amber (`StreetSectionBanner`, and a dashed polyline on the map) and states
plainly that it is not a located incident; each unit routes to whichever end of the
section is nearest its own hall rather than to a midpoint that may be past the incident.

With **no** map grid it stays unresolved and raises the §5 Tier 1 card — without a grid
the "section" is the whole street, up to 14 km, which is not a location.

### 17. Grade-separated interchanges have no junction to find
> **Status**: ⚠️ **Open — one manual row added, needs operational confirmation.**

Lougheed Hwy and Mariner Way never meet: closest approach **221.6 m**. The derived table
correctly holds `HIGHWAY RAMP & LOUGHEED HWY` (3 candidates) and `MARINER WAY & UNITED
BLVD` there instead. Crews nevertheless call the place "Lougheed and Mariner", so it exists
as a `source='manual'` row that `derive_intersections.py` will never overwrite.

**The coordinate is not operationally confirmed.** It is the midpoint of the shortest line
between the two centrelines (`49.240487, -122.816114`, map grid 49) — a defensible
derivation, but nobody has decided whether the centre of the gap is where apparatus should
be sent rather than a specific ramp head or the Mariner Way overpass. The row's `notes`
column says so. Needs review by whoever owns response geography.

---

## 🎙️ STT Vocabulary Biasing

### 18. 96% of the Whisper hotword list is silently discarded
> **Status**: ✅ **Closed 2026-08-22 — budget restored and measured.** Terms are now
> ranked by value and trimmed against the model's real token cap: **58 terms, 221 of 223
> tokens**, and `Lougheed`, `Westwood`, `Pinetree`, `Barnet`, `Como Lake` and `Guildford`
> are biased where previously **no** arterial was. The trim is logged every build, and a
> warning fires if no HITL-corrected street survives.
>
> Ranking, in priority order: core terms → units → HITL-corrected streets → streets by
> dispatch count (`public.dispatches`) → streets by parcel count (`public.parcels`) → call
> types. The parcel-count ranking is the one commit `79808cc` used before it was removed.
> `transcriber.py` supplies the loaded model's real `max_length` and tokenizer so the
> budget is measured rather than guessed from a term count — the earlier fix capped at 120
> terms, which is still roughly double the real cap.
>
> **Known remaining limit**: 58 terms is tight, so `Mariner` and `Austin` still miss the
> cut. An untested idea worth measuring — bias on the distinctive name alone
> (`Lougheed` rather than `Lougheed Highway`), since "Highway"/"Avenue" are common words
> the model already handles. That should roughly halve the per-street cost and about
> double coverage, but it changes what the model is primed for and needs a WER backtest
> before adoption, not a guess.
>
> The original finding follows.
>
> ⚠️ **Open — measured 2026-08-22 on the kiosk model.** This is the upstream
> cause of the transcription errors that #15 was trying to repair downstream.

`build_stt_bias_words` assembles every road name, unit, core term and call type into one
`hotwords` string — 1,173 entries, 5,172 tokens — with the comment *"Build complete
hotword list — NO artificial truncation"*, having replaced an earlier top-25 limit.

**faster-whisper truncates it anyway**, and keeps the *head*
(`faster_whisper/transcribe.py:1546-1547`, version installed on the kiosk):

```python
if len(hotwords_tokens) >= self.max_length // 2:
    hotwords_tokens = hotwords_tokens[: self.max_length // 2 - 1]
```

Measured against the loaded model (`max_length` 448, so the cap is 223 tokens):

| | |
|:--|--:|
| Hotword entries supplied | 1,173 |
| Tokens supplied | 5,172 |
| Tokens kept | **223** |
| Tokens discarded | **4,949 (95.7%)** |
| Entries actually surviving | **61 of 1,173** |

Because `all_streets` arrives alphabetically, the surviving set ends at **"Archworth
Avenue"** and everything from **"Argyle Street"** onward is dropped. Street biasing
therefore covers part of the letter A and nothing else. **Westwood, Lougheed, Pinetree,
Barnet, Mariner — every arterial in the city — receives no biasing at all.** Call types
sit last in the list and never survive.

Removing the top-25 limit made this *worse* than it was: a curated 25 was at least chosen;
an alphabetical prefix of 61 is arbitrary.

**This is why "Lowheed" and "Tasis" reached the geocoder.** #15 removed the dangerous
downstream guessing, which was right, but the errors themselves are produced here.

**Fix direction** — spend the 223-token budget on the highest-value terms, and measure the
spend rather than assuming it:
1. Core dispatch terms and unit names (small, always needed).
2. HITL-corrected streets — empirically demonstrated to be misheard, so the highest value
   per token. `get_hitl_verified_streets()` already tallies them and they are already
   ordered ahead of `all_streets`.
3. Remaining streets ranked by **dispatch frequency** from `public.dispatches`, not
   alphabetically.
4. Assert the encoded token count against the model's real cap at build time, so a future
   change that overflows the budget fails loudly instead of silently dropping arterials.

**Also unverified**: no Whisper or faster-whisper documentation is referenced anywhere in
the project, and the figures above were taken from the installed source and the loaded
model rather than from docs. Worth confirming against the faster-whisper release notes for
the pinned version before treating the 223-token cap as stable across upgrades.

### 19. Remaining fuzzy-match sites have not been reviewed
> **Status**: ⚠️ **Open — inventoried 2026-08-22, not yet reviewed.**

#15 fixed `intersection_resolver.lookup`. Five other similarity-matching sites share the
same exposure and have **not** been examined against the Coquitlam street-collision
measurements (`HAMBER`/`AMBER` 96, `WESTWOOD`/`EASTWOOD` 93, `BURKE MOUNTAIN`/`BLUE
MOUNTAIN` 93):

| Site | Call | Risk |
|:--|:--|:--|
| `address_resolver.py:44` | `token_set_ratio(parsed_street, db_norm)` | **Highest** — same metric and same subset trap as #15, on the main address path rather than only intersections |
| `address_resolver.py:345` | `token_set_ratio(parsed_street, db_norm)` | As above, second call site |
| `parser/location.py:196` | `fuzz.ratio(clean_base, ks_lower)` | Feeds `fuzzy_correct_cross_roads`, invoked from `announcement.py:123` |
| `parser/call_types.py:38` | `token_set_ratio(ct.lower(), transcript)` | Different class (classification, not location) — a wrong call type is serious but not a wrong address |
| `parser/channels.py:42` | `token_set_ratio(raw_clean, chan_clean)` | Radio channel selection |

`token_set_ratio` scoring a short string against a longer one that contains it returns 100
(#15), so any site comparing a street fragment against a full street name is exposed.
`sanitize_transcript`'s phonetic corrections are hardcoded regex rather than fuzzy — they
are deterministic and auditable, but should be checked for the same collision property:
a correction that rewrites one real street into another real street would be worse than
any fuzzy match, because nothing scores it.

---

## 🧱 Duplicated & Unsourced Frontend Constants

### 20. `TALK_GROUPS` duplicates `public.vocabulary`
> **Status**: ⚠️ **Open — found 2026-08-22 during the MapBoard decomposition.**

`frontend/src/components/review/verificationConstants.js` hardcodes eight talk groups.
`public.vocabulary` category `radio_channel` holds **the same eight**, and is what the
dispatch parser matches against. They have already drifted in format:

| Database | Frontend |
|:--|:--|
| `Talk Group 5 Coquitlam` | `5` |
| `Talk Group 10 Combined Response Coquitlam` | `10 Combined Response` |

Same defect class as the street-suffix vocabulary moved into the database earlier the same
day: two hand-maintained lists of one fact, free to diverge, with nothing reporting it when
they do. The operator's HITL dropdown reads the hardcoded list while the parser reads the
database, so a talk group change corrects one and not the other.

**Fix**: serve `radio_channel` from the API and have the sidebar consume it, as the kiosk
already does for hydrants. Left in place rather than changed as a side effect of a lint
extraction; the constant now carries a comment saying so.

### 21. Rail crossing list is hand-entered and probably incomplete
> **Status**: ⚠️ **Open — found 2026-08-22.**

`frontend/src/components/map/railroadCrossings.js` holds **four** level crossings with
seven-decimal coordinates and `avoidable` flags, none of which carry provenance (§6.3).

CLAUDE.md §6.2 already names the authoritative source for exactly this data — *"rail
crossings are `railway=level_crossing` in OSM, not `lat < 49.26`"*. This list is the same
defect one level up: four hand-placed points standing in for the OSM layer. Coquitlam
almost certainly has more than four level crossings, and **an incomplete hazard layer is
worse than an absent one**, because a crew reading a clear map concludes there is no
crossing.

**Mitigating for now**: display only. The layer defaults to off and no route avoids these
points, so no apparatus routing depends on them today.

**Fix**: derive from OSM `railway=level_crossing` into a table, the way intersections are
now derived from `public.roads`, and drop the `avoidable` judgement unless it can be
attributed to someone.

### 22. "Next 24h" / "Next 7d" closure filters matched nothing
> **Status**: ✅ **Closed 2026-08-22 — found and fixed during the MapBoard decomposition.**

The road closure fetch computed `start` and `end` as locals inside its `map()` and then
returned `{ ...evt, isActive, isFuture, isExpired }`, discarding both. The timeframe filter
downstream tested `closure.start`:

```js
const is24hFuture = closure.isFuture && closure.start && (...)
```

`closure.start` never existed — the API returns `startDate` and `endDate` — so both
`is24hFuture` and `is7dFuture` were permanently falsy and **the "Next 24h" and "Next 7d"
toggles matched nothing whatever the data**. Only "Active Now" ever showed a closure.

Measured against the live feed at the time of the fix: **94 closures, 18 future-dated, 13
of them starting within 7 days**. All 13 were unreachable through the UI.

Fixed by carrying `start` and `end` onto the returned object in
`frontend/src/hooks/useRoadClosures.js`. Nothing else changed.

This is the second defect of the shape "a guard tests a field that is never populated" —
see also the `cross_streets` plumbing, which is wired end to end but reached 1 of 410
dispatches. A truthy check on an absent field fails silently and looks like "no results".

### 23. Live dispatches lost their street-section fields on the way to the kiosk
> **Status**: ✅ **Closed 2026-08-22.** Found while unifying the dispatch state model.

`useMqttListener.formatDispatchPayload` was a **third** hand-written dispatch translation,
alongside `App.jsx:handleReviewCall` and MapBoard's own handling. It built an explicit
object with **no spread**, so every field it did not know about was silently dropped.

**The live defect**: `location_type`, `segment`, `endpoints`, `length_m` and
`resolution_note` were absent from it, so a street-section dispatch (#16) arriving over
MQTT reached the kiosk without them. `StreetSectionBanner` checks
`activeCall?.location_type`, so the amber banner and the highlighted road section **never
appeared for a real call** — only for a review replay, which went through `App.jsx`
instead. The fields were plumbed through the geocoder, payload builder, App.jsx and the
panels the same day and this path was missed.

Two further §6.1 violations in the same function:

* `address: ... || 'Unknown Location'` and `incident_type: ... || 'EMERGENCY DISPATCH'` —
  fabricated defaults standing in for missing data.
* `priority_code: record.priority_code ?? record.response_type ?? 1` — and `KioskView`
  treats `priority_code <= 2` as an emergency, so **a dispatch with no priority was
  rendered as an emergency**.

It also ignored `verified_address` and `verified_incident` entirely, so an operator's
correction never reached a live kiosk call.

**Fix**: one translation, `frontend/src/utils/dispatchModel.js`, used by the MQTT listener,
`App.jsx` and `MapBoard`. Verified with `frontend/scripts/verify_dispatch_model.mjs`
against **421 real dispatch records: 0 field mismatches** before and after.

### 24. The kiosk displayed an invented hydrant on every dispatch
> **Status**: ✅ **Closed 2026-08-22.** Found from an operator screenshot of a live call.

The screenshot showed `City Hydrant: D-163 (42m)` in the alert banner and
`City Hydrant: D-165 (42m)` in the route panel — **two different hydrants at the same
distance**, for one incident. Neither is near the dispatch coordinate: the actual nearest
hydrants to `49.26312, -122.79819` are `L-191` (72 m), `L-114` (85 m) and `L-221` (108 m).

They were not data. They were string literals in the JSX:

```jsx
// ActiveAlertBanner.jsx
{activeCall?.target?.nearest_city_hydrant || activeCall?.nearest_city_hydrant || 'D-163'}
{activeCall?.target?.nearest_city_dist   || activeCall?.nearest_city_dist   || '42'}m

// RouteOverviewPanel.jsx
{activeCall?.hydrant || activeCall?.target?.hydrant || 'City Hydrant: D-165 (42m)'}
```

**The fallback fired on every call ever displayed.** Measured: **0 of 422** dispatches
carry `nearest_city_hydrant`, `nearest_city_dist` or `hydrant`, and no such field exists
anywhere in `backend/` or `services/`. The fields were always absent, so the kiosk always
showed the invented values.

This is the §6.1 defect in its most direct form: a specific hydrant ID and distance,
presented to crews as the nearest water supply, invented in the view layer. Same class as
the `or "AA"` flow rating (#11) and the `COQUITLAM_CENTER` coordinates (#2).

**Fix**: both fallbacks removed. The banner chip renders only when the dispatch carries a
hydrant; the route panel shows *"Nearest hydrant not computed"*.

**Related, fixed in the same pass**: `MapBoard` still fetched
`frontend/public/data/hydrants.json`, deleted when hydrants moved to the database. The
request 404'd, the handler swallowed it into an empty array, and the console's
nearest-hydrant panel was silently empty on every search. It now reads `/api/hydrants`, as
`MapLayers` already did.

**Still open**: nothing computes a nearest hydrant for a dispatch. `public.hydrants` and
`/api/hydrants` exist, and the console already computes one for a searched address, so
wiring it into the dispatch payload is a feature rather than a repair. Until then the
kiosk correctly reports that it does not know.

### 25. A corrected re-broadcast queued itself as a second call
> **Status**: ✅ **Closed 2026-08-22 (kiosk side).** Reported by the operator from a live call.

A call arrived, displayed correctly, and simultaneously raised the amber *"1 New Call
Queued — Tap to View Next"* banner. Tapping it cleared the banner and appeared to do
nothing else.

`useKioskQueue.handleInsert` had **no de-duplication**: it queued any INSERT arriving while
a call was active, without ever comparing `dispatch_id`. Tapping "view next" activated a
near-identical copy of the call already on screen, which reads as nothing happening.

> [!IMPORTANT]
> **Root cause corrected 2026-08-22.** This item first attributed the duplicate to phase 2
> re-broadcasting a corrected payload as an INSERT. **That was wrong**, and the broadcast
> log — readable only after #26 restored the pipeline's logging — settles it. For
> `DISP-2026-F33FA3` the backend published exactly one INSERT and one UPDATE:
>
> ```
> 15:12:00  Published INSERT event to Mosquitto MQTT   (phase 1)
> 15:12:20  Published UPDATE event to Mosquitto MQTT   (phase 2, Match=True, Corrected=False)
> ```
>
> The operator still saw the queued-call banner, and the reporter confirmed it appears
> **immediately**, not after a correction. The cause is **MQTT QoS 1 redelivery**: both
> publish and subscribe use `qos=1`, which guarantees *at-least-once* delivery. Duplicates
> are part of that contract — the protocol carries a DUP flag for exactly this — and the
> subscriber is required to be idempotent. Exactly-once is QoS 2.
>
> The de-duplication below is therefore **not a workaround for a backend defect**. The
> backend is correct; this is the idempotency QoS 1 requires of every subscriber. See
> `docs/standards/dependency-behaviour.md`.
>
> A duplicate delivery and a phase 2 correction produce the *same visible symptom*, which
> is why this could not be settled from the symptom alone.

The two payloads genuinely differed. For `DISP-2026-282647` the screen showed **map grid
61** while the stored record has **grid 68** — the operator was reading uncorrected phase 1
values with the correction sitting unread in the queue.

**Fix**: identity is `dispatch_id`. A re-broadcast of the active call merges and flashes
"CALL UPDATED", a re-broadcast of a queued call replaces it in place, and only a genuinely
different incident queues and chimes. Correct regardless of which event type carries the
correction.

**Fixed alongside**: `handleUpdate` matched on `id` **or `address`**. The corpus holds three
separate overdose dispatches at `3030 Gordon Ave`, so two active at once would have
overwritten each other's units, transcript and coordinates. It now matches on dispatch
identity only.

**Backend, not yet fixed — a latent ordering defect.** `phase1.py` broadcasts before it
records its session:

```
publish_mqtt_dispatch(db_payload, event_type="INSERT")   # line 132
...
session_manager.record_phase_1_success(...)              # line 150
```

If anything in that broadcast block raises, an INSERT has been emitted with no phase 1
session stored. Phase 2 then finds `p1_data` empty, takes the "Phase 1 was skipped"
single-phase branch, and publishes a **second INSERT** (`phase2.py:135`) rather than the
UPDATE the correction path uses. Recording the session *before* broadcasting would make an
un-tracked INSERT impossible.

Ruled out as causes: the correction paths publish `UPDATE` correctly
(`phase2.py:222/305/336/351`); `cleanup_session` runs in a `finally` after phase 2, so the
ordering is right; and the session TTL is 600 s against a 46 s dispatch, so eviction is not
plausible.

**Whether this is what happened was not established** — see #26.

### 26. The dispatch pipeline's INFO logging is discarded
> **Status**: ✅ **Closed 2026-08-22.** Root cause found and fixed; **requires an agent
> restart to take effect**.
>
> **Cause**: Python 3.14 changed the default multiprocessing start method on Linux from
> `fork` to `forkserver` (verified on the kiosk: `get_start_method()` → `forkserver` under
> 3.14.4). A forked child inherits the parent's configured logging; a forkserver child does
> not. `orchestration.run_dispatch_system` configured logging and *then* spawned the
> worker — correct under `fork`, silently broken on 3.14.
>
> **Fix**: `setup_logging` moved to `cfr_dispatch/logging_setup.py` and called *inside*
> `background_worker_loop`, which is correct under any start method. The worker writes
> `dispatch-worker.log` rather than sharing the orchestrator's file, because a
> `TimedRotatingFileHandler` is not safe across processes — both would race on the
> rotation rename.
>
> **Verified** with a forkserver child on the kiosk: INFO now appears in the configured
> format on stderr (so systemd captures it) and in the worker's own file, where previously
> only `WARNING:root:` survived.
>
> Recorded in `docs/standards/dependency-behaviour.md`.
>
> Original finding follows.
>
> ⚠️ **Open — found 2026-08-22 while trying to diagnose #25.**

The two-phase pipeline runs in a **separate process** from the audio agent, and that
process never configures logging. It therefore uses the default root logger at **WARNING**,
so every `logging.info` in the pipeline is dropped.

Evidence, from the same journal:

```
2026-08-22 14:34:04,724 - INFO - TONES CONFIRMED: 'Rescue Tone'        <- agent, configured
WARNING:root:[DISP-2026-5AC92A] Phase 2 transcription returned empty   <- worker, default
```

Different format, and different PIDs (`cfr-agent[1949135]` vs `cfr-agent[1949225]`). Only
WARNING and above survive from the worker.

**What is lost:**

* `Published {event_type} event to Mosquitto` — **zero** occurrences today despite
  dispatches arriving. This is why the broadcast sequence for #25 could not be read back.
* `[METRICS] Phase 1 TTA: …` and `[METRICS] Phase 2 Finalized …` — zero. These carry the
  DSP / STT / GIS / MQTT timings, so the performance-metrics work has no source data.
* Every geocoder and parser INFO line, including the ones added this session to report
  why an address was unresolved.

The system is therefore **not diagnosable from its logs** for anything that does not raise
a warning. A dispatch that resolves to the wrong place leaves no trace of how it got there.

**Fix**: configure logging in the worker process entry point with the same format and level
as the agent. Until then, treat "the logs show nothing" as "the logs are not recording",
not as evidence that nothing happened.

---

## ⚙️ Dispatch Worker Process Architecture

The two-phase pipeline runs in a `multiprocessing.Process` spawned by
`orchestration.run_dispatch_system`. The separation is justified — Whisper int8 inference
takes seconds and must not stall PortAudio capture, and a pipeline crash must not take the
audio listener down with it. These items are about how that separation is *implemented*.

### 27. The worker process is unsupervised
> **Status**: ✅ **Closed 2026-08-22.** `cfr_dispatch/worker_supervisor.py` polls
> `is_alive()` every 15 s from a daemon thread and restarts the worker, logging every
> restart at CRITICAL.
>
> **Crash loops are handled rather than ignored.** Restarting forever buries the cause and
> looks like progress, so restarts are counted in a rolling window (5 in 600 s). Past the
> ceiling the supervisor stops restarting and **keeps reporting on every check** — going
> quiet after giving up would recreate the silent-dead-worker failure this exists to
> prevent.
>
> Verified with a worker that exits immediately:
>
> ```
> CRITICAL ProbeWorker died (exitcode 9). Restarting -- restart 1 of 3 ...
> CRITICAL ProbeWorker died (exitcode 9). Restarting -- restart 2 of 3 ...
> CRITICAL ProbeWorker died (exitcode 9). Restarting -- restart 3 of 3 ...
> CRITICAL ... restarted 3 times in 60 seconds. Refusing to restart again ...
> CRITICAL ProbeWorker is DEAD and the supervisor has stopped restarting it ...   (repeats)
> ```
>
> and a healthy worker left untouched (same pid, 0 restarts).
>
> Original finding follows.
>
> ⚠️ **Open — found 2026-08-22.**

`orchestration.py`:

```python
worker_process = multiprocessing.Process(target=background_worker_loop, args=(dispatch_queue,), daemon=True)
worker_process.start()
```

That is the only reference to it. The process is never checked with `is_alive()`, never
restarted, and emits no health signal. **A worker crash is permanent and silent** until
someone restarts the whole service.

Before #28 was fixed this compounded badly: a dead worker stopped draining the queue, the
queue filled, and the blocking `put()` then stopped the audio listener entirely. That path
is closed, but a dead worker still means no dispatch is ever processed, persisted or
broadcast — while the listener keeps happily detecting tones.

**Fix direction**: check `worker_process.is_alive()` from the listener loop, restart it, and
log the restart at CRITICAL. Restarting is cheap relative to the alternative — the worker
reloads the Whisper model and the GIS validator on start, which is seconds.

**Watch for**: a crash loop. If the worker dies repeatedly on the same task, restarting
forever is worse than stopping loudly. A restart counter with a ceiling, and a distinct
log line when the ceiling is hit, is the honest version.

### 28. A stalled worker could block the audio listener — fixed
> **Status**: ✅ **Closed 2026-08-22.**

`dispatch_queue` is a `multiprocessing.Queue(maxsize=10)` and both producers used a
**blocking** `put()`:

* `audio_listener.py` — `phase_2_finalize`, carrying the complete audio buffer.
* `sound_capture.py` — `phase_1_check`, enqueued **inside the capture loop**.

If the worker stalled or died, the queue filled and `put()` blocked the audio listener
indefinitely. It would stop capturing tones with no error and no warning: the system would
look like a quiet night while being deaf. For a dispatch system that is the worst available
failure mode, because nothing distinguishes it from no calls arriving. The `phase_1_check`
case was worse still, stalling capture of a dispatch already in progress.

**Fix**: `audio_service.enqueue_dispatch_task` — never blocks, and prioritises by task type,
because the two are not equally important:

* `phase_2_finalize` carries the full audio and is what persists and broadcasts the call.
  Losing one loses the call, so it is admitted by **displacing an older queued item**.
* `phase_1_check` is an optimistic early alert on a partial buffer. Dropping one costs
  notification latency; phase 2 still produces the full record. It is **discarded**.

A full queue is logged at ERROR (phase 1) or CRITICAL (phase 2) rather than swallowed, so it
reaches the journal — which it now can, since #26.

Verified against a genuinely full queue:

```
phase_1_check    accepted=False  elapsed=0.000s   -> ERROR, discarded
phase_2_finalize accepted=True   elapsed=0.000s   -> CRITICAL, displaced OLD-0
survivors: ['OLD-1', 'OLD-2', 'NEW-P2']
```

The newest call gets through and neither call blocks.

### 29. Phase 1 session state lives only in worker memory
> **Status**: ✅ **Closed 2026-08-22.** Phase 1 state is now persisted in
> **`public.dispatch_sessions`** (`cfr_dispatch/session_store.py`), so it survives a worker
> restart. `DispatchSessionManager` keeps the same interface, so phase 1 and phase 2 call
> it unchanged.
>
> `candidates` are `DispatchData` dataclasses stored as JSON and rebuilt on read, because
> phase 2 reads `.address` and `.intersection` off them as attributes. Unknown keys are
> dropped and missing ones default, so a session written before a deploy does not crash the
> worker reading it after one — these rows outlive a restart by design.
>
> **The ordering defect is fixed too.** `phase1.py` now records the session *before*
> broadcasting. It was the other way round, so any exception in the broadcast block left an
> INSERT published with no session stored — and phase 2, finding nothing, took the
> "Phase 1 was skipped" branch and published a second INSERT. Recording first makes an
> untracked INSERT impossible.
>
> Verified across a real process boundary — written by one process, read by another:
>
> ```
> read back: transcript='CLEAN' units=['E1'] target.lat=49.27533
> count=2  types=['DispatchData', 'DispatchData']
> phase2-style pick -> address='3025 Lougheed Hwy'
>                      intersection='Lougheed Hwy & Westwood St'  map_grid='82'
> is_triggered before cleanup: True / after: False
> ```
>
> Execution profiles stay in memory deliberately: rolling metrics for one process, not
> dispatch state.
>
> Original finding follows.
>
> ⚠️ **Open — found 2026-08-22.**

`DispatchSessionManager` holds phase 1 candidates in a plain dict inside the worker
process (`worker.py`, `_phase_1_candidates`). Nothing persists it.

If the worker dies, every in-flight dispatch loses its phase 1 context. Phase 2 then finds
`p1_data` empty and takes the **"Phase 1 was skipped"** single-phase branch
(`phase2.py:127`), which publishes a second `INSERT` rather than the `UPDATE` the
correction path uses — the exact mechanism implicated in #25.

It is also inconsistent with the rest of the system: PostgreSQL is the single source of
truth for dispatches, vocabulary, hydrants, intersections and road closures, and this is
the one piece of dispatch state that is not in it.

**Fix direction**: persist phase 1 candidates to Postgres keyed by `dispatch_id`, with the
existing 600 s TTL enforced by a timestamp column. Phase 2 then reads them regardless of
which process — or which *instance* of the worker — handled phase 1.

**Related and worth fixing with it**: `phase1.py` broadcasts its `INSERT` *before* calling
`record_phase_1_success`. Any exception in that broadcast block leaves an INSERT emitted
with no session recorded, producing the same "phase 1 was skipped" outcome. Recording the
session first would make an untracked INSERT impossible.

---

## 🏷️ Response Terminology & Status Colour

### 30. "Code 1 / Code 3" is not Coquitlam terminology, and the border has no warning or review state
> **Status**: ⚠️ **Open — found 2026-08-23.** Reported by the operator from a live kiosk
> screenshot (`1347 KENNEY ST`, GRID 88, routine call). The rendering sites below were
> **confirmed** by reading the working tree; the terminology correction itself is the
> operator's, and Coquitlam usage is not currently backed by a document in
> `docs/standards/` (see the gap note at the end).

**Two separate defects in one item, because they share the same `isEmergency` input.**

#### 30a. The code numbers are wrong, and should be removed entirely

The kiosk badge reads **`🟢 ROUTINE (CODE 1)`**. Coquitlam Fire/Rescue does not use Code 1;
the numeric scale in use is **Code 2 and Code 3**, so the label is doubly wrong — the wrong
number *and* a scale the department does not speak.

The operator's direction: **drop the numeric codes from the interface entirely.** The
authoritative terms are **`ROUTINE`** and **`EMERGENCY`**, which is also how the dispatch
itself is transmitted over the radio — so the display would match what crews actually hear.

Confirmed rendering and label sites:

| File | Line | Current |
|:--|:--|:--|
| [`frontend/src/components/hud/ActiveAlertBanner.jsx`](../frontend/src/components/hud/ActiveAlertBanner.jsx) | `36` | `isEmergency ? '🚨 Emergency (Code 3)' : '🟢 Routine (Code 1)'` |
| [`services/gis/src/gis_service/routing_engine.py`](../services/gis/src/gis_service/routing_engine.py) | `309`, `433` | `"response_mode": "Routine (Code 1)" if is_routine else "Emergency (Code 3)"` |
| [`backend/tests/test_routing_engine.py`](../backend/tests/test_routing_engine.py) | `338`, `341` | asserts both strings — **will fail** when the labels change, and must be updated with them |

`response_mode` has **no frontend consumer** — the grep above finds it only in the routing
engine that emits it and the test that asserts it. So the backend and frontend strings are
independently wrong rather than one feeding the other, and both need changing.

**Related, and the reason this is not purely cosmetic** —
[`frontend/src/components/kiosk/KioskView.jsx:93`](../frontend/src/components/kiosk/KioskView.jsx#L93):

```js
const isEmergency =
  activeCall.priority_code <= 2 ||
  String(activeCall.priority_code).toLowerCase() === 'emergency' ||
  String(activeCall.response_type).toLowerCase() === 'emergency';
```

The numeric branch encodes a **`<= 2` means emergency** rule. If the department's scale is
Code 2/Code 3 rather than 1/2/3, then `priority_code == 2` classifying as *emergency* needs
confirming against what the dispatch feed actually sends — under a 2/3 scale, 2 may well be
the *routine* value, which would invert the classification and the border colour with it.
**This branch must be resolved before the labels are cosmetically renamed**, or the display
will read correctly while classifying incorrectly.

> **Resolved by #31**: `priority_code` is not a column in `public.dispatches` and appears
> nowhere in the backend. Every branch of this expression reads an undefined field, so
> `isEmergency` is **always false** and *every* call — including all 343 emergency ones —
> renders green. The branch is to be deleted, not renumbered. **Fix #31 first; #30 is the
> wording on top of it.**

#### 30b. The border colour has only two of the four required states

Confirmed at [`KioskView.jsx:175`](../frontend/src/components/kiosk/KioskView.jsx#L175):

```js
const borderColor = isEmergency ? 'border-red-600' : 'border-emerald-500';
```

Applied as a `border-[6px]` ring on the fixed full-screen container (`:180`). The operator
confirms **green for routine is correct and worth keeping**. The required state set is:

| State | Border | Present today |
|:--|:--|:--|
| Routine | **Green** | ✅ `border-emerald-500` |
| Emergency | **Red** | ✅ `border-red-600` |
| Warning | **Amber** | ❌ no amber border state exists |
| Review mode | **Blue** | ❌ review keeps the red/green border; it is signalled only by a *purple* `🧪 REVIEW REPLAY` badge in `ActiveAlertBanner.jsx:39` |

Two follow-on notes for whoever implements this:

* **Review mode is currently purple, not blue** — the badge at `ActiveAlertBanner.jsx:39`
  uses `purple-950/purple-500/purple-200`. If blue becomes the review colour, the badge
  should move with the border or the two will disagree.
* **What drives the amber warning state is undefined.** The §5 Tier 1 unresolved-location
  card and the queued-call banner (`KioskView.jsx:185`) are both already amber, so they are
  the natural candidates — but which conditions raise the *border* to amber, and what
  happens when a warning coincides with an emergency (does amber override red, or red win?),
  is a precedence decision that has not been made. **Ask before implementing.**

#### Answered by the operator, 2026-08-23

1. **Numeric codes are removed from the system entirely.** Use the bare terms **`routine`** /
   **`emergency`** everywhere — that is how the dispatch is transmitted and how the parser and
   `public.vocabulary` already represent it, so there is nothing to translate. Code 2 / Code 3
   are **deleted, not renamed**, and no numeric mapping is retained as a fallback; if one is
   ever needed the operator will add it themselves. The `priority_code <= 2` branch is to be
   **deleted**, not corrected; see **#31**, which found it tests a column that does not exist.
2. **Amber is orthogonal to response type.** Green/red are *"stylistic, and a minor reminder
   to drivers"*. **Amber flags the call for additional attention regardless of response
   type**, so it **overrides** both green and red. Current triggers:
   * the system applied a **correction**,
   * **low confidence**,
   * a **call is queued**,
   * *(added 2026-08-23)* the **response type is `NULL`** — shown as `UNKNOWN`; see #31.
3. **Review stays purple.** No change; the existing `🧪 REVIEW REPLAY` badge colour is
   correct and the border should match it rather than going blue.

Revised target state for the border:

| State | Border | Precedence | Present today |
|:--|:--|:--|:--|
| Review mode | **Purple** | highest | badge only, border unchanged |
| Warning | **Amber** | overrides green/red | ❌ does not exist |
| Response type `NULL` | **Amber**, labelled `UNKNOWN` | as warning | ❌ cannot occur yet — see #31 |
| Emergency | **Red** | — | ✅ but never fires — see #31 |
| Routine | **Green** | — | ✅ fires on *every* call — see #31 |

**The "low confidence" threshold, measured 2026-08-23.** The operator asked for a new number
on the grounds that the existing `confidence_score >= 90` in `dispatchModel.js:74` is
unsourced. It is unsourced — but **the corpus supports it**, so the defect is the missing
provenance, not the value.

`confidence_score` is heavily quantised (435 rows, none NULL):

| Score | Rows |
|:--|--:|
| `0` | 30 |
| 45–78 | 25 |
| 81–89 | 27 |
| 91–96 | 19 |
| `100` | 334 |

Cross-referenced against HITL `quality_rating`, counting only **rated** calls:

| Band | Rated | Perfect | Failed |
|:--|--:|--:|--:|
| `0` | 5 | **0%** | **100%** |
| 45–78 | 14 | 14% | 21% |
| 81–89 | 13 | 15% | 8% |
| 91–96 | 8 | **63%** | **0%** |
| `100` | 116 | 59% | 3% |

**The behavioural break is between 89 and 91.** 91–96 behaves like 100 (≈60% perfect, no
failures); 81–89 behaves like 45–78 (≈15% perfect, failures present). A cut at 90 lands
exactly on that boundary. Moving it to 80 would sweep the 81–89 band — the band that
actually behaves badly — into the "confident" side.

At `< 90`, **82 of 435 calls (19%)** would raise amber.

⚠️ **Caveats, stated rather than buried**: the 91–96 and 81–89 bands have only 8 and 13
*rated* calls, so the boundary is suggestive, not established. 77% of the `100` band is
unrated. And `quality_rating` is the operator's own judgement, so this measures agreement
between the parser's self-assessment and the reviewer, not ground truth.

**Recommendation**: keep **90**, and convert it from an unsourced constant into a §6.3 tier-3
*measured* one by citing this analysis inline. Revisit once the rated sample in the 81–96
range grows. **Operator decision still required** — see the question below.

`confidence_score = 0` is a distinct case, not merely "low": all 30 such rows are hard
resolution failures (13 have no address at all, 19 are already flagged `verify_location`),
and every rated one was graded FAILED. Worth treating as its own amber reason rather than
folding into the threshold.

Still to pin down: the predicate for "applied a correction". `isRecentlyUpdated` (already
plumbed into `ActiveAlertBanner`) is the likely signal, and `queuedCalls.length > 0` the
queued one.

**Operator decision 2026-08-23**: **keep 90 for now**, commented with its measurement, and
tag it for future QA review once more dispatches have been rated. Tracked as **#32**, which
also records what the operator wants the flag to *mean* — "would the crew have reached the
right address", i.e. below OPERATIONAL or a poor geocode score — and a re-measurement against
`verified_address` that partly contradicts the `quality_rating` analysis above.

> **Standards gap** — Coquitlam Fire/Rescue response-mode terminology is not held in
> `docs/standards/`. Recorded there per CLAUDE.md §7.5; until it exists, the operator is the
> authority, and the authority's ruling is: **`routine` / `emergency`, no numeric code.**

---

### 31. `response_type` never reaches the kiosk — every call renders as ROUTINE
> **Status**: ⚠️ **Open — found 2026-08-23 while investigating #30.** **Confirmed** against
> the running kiosk database and the working tree. This is the defect #30 was sitting on
> top of; #30 is the wording, this is the data.

**The kiosk cannot tell an emergency call from a routine one. It never receives the field.**

#### Confirmed by query, not by reading

`public.dispatches` has **22 columns and none of them carry a response type**:

```
id, dispatch_id, timestamp, incident_type, responding_units, target,
raw_transcript, sanitized_transcript, confidence_score, verify_location,
origins, audio_url, audio_duration, verified_transcript, verified_address,
verified_incident, verified_units, feedback_submitted, quality_rating,
model_updated, review_notes, routing_metrics
```

There is **no `priority_code` column, and no `response_type` column.** Neither key appears
anywhere in the `target` JSONB either — a scan of every `target` key across all 435 rows
matching `%resp%`, `%prior%` or `%code%` returns **zero**.

Yet the information is plainly present in the audio:

| | rows |
|:--|--:|
| Total dispatches | 435 |
| Transcript contains `respond emergency` | **343** |
| Transcript contains `respond routine` | 66 |

#### Consequence

[`KioskView.jsx:93`](../frontend/src/components/kiosk/KioskView.jsx#L93):

```js
const isEmergency =
  activeCall.priority_code <= 2 ||                                  // undefined <= 2      -> false
  String(activeCall.priority_code).toLowerCase() === 'emergency' || // "undefined"          -> false
  String(activeCall.response_type).toLowerCase() === 'emergency';   // "undefined"          -> false
```

All three branches read fields that do not exist, so `isEmergency` is **always `false`**.
Every dispatch renders with the green routine border and the `🟢 ROUTINE` badge — including
all **343 emergency calls**. The screenshot in #30 happens to be a genuine routine call,
which is why the error is invisible there.

The operator states the border is *"stylistic, and a minor reminder to drivers"*, so this is
not a life-safety failure — but it is a signal that has never once been correct for an
emergency call, and drivers have been receiving a green cue on every call regardless.

`dispatchModel.js:73` faithfully maps `priority_code: record.priority_code` — it is
propagating a field the backend has never produced.

#### Root cause: the value is computed, used, and then discarded

[`payload_builder.py:186`](../backend/cfr_dispatch/pipeline/payload_builder.py#L186):

```python
detected_resp = next((d.response_type for d in all_candidates if d.response_type), "emergency")
routing_metrics = router.calculate_units_routing(
    responding_units, lat, lng, response_type=detected_resp, ...)
```

`detected_resp` is parsed correctly from the transcript, passed to the routing engine, logged
— and then **never added to `target_payload`** (`:195–202`). It dies in the local scope. The
parser side is fine: `destructive_parser.py:74` and `announcement.py:171` both extract it,
and `public.vocabulary` already stores `response_type` as the two strings **`routine`** and
**`emergency`** (`2026-08-21_vocabulary_seed.sql:232-233`).

The only place it survives to the database is incidentally, inside per-unit routing metrics —
and almost never:

| `target.routing_metrics[].response_mode` | unit rows |
|:--|--:|
| `null` | **405** |
| `Emergency (Code 3)` | 8 |
| `Routine (Code 1)` | 2 |

#### Two smaller defects found alongside

1. **The defaults disagree — resolved to `NULL`.** When no candidate carries a response type,
   `payload_builder.py:186` defaults to **`"emergency"`**, while `payload_builder.py:228`
   (template reconstruction), `phase2.py:177`/`:260` and `destructive_parser.py:39` all default
   to **`"routine"`**. The same unparsed call is therefore routed as emergency but
   reconstructed as routine. **Operator ruling 2026-08-23: all four fallbacks are removed and
   an unparsed response type propagates as `None`** (§6.1), displaying as unknown. The visible
   consequence — some calls showing neither the green nor the red border — is accepted.

   **Where `NULL` surfaces — both settled by the operator 2026-08-23:**
   * **Border**: a `NULL` response type is an **amber** condition with the response type shown
     as `UNKNOWN`. It joins the amber trigger set in #30 rather than producing a borderless
     call, so the gap is loud rather than quiet.
   * **ETA**: `routing_engine.py:279` and `:407` derive
     `is_routine = str(response_type).lower().strip() == "routine"`; a boolean cannot represent
     unknown, so `None` already falls through to the **emergency** branch. The operator has
     ruled this **correct** — most calls are emergency and time-critical, and ETAs are not
     currently relied upon operationally. It must stop being *accidental*: both sites need a
     §6.3 tier-4 provenance comment naming the decision. The **stored** value stays `NULL`;
     only the routing calculation assumes emergency. That distinction is the whole point —
     inventing a stored response type is banned, computing under a declared and displayed
     assumption is not.
2. **`public.dispatches.routing_metrics`** (the top-level column, distinct from
   `target.routing_metrics`) is an empty object on every row scanned. Possibly dead; worth
   confirming before anything new is written to it.

#### Direction agreed with the operator (2026-08-23)

**Use the strings; do not introduce a numeric code.** The dispatch is transmitted as
"respond routine" / "respond emergency", the parser already produces exactly those two
lowercase strings, and `public.vocabulary` already stores them — so a numeric code would be a
translation layer with no source and two more places to get inverted.

Accordingly:

* Persist `response_type` (`'routine'` | `'emergency'` | `NULL` when unparsed) through
  `target_payload` so it reaches the kiosk.
* Replace the three-branch `isEmergency` in `KioskView.jsx:93` with a single string test.
  **Delete the `priority_code <= 2` branch outright** — it tests a field that has never
  existed, and under the department's Code 2/Code 3 scale its arithmetic would be inverted
  anyway. This resolves open question 1 of #30.
* **Remove Code 2 / Code 3 from the system entirely** (operator, 2026-08-23) — deleted, not
  renamed and not retained as a mapping. No numeric response code should survive anywhere in
  the codebase. If a numeric scale is ever genuinely needed, the operator will make that
  change themselves; no translation layer is to be left in place in anticipation.
* **An unparsed response type is `NULL`, never a guess** (operator, 2026-08-23). This closes
  the conflicting-defaults question below: all four fallbacks come out.
* Add a **reviewer verification control** for response type in the HITL panel, modelled on
  the tone selectors — see the briefing below.

> **Handed to the parser agent 2026-08-23**:
> [`docs/briefings/response_type_persistence.md`](./briefings/response_type_persistence.md)
> covers both the persistence fix and the review-panel control, with the operator ruling and
> the conflicting-defaults question that must be raised before implementing.

---

### 32. QA review: re-derive the amber "needs attention" threshold once more calls are rated
> **Status**: 🕓 **Deferred by the operator 2026-08-23 — revisit after more HITL reviews.**
> The threshold stays at **90**, now carrying its measurement inline
> (`frontend/src/utils/dispatchModel.js`). This item exists so the provisional decision is not
> mistaken later for a settled one.

#### What the operator actually wants the flag to mean

Not "low transcript confidence" — **"would the crew have reached the right address."** In the
operator's words, *operational* means the crew would at least get to the right address even if
other data was poor, and that is the factor that matters. So the amber trigger should fire on
**anything below OPERATIONAL, or a poor geocode score**, rather than on overall parser
confidence.

That is a different signal from `confidence_score`, and the two do not agree.

#### Measurement run 2026-08-23 — and a correction to an earlier figure

202 reviewed calls (`feedback_submitted` with a non-empty `verified_address`), comparing the
system address to the operator's correction.

**A first pass compared the strings raw and reported 25% of the `score 100` band as
"corrected". That figure was wrong and is withdrawn.** Most of those diffs were cosmetic —
suffix expansion (`HWY`→`HIGHWAY`, `AVE`→`AVENUE`, `CRES`→`CRESCENT`), unit-number stripping
(`1142 DUFFERIN ST 152` → `1142 DUFFERIN ST`), and removal of the `(street centroid)`
annotation. None of those would send a crew anywhere different.

After normalising suffixes, trailing unit numbers and annotations:

| Confidence | Reviewed | Substantively wrong address |
|:--|--:|--:|
| `0` | 10 | **100%** |
| 45–78 | 20 | **60%** |
| 81–89 | 15 | **0%** |
| 91–96 | 9 | **0%** |
| `100` | 148 | **8%** |

**The break is at 80, not 90.** The 81–89 band — which looked mediocre against
`quality_rating` — is *flawless* on address. So a cutoff at 90 is **conservative rather than
wrong**: it flags a band that has not actually failed. For a warning colour that is the safe
direction to err, which is why 90 is retained rather than moved.

#### Why it is not moved to 80 today

* 81–89 has only **15** reviewed calls. Zero failures in 15 is not yet zero failure rate.
* **`score 100` still gets 8% wrong** (12 of 148). Confidence is not a complete proxy for
  geocode correctness, so *no* threshold on this field alone catches everything the operator
  cares about. A geocode-specific quality signal would serve better than a parser-confidence
  one — see below.
* `confidence_score = 0` is a **distinct failure mode**, not merely "low": all 30 such rows
  are hard resolution failures (13 have no address, 19 already flagged `verify_location`) and
  10 of 10 reviewed had the address corrected. Worth its own amber reason.

#### Data-quality problem this exposed, worth fixing before the next measurement

**`verified_address` is being used for cosmetic edits, which contaminates it as ground truth.**
Reviewers expand suffixes and strip unit numbers, so a naive comparison overstates the geocode
error rate by roughly 3× (37 raw diffs vs 12 real ones in the `100` band). Any future accuracy
metric built on `verified_address` must normalise first, or the numbers will be wrong in the
alarming direction.

Two related observations from the same sample:

* Genuine failures are visible and do look like real defects — `1` → `657 Whiting Way`,
  `1550` → `1550 United Blvd`, `3000 Walton Ave` → `3007 Anson Ave`, and STT damage such as
  `3025 Low Heat Hwy` → `3025 Lougheed Highway` (*"Low Heat"* for *Lougheed*).
* One record looked like a rating inconsistency and turned out to be something else:
  `3030 Gordon Avenue Rain City Housing` verified to `2648 Sandstone Cres`, rated **PERFECT**.
  It was the review form's own placeholder examples saved as data — see **#33**, now closed.
  The operator has corrected the record. It was the only genuine case in the 202 reviewed.

#### To do when revisiting

1. Re-run the banded comparison once the rated sample in 81–96 is materially larger.
2. Decide whether the trigger should key off **`quality_rating < OPERATIONAL`** (the
   operator's stated preference) rather than `confidence_score` — noting ratings are applied
   *retroactively*, so they cannot flag a live call. A live proxy is still needed; the
   question is which one best predicts the retroactive rating.
3. Consider a dedicated **geocode confidence** distinct from parser confidence. The geocoder
   already knows whether it returned an exact parcel match, a street centroid, or a fuzzy
   suggestion — that is a far more direct answer to "will the crew reach the right address"
   than a transcript score. Related to #12.

---

### 43. Call-type vocabulary carries locale variants as duplicate rows; HITL captures incident as free text
> **Status**: 🔧 **In progress — found 2026-08-23 during the parser audit.** All counts below
> are **confirmed** by query against the kiosk database (`100.95.146.94:5432`), not read from
> code. Two records are **flagged for operator re-review** (see the last section) and are not
> being guessed at.

**Root cause is the input, not the data.**
[`VerificationSidebar.jsx:429`](../frontend/src/components/review/VerificationSidebar.jsx)
captures `verified_incident` as a bare `<input type="text">` — no datalist, no select, no
validation against `public.vocabulary`. Reviewers hand-type the incident type, so ground truth
drifts from the vocabulary the parser is matching against. Every item below is downstream of
that one control.

#### The vocabulary is doing two jobs at once

`public.vocabulary` (`category='call_type'`, 66 rows, all `source='cfr_curated'`) is
simultaneously **what the parser listens for** and **what the kiosk displays**. Where those
two disagree, the table has grown a second row instead of a second field.

Measured, `raw_transcript` vs vocabulary:

| Pair | STT writes | Reviewers confirm | Verdict |
|:--|:--|:--|:--|
| `Wildland Fire - Smoldering` / `- Smouldering` | `smoldering` **5/5**, `smouldering` **0/5** | `Smouldering` **2/2** | **not a duplicate — a recognition alias** |
| `Medical Aid - Breathing Problem` / `- Problems` | `breathing problem` **24/24** singular | split 5 / 4 | plural row is dead weight |

Whisper writes American English consistently; the department writes Canadian. The
`- Smoldering` row is the only reason those five calls classify at all — **retiring it as a
duplicate would introduce the qualifier-drop defect this audit set out to measure.**

Genuinely dead rows (zero usage on either side, safe to retire):
`Alarms Activated`, `Alarms Activated - High Risk`, `Medical Aid - Cardiac Problems`.

#### Ground truth contains terms the parser structurally cannot emit

Seven `verified_incident` values have no matching vocabulary row. `match_incident_type` returns
a vocabulary term or `Unknown Incident`, so these can never be produced no matter how good the
parse. They are vocabulary gaps, **not** parser defects:

`Structure Fire - Detached Structure`, `Tent Fire - High Risk`,
`Medical Aid - Airway Obstruction`, `Odor - Unknown Source` — legitimate, being added.

#### Correction to an earlier claim in this audit

An earlier pass in this session reported `Tent Fire - High Risk` and
`Structure Fire - Detached Structure` as **2 live parser defects**. That was wrong — both are
missing vocabulary rows. Recorded here so the claim is not repeated (CLAUDE.md §6.6).

Also corrected: the qualifier-drop class is **not** 22 live defects.
Re-running current code over the class gives **16 already correct, 6 remaining**, of which 4
were these locale variants. The stored-vs-verified figure was measuring history, exactly the
ghost-defect trap `docs/parser_audit_handoff.md` §4.2 warns about.

#### ⚠️ Flagged for operator re-review — do not guess

Two records have `verified_incident` values that are data-entry errors. The correct incident
type cannot be recovered from the vocabulary and **must not be inferred** (CLAUDE.md §6.1):

**Both records have since been cleared. Neither was an operator error.**

| Dispatch | `verified_incident` | Outcome |
|:--|:--|:--|
| ~~`DISP-2026-E05DBD`~~ | ~~`''`~~ | **CLEARED** — not a dispatch. See below. |
| ~~`DISP-2026-266B57`~~ | ~~`Assist`~~ | **CLEARED** — `Assist` was a missing vocabulary term, since added. |

`DISP-2026-E05DBD` is a **station PA page**, not a call:

```
raw_transcript      : 'Lunch, lunch is up, lunch is up.'
verified_transcript : ''      verified_units: []      verified_incident: ''
audio_duration      : 10.24s  confidence_score: 0.00  address: 'Unknown Location'
```

The reviewer emptied *every* verified field — a deliberate, internally consistent way of
marking "this is not a dispatch". Reading the empty string as a data-entry slip was wrong;
it is the correct answer to a record that should never have been created.

**This is punch-list #14 (PA page leakage) with concrete IDs.** The corpus holds at least
four non-dispatches captured as calls:

| Dispatch | Duration | Transcript |
|:--|--:|:--|
| `DISP-2026-E05DBD` | 10.2s | `Lunch, lunch is up, lunch is up.` |
| `DISP-2026-415E9F` | 8.2s | `Lunch is ready. Lunch is ready.` |
| `DISP-2026-E82B53` | 9.9s | `Medic 1, Medic 1, we're heading out.` |
| `DISP-2026-FEB541` | 10.0s | `Wilson, Wilson, you're good to go.` |

All are well under the ~25s double-round dispatch length. They contaminate any
incident-type or WER metric computed over the corpus unless excluded, and the only current
signal that they are not calls is that a human emptied their verified fields.

#### The domain model, recorded (CLAUDE.md §7.2)

No external standard governs the call-type vocabulary (`source='cfr_curated'`). The operator
supplied the model on 2026-08-23, and it is now a row in
[`docs/standards/README.md`](standards/README.md) and a comment block above `CALL_TYPES` in
[`config/vocab.py`](../backend/cfr_dispatch/config/vocab.py):

> A call type is a **main type** optionally followed by a **sub type**, joined by ` - `.
> A main type can stand on its own — 25 of 27 currently do — but most calls arrive with the
> expanded form, and the sub type is the operationally significant half.

**The two levels are deliberately not modelled separately.** One flat running list of complete
terms; ` - ` is the only structure. Do not split into main/sub categories, columns, or tables,
and do not offer or store a sub type alone — `Overdose` is not a call type,
`Medical Aid - Overdose` is.

Canonical spellings are operator decisions (`Breathing Problem` singular, `Smouldering`
Canadian). If E-Comm / Coquitlam Fire dispatch publishes an official list, it supersedes this.

#### The assist family: three distinct call types, one missing row — RESOLVED

**Correction to an earlier claim in this item.** `Public Assist`, `Lift Assist`,
`Medical Aid - Assist` and `Assist` were written up here as a naming inconsistency to be
rationalised. That was wrong. Operator ruling 2026-08-23: **they are separate call types,
not variants of one**, and the model does not require `Lift Assist` to be re-spelled
`Assist - Lift`. Nothing needed rationalising.

The actual defect was narrower and measurable: **bare `Assist` had no vocabulary row.**
`match_incident_type` can only return a vocabulary term, so dispatch saying
*"respond routine, assist, 1331 Green Bank Court"* fell through to `Unknown Incident`.

Added 2026-08-23. **Six calls recovered** from `Unknown Incident` to `Assist`:
`DISP-2026-587456`, `DISP-2026-266B57`, `DISP-2026-F1F328`, `DISP-2026-6547A7`,
`DISP-2026-511E01`, `DISP-2026-BF90E3`.

**This also clears one of the two records flagged above.** `DISP-2026-266B57` carried
`verified_incident = 'Assist'` and was flagged as an ambiguous data-entry error needing
operator disambiguation. It was neither — it was a **correct human answer to a vocabulary
gap**, and it now matches the parser exactly. Only the empty-string record remains flagged.

Worth generalising: a `verified_incident` with no vocabulary row is evidence of a **missing
term** first, and a reviewer mistake only second. The reviewer heard the call; the
vocabulary is the thing that was incomplete.

#### Two non-spoken terms retired — RESOLVED

Operator ruling 2026-08-23, after the corpus showed both had never been used:

* **`Vehicle Rollover` — retired.** `Motor Vehicle Incident - Rollover` **is** a spoken call
  type and stays; the bare form is not. Neither had ever been used and no transcript in the
  corpus contains "roll" at all, so the duplicate is gone before it could ever win a match.
* **`Public Assist` — retired.** Zero occurrences in any `raw_transcript`, `incident_type` or
  `verified_incident`. `Assist` and `Lift Assist` are the spoken forms and remain.

Both were retired via `is_active = FALSE`, not deleted, so the rows survive if either turns
out to be a real spoken form later. The script guards on live usage before retiring any term,
so re-running it is safe.

**64 active call types.** No regression: incident-type disagreement stayed at 4.5% (9/202).

#### A note for whoever extends this vocabulary next

Every change in this item was settled by **measuring the corpus, then asking the operator** —
never by reasoning from the term names. Three of this session's own conclusions were wrong and
were corrected the same way:

| Claim | Reality |
|:--|:--|
| `Smoldering` is a duplicate spelling to retire | It is the **only** form STT produces; retiring it would have broken 5 calls |
| `Assist` is an ambiguous data-entry error | A **correct** human answer to a missing vocabulary row; 6 calls recovered by adding it |
| Sub types are rare ("25 of 27 mains stand alone") | **77%** of calls carry one; 93% of `Medical Aid` |

A term's name tells you nothing about whether dispatch says it. The corpus does. Query
`raw_transcript` before adding, retiring, or merging anything here.

---

### 33. Legacy worked-example placeholders in the review form — one reached the training set
> **Status**: ✅ **Closed 2026-08-23.** Removed from
> `frontend/src/components/review/VerificationSidebar.jsx`; `lint:crash` and `npm run build`
> both pass. Not yet deployed to the kiosk.

Four fields in the HITL verification sidebar fell back to hand-written worked examples when
the parser produced no value:

| Field | Line | Legacy fallback |
|:--|:--|:--|
| Responding units | `:444` | `"e.g. E1, L1"` |
| Incident type | `:473` | `"e.g. Structure Fire"` |
| Address | `:511` | `"e.g. 2648 Sandstone Cres"` |
| Map grid | `:597` | `"e.g. 92"` |

**These are obsolete.** They predate the current design, in which the **system hypothesis is
itself the placeholder** and the reviewer presses **Ctrl+Space** to accept it — which is what
saves typing and prevents spelling drift. Once the real value sits in the background, a worked
example is dead weight.

#### How it was found — one of them reached the corpus

`DISP-2026-D106EB` (2026-07-13) was saved with **all three text examples as its verified
data**, an exact three-for-three match:

| Field | System output (matches the audio) | What was saved |
|:--|:--|:--|
| Address | `3030 Gordon Avenue Rain City Housing` | `2648 Sandstone Cres` |
| Incident | `Medical Aid - Overdose` | `Structure Fire` |
| Units | `M1` | `E1, L1` |

Its own `verified_transcript` says *"medic 1 respond emergency medical aid overdose 3030
gordon avenue rain city housing"* — so the system was right on every field and the
corrections were the form's examples. The record was rated **PERFECT**, carried
`include_in_training = true` and `model_updated = true`, and had therefore **already been
exported as ground truth** — teaching Whisper that audio describing an overdose on Gordon
Avenue transcribes to a structure fire on Sandstone Cres.

Attributed by the operator to an early-system reviewer mistake, from before the prefill
design; the record has since been corrected by hand. A scan of all 202 reviewed calls for
verified addresses whose street never appears in the transcript found **no other genuine
case** — the other three hits were `Crt`→`Court` suffix expansions.

The **mechanism was not reproduced**. The placeholders are conditional
(`selectedCall.incident_type || "e.g. …"`), and that call had a real incident type, so the
examples should not have been visible on that record at all.

#### Why it was worth removing rather than tolerating

* `2648 Sandstone Cres` matches exactly **one real parcel** in `public.parcels` — a real
  Coquitlam property, used as decorative example text in a form that writes to the
  ground-truth corpus.
* All four examples are *plausible dispatch values*. §6.1 and §6.5 exist because a
  plausible-looking wrong answer cannot be distinguished from a real one; this is that rule
  applied to a UI affordance rather than to a computed value.

#### Fix

A single `NO_SYSTEM_VALUE = '-- nothing parsed --'` constant replaces all four, carrying the
history above as an inline comment. When the parser produced nothing, the field now says so
instead of showing something that reads like data. The system-hypothesis placeholder and the
Ctrl+Space prefill are untouched — they were always the point.

---

### 34. Apparatus names collide with call-type names, turning STT damage into a confident wrong answer
> **Status**: ⚠️ **Open — found 2026-08-23 investigating `DISP-2026-A19179`.** **Confirmed**
> by re-running current code against the kiosk database. Characterised only; no fix applied.

**`Rescue` is both an apparatus type and a call type.** When STT garbles the incident
phrase, the apparatus name supplies a false call type — and does so at maximum score.

#### The worked case

`DISP-2026-A19179` (2026-07-29, 54.9s, rated FAILED). Ground truth
`Alarm Activated - High Risk`.

```
verified_transcript : ...respond emergency alarm activated high risk 1188 pinetree way near...
raw_transcript      : ...respondents way near glen drive and atlantic avenue...
```

STT collapsed *"respond emergency alarm activated high risk 1188 pinetree"* into
*"respondents"* — **the incident phrase is simply not in the transcript.** What remains is
the unit list, `engine 1 engine 2 rescue 2`, and `Rescue` is an active call type:

```
step-1 exact substring hits : ['Rescue']          <- "rescue 2" contains "rescue"
token_set_ratio('rescue', transcript) = 100       <- subset trap, would also fire
ratio('rescue', transcript)           =   7       <- what the name implies
```

Both matching stages independently produce `Rescue`. There is no path to `Unknown Incident`.

#### This is not a regression, and not the alias work

* Verified by re-running with `aliases={}`: still `Rescue`. The 2026-08-23 alias change is
  not the cause.
* The **stored** value is `Unknown Incident` (confidence 0.00) — correct at the time. The
  `Rescue` call-type row was created **2026-08-21**, three weeks *after* this call ran. The
  2026-08-21 vocabulary seeding introduced a term that collides with an apparatus name.

This is the §4.2 ghost-defect check run in the opposite direction, and worth noting as a
pattern: *older calls usually show already-fixed defects, but a vocabulary addition can make
a historical call newly wrong.* Re-running current code is what distinguishes the two.

#### Why it matters more than one call

Collisions between `UNITS_VOCABULARY` and `call_type`: **`Rescue`, `Hazmat 1`, `Hazmat 2`,
`Hazmat 3`.**

| Measure | n |
|:--|--:|
| Calls mentioning rescue apparatus (`rescue` + digit) | 64 |
| …verified as an incident **other** than `Rescue` (latent exposure) | 24 |
| …currently misclassified because of the collision | **1** |
| Calls whose true incident genuinely **is** `Rescue` | 7 |

Exposure is 1 of 24 because longest-first ordering saves it: when the real incident phrase
survives STT, the longer term (`Alarm Activated - High Risk`, 27 chars) is tested before
`Rescue` (6 chars) and wins. **The collision only bites when STT has already damaged the
incident phrase** — precisely when the system should be reporting `Unknown Incident`.

So the defect does not create wrong answers on its own. It **converts honest failures into
confident ones**, which is the more dangerous direction (CLAUDE.md §6.1). `Rescue` is a
legitimate call type on 7 verified calls, so it cannot simply be removed.

#### Fix, validated against the corpus but NOT applied

**Operator ruling 2026-08-23 supplied the rule**: the apparatus is always `Rescue 1`,
`Rescue 2` — never bare — and the call type is announced **after** the units. The
announcement template is:

```
[units] respond [routine|emergency] [CALL TYPE] [address] near [cross streets] ...
```

So the call type occupies the slot *after* `respond [mode]`, and everything before it is the
unit list.

**A first attempt keyed on "followed by a digit" and was wrong** — worth recording so it is
not retried. The call type is *also* followed by digits, because the address number comes
next: `"respond routine, rescue, 2968 glen drive"` reaches STT as `"Rescue 2, 968 Glen
Drive"`. Six of the seven true-`Rescue` calls have no bare `rescue` at all.

The rule that does work, tested over all 202 verified calls:

1. Match the call type only in the text **after** the `respond [mode]` marker.
2. A round with **no** `respond` marker is a **unit tail, not an announcement** — it has no
   call-type slot and is skipped entirely.
3. Across rounds, the **most specific** match wins (see below).

| | correct | wrong |
|:--|--:|--:|
| current (whole transcript) | 193/202 | 4.5% |
| proposed | 193/202 | 4.5% |

**One call changes**: `DISP-2026-A19179` goes from `Rescue` — confident and wrong — to
`Unknown Incident`, which is the honest answer for a transcript that never contained the
incident phrase. No regressions. Same accuracy, strictly better on the axis that matters
(CLAUDE.md §6.1: an unknown reported as unknown is a correct answer).

`split_rounds` already isolates the problem cleanly:

```
round 1: 'coquitlam engine 1 engine 2 rescue 2 respond way near glen drive ... map grid 82'
         -> has respond, nothing in the call-type slot -> Unknown  (correct)
round 2: 'coquitlam engine 1 engine 2 rescue 2'
         -> no respond marker: a unit tail -> skipped  (currently the source of 'Rescue')
```

#### Step 3 is not optional — it is punch-list #44's round-1 bias in miniature

Selecting the **first** non-Unknown round instead of the most specific one **breaks**
`DISP-2026-E792B0`:

```
round 1: 'medical aid epidominal pain'   <- STT garbled -> matches only 'Medical Aid'
round 2: 'medical aid abdominal pain'    <- correct     -> 'Medical Aid - Abdominal Pain'
```

Current code gets this right **by accident**: it matches against both rounds concatenated, so
round 2's correct wording is in the string and longest-first finds the qualified type. Any
move to per-round parsing must therefore choose the most specific answer across rounds, or it
reintroduces the round-1-wins defect described in
[`parser_audit_handoff.md`](parser_audit_handoff.md) §5 — which
[`pipeline/phase2.py:146`](../backend/cfr_dispatch/pipeline/phase2.py) still has for
addresses (`next(...)`, first candidate wins, unconditionally, across 201 double-round calls).

Related: the subset trap inventory in #19, and `Rescue`'s `token_set_ratio` of 100 above is
a fifth instance of it.

#### Numbering note — resolved

Two items were briefly numbered 33, written concurrently by two sessions. Operator ruling
2026-08-23: the **call-type vocabulary** item was renumbered to **#43**; "Legacy worked-example
placeholders…" keeps **#33**. Code comments citing "punch-list #33" in `config/vocab.py`,
`parser/call_types.py`, `api/routers/vocabulary.py`, the two vocabulary scripts and
`docs/standards/README.md` were updated to #43 in the same commit. The `#33` citation in
`review/VerificationSidebar.jsx` for the placeholder defect is correct and was left alone.

---

## 🖥️ Live Operation Batch, 2026-08-23

Eight items reported by the operator from one review session. Each was characterized
read-only against the working tree and the running kiosk; what was measured is stated.

### 34. Live overdose call still showed the green ROUTINE (Code 1) badge
> **Status**: ⚠️ **Open — duplicate symptom of #31, now confirmed in live operation.**

An overdose dispatch (an *emergency* response) rendered with the green border and the
`ROUTINE (CODE 1)` badge. This is exactly the failure #31 predicts: `response_type` never
reaches the kiosk, `isEmergency` is always false, so every call renders routine. **No separate
fix — #31 and #30 cover it.** Logged because it is the first live confirmation rather than a
database inference.

**Second, separate defect in the same sighting**: the kiosk announced an update that did not
exist. `triggerUpdateFlash` (`frontend/src/hooks/useKioskQueue.js:41-48`) sets
`isRecentlyUpdated` for 4 s, which renders the `⚡ UPDATED` badge
(`ActiveAlertBanner.jsx:46`). Nothing in that path compares the new payload to the old one, so
the badge fires on **any** re-delivery — and MQTT QoS 1 is at-least-once, so duplicate
delivery of an unchanged call is the contract, not an anomaly (see the kiosk idempotency note
in the handoff). The operator is told data changed when it did not.

**Fix direction**: fire the flash only when a field the operator can see actually differs —
address, incident, units, grid, talkgroup, coordinates — rather than on receipt. Worth
deciding *what counts as a change* before implementing, since "updated" is an operational
claim (§6.1: a badge asserting something that did not happen is fabricated state).

---

### 35. Google Street View panel still not working
> **Status**: ⚠️ **Open — cause identified, not yet confirmed on the kiosk.**

`frontend/src/components/kiosk/StreetViewPanel.jsx:8`:

```js
const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';
```

Two hard requirements, either of which produces the blank panel seen in the screenshot:

1. **The key must be present at BUILD time.** Vite inlines `import.meta.env.*` when
   `npm run build` runs — it is not read at runtime. The key lives in `frontend/.env.local`,
   which is **git-ignored** (CLAUDE.md §3.6) and therefore *not* synced by `git pull`. If the
   kiosk's `.env.local` lacks the key, every build there produces `apiKey = ''` and the panel
   renders empty no matter how many times the code is corrected locally.
2. **It needs WAN.** `:135` gates on `isOnline`, and `:301` loads
   `https://maps.googleapis.com/maps/api/js`. Street View cannot work offline, which is a
   standing exception to the §1 offline-first rule and is worth stating explicitly somewhere
   the next reader will find it.

**Next step is a two-minute check on the kiosk**, not a code change:
`grep -c VITE_GOOGLE_MAPS_API_KEY /home/tcfire/CFR-EVO-APP/frontend/.env.local`, then confirm
the built bundle actually contains the key. If it is missing, `scp` the file and rebuild.
**Not verified from here** — the check needs the kiosk.

---

### 36. Double-click-to-autofill removed from the review form
> **Status**: ✅ **Closed 2026-08-23.** Operator request: Ctrl+Space alone is working well.

Six `onDoubleClick={() => onPrefillField(...)}` handlers removed from
`VerificationSidebar.jsx` (transcript, units, incident, address, subaddress, map grid), and
the five tooltips advertising the gesture updated to
`"Click, or press Ctrl+Space, to import the system value"`.

The `Sys:` click affordance and the Ctrl+Space handler are untouched. `lint:crash` and
`npm run build` both pass. **Not yet deployed to the kiosk.**

---

### 37. Close button and timer timeout should not dismiss to the same place
> **Status**: ⚠️ **Open — noted for change by the operator 2026-08-23.**

Required behaviour:

| Dismissal | Should go to |
|:--|:--|
| **Call timer times out** | main map (EXPLORE) |
| **Operator presses Close** | back to whatever screen they were on |

Today both do the same thing, and the "drop to map" is *forced*. `App.jsx:52-54`:

```js
const activeIsLive = !!kioskState.activeCall && !kioskState.activeCall.isReview;
if (activeIsLive && returnMode !== 'EXPLORE') setReturnMode('EXPLORE');
```

That is a deliberate decision recorded on 2026-08-22 — a live call interrupting a review was
meant to return the crew to the map, not to an admin table. The reasoning is sound for a real
response; it is simply wrong for the operator doing review work, which is what this item
changes.

`useKioskQueue.js:177` `dismissActiveCall` is shared by **both** paths — the Close button
(`KioskView.jsx:226`) and the countdown (`:199`) call the identical function, so nothing
downstream can distinguish them.

**Fix direction**: give `dismissActiveCall` a reason (`'timeout' | 'manual'`); stop clobbering
`returnMode` on activation and instead capture the pre-call mode; on `'timeout'` set EXPLORE,
on `'manual'` restore what was captured. **Note this touches the live dispatch path**, so the
2026-08-22 intent must survive: a live call that interrupts a review and then *times out*
still lands on the map.

---

### 38. `DISP-2026-ACCF6D` routed to the wrong street — the parcel front point is on Pinetree Way
> **Status**: ⚠️ **Open — confirmed by spatial query. Likely systemic; see the estimate.**

Dispatch (2026-08-23 09:29) for **`1178 Heffley Cres`**, transcript
*"medical aid - chest pain, 1178 heffley crescent Number 1202"*, confidence 100. The operator
reports the route ends one street over.

**It does.** The dispatch used `lat/lng = 49.2807084, -122.7932581`, taken from the parcel
`front_lat` / `front_lng`. Measured against `public.roads`:

| Point | Nearest road | Distance |
|:--|:--|--:|
| **Stored front point** | **Pinetree Way** | **0.0 m** |
| Stored front point | Heffley Crescent | **109.2 m** |
| Parcel centroid | Pinetree Way | 56.8 m |
| Parcel centroid | Heffley Crescent | 59.4 m |

The stored "front" of a Heffley Crescent address sits **exactly on Pinetree Way**, 109 m from
the street it is addressed on. Heffley Crescent is not even among the three nearest roads.
OSRM is behaving correctly — it is being handed the wrong destination.

Note the centroid is not obviously better here (roughly equidistant), so this is not a
"use the centroid instead" fix; the front point is simply wrong.

**Scope estimate — read the caveats.** Over a random 1,500-parcel sample with a front point,
comparing the first token of the address street to the nearest road `roadname`:

| Result | Parcels |
|:--|--:|
| Front point within 30 m of its own named street | 1,058 |
| Marginal, 30–60 m | 139 |
| **Over 60 m from its own street** (the Heffley signature) | **173 (11.5%)** |
| Own street name not matched in `public.roads` | 130 |

⚠️ **This is an estimate, not a count.** The comparison uses only the *first word* of the
street name, so multi-word streets fall into the "not matched" bucket rather than being
judged; large institutional parcels may legitimately sit far from their named street; and no
sampled case other than Heffley was inspected individually. Extrapolating ~11.5% across 65,400
parcels would be roughly 7,500 affected — **do not quote that figure as fact** until a proper
audit runs.

**Next step**: a real audit of `parcels.front_lat/front_lng` provenance — how the front point
was derived, and whether it can be re-derived by projecting the parcel centroid onto the
nearest segment *of the road it is addressed on* rather than the nearest road of any name.
That is the same class of defect as the intersections rebuild: a plausible geometric shortcut
standing in for the real relationship (§6.2).

---

### 39. Review table: restore the verified value in the row, drop the pencil-and-legend
> **Status**: ⚠️ **Open — operator wants the earlier behaviour back, with a caveat below.**

The operator ask: *"I just want to see the accurate information in the row if it has been
verified, and if something was updated by a reviewer, make that obvious."*

**What it is now**: `SystemVsVerified` in `frontend/src/components/review/ReviewTable.jsx:17`
renders the **system** value plus a `✎` marker, with the verified value only in a `title`
tooltip, and a `✎ = corrected` legend in the column header (`:169-170`).

**What it was**: the column showed the **verified** value once `feedback_submitted` was set,
replacing the system value outright.

**Why it was changed — this matters, and it is documented at `ReviewTable.jsx:4-16`.** The
column is headed *"System Output"*, and swapping in the human answer meant a call whose
system address was **wrong** looked identical to one that was **right** — hiding the exact
disagreement the list is scanned to find. The stated reason for the tooltip rather than an
inline pair was column width: two values on one line clipped the address.

**So neither design is what the operator actually asked for.** The ask is *both*: show the
accurate (verified) value **and** make the correction obvious. That is achievable and is a
third design, not a revert:

* Render the **verified** value as the primary text when one exists.
* Style it distinctly — colour or weight — so a corrected row is obvious at a glance without
  a legend to decode.
* Keep the **system** value reachable (tooltip, or the review panel, which already shows both
  side by side when a row is selected).
* Consider renaming the column, since it would no longer be "System Output".

**Recommendation**: do not simply revert. Reverting reintroduces the defect the comment
describes — a wrong system answer becoming invisible — which is a §6.6-style honesty problem
in the one view used to audit accuracy. **Confirm the design with the operator before
building it**, in particular whether the column should remain system-first or become
verified-first with the system value on hover.

---

### 40. Street basemap has no tiles above zoom 18 — but the reported symptom did not reproduce
> **Status**: ⚠️ **Open — partially characterized; needs the exact location from the operator.**

Reported: *"Zoom 17 and greater, on map mode in Austin's north area is showing blank."*

**Measured** against the live tile server (`http://100.95.146.94:8081`), tileset metadata:

| Layer | minzoom | maxzoom | Format |
|:--|--:|--:|:--|
| `street` | 12 | **18** | png |
| `street_nolabels` | 12 | **18** | png |
| `satellite` | 12 | 20 | jpg |
| `cadastral` | 14 | 20 | png |

Above z18 the street layers return a **116-byte empty PNG**, not a 404. Probed around Austin
Heights (49.2505, −122.86) and north of it (49.262, −122.86):

```
z17  satellite=14858b  street=7406b     <- both have content
z18  satellite=17760b  street=1744b     <- both have content
z19  satellite=14806b  street=116b      <- street empty
z20  satellite=12602b  street=116b      <- street empty
```

**I could not reproduce blank at z17.** Both layers return real tiles at z17 and z18 at the
coordinates probed. The street layers do die at **z19+**, which is a real limitation but does
not match the reported zoom.

Further, the frontend is configured correctly for it: `MapConstants.js` sets
`maxNativeZoom: 18` on `GREY`/`DARK`/`OSM`/`VOYAGER` and `20` on `SATELLITE`, and
`MapLayers.jsx:100` passes it through to the Leaflet layer — so Leaflet should **upscale** the
z18 tile past 18 rather than request an empty z19. On that configuration the symptom should be
*blurry*, not *blank*.

**Open questions for the operator**: which base layer was selected (satellite, street, grey,
dark), and roughly which coordinates? "Austin's north area" is ambiguous, and the answer
determines whether this is a tile-coverage gap in a specific spot, an overzoom bug, or the
116-byte blank tile defeating the Leaflet upscale in a way the config implies it should not.
A screenshot with the zoom indicator visible would settle it.

---

### 41. `629 Cottonwood Ave` is absent from `public.parcels`
> **Status**: ⚠️ **Open — confirmed. A data gap, not a search bug.**

The operator could not find `629 Cottonwood Ave` in the search bar. It is not there to find:
723 parcels match `%Cottonwood%`, and **zero** match `629 Cottonwood%`.

The neighbours exist, and the gap is a run of consecutive odd numbers:

```
... 620, 622, 625, 628, [627, 629, 631 MISSING], 633, 635, 637, 639 ...
```

So the search bar is reporting the database honestly. Either the addresses are genuinely
absent from the City of Coquitlam `Addresses.shp` import, or they were dropped during
`backend/scripts/import_parcels.py`. A run of three consecutive missing odd numbers on one
side of the street suggests a real-world cause (a consolidated lot, a redevelopment, a
renumbering) at least as strongly as an import defect — **do not assume the importer is
broken without checking the source shapefile.**

Per §6.2 this belongs in the data, not in application code: if the addresses are real, the fix
is a parcel import correction, never a string-match special case in the geocoder.

**Next step**: check whether 627/629/631 Cottonwood Ave exist in the source `Addresses.shp`,
and whether the operator can confirm from local knowledge that 629 is a real, currently
addressable property.

---

## 🔁 Batch follow-up, 2026-08-23 (operator screenshots + kiosk probes)

### 40 (revised). Street AND satellite basemaps stop at zoom 17 across western Coquitlam
> **Status**: ⚠️ **Open — REPRODUCED and localised. Wider than first characterized.**
> This supersedes the "could not reproduce" note in #40 above, which was **wrong**: the first
> probe ran against coordinates ~1.5 km east of the affected area and a `while`-loop curl
> failure printed `0b` for every layer, which masked the result. Both errors are recorded
> rather than overwritten.

The operator's screenshot shows Explore mode, **Street Map** basemap, **zoom 17.0**, around
Cottonwood Ave / Regan Ave / Marshall St (Austin Heights). Parcel outlines and address labels
render on pure black — that is the **cadastral overlay alone**, with no basemap underneath.

**Measured** at 49.2588, −122.8843 (a real parcel front point from `public.parcels`):

| Zoom | `street` | `satellite` | `cadastral` |
|--:|--:|--:|--:|
| 15 | 24,805 b | — | — |
| 16 | 16,644 b | 24,452 b | — |
| **17** | **116 b (empty)** | **116 b (empty)** | 25,761 b |
| **18** | **116 b (empty)** | — | — |

A 116-byte PNG is the tile server's empty tile. **Both the street and satellite archives stop
at z16 here, while cadastral continues** — exactly the black-with-parcels rendering reported.

**The gap is a clean vertical cut, identical in both archives.** Scanning west→east along
z17 y=44869:

```
x=20780..20801  116 b   (empty)
x=20802         8,419 b (content)   <- boundary, lng ≈ -122.8656
x=20804..20830  content
```

Identical boundary for satellite (`x≤20801` empty, `x=20802` = 20,331 b), and the same cut at
z18. A north–south scan at x=20795 is empty at every latitude tested (y = 44820…44920), so
this is a longitude clip, not a patchy hole.

**Everything west of roughly −122.866 has no basemap above zoom 16** — Austin Heights,
Maillardville and Burquitlam, i.e. a populated strip roughly 4 km wide running the full height
of the city. Crews zooming in on any west-side address see parcel outlines on black.

**The declared metadata is wrong, which is why nothing detected this.** Both archives report:

```
street     minzoom 12  maxzoom 18  bounds [-123.04, 49.15, -122.6, 49.48]
satellite  minzoom 12  maxzoom 20  bounds [-123.04, 49.15, -122.6, 49.48]
```

The declared western bound of −123.04 overstates actual z17+ coverage by ~0.17° of longitude.
Because the metadata claims the coverage exists, the frontend has no way to know it does not,
and `maxNativeZoom` cannot help — the tiles are *within* the declared range and simply empty.

**This is not a frontend defect.** `MapConstants.js` (`maxNativeZoom: 18` street / `20`
satellite) and `MapLayers.jsx:100` are correct. The fix is in the MBTiles build: re-crawl the
western extent at z17–z20 for both archives, and correct the declared bounds so the two agree.
See the `mbtiles-tile-server` skill.

**Recommend raising the priority.** Austin Heights is a dense residential area, and losing the
basemap at exactly the zoom used to identify a specific property is an operational gap, not a
cosmetic one. Cadastral coverage masks it just enough to look intentional.

---

### 41 (revised). `629 Cottonwood Ave` exists on the map but not in `public.parcels`
> **Status**: ⚠️ **Open — confirmed as an import gap, not a real-world absence.**

The operator points out that 629 **is** labelled as a parcel on the cadastral layer, and the
screenshot confirms it: one parcel carries **two** labels, `625` and `629`.

That resolves the question left open above. The parcel is an **address range, 625–629**, and:

* the **cadastral MBTiles** (built from the City data) renders both numbers;
* **`public.parcels` holds only `625 Cottonwood Ave`** (49.2595007, −122.8843437). There is no
  `629` row, so the search bar cannot find it.

So the earlier suggestion that a consolidated lot or renumbering explained it was **wrong** —
the address is real and the City data has it. Two derivations of the same municipal source
disagree, and the one the search reads is the lossy one.

**This is very likely not a single missing address.** Any parcel carrying an address *range*
would lose every number except the one imported. `public.roads` already stores
`left_begin/left_end/right_begin/right_end`, so range semantics exist elsewhere in the schema
— worth checking whether `Addresses.shp` carries a range per parcel that
`backend/scripts/import_parcels.py` collapses to a single value.

**Next step**: inspect the source `Addresses.shp` attributes for 625 Cottonwood Ave, determine
whether ranges are represented, and count how many parcels are affected before deciding on a
fix. Per §6.2 the correction belongs in the import, never as a geocoder special case.

---

### 39 (revised). Review table now shows verified data, marked
> **Status**: ✅ **Closed 2026-08-23** to the operator's specification. Not yet deployed.

Operator direction: *"If verified data is different from system data, I want it marked (by
bolding, or a slight color change), and have a hover over show system original hypothesis."*

`SystemVsVerified` in `frontend/src/components/review/ReviewTable.jsx` now:

* renders the **verified** value when it differs from the system value, in **amber and bold**,
  with `title` = *"Corrected by reviewer. System originally produced: …"*;
* renders the system value plainly when there is no correction, or the correction is only
  whitespace/case.

The column header changed from **"System Output — ✎ = corrected"** to **"Call Data — amber =
reviewer corrected"**, since it no longer shows system output unconditionally.

This is the third design, not a revert, and the full history is preserved in the code comment:
the original showed verified values *unmarked* (hiding disagreement), the second showed system
values with a pencil (burying the accurate address behind a hover and needing a legend). The
current one makes the row read true at a glance while keeping the correction visible and the
system hypothesis one hover away. `lint:crash` and `npm run build` pass.

---

### 35 (revised). Street View: the API-key hypothesis was wrong
> **Status**: ⚠️ **Open — cause NOT yet identified. Needs the kiosk browser console.**

Checked directly on the kiosk. **All three prerequisites are satisfied**, so the theory
recorded in #35 above is withdrawn:

| Check | Result |
|:--|:--|
| `frontend/.env.local` present | yes — 285 bytes, dated Aug 9 |
| `VITE_GOOGLE_MAPS_API_KEY` set in it | yes |
| Key baked into the built bundle | yes — found in `dist/assets/MapBoard-*.js` |
| `maps.googleapis.com` reachable from the kiosk | yes — HTTP 200 in 0.17 s |
| Build freshness | `dist/index.html` 2026-08-23 12:26 (today) |

So the key is present at build time, the SDK host is reachable, and the bundle is current.
The blank panel is something else.

**What the code does when the key IS present** (`StreetViewPanel.jsx:466-487`): it renders an
*empty* `div` and relies on the Google SDK to inject the panorama into `containerRef`. The
`<iframe>` fallback is only rendered when `!apiKey` or `sdkError`. So any silent failure of
`new google.maps.StreetViewPanorama(...)` leaves a genuinely empty container — and the
skeleton loader is cleared unconditionally by a 3.5 s timer (`:283-285`) whether or not the
panorama ever mounted. **A failed load and a successful one look identical to the operator.**

Plausible causes, none verified: the Maps JS API key lacking Street View / billing
entitlement (Google returns an error to the console, not to the callback), the newer SDK
loader requirements, or `hasCoords` false for the call in question.

**Next step needs the operator**: open the kiosk browser console (F12) with a call active and
capture any `maps.googleapis.com` errors. That is the fastest path — the in-app browser cannot
drive an MQTT-driven kiosk view.

**Worth fixing regardless of cause**: the 3.5 s timer that clears the loading state without
checking whether the panorama mounted. An unmounted panorama should surface an explicit
"Street View unavailable" state rather than an indistinguishable black rectangle (§6.1 — the
failure is currently invisible).

---

### 35. "Near roads" stopped being recorded on 2026-08-21 — Phase 2 rebuilds `target` and drops `cross_streets`
> **Status**: 🔴 **Open — live regression, found 2026-08-23.** Reported by the operator
> ("we've seemed to have dropped recording near roads completely") and **confirmed** against
> the kiosk database and the working tree. Root cause identified; no fix applied.

#### The regression is real and dated

| Date | Calls | Said "near" | `intersection` recorded |
|:--|--:|--:|--:|
| 2026-08-18 | 9 | 9 | 9 |
| 2026-08-19 | 8 | 7 | 7 |
| 2026-08-20 | 10 | 9 | **9** |
| **2026-08-21** | 10 | 6 | **1** |
| 2026-08-22 | 19 | 16 | **3** |
| 2026-08-23 | 13 | 12 | **1** |

The operator's own HITL notes track the changeover precisely: 2026-08-20 reads
*"Spelling mistakes for near roads"* and *"Misspelled one of the near roads"* — captured, just
misspelled. From 2026-08-21 the notes read *"Missed near roads"*.

#### It is NOT a parser failure

The parser still extracts the near roads correctly. Replaying `DISP-2026-ABD874` (2026-08-23)
through current code:

```
addr='3098 Guildford Quay'  cross_street_1='Eastwood Street'  cross_street_2='Pipeline Road Rd'
```

`build_dispatch_payload` also does the right thing, writing them at
[`payload_builder.py:203`](../backend/cfr_dispatch/pipeline/payload_builder.py):

```python
target_cross_streets = [s for s in [cross_street_1, cross_street_2] if s]
...
"cross_streets": target_cross_streets
```

#### Root cause: Phase 2 rebuilds `target` from a hand-picked subset

[`phase2.py:190`](../backend/cfr_dispatch/pipeline/phase2.py) and again at `:272` construct a
**new** `target_payload` rather than updating the existing one, then PATCH it over the record:

```python
target_payload = {
    "address": p1_address, "lat": ..., "lng": ..., "rings": ...,
    "map_grid": p2_grid, "radio_channel": p2_channel,
}
if p1_target.get("subaddress"):   target_payload["subaddress"] = ...
if p1_target.get("tone_name"):    target_payload["tone_name"] = ...
if p1_target.get("intersection"): target_payload["intersection"] = ...
```

`cross_streets` is not on the carry-forward list, so the PATCH **destroys** whatever Phase 1
wrote. Confirmed against stored records — the surviving key set matches this dict exactly:

```
address, lat, lng, map_grid, radio_channel, rings, subaddress, tone_name
```

`routing_metrics`, `location_type`, `resolution_note` and `requested_address` are lost the same
way. Only **4** dispatches in the entire corpus have ever carried a `cross_streets` key, and
only **1** has a non-empty one.

#### Why it surfaced on 2026-08-21 and not earlier

Two changes had to line up:

1. **Before 2026-08-21** the near roads rode in the `intersection` field, which *is* on the
   carry-forward list, so they survived — semantically wrong but functional:
   ```
   addr='1535 Parkway Blvd'  intersection='Salal Cresson and Sunridge'
   addr='2968 Glen Dr'       intersection='Pacific Street and The High St'
   ```
2. **On 2026-08-21** the geocoder work correctly stopped overloading `intersection` for civic
   addresses. `intersection` now means what it says — set only when the location genuinely
   *is* a junction (`'Barnet Hwy & Lougheed Hwy'`).

That fix was right. It exposed a latent defect: the field that *should* carry near roads was
already being thrown away, and nothing noticed because the wrong field was masking it.

**This is the shape worth remembering.** A correct fix in one module surfaced silent data loss
in another. The regression is not in the 08-21 change; it is in the Phase 2 rebuild, which has
been lossy since `cross_streets` was introduced (`0ec3061`, 2026-08-20).

#### Suggested fix, not applied

Merge into the existing target rather than replacing it — `{**p1_target, **updates}` — so a
field added to Phase 1 is not silently dropped by Phase 2. An explicit allowlist that must be
edited every time a field is added is the mechanism that produced this defect.

Operationally, near roads are how crews confirm they are on the right block, and the two-tier
warning of CLAUDE.md §5 does not cover a *silently missing* corroboration field.

---

### 44. Round 1 wins the address unconditionally — Phase 2 never compares the two rounds
> **Status**: ⚠️ **Open — measured 2026-08-23.** **Confirmed live**, not historical: split by
> month, it still costs ~5% of double-round calls in 2026-08. Characterised only; no fix
> applied. Related to `parser_audit_handoff.md` §5, which flagged this as a lead but never
> sized it.

**The dispatcher announces every call twice, and the system reads only the first answer.**

#### Mechanism

`all_candidates` is built by iterating rounds in order
([`phase2.py:113`](../backend/cfr_dispatch/pipeline/phase2.py)):

```python
announcements = split_rounds(transcript, units_vocab)
for text in announcements:
    all_candidates.extend(parse_dispatch_announcement(text, units_vocab))
```

then the address is selected at [`phase2.py:146`](../backend/cfr_dispatch/pipeline/phase2.py):

```python
p2_candidate = next((d for d in all_candidates if d.address or d.intersection), None)
```

The **first round that yields any address wins.** There is no scoring, no comparison, no
fallback. Round 2 is never consulted once round 1 produced something — even when what it
produced is `29883 Robson Dr`.

Note `p2_grid` and `p2_channel` (`:164`, `:167`) use the same `next(...)` idiom, but for those
it is benign: they skip nulls, so any round holding the value supplies it. The address is
different because a *corrupted* address is still an address, and it short-circuits the search.

#### Measured against ground truth, by month

Double-round verified calls, parsing each round separately and asking which agrees with
`verified_address`:

| Month | rounds agree | R1 right | **R2 right (bias hurts)** | neither | single round |
|:--|--:|--:|--:|--:|--:|
| 2026-07 | 93 | 51 | **8** | 38 | 15 |
| 2026-08 | 63 | 20 | **5** | 11 | 0 |

**~5% of double-round calls in 2026-08.** Unlike the map-grid figure corrected in
`parser_audit_handoff.md` §4.3a, this one survives the date split.

#### The failure mode is consistent: round 1 has digit or street corruption

```
29883 Robson Dr                   ->  2983 Robson Dr        extra digit
303030 Gordon Ave                 ->  3030 Gordon Ave       repeated digits
3025 Loheed Hwy                   ->  3025 Lougheed Hwy     street mis-heard
2991 Lockheed Hwy                 ->  2991 Lougheed Hwy     street mis-heard
47 Lougheed Hwy                   ->  2747 Lougheed Hwy     house number truncated
2615 Harrier Drive Nearcastoral…   ->  2615 Harrier Dr       "near" swallowed into the street
```

Affected: `DISP-2026-E5D4EC`, `DISP-2026-9B16EB`, `DISP-2026-4C4BAF`, `DISP-2026-070BC2`,
`DISP-2026-D239B1` (2026-08); `DISP-2026-4F427E`, `DISP-2026-76A4BF`, `DISP-2026-1D8368` and
others (2026-07).

#### ⚠️ Do NOT "fix" this by preferring round 2

Round 1 is right and round 2 wrong in **20** of the 2026-08 cases, against 5 the other way.
Preferring round 2 trades 5 wins for 20 losses. Preferring *either* round positionally is the
same class of mistake as the original.

#### Suggested fix: let the parcel data decide, not the round order

The geocoder already knows which candidate is real. `29883 Robson Dr` is absent from
`public.parcels`; `2983 Robson Dr` is present. `3025 Loheed Hwy` is not a Coquitlam street;
`3025 Lougheed Hwy` is. So the selection rule should be **"prefer the candidate that resolves
to a real parcel"**, using the authority that already exists rather than a positional
heuristic (CLAUDE.md §6.2 — prefer the authoritative source over a local model).

This should also recover part of the **11** "neither" cases, where round 1 won with a corrupted
address and neither round matched the verified string exactly.

`validate_address_exists` in
[`address_resolver.py`](../services/gis/src/gis_service/address_resolver.py) is the obvious
hook — noting it currently shares the no-`ORDER BY` tie-break bug inventoried in
`parser_audit_handoff.md` §6, which should be settled first.

#### Before implementing

This is a more invasive change than the vocabulary and payload fixes. Build the replay
harness as a regression gate first — `trace_geocode_corpus.py` already replays the geocoder;
the missing half is the parser-side equivalent (`parser_audit_handoff.md` §3). Any candidate
rule must be scored over the full corpus **split by month**, because a pooled figure here
would be dominated by 2026-07 STT damage that no longer occurs.

---

## 🧾 Import Completeness Audit, 2026-08-23

Run because the operator was worried that **imports are silently dropping data** — #41
(a missing address) and a parallel report of missing `public.roads` entries.

**Headline: both importers are faithful to their sources. The losses are real, but they are
deliberate filters and stale source data, not import bugs.** One filter is a genuine
operational problem and is the largest finding in this batch.

---

### 42. The roads import silently discards 242 road segments, including 45 streets that 1,918 parcels are addressed on
> **Status**: ⚠️ **Open — confirmed against source and database. This is the answer to the
> "missing `public.roads` entries" report.**

`backend/scripts/import_gis_data.py`, `step2_import_roads` (~`:228`):

```python
status = props.get("STATUS")
if status and str(status).strip().upper() != "OPERATING":
    continue
```

**The arithmetic reconciles exactly, so nothing is lost accidentally:**

| | |
|:--|--:|
| `road_centre_lines.geojson` features | 3,456 |
| Dropped — `STATUS != 'OPERATING'` | **242** |
| Dropped — missing `FULLNAME` | 0 |
| Expected in `public.roads` | 3,214 |
| **Actual `public.roads` rows** | **3,214** ✅ |

The 242 break down as **170 PRIVATE, 71 MOT, 1 METRO**, and `public.roads` contains exactly
one distinct status: `OPERATING`.

#### Why this matters operationally

**68 named roads exist *only* as non-OPERATING segments and are therefore entirely absent
from `public.roads`** — not thinned, absent. Among them:

* **`Highway #1`** (Trans-Canada) — 7 MOT segments, 0 OPERATING. Confirmed: `SELECT count(*)
  FROM public.roads WHERE fullname ILIKE '%Highway #1%'` returns **0**.
* **`Mary Hill By-Pass Road`** — 4 MOT segments, 0 OPERATING. Also **0** rows.
* ~60 strata/private residential streets.

Partial losses too, where a road survives but loses segments: `Lougheed Highway` 8 of 45,
`United Boulevard` 6 of 22, and **`Highway Ramp` 41 of 44**.

**The residential side is the serious part.** Cross-referencing `public.parcels.street`
against `public.roads.roadname`:

| | |
|:--|--:|
| Distinct streets in `public.parcels` | 997 |
| **Streets with no matching road** | **45** |
| **Parcels addressed on those streets** | **1,918** |

Largest affected streets:

| Street | Parcels |
|:--|--:|
| Princess | **568** |
| Silver Springs | **359** |
| Riverbend | 227 |
| Whisper | 193 |
| Bluff | 63 |
| River | 60 |
| Bow | 55 |
| Flynn | 50 |

Verified in the source: `Princess Crescent (PRIV)`, `Silver Springs Boulevard`,
`Riverbend Drive`, `Whisper Way`, `Oxbow Way (PRIV)`, `Parkland Drive (Private)` are all
present in `road_centre_lines.geojson` and all carry `STATUS = PRIVATE`. They are strata
roads — **but people live on them and crews respond to them.** A dispatch to
`2980 Princess Cres` is in the corpus already.

**What still works**: direct address geocoding, because `public.parcels` holds these
addresses with coordinates. **What does not**: anything road-derived — `public.intersections`
(derived from `public.roads`, so no junction on these streets can exist), "near \<road\> and
\<road\>" matching, cross-street validation, and street-name vocabulary.

#### Recommendation

Do not simply delete the filter — `STATUS` is meaningful municipal data and MOT/PRIVATE
segments may need different routing treatment. Instead **import all statuses and keep the
`status` column populated**, letting consumers decide. `public.roads.status` already exists
and currently holds one value for every row, which is the tell that a distinction was
flattened at import rather than preserved.

Requires a re-import and an `public.intersections` re-derivation. **Confirm with the operator
before running** — it changes the geocoder's street vocabulary.

---

### 41 (closed). `629 Cottonwood Ave` — the parcel import is correct; the shapefile does not have it
> **Status**: ✅ **Closed 2026-08-23 as "not an import defect."** The underlying discrepancy is
> real and is recorded below, but nothing in this project is losing it.

**The parcel import reconciles exactly**, read straight from `Addresses.dbf` (no GDAL locally,
so via a minimal DBF reader):

| | |
|:--|--:|
| Records in `Addresses.shp` | 69,708 |
| Blank `ADDRESS` | 167 |
| Exact duplicate `ADDRESS` strings | 4,141 |
| **Unique = expected import** | **65,400** |
| **Actual `public.parcels` rows** | **65,401** |

That is a clean reconciliation. (The extra row is 1 above the source; worth a glance but it is
a single record, not a pattern.)

**`629 Cottonwood Ave` is not in `Addresses.shp` at all.** Searching the source for
Cottonwood house numbers 625–633 returns exactly two records: `625 Cottonwood Ave` and
`633 Cottonwood Ave`, both `STATUS = Active`. So the earlier suggestion that the importer
collapses address *ranges* was **wrong** — there is no range to collapse.

**Where the map label comes from.** The cadastral layer is not rendered from a shapefile —
`backend/scripts/crawl_cadastral_tiles.py` pre-caches tiles from the **City of Coquitlam
ArcGIS Cadastral MapServer**, layers `[0: Road Labels, 1: Address Labels, 16: Parcels]`. So
`629` is drawn by the City's own live map service.

**The two municipal sources disagree**, and this project faithfully reflects both:

| Source | Has 629? |
|:--|:--|
| `Addresses.shp`, extract dated **2025-06-22** | **No** |
| ArcGIS Cadastral MapServer address labels (crawled later) | **Yes** |

The most likely explanation is simply that the shapefile extract is **over a year old** and
the address was created after it. That is worth acting on independently of 629: the whole
parcel layer is running on a 2025-06-22 snapshot.

**Next step**: re-pull `Addresses.shp` from the Open Data portal and re-run the import — it is
a non-destructive `ON CONFLICT (address) DO UPDATE` upsert that preserves operational data
(pre-plans, lockbox notes, Street View headings), so it is low risk. See the
`gis-pipeline-sync` skill. Then confirm 629 appears.

---

### 40 (quantified). The basemap gap covers 28% of the city's parcels
> **Status**: ⚠️ **Open — extent now measured. Recommend raising priority.**

Adding numbers to the coverage cut at longitude ≈ **−122.8656** established earlier (street
*and* satellite both empty above z16 west of it, cadastral unaffected):

| | |
|:--|--:|
| Parcels with coordinates | 65,401 |
| **Parcels west of the cut** | **18,568** |
| **Share of the city** | **28.4%** |
| Distinct emergency response zones affected | **20** |

So **more than a quarter of Coquitlam's addressed properties have no basemap above zoom 16**,
spanning 20 response zones — Austin Heights, Maillardville, Burquitlam. At the zoom used to
identify a specific driveway or roofline, crews see parcel outlines on black.

This is a tile-build defect, not a frontend one: `MapConstants.js` and `MapLayers.jsx` are
configured correctly, and the archives' own declared bounds (`-123.04 … -122.6`) overstate
their real coverage, so nothing in the system can detect the gap. Fix is a re-crawl of the
western extent at z17–z20 for `satellite` and `street`/`street_nolabels`, plus corrected
metadata bounds. See the `mbtiles-tile-server` skill.

---

### Method note

`Addresses.shp` and `road_centre_lines.geojson` are git-ignored and were read **locally**, as
standalone scratch checks (CLAUDE.md §3.2). GDAL/fiona are not installed on the dev machine,
so the DBF was parsed directly with a ~40-line reader rather than geopandas — worth knowing
before anyone plans shapefile work here. Tailscale SSH lapsed mid-session and needs browser
re-auth, so kiosk-side checks in this batch were done over HTTP to the tile server and via the
`cfr-postgres` MCP connection instead.

---

### 40 (root cause). The tile compiler narrows its bounding box above z16, and then declares the wide one anyway
> **Status**: ⚠️ **Open — ROOT CAUSE FOUND 2026-08-23. Confirmed: the measured cut matches
> the constant to four decimal places.**

`backend/scripts/compile_mbtiles.py:397-406` downloads a **different bounding box per zoom
tier**:

```python
for z in range(min_z, max_z + 1):
    if z <= 16:
        # Full regional bounds for Zooms 12-16
        z_tiles = calculate_tiles(REGIONAL_MIN_LAT, REGIONAL_MIN_LON, ...)      # west -123.04
    elif z <= 18:
        # Coquitlam operational corridor for Zooms 17-18
        z_tiles = calculate_tiles(COQUITLAM_MIN_LAT, COQUITLAM_MIN_LON, ...)    # west -122.865
    else:
        # Urban Core & Apparatus Bay Stations 1-4 Corridor for Zooms 19-20
        z_tiles = calculate_tiles(URBAN_CORE_MIN_LAT, URBAN_CORE_MIN_LON, ...)  # west -122.870
```

| Constant | West | East | South | North | Applies to |
|:--|--:|--:|--:|--:|:--|
| `REGIONAL_*` | **−123.04** | −122.60 | 49.15 | 49.48 | z12–16 |
| `COQUITLAM_*` | **−122.865** | −122.685 | 49.208 | 49.385 | z17–18 |
| `URBAN_CORE_*` | **−122.870** | −122.730 | 49.240 | 49.340 | z19–20 |

**`COQUITLAM_MIN_LON = -122.865` (`:59`) is the defect.** The measured boundary was
**−122.8656** (tile x=20801 empty, x=20802 content at z17). That is the same line to four
decimal places — it is this constant, not a crawl failure, not a corrupted archive.

Every observation now follows from it:

* z16 renders at Cottonwood Ave (−122.884) — inside `REGIONAL`. **Measured 16,644 b.** ✅
* z17 is empty there — outside `COQUITLAM`. **Measured 116 b.** ✅
* `street` and `satellite` share the **identical** boundary because they share this function,
  differing only in `max_zoom`. ✅
* `cadastral` is unaffected — it is built by a *different* script,
  `crawl_cadastral_tiles.py`, whose `DEFAULT_MIN_LON = -122.92`. That is why the operator's
  screenshot shows parcels and labels on black: the only layer with western high-zoom
  coverage is the overlay. ✅

#### The constant contradicts the project's own definition of the city

The comment at `:57` calls it *"Coquitlam Municipal Core Bounds"*, but Coquitlam extends west
to roughly **−122.93**. Two other places in this codebase already say so:

* `crawl_cadastral_tiles.py` uses **−122.92**.
* **CLAUDE.md §5** defines out-of-bounds as `lng < -122.92`, via `isWithinCoquitlam()`.

So the kiosk considers −122.90 to be **inside** the city and will happily route there and
suppress the out-of-bounds card — while having no basemap above z16 for it. The bounds check
and the tile build disagree about where Coquitlam is.

#### The declared metadata hides it

`compile_mbtiles.py:142` writes the metadata `bounds` for **every** layer as the *regional*
box:

```python
"bounds": f"{REGIONAL_MIN_LON},{REGIONAL_MIN_LAT},{REGIONAL_MAX_LON},{REGIONAL_MAX_LAT}",
```

The archive therefore advertises coverage from −123.04 while only holding −122.865 above z16.
This is the reason nothing detected the gap: the frontend's `maxNativeZoom` is correct and has
no way to know, `mbtileserver` serves a 116-byte empty tile rather than a 404, and the
metadata says everything is fine. **A layer that reports coverage it does not have is the same
defect class as §6.1** — a confident wrong answer beats a visible unknown.

#### Scope, measured against `public.parcels`

| Missing above | Parcels affected | Share of city |
|:--|--:|--:|
| **z16** (outside `COQUITLAM` box) | **18,735** | **28.6%** |
| **z18** (outside `URBAN_CORE` box) | **21,023** | **32.1%** |

So roughly **a third of the city has no basemap at the zoom used to pick out a driveway,
roofline or hydrant** — Austin Heights, Maillardville, Burquitlam, plus the northern and
eastern edges. 20 emergency response zones are affected.

#### Fix

1. **Correct the constants.** `COQUITLAM_MIN_LON` should be ≈ **−122.93** to match
   `isWithinCoquitlam()` and the cadastral crawl, and the other three `COQUITLAM_*` bounds
   should be reviewed against the real municipal boundary at the same time. Give them a
   provenance comment naming the source (§6.3) — the current values have none.
2. **Reconsider the `URBAN_CORE` tier for z19–20.** A 0.14° × 0.10° box is a small fraction of
   the city, and it excludes 32% of parcels from the highest-detail imagery. If it exists to
   bound archive size, that trade-off should be stated and sized, not implied.
3. **Write honest metadata.** The `bounds` value must describe what the archive actually
   contains. If coverage differs per zoom, the declared bounds should be the *narrowest*
   tier, not the widest — under-promising is safe, over-promising is what produced this.
4. **Re-crawl** the western extent at z17–20 for `satellite`, `street` and `street_nolabels`,
   then checkpoint to `journal_mode = DELETE` per CLAUDE.md §1 before the read-only mount.

**Worth doing regardless of the re-crawl**: give the kiosk a visible signal when a base layer
has no tile, rather than rendering black. The operator diagnosed this as "blank" and could not
tell it apart from a failed tile server.

See the `mbtiles-tile-server` skill for the compile and checkpoint procedure.

---

### 45. Geocoder harness needs a review pass before its numbers are trusted again
> **Status**: ⚠️ **Open — raised 2026-08-26** while building the parser harness. Not a defect
> in the geocoder; a staleness risk in the tool used to measure it. See
> [`docs/qa_harnesses.md`](qa_harnesses.md) §3.

`backend/scripts/trace_geocode_corpus.py` (committed `8d00ea3`) replays verified dispatches
through the live geocoder and records which of seven resolver steps answered. Four reasons its
output should not be quoted until it is re-checked:

1. **It predates the 2026-08-21/23 geocoder rewrite.** Nine commits landed on `services/gis/`
   in that window — map-grid tie-breaking, near-road ranking, bounded civic substitution,
   honest centroid labelling. Whether the seven-step ladder it wraps is still the seven steps
   that run has not been verified.
2. **No date split.** Its headline "30 of 34 stored defects already remediated" is a historical
   statement. Every pooled rate over this corpus is suspect (#5 below, and `qa_harnesses.md` §5).
3. **No cosmetic bucketing.** Reviewers use `verified_address` for suffix expansion and unit
   stripping, which inflates a naive error rate roughly 3×. `backtest_parser_corpus.py` buckets
   EXACT / COSMETIC / WRONG; this should adopt the same.
4. **It measures the geocoder's own output** (`target->>'address'`), so it can never see how the
   parser arrived at that string. The parser harness now fills that gap — read them together.

**Work:** re-run against current `services/gis/`, confirm the resolver list, add `--by-month`
and cosmetic bucketing, record a fresh baseline in `qa_harnesses.md` §3.

---

### 46. No STT harness exists — WER is computed for training, never for regression
> **Status**: ⚠️ **Open — raised 2026-08-26.** See [`docs/qa_harnesses.md`](qa_harnesses.md) §4.

`extract_training_data.py` and `backtest_regression.py` compute Word Error Rate to feed Whisper
training. Neither answers **"did this STT change make the system better or worse against
historical audio?"** — so STT configuration changes currently ship unmeasured.

Audio is available on essentially every dispatch (`audio_url`), so the corpus supports this.

**What it needs:**

* Replay stored audio through the current faster-whisper configuration.
* Score against `verified_transcript` — **after** handling the round trap below.
* Report **by month**, and report *both* WER and downstream field accuracy. A WER improvement
  that loses the map grid off the tail is not an improvement, and WER alone cannot see that.

#### ⚠️ The trap that will corrupt any STT measurement

**`verified_transcript` holds ONE round; `raw_transcript` holds two.** The reviewer verifies a
single round; the duplication that matches it to the two-round audio happens only at training
extraction ([`extract_training_data.py:182`](../backend/scripts/extract_training_data.py)),
never in the database column. Confirmed by query: `respond` appears once in 197 of 202 verified
transcripts.

**Diffing the two columns directly reports ~50% error on a perfect transcription.** Duplicate
the verified text first the way the extractor does, or compare round-for-round.

#### Two findings already waiting for it

* **Tail truncation** — 2026-07 lost `map grid` from 37 transcripts (18%) while those calls had
  *longer* median audio (50.6s vs 47.5s) and *fewer* words (37 vs 51). Fixed by the operator's
  audio-listener work around 2026-07-29; zero since. A harness would have flagged it the week
  it started.
* **Stable mis-recognitions** — faster-whisper writes `smoldering` 5/5 (never `smouldering`)
  and `Tassus` for Tahsis in 2 of 3 occurrences. These belong as recognition aliases in the
  street vocabulary, the same pattern already applied to call types in #43.

---

### 40 (plan). Coverage decided by the municipal polygon, not a box
> **Status**: 🔧 **Scripts updated 2026-08-26; crawl NOT yet run.**

The operator rejected a bounding box: *"pulling a square city boundary doesn't really work
either. The city is an odd shape."* Correct — Coquitlam is an L wrapped around Port Moody and
Port Coquitlam, and **fills only 44.8% of its own bounding box** (129.7 km² of 289.3 km²).

Tiles are now tested against the real boundary + 1 km buffer:

| z12–20 tiles | |
|:--|--:|
| Bounding box | 778,515 |
| **Polygon** | **430,845** |
| Saved | **44.7%** — and the saving grows with zoom (44.7% at z20) |

**Agreed coverage, 2026-08-26:**

| Layer | Area | Zooms | Tiles | Size |
|:--|:--|:--|--:|--:|
| `street` (labelled) | city polygon **+ region for context** | 12–20 city, 12–**16** region | 439,157 | 1.54 GB |
| `street_nolabels` | city polygon | 12–20 | 430,845 | 1.21 GB |
| `satellite` (+7.5 cm ortho) | city polygon | 12–20 | 430,845 | 6.29 GB |
| `cadastral` | city polygon | 14–20 | ~430k | ~0.69 GB |
| | | | **~1.73 M** | **~9.7 GB** |

Sizes use bytes/tile **measured from the existing kiosk archives** (street 3.5 KB, nolabels
2.8 KB, satellite 14.6 KB, cadastral 1.6 KB), not estimates. Kiosk has 226 GB free, so disk
is not the constraint — crawl time and CDN load are.

Regional context is deliberately a plain **box**, not the polygon: it is explicitly *not* the
city, and at z12–16 the whole region is only 10,149 tiles / 36 MB. `REGIONAL_MAX_ZOOM = 16`
because z12–20 region-wide would be 2,523,994 tiles (~8.8 GB, over a day of crawling) for
street detail in municipalities CFR does not respond to.

**Changes made:**

* `compile_mbtiles.py` — `filter_tiles_to_city()` tests each tile against the polygon.
  Uses **intersects, not contains**: a tile straddling the boundary holds real city ground,
  and contains-style strictness would carve a ragged hole around the whole perimeter (the
  same trap as #13). Falls back to the bounding box if shapely or the GeoJSON is missing —
  **over**-fetching, the safe direction.
* `backend/data/gis/coquitlam_tile_coverage.geojson` — 55-point polygon, generated.
* `backend/scripts/export_tile_coverage.py` — regenerates it from `public.city_boundary`.
  Hand-editing is what caused this defect; the script exists so nobody has to.
* `crawl_cadastral_tiles.py` — same polygon filter, and its bounds corrected from the
  hand-picked `-122.92 … -122.72` to the real extent. The old east limit stopped 0.1° short
  of the city at `-122.621`, leaving **Pinecone Burke and Minnekhada with no parcel or
  address labels at any zoom** — the wildland end of the response area.
* All layers now reach **z20 inside the city** rather than z18.

**Before crawling — unverified:** whether Carto Voyager and ArcGIS World Imagery actually
serve real z19/z20 raster tiles here, or upscale. The dev machine is sandboxed from both CDNs
(HTTP 000), so this must be checked **on the kiosk** first. If either upscales, ~322k tiles
per layer at z20 would be fetched for no added detail. Check before committing to the crawl,
not after (§7.3a).


**Runbook**: [`docs/briefings/tile_recrawl_runbook.md`](./briefings/tile_recrawl_runbook.md) —
`nohup`-launched, resumable crawl commands for a poor connection, plus the pre-crawl z19/z20
availability check, the mandatory WAL checkpoint, and the verification queries.

---

### 47. `Chartwell Rd` does not exist in municipal data — three sources give three street names
> **Status**: 📋 **Open — for the City GIS team, not a code defect.** Raised by the operator
> from HITL review of `DISP-2026-EC4501` (2026-08-19, rated OPERATIONAL): *"Flag this call.
> The dispatch announces 3305 Chartwell Rd, but that's not on the cadastral data. The map only
> shows it as 3305 Chartwell Green. Strange?"* All figures below **confirmed** by query.

**One address, three different street names, depending on who you ask:**

| Source | Street name |
|:--|:--|
| STT (`raw_transcript`) | `Chartwell **Grove**` |
| Operator, from the audio (`verified_address`) | `Chartwell **Rd**` |
| City of Coquitlam cadastre (`public.parcels`, `public.road_names`) | `Chartwell **Green**` |

#### What the municipal data actually holds

`public.road_names` contains exactly two Chartwell streets, and neither is a road:

```
Chartwell Green
Chartwell Lane (PRIV)
```

`public.parcels` agrees:

| Street | Parcels | House range |
|:--|--:|:--|
| Chartwell **Green** | 57 | 3255–3325 |
| Chartwell **Lane** (private) | 11 | 3221–3239 |

**There is no `Chartwell Rd`, `Chartwell Road`, or `Chartwell Grove` anywhere** in
`road_names` or `parcels`. House number **3305 is valid and unique** on Chartwell Green:

```
3305 Chartwell Green   49.317005655150034, -122.78752037030098
```

#### The system resolved it correctly

The pipeline produced `3305 Chartwell Green` at the parcel coordinates above — the right
place, per the only authoritative source available. Crews would have been routed correctly.

**So this call is scored `address WRONG` by the parser harness only because
`verified_address` disagrees with the cadastre, not because the system erred.** Worth knowing
when reading the address column: a small number of "failures" are ground-truth-versus-cadastre
conflicts of this kind.

#### The question for the City GIS team

Not answerable from anything this project holds:

1. Is **`Chartwell Rd` a legacy or alias name** for what the cadastre now calls Chartwell
   Green — a renamed street where the old name is still in circulation?
2. Does **E-Comm's CAD carry a different street name** for this block than the City's
   cadastral extract? If dispatch reads addresses from a CAD table that disagrees with the
   Open Data cadastre, that is a systematic divergence, not a one-off.
3. Is there any **`Grove`** designation in the area that would explain the STT reading, or is
   `Chartwell Grove` purely a mis-hearing of one of the other two?

Question 2 is the one that matters operationally. A single alias is a curiosity; a CAD/cadastre
divergence would mean an unknown number of announced addresses cannot be matched against
`public.parcels` at all — the same failure shape as #41 (`629 Cottonwood Ave` absent from
parcels).

#### Do not "fix" this in code

No string-match special case, and no alias row, until the source of the discrepancy is known
(CLAUDE.md §6.2 — a geocoding miss belongs in the data as a data fix, never as a special case
in application code). If GIS confirms `Chartwell Rd` is a legitimate legacy name, it belongs in
the street vocabulary as a recognition alias, the same mechanism as the call-type aliases
in #43.

---

### 40 (resolved). Re-crawl complete — the gap is closed and verified
> **Status**: ✅ **Closed 2026-08-27.** Verified against the running tile server, not inferred.

The re-crawl ran unattended on the kiosk via a sequential chain (`/tmp/run_all_crawls.sh`).
All four layers completed `rc=0`.

**The tile that started this** — Cottonwood Ave z17, `17/20795/44869`, the exact one blank in
the operator's screenshot. It served a **116-byte empty PNG** before:

| Layer | Before | After |
|:--|--:|--:|
| `street` | **116 b** | **8,884 b** |
| `street_nolabels` | **116 b** | **7,613 b** |
| `satellite` | **116 b** | **20,745 b** |
| `cadastral` | 25,761 b | 25,761 b (was never affected) |

Deep zoom on the west side also confirmed: `street` z19 → 3,130 b, `satellite` z20 → 12,284 b.
Austin Heights, Maillardville and Burquitlam now have basemap coverage at every zoom.

**Final archives:**

| Layer | Tiles | Size | Zooms |
|:--|--:|--:|:--|
| `street` | 130,387 | 469.5 MB | 12→19 |
| `street_nolabels` | 130,387 | 428.6 MB | 12→19 |
| `satellite` | 511,118 | 7,695.2 MB | 12→20 |
| `cadastral` | 606,938 | 990.6 MB | 14→20 |

All four report `Integrity: ok` and `Journal Mode: delete`. Disk went 218 GB → 223 GB used,
222 GB free.

**The metadata now tells the truth** — the specific lie that hid this defect:

```
street           12 -> 19  bounds [-123.04,   49.15,    -122.6,     49.48]     <- regional, correct
street_nolabels  12 -> 19  bounds [-122.90723, 49.21087, -122.60729, 49.36017] <- city
satellite        12 -> 20  bounds [-122.90723, 49.21087, -122.60729, 49.36017] <- city
cadastral        14 -> 20  bounds [-122.90723, 49.21087, -122.60732, 49.36017] <- city
```

Only `street` declares the regional box, because it is the only layer that actually holds
regional tiles. Previously all four declared `-123.04` regardless of content.

#### Two things worth recording for next time

**1. `finalize_mbtiles.py` cannot convert a WAL archive while `cfr_tiles` is running.**
The chain's finalize step failed with `sqlite3.OperationalError: database is locked` on
`street.mbtiles`, which still had `-wal`/`-shm` files. `PRAGMA journal_mode = DELETE` needs an
exclusive lock, and mbtileserver holds the file open. `cadastral` and `satellite` appeared to
succeed only because they were *already* in `delete` mode, so their pragma was a no-op — the
script was one archive away from reporting success on work it had not done.

Fix applied by hand: `docker stop cfr_tiles` → finalize → `docker start cfr_tiles`. **The
runbook's step 4 is wrong as written** and needs the stop/start added.

**The chain's failure guard did its job**: it refused to restart `cfr_tiles` after the failed
finalize and exited non-zero, rather than pressing on and leaving un-checkpointed archives to
fail differently under a read-only mount.

**2. `Pillow` was missing from the kiosk venv.** `compile_mbtiles.py` imports `PIL` at module
level, so the first launch died instantly with `ModuleNotFoundError`. Installed 12.3.0. The
runbook only mentioned `shapely`.

#### Timings, measured

| Layer | Duration | Rate |
|:--|:--|:--|
| `street` | 13 min (87,502 tiles) | 112.6 tiles/s |
| `street_nolabels` | 13 min | ~112 tiles/s |
| `satellite` | 29 min | ~110 tiles/s |
| **`cadastral`** | **8 h 35 min** | **~10 tiles/s** |

**The City's ArcGIS MapServer is ~11× slower than the Carto and ArcGIS World Imagery CDNs**
and dominated the run — 8.5 of the 9.5 hours. Budget for that before scheduling any future
cadastral re-crawl; the estimate of "~2.5–3 hours total" was wrong because it assumed a
uniform rate across all four sources.

#### Correction: the slow cadastral crawl was self-inflicted

The claim above that "the City's ArcGIS MapServer is ~11× slower" is **wrong and withdrawn.**
The operator questioned it, and the config says otherwise:

```
Workers / Delay: 8 concurrent workers | 200ms delay (~5.0 req/s)
Crawl phase completed in 08:35:12 (153,094 ok, 8 failed, 5.0 tiles/s).
```

`crawl_cadastral_tiles.py` carried a global `RateLimiter` with `min_interval = 0.2s`. It
serializes every request behind a single lock, so it is a hard **5 req/s** ceiling that the
worker count does **not** multiply. The crawl finished at exactly 5.0 tiles/s — pinned to the
limiter for the whole 8½ hours. `compile_mbtiles.py` has no limiter at all (32 workers,
~110 tiles/s), which is the entire 22× difference.

**How the wrong conclusion was reached**: the "~10 tiles/s" figure was derived by dividing the
*total archive* (606,938 tiles) by elapsed time instead of the *newly downloaded* 153,094. The
real rate was 4.95/s, which would have pointed straight at the 0.2 s constant. A cause was
inferred from a mis-computed number rather than read from the config — the exact failure mode
CLAUDE.md §7 exists to prevent, and worth recording as such.

**Resolution**: `DEFAULT_DELAY_SEC = 0.05` (~20 req/s), operator decision 2026-08-27, with
provenance inline. Deliberately not unlimited — the City's MapServer is municipal
infrastructure belonging to the department's data partner and the licensor of this data, not a
commercial CDN. Expect a full cadastral re-crawl near 2 h rather than 8.5 h.

**Still open**: **8 tiles failed** in that run and have not been investigated. The crawler is
resumable and would retry them, so a short re-run would show whether they are transient or a
genuine gap.

---

### 48. One civic address, many parcels — the import keeps whichever the shapefile lists first
> **Status**: ⚠️ **Open — measured 2026-08-28. Ours, not a City data gap.**

Found while accounting for the 4,307-record difference between `Addresses.dbf` (69,708) and
`public.parcels` (65,401). **The accounting reconciles exactly** — there are 65,401 distinct
`ADDRESS` values in the source, so nothing is being lost at import:

| | |
|:--|--:|
| Records in `Addresses.dbf` | 69,708 |
| Distinct `ADDRESS` values | **65,401** |
| Rows in `public.parcels` | **65,401** |
| Duplicated addresses | 1,509 |
| Extra rows they account for | **4,307** ✅ |

`Addresses.dbf` also has its own `STATUS` column — worth checking after the roads import
filter (#42) — but its entire domain is `Active` (69,704) plus 4 blanks. Nothing is filtered.

#### The problem is *which* duplicate wins

`backend/scripts/import_parcels.py:336` deduplicates on the raw address string:

```python
if raw_addr in seen_addresses:
    continue
seen_addresses.add(raw_addr)
```

First-wins, **in shapefile row order, with no ordering rule** — the same shape as the
unordered-parcel-query defect in #19. That is only safe if the duplicates sit in the same
place, and measured against the shapefile geometry (UTM 10N, representative points) they
frequently do not:

| Duplicate groups | With a house number | Street-only |
|:--|--:|--:|
| Total | 1,452 | 56 |
| More than 5 m apart | 708 | 54 |
| More than 25 m apart | **631** | 53 |
| More than 100 m apart | **143** | 47 |
| More than 500 m apart | 14 | 26 |

The duplicates never differ in `HOUSE`, `STREET`, `STREETTYPE`, `UNIT` or `UNITTYPE` — only
in `LEGALDESC` (714 groups), `FOLIO` (712) and `GIS_ID` (676). So this is **one civic address
spanning several legal lots**, which is legitimate municipal data, not a City defect.

> **A first hypothesis was wrong and is recorded rather than overwritten.** The worst
> spreads looked like street-only right-of-way records (`Shaughnessy St` ×469,
> `Pitt River Rd` at 13.5 km), so the effect appeared to be confined to records with no
> house number. Splitting the two classes disproved it: **1,452 of the 1,508 duplicate
> groups DO carry a house number**, and 631 of those are more than 25 m apart.

#### Operational exposure so far

Seven dispatches in the corpus went to an address whose duplicates are >25 m apart. Five are
street-only (`Pipeline Rd`, `United Blvd` ×3, `Gatensbury St`) and already handled as
street-level. **Two are genuine numbered addresses:**

```
DISP-2026-C0F4AA   2865 Glen Dr    216.6 m spread   8 features, 7 sharing GIS_ID !4190583
DISP-2026-A977D4   210 Lebleu St    35.3 m spread   4 features, 2 distinct locations
```

Small in the observed corpus, but the mechanism affects 631 addresses that have not been
dispatched to yet.

**Second-order effect, easy to miss**: `parcels.rings` comes from the kept record too, so the
kiosk highlights **one lot of eight** for 2865 Glen Dr rather than the whole property.

#### What to do is a domain decision (§7.2), not a coding one

Do **not** pick a tiebreak by feel. Candidate rules, each with a different failure mode:

1. **Largest parcel by area** — favours the main site, but a large rear lot can beat the
   building that fronts the street.
2. **Closest to the road centreline for that street** — favours the frontage a crew arrives
   at, and `public.roads` is now complete enough to support it (#42).
3. **Union all duplicate geometries into one parcel** — most honest about what the address
   is, and would fix the rings; changes the meaning of a parcel row.
4. **Keep all rows and mark the address ambiguous** — surfaces it via the amber banner
   rather than choosing, consistent with §6.1.

Whichever is chosen, the selection must become **deterministic and stated**, and the change
measured against the corpus the way #42 was.

**Also worth asking the City** (see `docs/city_gis_data_register.md`): is one civic address
across 8 legal parcels expected, and is there an attribute marking the primary parcel?

---

### 43. The 8 failed cadastral tiles, and what the "blank" tiles actually are
> **Status**: ✅ **Closed 2026-08-27.** Both questions answered by measurement.

#### The 8 failures were transient

Re-ran the crawler; it found exactly 8 missing tiles and fetched all 8 with **zero failures**
in under a second. No pattern, no bad region — network noise across 153,102 requests over 8½
hours. Cadastral coverage is now provably complete:

```
archive tiles      : 606,946
inside coverage    : 430,801
grid expects       : 430,801
missing from grid  : 0
```

Archive re-finalized (`Integrity: ok`, `Journal Mode: delete`) and `cfr_tiles` restarted — the
retry had put it back into WAL mode, which would have broken the read-only mount if left.

**But the log could not say which 8 they were.** Every failure path in `fetch_tile` logged at
`logger.debug` while logging is configured at `INFO`, so the details were discarded and the run
reported a bare count. Identifying them required a re-run with `force=True` DEBUG logging.
That is the same defect as **#26**, one layer down: a count with no cause. It did not matter
here because the failures were transient — but a *systematic* failure over one region would
have produced an identical-looking log.

**Fixed**: the three retry-exhausted paths now log at `WARNING`.

#### Retraction: the "dead weight" claim about outside-coverage tiles was wrong

An earlier note called the 176,145 tiles outside the coverage polygon "dead weight" and
suggested purging them for space. **The operator questioned whether the City would even
produce cadastral data outside its own boundary. That instinct was right, and the reasoning
behind the purge suggestion was weak.**

Measured: all 176,145 are **exactly 885 bytes** — min, median and max identical. Decoded:

```
md5 = 72accbca6aa1edbf6fec07c32f2df94a
256x256, alpha min/max = 0/0, distinct pixels = 1
```

One fully transparent image, repeated. The City renders **nothing** beyond its cadastral
extent, so the coverage polygon is **not excluding any real data** — which was the question
worth asking.

Two comparable tiles at z18, both against the City's MapServer, for anyone re-checking this:

* **Outside**, 49.21984, −122.91985 → blank, 885 b
* **Inside**, 49.24316, −122.89238 → parcel lines and address labels, 9,415 b

`bbox` is EPSG:3857; the export URL pattern is in `MAPSERVER_EXPORT_URL`.

**And the space argument does not hold either.** There are **488,668** 885-byte blank tiles in
the whole archive — **80.5%** of 606,946 — of which only 176,145 are outside the polygon. So
**312,523 blanks are *inside* the city**, and that is entirely normal: at z20 a tile is ~30 m
across and parcels render as outlines, so tiles landing inside a lot, a park or the river have
nothing to draw. **Blank is not a proxy for "should not be there."**

The 176,145 outside tiles are ~150 MB of a 991 MB archive against 222 GB free, and they do
useful work: without them the tile server has no cached answer for a pan just past the boundary
and the frontend would paint its "no map data" hatch over Port Moody — reintroducing #40's
symptom at the edges.

**Recommendation reversed: leave them.** Recorded rather than quietly dropped, because the
original suggestion came from inferring purpose from file size instead of decoding one tile
(§7.1). The semantics are now an inline comment at the PNG-validation site so nobody
"optimises" blanks away later.

---

### Status sync, 2026-08-27

* **#38 (parcel front points on the wrong street)** — ⏳ **being handled by another agent.**
  Not to be worked here; see the roads/GIS thread. The measurement stands as recorded:
  `1178 Heffley Cres` sits 0.0 m from Pinetree Way and 109.2 m from Heffley Crescent, with a
  sampled ~11.5% of parcels more than 60 m from their own named street.

* **#42 (roads `STATUS` filter)** — ✅ **Closed by another agent** in `302af14`
  *"fix(gis): import roads of every status, and repair the import script itself"*, which took
  the recommended shape rather than deleting the filter. Verified against the kiosk database:

  | | Before | Now |
  |:--|--:|--:|
  | `public.roads` rows | 3,214 | **3,451** |
  | Distinct `status` values | `OPERATING` only | **`METRO, MOT, OPERATING, PRIVATE`** |
  | Parcel streets with no matching road | 45 | **17** |

  So 28 of the 45 missing streets are resolvable again, and jurisdiction is preserved rather
  than flattened. **17 remain** — worth a look in that thread, since they are now a different
  and smaller problem than the `STATUS` filter (likely name-form mismatches rather than absent
  geometry, given `Highway #1` and the strata roads are back).

* **#41 (parcel import / `629 Cottonwood Ave`)** — partly overtaken by `e0466df`
  *"account for the 4,307-row parcel gap — reconciled, but selection is arbitrary"*. The
  remaining action from this thread is unchanged and independent: **`Addresses.shp` is dated
  2025-06-22, over a year old.** Re-pull and re-import; the upsert preserves pre-plans, lockbox
  notes and Street View headings.


---

### 34 (resolved). The phantom "UPDATED" badge
> **Status**: ✅ **Closed 2026-08-27.** Not yet observed on a live call — the change is
> unit-tested against realistic payloads, but the operator's own confirmation is what closes
> the loop on anything MQTT-driven.

**Cause.** `useKioskQueue.js` called `triggerUpdateFlash()` unconditionally at both merge
sites — `handleNewDispatch` (`:107`) and `handleUpdate` (`:136`) — whenever the incoming
record matched the active one by `dispatch_id`. Nothing compared the payloads. MQTT QoS 1 is
**at-least-once**, so a duplicate delivery of a byte-identical call is the contract rather
than an anomaly, and the badge fired on it every time.

That is an operational claim with nothing behind it (§6.1): the kiosk told the operator data
had changed when frequently none had, which is the same class of defect as a fabricated value
— it just fabricates an *event* instead.

**Fix.** `getVisibleChanges(current, incoming)` in `utils/dispatchModel.js` returns the names
of the **operator-visible** fields that actually differ; `triggerUpdateFlash` is a no-op on an
empty list. The merge still happens either way — the corrected values are what the crew needs
— only the *announcement* is now conditional.

Comparison notes, each deliberate:

* **`routing_metrics` is excluded.** OSRM re-runs per broadcast and can return a duration
  differing by a second for an identical call. Including it would make the badge fire on noise
  — precisely what this fixes.
* `null`, `undefined` and `''` are all "not present" and do not read as a change.
* Numeric strings compare numerically, so `lat: '49.2963'` vs `49.2963` is not a change.
* Unit **order is significant** — it is the dispatch order, which the kiosk preserves
  deliberately — so a reorder counts as a real change.

**The badge now says what changed**, which was the operator's other complaint ("it defaulted
by saying there was an update, but didn't give any"). `⚡ UPDATED: address, map grid`, with the
full list on hover, mapped to operator-facing words (`radio_channel` → "talk group").

**Verified** against 11 realistic payload pairs — all pass:

```
PASS  identical redelivery (QoS1 duplicate)     -> []
PASS  noise only: timestamp/confidence/audio    -> []
PASS  null vs empty string                      -> []
PASS  lat as string vs number                   -> []
PASS  phase2 corrects grid                      -> [map_grid]
PASS  address + coords corrected                -> [address,lat,lng]
PASS  units reordered                           -> [responding_units]
PASS  whitespace only                           -> []
```

`lint:crash` and `npm run build` clean.

---

### 49. Access-point review UX — operators cannot set an entrance without direct SQL
> **Status**: 🔴 **Open — HIGH PRIORITY. Schema and data are ready; only the UI is missing.**
> Operator decision 2026-08-29: build the geometry now, defer the UX as the next feature.

The arrival-point pipeline is complete and correct for ordinary properties. What has no
interface is the exception path.

#### What is already done

* `backend/scripts/import_parcels.py` computes every front point as the closest point on the
  road **the address names** to the parcel **polygon**, recomputing all 65,401 rows on each
  run. Verified: **0 parcels sit off their addressed street** where such a street exists; the
  54 that do are municipal data gaps in `docs/city_gis_data_register.md`.
* `public.parcels.entrance_lat` / `entrance_lng` are now the **operator-verified** access
  point, cleared of the copied centroids they used to hold, with `entrance_set_by`,
  `entrance_set_at` and `entrance_note` for attribution.
* Resolution precedence is **entrance → front → centroid**
  (`services/gis/src/gis_service/address_resolver.py`). A recorded human answer outranks the
  calculation.
* `public.parcels.access_far_corner_m` records how much property lies beyond the arrival
  point, so the review queue is a query rather than a stale list.

**All 65,401 entrance points are NULL.** There is no way to set one except by hand-writing SQL
against production, which is exactly the practice this workstream spent two days arguing
against.

#### The queue is smaller than it looks

`docs/complex_sites_for_review.csv` — 1,395 sites, 25,475 addresses behind them:

| Sites reviewed | Addresses covered | |
|--:|--:|--:|
| 25 | 7,750 | 30% |
| 50 | 11,612 | 46% |
| **100** | **16,635** | **65%** |
| 252 | 23,417 | 92% |

Highrises dominate by address count, trailer parks by distance: `1158 The High St` is 645
addresses at 120 m; `201 Cayer St` is 266 addresses at 366 m across a 122,923 m² site. Both
need one decision each.

#### What the UX needs to do

One screen per site, worked worst-first:

1. Orthophoto at the site, parcel outline drawn, current computed arrival point pinned.
2. Click to place the verified access point.
3. A note in the officer's words — *"gated, keypad at Glen Dr west end"* — stored in
   `entrance_note` and shown to crews.
4. Save writes `entrance_lat/lng`, `entrance_set_by`, `entrance_set_at`.

Roughly 30 seconds per site. The top 100 is an afternoon.

#### Constraints that must hold

* **An import must never overwrite `entrance_*`.** `import_parcels.py` already carries that
  comment; a UI that writes through the same path would break it.
* **Every override is attributable.** An unattributed override is just another unexplained
  number (§6.3).
* **Do not offer a "clear all" or bulk-apply.** These are per-site human judgements.
* The kiosk should show `entrance_note` when an override is in play, so crews know why the pin
  is where it is rather than wondering if it is wrong.

---

### 14 (analysed). PA leakage — the discriminator is 647 Hz, and 595 Hz is what breaks the filter
> **Status**: ⚠️ **Open — root cause found and a rule validated against 122 real tone events.
> Not implemented: the change affects whether a real dispatch can be dropped (§7.2).**
> Full analysis: [`docs/briefings/pa_tone_discriminator.md`](./briefings/pa_tone_discriminator.md).

**647 Hz appears in 15 of 15 system-labelled PA events**, and in all three operator-`[PA]`-tagged
dispatches that occurred while `tone_spectral_history.jsonl` was running. It is the only
consistent PA marker — the tone's other component wanders (588, 576, 610, 526, 556…).

**Why the existing PA rejection fails.** `audio_listener.py:139` reads
`if pa_matches and not apparatus_matches`, so any apparatus match wins the tie — and with
`MATCH_THRESHOLD_PERCENT = 0.50`, a single frequency within ±8 Hz is enough to "match" a
two-tone fingerprint. A PA page's harmonics routinely graze one:

```
TRIGGER-1787409188  [561, 591, 647, 728, 842, 905, 1338]
   647 -> PA 647      | 591 -> PA 595   => PA 100%
   728 -> Rescue 727  => Rescue 50%     => apparatus wins, PA page dispatched
```

**And 595 Hz is not a PA signature at all** — it is present in **59 of 107** non-PA events, more
than half of real dispatches. Engine Tone's 600 Hz also sits 5 Hz from it, inside the ±8 Hz
tolerance, so those fingerprints are not separable on that component.

**Rules scored against all 122 events:**

| Rule | PA caught | **Real dispatches wrongly dropped** |
|:--|--:|--:|
| Current (`pa and not apparatus`) | 15 / 24 | 0 |
| **`647 Hz present`** | **24 / 24** | **0** |
| `647 Hz and apparatus < 100%` | 23 / 24 | 0 |
| `PA >= 50%` (PA wins outright) | 24 / 24 | **54** |
| `PA = 100%` | 6 / 24 | 0 |

Against strict ground truth only (15 system-labelled + 3 operator-tagged, excluding inference),
`647 Hz present` is **18/18 with zero false positives**.

The intuitive fix — letting PA win outright — is the **worst** option, dropping 54 real
dispatches, exactly because 595 Hz is common in genuine tones.

**Blocked on the operator** (all three in the briefing): confirm six untagged candidates are
PA (`87EA26`, `A9D408`, `8E6CAD`, `2410A2`, `D467FE`, `002248`); confirm the mid-call PA tone
case recorded on `DISP-2026-282647` cannot be affected; and choose whether to ship directly or
run log-only first.

**Also noted**: `647.00` already sits in `GOLDEN_FINGERPRINTS` with no provenance. Whatever
ships should cite this analysis (§6.3 tier 3) or a published PA tone spec if one exists.

---

## 🔊 Audio Playback & UI State

### 19. Audio player loading inconsistency & Auto-play removal
> **Status**: ✅ **Closed 2026-08-29 — fixed.**

* **Observed Problem**: The audio player displays properly in the Dispatch Review panel, but the audio file buffering sometimes shows as not loading. Auto-play works inconsistently (sometimes triggers on advance, sometimes not), and occasionally clicking play changes the icon or shows the bar progressing but no audio is heard. The user requested all auto-play features be stripped entirely.
* **Root Cause**: 
  1. The auto-play logic used a `setTimeout` of 300ms to call `audioRef.current.play()` on advance, which is race-condition prone and explicitly unwanted.
  2. The `<audio>` HTML element reuses the same DOM node when the `src` attribute changes. Browsers (especially Safari/Chrome) can fail to properly re-initialize the media buffer or get stuck in a bad state when the source is swapped dynamically on the same element repeatedly.
* **Fix**:
  1. Removed the `setTimeout` block in `DispatchReview.jsx` `handleSubmitReview` that was responsible for auto-playing the next call's audio. This was the only auto-play location found in the frontend codebase.
  2. Added `key={selectedCall.id || selectedCall.dispatch_id}` and `preload="auto"` to the `<audio>` element in `VerificationSidebar.jsx`. The React `key` forces the component to completely unmount and remount a fresh `<audio>` player element each time a new dispatch is selected, guaranteeing immediate and reliable buffering while waiting for a user trigger.
