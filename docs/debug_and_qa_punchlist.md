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
> Still open: **#1**, **#6**, **#10**, **#12**, **#14**, **#17**, **#19**, **#20**, **#21**.

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
> **Status**: ⚠️ **Open — still unverified (re-checked 2026-08-21).** Correct as written.
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
