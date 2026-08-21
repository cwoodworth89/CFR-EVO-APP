# CFR EVO: Module Decomposition & Review Plan

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

### 1.1 `backend/api/road_closure_service.py` (449 lines)

**Start here.** This is the clearest architectural regression in the codebase.

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
geocode, persist, MQTT and ntfy. Natural seams already exist as numbered comment
blocks. Review alongside `phase1.py` for duplicated broadcast logic.

### 1.3 `backend/cfr_dispatch/parser.py` (1053 lines, 20 functions)

Largest backend module. Clear functional groupings are already present: transcript
sanitisation, call-type matching, unit abbreviation and merge, street suffix
normalisation, radio channel matching, location extraction.

Candidate split: `parser/sanitize.py`, `parser/units.py`, `parser/location.py`,
`parser/channels.py`. Has a sibling `destructive_parser.py` — review the two together
for divergence.

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

### 2.1 `frontend/src/components/DashboardHUD.jsx` (1083 lines, 5 components)

**Best effort-to-payoff ratio in the frontend.** One file exports five separate
components: `Header`, `LeftSidebar`, `RightSidebar`, `ActiveDispatchPanel`, and a
private `SatelliteMiniMap`. Splitting them into five files is mechanical and resolves a
large share of the 15 outstanding `react-refresh/only-export-components` warnings.

Note: `SatelliteMiniMap` here duplicates the standalone component deleted in `d5fbdcc`.
This copy **does** guard coordinates correctly (`if (!lat || !lng) return null`), so it
is not a §5 defect — but decide whether it should exist at all.

### 2.2 `frontend/src/components/MapBoard.jsx` (1155 lines, **52 hook calls**)

Largest file in the project and the densest state container by a wide margin. Two of
the four runtime crashes fixed on 2026-08-21 originated here, both from identifiers
left behind by the training-mode removal.

Candidate extractions: road-closure marker and state, layer-toggle state,
target-address resolution, and the already-exported `enrichAddressWithBuilding` helper.

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

### 4.2 Other scripts

`import_parcels.py` (566), `compile_mbtiles.py` (538), `crawl_cadastral_tiles.py` (491),
`extract_all_intersections_from_gis.py` (462), `precache_satellite_tiles.py` (458),
`backtest_regression.py` (446). Independent and individually reviewable; low urgency.

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

1. **`road_closure_service.py` → PostGIS.** Self-contained, removes a real architectural
   regression, and is verifiable against `public.zones`.
2. **`DashboardHUD.jsx` → five files.** Mechanical, no logic change, clears most of the
   remaining lint.
3. **`parser.py` → four modules.** Highest-value backend split; pair with
   `destructive_parser.py` to check for divergence.
