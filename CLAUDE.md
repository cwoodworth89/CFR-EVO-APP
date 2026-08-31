# CFR EVO: Workspace & Architectural Rules

This rule file defines domain constraints, runtime environments, and workflow standards for **CFR EVO**.

---

## 1. 100% Local Container Stack, $0 Subscription-Free & Municipal Open Data Architecture
* **Total Offline Survival**: The entire system (STT audio transcription, geocoding, turn-by-turn apparatus routing, GIS spatial queries, tile serving, and WebSocket dispatches) MUST function 100% offline without requiring internet/WAN connectivity.
* **$0 Monthly Costs (Cloud Deprecation)**: Do NOT re-introduce Supabase, Firebase, AWS RDS, or external cloud database dependencies. All dispatches, audio recordings, and MLOps metrics persist directly to containerized PostgreSQL 16 (`localhost:5432`). Zero recurring SaaS or geocoding API fees.
* **Authoritative Municipal Open Data Authority**: All parcel maps, zone polygons, hydrants, building footprints, and orthophotos are sourced directly from the City of Coquitlam Open Data Portal under the Open Government Licence:
  - 65,400 clean property parcels (`public.parcels` from `Cadastral.shp` + `Addresses.shp`)
  - 118 active emergency response zones (zones 1–134, `Emergency_Response_Zones.shp`)
  - City of Coquitlam 2025 7.5cm aerial orthophotos, ingested from the source MrSID into
    `ortho.mbtiles` and served at `/services/ortho` (sub-decimetre clarity for rooflines,
    hydrants and driveways; z20-native, Leaflet upscales above it). **The separate
    `satellite.mbtiles` is Esri World Imagery, not City data** — see §1 licensing note below
    and `docs/debug_and_qa_punchlist.md` #47. Ingest procedure: `gis-pipeline-sync` skill §4.1.
  - NFPA 291 color-coded fire hydrants with GPM ratings (`hydrants.json`)
  - 3D building footprints with LiDAR-derived heights (`Buildings.shp`)
* **Third-Party Basemap Sources Are Not Covered By The City's Licence**: The Open Government
  Licence covers City data only — parcels, zones, hydrants, buildings, cadastral and the 7.5cm
  orthophotos. It does **not** reach `basemaps.cartocdn.com` (street layers) or Esri World
  Imagery (`satellite.mbtiles`); the City neither owns nor sublicenses either. Building this
  for the department does not inherit rights the department never held. Carto began stamping
  unauthenticated tiles `API KEY REQUIRED` between the original crawl and the 2026-08-27
  re-crawl, which is that licence answering for itself. Do not raise the street layers'
  `max_zoom` while Carto is the source. Open item: `docs/debug_and_qa_punchlist.md` #47.

* **PostGIS Spatial Database**: PostgreSQL 16 runs with PostGIS 3.4 extension (`postgis/postgis:16-3.4-alpine`). All GIS data (parcels, roads, intersections, emergency zones, city boundary, road names, custom_places) is stored in PostgreSQL as the single source of truth. In-memory shapefile loading has been eliminated. Vocabulary (units, call types, radio channels) is stored in `public.vocabulary` table. Import scripts: `backend/scripts/import_parcels.py` (parcels), `backend/scripts/import_gis_data.py` (roads, intersections, zones, vocabulary).
* **Centralized Offline Tile Architecture (`cfr_tiles` on Port 8081)**:
  - Base layers and high-resolution orthophotos are served directly by `mbtileserver` (`ghcr.io/consbio/mbtileserver:latest`) on port `8081` mounting `backend/data/tiles/`.
  - **OpenStreetMap Slippy Map Specification Compliance**: All MBTiles archives conform to standard Slippy XYZ Web Mercator (`EPSG:3857`) with top-left origin (`{z}/{x}/{y}`), eliminating TMS Y-inversion overhead at runtime.
  - Base layer endpoints:
    - SATELLITE: `http://${window.location.hostname}:8081/services/satellite/tiles/{z}/{x}/{y}.jpg` (Z12–Z20 zoom depth)
    - VOYAGER / OSM (Street): `http://${window.location.hostname}:8081/services/street/tiles/{z}/{x}/{y}.png`
    - GREY / DARK (No-Labels): `http://${window.location.hostname}:8081/services/street_nolabels/tiles/{z}/{x}/{y}.png`
    - CADASTRAL (Overlay): `http://${window.location.hostname}:8081/services/cadastral/tiles/{z}/{x}/{y}.png` (Z14–Z20 parcel & address overlay)
  - All layers maintain `fallbackUrl: null` for 100% offline integrity with zero external CDN/WAN asset leaks.
  - **SQLite WAL Read-Only Volume Constraint**: Because `cfr_tiles` mounts `backend/data/tiles/` as read-only (`:ro`), all `.mbtiles` archives must be checkpointed and converted to `PRAGMA journal_mode = DELETE` on compilation (`SQLITE_CANTOPEN` prevention).
  - **HTTP Method Constraint**: `mbtileserver` supports `GET` and `OPTIONS` only (`405 Method Not Allowed` on `HEAD` / `curl -I`).
* **API Gateway & Routing**: REST operations and dispatch persistence route via FastAPI (`http://localhost:8000/api/dispatches`). Apparatus turn-by-turn routing routes via local OSRM (`http://localhost:5000`).
* **Frontend API Endpoint Resolution**: All frontend components performing `fetch()` operations MUST import and use `API_BASE_URL` and `TILE_BASE_URL` from [`frontend/src/apiClient.js`](frontend/src/apiClient.js) (e.g., `fetch(\`${API_BASE_URL}/api/route?...\`)`). Never use raw relative paths (`fetch('/api/...')`) or hardcoded `localhost` strings, as remote kiosk browsers accessing the UI over Tailscale (`http://100.95.146.94:5173`) will route relative requests to the Vite static server (resulting in 404s).
* **Real-Time Broadcast**: Station kiosks listen to Mosquitto MQTT over WebSockets on port `9001` (topic: `cfr/dispatches`).

---

## 2. Sibling Service Import Path Resolution
Sibling microservices in `/services/*/src` (`gis_service`, `audio_service`, `notification_service`) are decoupled from `/backend`.
* **Important**: Do NOT modify or "fix" sibling import statements in the backend orchestration files (e.g., `from gis_service...`).
* **Runtime Injection**: Sibling paths are injected into `sys.path` dynamically inside [`backend/cfr_dispatch/__init__.py`](backend/cfr_dispatch/__init__.py).
* **Static Analysis**: Workspace `.vscode/settings.json` appends these paths to `python.analysis.extraPaths`.

---

## 3. Git & Remote Kiosk Deployment Protocol
The kiosk (`tcfire@100.95.146.94`, hostname `cfr-mapping-tcfh`, reachable over Tailscale) **is the test machine** — the full Docker Compose stack (Postgres, MQTT, OSRM, tiles, FastAPI) runs there, not locally. Nothing runs locally except standalone scripts as needed; there is no separate local stack to keep in sync.
1. **Local Edits First**: Make all code, config, and doc changes in the local Git repository first. **Never edit production code directly on the remote kiosk.**
2. **Local Scope Restriction**: Local command execution is reserved strictly for pre-development mini-scripts, scratch isolation tests, or standalone unit checks.
3. **Full-Stack Testing Happens on the Kiosk**: Once a fix or feature is implemented, commit and push to Git, pull on the kiosk, rebuild assets, and verify there — this is the normal test loop, not an exceptional deploy.
4. **Commit, Pull & Rebuild Execution**:
   ```bash
   git add . && git commit -m "..." && git push origin main
   ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull && cd frontend && npm run build"
   ```
5. **Pre-Commit Lint Guard**: `git config core.hooksPath .githooks` (once per clone) enables
   [`.githooks/pre-commit`](.githooks/pre-commit), which runs `npm run lint:crash` in
   `frontend/` whenever staged changes touch `frontend/src/**`. It blocks only the
   **crash class** — `no-undef` and use-before-declaration (TDZ) — because those compile
   cleanly through Vite and throw only at runtime on the kiosk. `npm run build` does NOT
   catch them. Style/hygiene lint (`npm run lint`) is advisory and never blocks.
   Bypass a single commit with `git commit --no-verify`.
6. **Git-Ignored Files**: Files in `.gitignore` (e.g. `backend/.env`, `frontend/.env.local`, model caches in `backend/models/`, shapefiles in `backend/data/`) are not synced via git and must be transferred manually via `scp` when updated.
7. **Local DB Access**: The `cfr-postgres` MCP server and any local scripts connect to the kiosk's Postgres directly over Tailscale (`DATABASE_URL` → `100.95.146.94:5432`), since that's the one authoritative database.

---

## 4. Skills & Sub-agents
This project's operational runbooks and specialist personas were migrated from Antigravity into Claude Code's native conventions:
* **Skills** live in [`.claude/skills/`](.claude/skills) (one `SKILL.md` per topic) and load automatically via the `Skill` tool when relevant — check there before writing a new runbook. Current skills: `dispatch-pipeline-ops`, `e2e-dispatch-testing`, `local-stack-orchestrator`, `mbtiles-tile-server`, `emergency-routing-engine`, `stt-mlops-backtest`, `hitl-log-analysis`, `gis-spatial-analysis`, `gis-pipeline-sync`, `road-closure-management`, `kiosk-remote-ops`, `kiosk-ui-audit`, `kiosk-responsive-ergonomics`, `google-imagery-streetview`, `performance-metrics-analytics`.
* **Sub-agents** live in [`.claude/agents/`](.claude/agents) and are invoked via the `Agent` tool for delegated work (parallel investigation, large mechanical edits, protecting main context): `call-review-analyst`, `dispatch-qa-engineer`, `frontend-kiosk-architect`, `gis-spatial-engineer`, `kiosk-remote-operator`, `performance-metrics-analyst`, `pipeline-core-engineer`, `stt-mlops-evaluator`.
* **Delegate mechanical/parallelizable work**: bulk file edits, test runners, log parsing, and independent research are good fits for a sub-agent so the main conversation stays focused on architecture and review. Don't delegate work whose result gates your very next step unless it's run in the foreground.
* When a recurring workflow emerges, propose updating this file or adding a new skill under `.claude/skills/`.

---

## 5. Universal Address Normalization, Error Banner & Two-Tier Out-of-Bounds Standard
* **No Silent Coordinate Fallbacks**: Kiosk HUD panels and mapping components MUST NEVER silently fall back to default station/city coordinates (e.g. `49.2838, -122.7932` or `49.27305, -122.88452`) when coordinates are missing or unresolved.
* **Two-Tier Out-of-Bounds & Standby Protocol**:
  - **Tier 1 (Location Unresolved / Missing Coordinates)**: If coordinates are null, NaN, or 0, suppress routing lines and display a high-visibility amber standby card (`⚠️ LOCATION UNRESOLVED — Coordinates awaiting operator verification` / `⚠️ UNRESOLVED INCIDENT LOCATION — ROUTING PAUSED`).
  - **Tier 2 (Out-of-Bounds Coordinates)**: If coordinates fall outside the authoritative City of Coquitlam spatial bounding box (`lat < 49.20 || lat > 49.39 || lng < -122.92 || lng > -122.70` via `isWithinCoquitlam(lat, lng)`), display: `🌐 NOT AVAILABLE OUTSIDE OF CITY — 7.5cm Orthophotos & Cadastral Parcels Cover City of Coquitlam Only.`
* **Dual Junction & Ambiguity Handling**: When `activeCall.is_ambiguous` or `candidates.length > 1`:
  - Display an interactive tactical candidate selector banner at the top of the route map (`⚠️ DUAL JUNCTION AMBIGUITY (N JUNCTIONS IN AREA)`).
  - Plot distinct markers for each candidate location (Active candidate: Gold, Alternate candidates: Sky Blue).
  - Enable one-touch switching so tapping candidate buttons or map markers immediately recalculates OSRM apparatus routes and updates destination targets in real time.
* **Canonical Address Normalization**: Standardize unit designations (`#105`, `Unit B`, `Suite 200`, `105-3000`), street suffix canonicalization (`AVE`, `ST`, `RD`, `DR`, `HWY`, `BLVD`, `WAY`, `CRT`, `PL`, `LN`, `CRES`), and intersection separators (` & `) across frontend and backend utilities (`frontend/src/utils/addressUtils.js`).

---

## 6. No Fabricated Data, No Unsourced Constants

This is an emergency dispatch system. A plausible-looking wrong answer is more
dangerous than a visible unknown, because crews cannot tell it is wrong. These rules
are absolute and override convenience, tidiness, and "the UI looks broken without it."

### 6.1 Never Invent a Value to Fill a Gap
If a value is unknown, it MUST propagate as `null` / `None` and render as an explicit
unknown (`--`, `--:--`, `-- km`, or a Tier 1 warning card). It MUST NEVER be replaced by:
* A default coordinate (see §5 — this is the same rule applied beyond geocoding).
* An estimated ETA, distance, or travel time.
* A default apparatus list, unit roster, radio channel, or incident type.
* A placeholder that reads as real data (`'02:30'`, `'Simulated Address'`, `['SQ1','E1','L1']`).

Suppress the output, warn, and let the operator see the gap. **An unknown reported as
unknown is a correct answer. An unknown reported as a number is a defect.**

### 6.2 Prefer the Authoritative Source Over a Local Model
Where a system of record already computes a value, use its answer rather than
re-deriving one:
* **Routing**: OSRM's `distance` and `duration` are authoritative. Do not recompute
  travel time from speed × distance, and do not estimate turn counts — OSRM returns
  the real turn list in `steps`.
* **Spatial**: PostGIS/PostGIS-backed municipal data is authoritative over hand-derived
  geometry. Do not approximate a spatial relationship with a latitude/longitude
  threshold comparison when the real geometry exists (e.g. rail crossings are
  `railway=level_crossing` in OSM, not `lat < 49.26`).
* **Geocoding**: A miss belongs in `public.intersections` / `public.parcels` as a data
  fix, never as a string-match special case in application code.

### 6.3 Every Magic Number Carries Its Source
Any hardcoded constant affecting operational output MUST carry an inline comment naming
where it came from. Acceptable provenance, in order of preference:

1. **Published standard** — cite it precisely, e.g.
   `# NFPA 1710 s4.1.2.1: 80s turnout time, alarm-to-en-route, fire suppression`
2. **Municipal / authoritative dataset** — name the table or layer, e.g.
   `# public.roads.speed (City of Coquitlam Transportation, posted limit)`
3. **Measured on this system** — state what was measured and when, e.g.
   `# Measured Hall 1 -> 428 Nelson, kiosk OSRM graph 2026-08-21: 9.74 km`
4. **Department operational policy** — name the decision and who set it.

A constant with no comment, or a comment that only restates the number, is treated as a
defect and removed. Invented-sounding rationale ("vehicle momentum preservation",
"assuming ~1.2 turns per km") is not provenance.

Where NFPA figures apply, prefer them over locally invented ones — notably **NFPA 1710**
(turnout and response time objectives) and **NFPA 291** (hydrant flow classification,
already used for hydrant colour coding).

### 6.4 Domain Constants Are Staged, Not Silently Applied
Apparatus physics, response-mode factors, and similar tuning values MUST NOT be applied
implicitly inside a calculation path. They belong in a named configuration surface that
is explicitly enabled and auditable. Until such a feature exists, the data may be
retained as clearly-marked staged seed data that is documented as **not applied** (see
`APPARATUS_TIERS` in `services/gis/src/gis_service/routing_engine.py` and
`frontend/src/utils/EVORoutingEngine.js`).

### 6.5 No Fabricated Dispatches
Test and demonstration paths MUST replay real historical dispatch records
("review" mode). Do not synthesise fake calls, addresses, units, or transcripts to
exercise the kiosk. Genuine pipeline test dispatches use the existing `is_test` flag and
`*TEST*` labelling.

### 6.6 Report Verification Honestly
Do not mark a bug fixed, a phase complete, or a value verified without checking it
against the running system or the working tree. Distinguish **reported** from
**confirmed** in status documents (see `docs/debug_and_qa_punchlist.md`), and state
plainly when something could not be verified and why.

---

---

## 7. Start From The Source Of Record

§6.3 requires every operational constant to carry its provenance. This section is that
rule moved upstream: **find the source before you write the value, not after.**

Every serious defect found in the 2026-08-21/22 review was a missing or wrong source
rather than a coding error — parcel proximity standing in for road topology, a fuzzy
score standing in for a street vocabulary, an alphabetical list standing in for a token
budget. None of them looked like bugs. They looked like working code.

### 7.1 Before Implementing, Identify What Governs It
Any change that produces an **operational value** or defines a **domain model** —
routing, geocoding, spatial relationships, response-time figures, hydrant classification,
dispatch parsing, STT tuning — starts by identifying the authority for it.

The first stop is [`docs/standards/README.md`](docs/standards/README.md), the index of
standards this project has obtained and what each one governs.

This does **not** apply to ordinary engineering choices — file layout, naming, a helper
extraction, a React hook. Those are judgement, not domain. The test is: *if this value or
model is wrong, can crews tell?* If not, it needs a source.

### 7.2 If Nothing Covers It, Stop And Say So
If `docs/standards/` has no entry covering the decision, **raise it with the user before
implementing.** State what you are about to decide, what would normally govern it, and
that nothing in the project covers it.

Do not improvise a model and carry on. Do not settle it with a "reasonable default". An
invented domain model is the most expensive kind of defect here, because it is invisible:
it produces plausible output indefinitely and nothing flags it.

### 7.3 Recollection Is Not Provenance
If you rely on a specification you know but that is **not** in `docs/standards/`, label it
as recollection and verify it against something authoritative before it reaches code —
the installed source of a pinned dependency counts, memory does not.

This has already bitten: a "224 token" Whisper limit was asserted from memory during the
review. It happened to be right, confirmed afterwards against the installed
`faster_whisper/transcribe.py`, but it was stated as fact before it was checked.

### 7.3a The API Name Is Not The Contract
Most of what governs this system is not a published standard at all — it is the behaviour
of the libraries it runs on. Those defects are the more dangerous kind, because a missing
standard *feels* like a gap while a library assumption feels like knowledge.

Every library defect found so far had the same shape: **the name described the intent, not
the behaviour.**

| Called | The name implies | It actually does |
|:--|:--|:--|
| `hotwords=` | these words are boosted | keeps the first 223 tokens, discards the rest silently |
| `token_set_ratio` | a similarity ratio | returns **100** when one token set is a subset of the other |
| `ST_Contains` | the point is in the polygon | excludes the boundary, so a junction on a zone edge is not contained |

Before an operational decision rests on a library function's behaviour, verify it against
the installed source of the pinned version, and record it in
[`docs/standards/dependency-behaviour.md`](docs/standards/dependency-behaviour.md).

The check is cheap. `token_set_ratio('LOUGHEED HWY', 'ALDERSON AVE & LOUGHEED HWY')`
returns `100`; running that took ten seconds and would have prevented a 4.3 km routing
error.

### 7.4 Cite The Clause, Not The Document
"Per NFPA 1710" is not provenance; `NFPA 1710 s4.1.2.1` is. A citation that cannot be
looked up is decoration. Where a standard has revisions, record which one.

### 7.5 Absence Is Recorded, Not Silent
When a standard *should* exist for something and the project does not have it, it belongs
in `docs/standards/README.md` as an open gap. An unknown source is tracked the same way an
unknown value is (§6.1): visibly.


**Picking up debugging work?** Start at
[`docs/review_status_handoff.md`](docs/review_status_handoff.md) — system state, what
changed, open items in priority order, and the environment gotchas that cost the most time.

See also: [`docs/standards/README.md`](docs/standards/README.md) for the standards index and
[`docs/standards/dependency-behaviour.md`](docs/standards/dependency-behaviour.md) for verified library semantics (§7),
[`PROJECT.md`](PROJECT.md) for architecture/feature/milestone tracking, [`README.md`](README.md) for setup instructions, and [`docs/agent_onboarding.md`](docs/agent_onboarding.md) for the full CLI command reference, SSH/audio (`XDG_RUNTIME_DIR`) heuristics, and the STT MLOps feedback pipeline.
