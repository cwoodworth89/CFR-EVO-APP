# CFR EVO: Module Decomposition & Review Plan

> [!NOTE]
> **Historical planning document.** Compiled 2026-08-21 against `c7f70ff`. Sections marked
> ✅ DONE record work that landed; the rest was not re-verified after 2026-08-31. For the
> current state read `docs/review_status_handoff.md`.

Working document for the module-by-module review, hardening, simplification and
documentation stage. Each section is scoped to be reviewable in a single focused
session without carrying the whole system in context.

**Compiled 2026-08-21** against commit `c7f70ff`. Line counts and findings were
measured on the working tree, not estimated.

---

## How to use this

Each module below is a self-contained review unit. Suggested order is by **risk × blast
radius**, not by size — a 449-line file wired into the live dispatch path matters more
than a 1000-line import script that runs quarterly.

For each module the review should cover: interactions in/out, dead code, CLAUDE.md §6
compliance (no fabricated data, sourced constants), error handling, and documentation.

---

## Tier 1 — Live dispatch path (highest risk)

### 1.1 `backend/api/road_closure_service.py` (449 lines) — ✅ DONE (`206af55`)

Completed 2026-08-21. Hand-rolled ray-casting, `zones.json` disk loading, the Fraser
River latitude threshold, the neighbouring-city string blocklist, the coordinate-order
guessing heuristic, and both `lat, lng = 49.28, -122.80` placeholders are gone.
Replaced by `backend/api/closure_spatial.py` using `ST_Intersects` / `ST_Contains`
against `public.city_boundary` and `public.zones`.

Also added `zones.unit_id/station/hall_id` (backfilled by
`backend/scripts/oneshot/import_zone_units.py`, 134/134 zones) and
`road_closures.geom` + `hall_id`, so hall grouping is resolved server-side instead of
the kiosk fetching `zones.json`.

Measured justification for using the real polygon over a bounding box: the §5 bbox
covers 338.1 km² against the city's actual 129.7 km² — **61.6% of that rectangle is not
Coquitlam**, admitting Port Moody, Port Coquitlam, Burnaby, New Westminster and Anmore.

*Original finding, for reference:*

- Uses **zero PostGIS** (`grep -c "ST_"` returns 0) despite `public.zones` holding all
  134 authoritative zone polygons with real geometry.
- `_load_emergency_zones()` reads `zones.json` off disk, with three fallback paths.
- `point_in_polygon()` is a hand-rolled ray-casting implementation.
- Phase A of the freeze summary states in-memory shapefile/JSON spatial loading was
  "completely purged" — **this file survived that migration unnoticed.**

Direct violation of CLAUDE.md §6.2 (prefer the authoritative source). Replacing the
ray-casting with `ST_Contains` against `public.zones` removes the JSON dependency, the
module-level cache, and roughly 80 lines of geometry code.

### 1.2 `backend/cfr_dispatch/pipeline/phase2.py` (464 lines, 3 functions)

Only three functions across 464 lines — `process_phase_2_finalize` and
`process_full_dispatch` are each around 300 lines covering audio save, STT, parse,
geocode, persist, MQTT and ntfy. **Updated 2026-08-31**: `process_full_dispatch` was
deleted with its only caller, taking the file to 480 lines and leaving
`process_phase_2_finalize` as the single large function here. Natural seams already exist as numbered comment
blocks. Review alongside `phase1.py` for duplicated broadcast logic.

### 1.3 `backend/cfr_dispatch/parser/` (1053 lines) — ✅ DONE

Converted to a package, module path unchanged:

| Module | Lines | Responsibility |
|:--|--:|:--|
| `parser/sanitize.py` | 200 | transcript normalisation |
| `parser/call_types.py` | 64 | call-type vocabulary, fuzzy incident matching |
| `parser/units.py` | 94 | unit abbreviation, expansion, P1/P2 merge |
| `parser/channels.py` | 52 | radio talkgroup matching and formatting |
| `parser/location.py` | 203 | street suffix, location cleaning, subaddress, fuzzy street |
| `parser/announcement.py` | 411 | segmentation + template parser |

`__init__.py` re-exports all 18 public names, so the nine consumers were not edited.
Dependency direction is one-way: `announcement` depends on the other five; those five
are independent of each other.

Verified two ways: the test suite is identical before and after (11 failed / 72 passed
both, same list, all pre-existing and environmental), and a golden diff against the
pre-split module loaded side by side produced **byte-identical output on 6/6
transcripts**, five of them reconstructed from real dispatches.

**Still outstanding:** `destructive_parser.py` was not reviewed for divergence against
the template parser. It imports `sanitize_transcript` from this package and duplicates
some location logic. That comparison remains a separate task.

### 1.4 `backend/cfr_dispatch/audio_listener.py` + `config/dsp.py`

Small but operationally critical. Open question from the 2026-08-21 investigation:
`GOLDEN_FINGERPRINTS` defines `"Dispatch Announcement": [1000.00]` and `"PA Tone"`, but
the listener only actions `Chief Tone`, `Engine Tone` and `Rescue Tone`. That is the
intended behaviour today.

Worth reviewing: the PA tolerance. An 08:10 event matched PA Tone on peaks `588/647`
against golden `595/647` — inside the 8 Hz `FREQUENCY_TOLERANCE_HZ` by a single hertz.
A dispatch misclassified as a PA page is discarded before recording.

---

## Tier 2 — Kiosk UI

All four crash-class bugs found on 2026-08-21 were in this tier.

### 2.1 `frontend/src/components/DashboardHUD.jsx` (1083 lines, 5 components) — ✅ DONE

Split into `components/hud/`: `Header.jsx` (93), `SatelliteMiniMap.jsx` (43),
`ActiveDispatchPanel.jsx` (184), `LeftSidebar.jsx` (485), `RightSidebar.jsx` (263).
`DashboardHUD.jsx` deleted; `MapBoard.jsx` imports the three exported components
directly. Four of the five files are now completely lint-clean.

**Correction to this plan's original claim:** the split did *not* reduce the 15
`react-refresh/only-export-components` warnings, because none of them were in
DashboardHUD. They are in `MapLayers.jsx` (5), `hud/ActiveAlertBanner.jsx` (3),
`hud/RoutingConfigModal.jsx` (1), `review/ReviewTable.jsx` (3) and
`review/VerificationSidebar.jsx` (2) — files that export helper functions and constants
alongside components. Clearing them means moving those helpers to their own modules,
which is a separate task from splitting multi-component files.

`RightSidebar.jsx` still carries 4 issues that came with the component: three
`preserve-manual-memoization` and one `exhaustive-deps` on the closure-grouping
`useMemo`. Worth addressing when that component is reviewed.

Note: `SatelliteMiniMap` duplicates the standalone component deleted in `d5fbdcc`. This
copy **does** guard coordinates correctly (`if (!lat || !lng) return null`), so it is
not a §5 defect — but decide whether it should exist at all.

### 2.2 `frontend/src/components/MapBoard.jsx` — ✅ DONE (2026-08-22), 1,184 → 662 lines

Extracted to `components/map/`: `ZonesLayer`, `RoadClosuresLayer`, `DispatchTargetLayer`,
`MapViewControls`, `RoadClosureMarker`, plus `mapIcons`, `mapGeometry`, `layerIcons` and
`railroadCrossings`. State lifted into `hooks/useMapLayerPreferences` and
`hooks/useRoadClosures`. Two dead exports deleted (`GeometryDecoder`, `createSchoolIcon`).

Found while decomposing: the closure "Next 24h"/"Next 7d" filters matched nothing
(punch-list #22), `TALK_GROUPS` duplicates the database (#20), and the rail crossing list
is hand-entered (#21).

The remaining work is architectural rather than mechanical — see
[`architecture/unified_map_surface.md`](architecture/unified_map_surface.md), which
proposes collapsing MapBoard and KioskView into one mode-selected surface. The layer
extraction above is step one of it.

<details><summary>Original entry (1155 lines, 52 hook calls)</summary>


Largest file in the project and the densest state container by a wide margin. Two of
the four runtime crashes fixed on 2026-08-21 originated here, both from identifiers
left behind by the training-mode removal.

Candidate extractions: road-closure marker and state, layer-toggle state,
target-address resolution, and the already-exported `enrichAddressWithBuilding` helper.

</details>

### 2.3 `frontend/src/components/kiosk/RouteOverviewPanel.jsx` (430 lines)

Recently cleaned and now lint-clean, but still mixes Leaflet lifecycle, OSRM candidate
disambiguation, and panel rendering. Smallest Tier 2 unit — a reasonable warm-up.

### 2.4 `frontend/src/components/kiosk/StreetViewPanel.jsx` (613 lines, 15 hooks)

Google Maps SDK lifecycle, DB override lookup, expand/collapse modal, and heading
persistence in one component. Carries two deliberate
`eslint-disable react-hooks/set-state-in-effect` comments that should be re-examined
when the component is split.

### 2.5 `frontend/src/components/MapLayers.jsx` (528 lines, 8 components)

Seven exported layer components plus a detail card. Each layer is independent, so
splitting to one file per layer is low-risk and mechanical.

---

## Tier 3 — Review and admin surfaces

### 3.1 `frontend/src/components/DispatchReview.jsx` (650 lines, **43 hooks**)

Second-densest state container. Review together with `ReviewTable.jsx` (363) and
`VerificationSidebar.jsx` (669) as a single "call review" module — they are tightly
coupled and share the HITL verification flow.

### 3.2 `frontend/src/components/review/VerificationSidebar.jsx` (669 lines, 1 component)

A single 669-line component, almost entirely form fields. Mostly a rendering split.

---

## Tier 4 — Scripts

### 4.1 `backend/scripts/import_gis_data.py` (1007 lines)

Already organised as `step1_…` through `stepN_…`, so splitting to one module per step is
nearly free.

Note it applies `ST_Multi(geom)` to every road — the cause of the block interpolation
outage fixed on 2026-08-21. Worth deciding whether `MultiLineString` is the right
storage type at all, given only 30 of 3,214 roads are genuinely disjoint.

### 4.2 Maintenance and sync scripts — architecture conformance pass

**Required before the review is considered complete.** Several scripts predate the
PostGIS migration and still read or write JSON/shapefiles instead of the database. Each
one found so far was carrying a real defect:

| Script | Finding |
|:--|:--|
| `sync_hydrants.py` | Defaulted missing `flow_class` to `"AA"` (highest NFPA 291 class) and missing `status` to `"OPERATING"`. Fixed 2026-08-21; now writes `public.hydrants` with nulls preserved. |
| `generate_street_list.py` | Read `Addresses.shp` and wrote a `.txt` nothing consumed. Deleted. |
| `import_gis_data.py` step7 | `TRUNCATE`d `public.vocabulary` before re-importing from `.txt`, destroying HITL-learned terms. Now applies an additive seed migration. |
| `update_gis_data.py` | Uses `or ""` for `flow_class` where `sync_hydrants.py` used `or "AA"` — the two disagreed on the same field. Not yet reviewed. |

Every remaining script needs the same three questions asked:
1. Does it read or write a JSON/shapefile that a database table now owns?
2. Does it substitute a default for a missing source value (CLAUDE.md §6.1)?
3. Is it destructive on re-run (`TRUNCATE`, overwrite) in a way that discards data
   added since the last run?

Scripts still to audit: `update_gis_data.py`, `import_parcels.py`, `download_gis_data.py`,
`compile_mbtiles.py`, `crawl_cadastral_tiles.py`, `extract_all_intersections_from_gis.py`,
`oneshot/backfill_routing_metrics.py`,
`oneshot/backfill_audio_urls.py`, `extract_training_data.py`.

Remaining JSON under `frontend/public/data/`: `zones.json`, `coquitlam_city_boundary.json`,
`coquitlam_boundary_opt.json` — all three duplicate data already in PostGIS
(`public.zones`, `public.city_boundary`) and are candidates for the same treatment
hydrants just received.

### 4.2b Audio storage — resolved 2026-08-21

`backend/audio_files/recordings/` (421 files) is the sole recordings store, served at
`/api/audio` from `RECORDINGS_DIR`. Seven other locations held duplicates and were
removed:

| Location | Files | Cause |
|:--|--:|:--|
| `frontend/public/recordings/` | 131 | `phase2.py` dual-write, never read |
| `backend/frontend/public/recordings/` | 284 | same dual-write under a path that resolved differently |
| `services/backend/audio_files/recordings/` | 51 | off-by-one in the `dispatch_persistence.py` fallback (`range(4)` vs `range(5)`) |
| `backend/data/training/audio/` | 53 | duplicated dispatch audio, no reader |
| `backend/client/public/recordings/` | 6 | pre-rename frontend directory |
| `frontend/dist/recordings/` | — | build copy |
| `backend/test_capture.wav` | 1 | stray debug capture |

Every file was verified present in the canonical store before deletion. The dual-write
in `phase2.py` is removed, so none of these regenerate.

**Backtesting must read the canonical store**, filtered by the HITL review flags
(`feedback_submitted`, `verified_transcript`) on `public.dispatches`, rather than keeping
a second copy of the audio. `backend/data/training/audio/` was that second copy and had
no code reading it — likely residue from the Whisper/LoRA training experiment.

`backend/tests/audio_samples/` was removed. Its single fixture,
`pa_page_DISP-2026-AB76A8.wav`, was the only `.wav` tracked in git, nothing referenced it,
and its dispatch had no row in `public.dispatches`. The PA negative-control corpus will
instead come from accidental captures tagged `[PA]` in the HITL review notes, whose audio
is already in the canonical store (punch-list #14).
`backend/tests/test_calls/` and `run_test_suite.py` were both **deleted 2026-08-31**. The
eight WAV/transcript pairs were synthesised scenarios, named by incident type rather than
dispatch id, which §6.5 forbids as a test corpus.

### 4.3 Other scripts

`import_parcels.py` (566), `compile_mbtiles.py` (538), `crawl_cadastral_tiles.py` (491),
`extract_all_intersections_from_gis.py` (462), `backtest_regression.py` (446).
Independent and individually reviewable; low urgency.

> `precache_satellite_tiles.py` and `ingest_coquitlam_orthos.py` were **deleted 2026-08-31**
> with the Esri layer and the MrSID pipeline, so they no longer need auditing.

---

## Cross-cutting items

Not tied to a single file — worth handling as their own passes.

- **Worker process logging.** The background worker runs at default level (WARNING), so
  `logging.info` from the pipeline never reaches the journal. This actively obstructed
  the ntfy diagnosis on 2026-08-21: absence of log lines was mistaken for absence of
  calls. Configure the worker's logging to match the main process.
- **Config split between `backend/.env` and `docker-compose.yml`.** The host agent reads
  `backend/.env` (gitignored, so invisible in review) while containers read compose
  environment. `NTFY_TOPIC` diverged silently and cost a day of missed pushes. Audit
  every setting both sides read.
- **`APPARATUS_TIERS` duplication** across `routing_engine.py` and `EVORoutingEngine.js`,
  both marked PROVENANCE REQUIRED. Resolve as part of PROJECT_IDEAS #6.
- **Remaining lint (22).** 15 `react-refresh/only-export-components` — largely resolved
  by the DashboardHUD and MapLayers splits above. 4 `react-hooks/exhaustive-deps` and 3
  `react-hooks/preserve-manual-memoization` need per-case judgement.

---

## Suggested first three sessions

1. ~~`road_closure_service.py` → PostGIS.~~ **Done** (`206af55`).
2. ~~`DashboardHUD.jsx` → five files.~~ **Done.**
3. ~~`parser.py` → modules.~~ **Done** (six-module package). The
   `destructive_parser.py` divergence review was *not* done and is still open.
4. **Helper extraction for `react-refresh`.** Move non-component exports out of
   `MapLayers.jsx`, `ActiveAlertBanner.jsx`, `ReviewTable.jsx` and
   `VerificationSidebar.jsx` into sibling modules. Mechanical, clears 14 of the
   remaining 22 lint issues.

### Lesson recorded
`wc -l` counts newlines, not lines. `DashboardHUD.jsx` ended without a trailing newline,
so its final `}` sat on line 1084 while `wc -l` reported 1083 — the first extraction
silently truncated `RightSidebar`. When splitting by line range, verify brace and paren
balance per output file before trusting the build.

---

## Final phase — code hardening and review

The last stage of this review. Not started as of 2026-08-21.

### H1. PA page leakage (punch-list #14)
PA announcements carrying apparatus tones are captured as dispatches, because
`audio_listener.py` discards a page only when it matches the PA tone AND no apparatus
tone. Operator is tagging accidental captures with `[PA]` in the HITL review notes; the
field is already wired end to end, no code change needed. Once a corpus exists, pull the
audio by dispatch_id from the canonical store and fingerprint against it.

Most promising fix: post-transcription retraction. A real dispatch yields units, an
address and a map grid under the Locution template; a PA page parses to nothing. That
uses the structure of the announcement rather than trying to separate tones that may be
genuinely identical.

### H2. Maintenance and sync script conformance (§4.2 above)
Eleven scripts unaudited. Every one reviewed so far carried a real defect.

### H3. `public.intersections` integrity (punch-list #9, #13)
One confirmed false intersection; scope unknown. Consider deriving intersections from
`public.roads` geometry rather than importing a separate list.

### H4. Geocoder honesty gaps (punch-list #12)
Steps 5 and 6 report the requested address rather than what was actually resolved.

### H5. Test suite repair (punch-list #8, #10)
One stale test cascades into ~6 others. Three modules have never run in review.

### H6. Hook-dependency lint (7 remaining)
Per-case judgement; changes runtime behaviour; must not be bulk-edited.

### H7. Deferred from earlier phases
* `destructive_parser.py` divergence review — deferred from the parser split.
* `EVORoutingConfigModal` controls reference values removed in `c332b81` and currently do
  nothing; rebuild against PROJECT_IDEAS #6.
* `isWithinCoquitlam()` uses a bounding box that is 61.6% larger than the real municipal
  polygon; the backend could return an authoritative `in_city` flag now that
  `public.city_boundary` is queryable.

<!-- audit-ok: backend/tests/audio_samples/ -- records that the directory was removed -->
<!-- audit-ok: frontend/src/components/DashboardHUD.jsx -- §2.1 records its split into five components (4e9d578) -->
<!-- audit-ok: backend/test_capture.wav -- listed as a stray artefact to remove -->

<!-- audit-ok: backend/tests/test_calls/ -- records that the synthesised corpus was deleted 2026-08-31 -->
