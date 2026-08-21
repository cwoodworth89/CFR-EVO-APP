# CFR EVO: Workspace & Architectural Rules

This rule file defines domain constraints, runtime environments, and workflow standards for **CFR EVO**.

---

## 1. 100% Local Container Stack, $0 Subscription-Free & Municipal Open Data Architecture
* **Total Offline Survival**: The entire system (STT audio transcription, geocoding, turn-by-turn apparatus routing, GIS spatial queries, tile serving, and WebSocket dispatches) MUST function 100% offline without requiring internet/WAN connectivity.
* **$0 Monthly Costs (Cloud Deprecation)**: Do NOT re-introduce Supabase, Firebase, AWS RDS, or external cloud database dependencies. All dispatches, audio recordings, and MLOps metrics persist directly to containerized PostgreSQL 16 (`localhost:5432`). Zero recurring SaaS or geocoding API fees.
* **Authoritative Municipal Open Data Authority**: All parcel maps, zone polygons, hydrants, building footprints, and orthophotos are sourced directly from the City of Coquitlam Open Data Portal under the Open Government Licence:
  - 65,400 clean property parcels (`public.parcels` from `Cadastral.shp` + `Addresses.shp`)
  - 118 active emergency response zones (zones 1–134, `Emergency_Response_Zones.shp`)
  - City of Coquitlam 2025 7.5cm aerial orthophotos pre-cached locally on the kiosk SSD in SQLite MBTiles archives (sub-decimeter clarity for rooflines, hydrants, and driveways across Z12–Z20)
  - NFPA 291 color-coded fire hydrants with GPM ratings (`hydrants.json`)
  - 3D building footprints with LiDAR-derived heights (`Buildings.shp`)
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
5. **Git-Ignored Files**: Files in `.gitignore` (e.g. `backend/.env`, `frontend/.env.local`, model caches in `backend/models/`, shapefiles in `backend/data/`) are not synced via git and must be transferred manually via `scp` when updated.
6. **Local DB Access**: The `cfr-postgres` MCP server and any local scripts connect to the kiosk's Postgres directly over Tailscale (`DATABASE_URL` → `100.95.146.94:5432`), since that's the one authoritative database.

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

See also: [`PROJECT.md`](PROJECT.md) for architecture/feature/milestone tracking, [`README.md`](README.md) for setup instructions, and [`docs/agent_onboarding.md`](docs/agent_onboarding.md) for the full CLI command reference, SSH/audio (`XDG_RUNTIME_DIR`) heuristics, and the STT MLOps feedback pipeline.
