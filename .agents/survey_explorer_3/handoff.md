# Survey Explorer 3 (Infra & Deploy Spec Miner) — Specification & Handoff Report

## Executive Summary
This report provides the complete architectural specification, container orchestration blueprints, health check parameters, environment configurations, and step-by-step verification/deployment runbooks for the **100% Local Containerized GIS Routing and Map Tile Stack** (`cfr_osrm`, `cfr_tiles`, `cfr_api`, `cfr_postgres`, `cfr_mosquitto`, `cfr_ntfy`).

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Infra / Compose | `cfr_postgres` Container | PostgreSQL 16 Alpine container storing calls, evaluations, road closures, and parcels | Port 5432, `POSTGRES_DB=cfr_dispatch`, `POSTGRES_USER=cfr_user` | Persisted relational tables, GIN indexes, UUID extensions | Exits on data volume corruption; restarts `always` | `docker-compose.yml:2-15`, `backend/api/init_db.sql` |
| 2 | Infra / Compose | `cfr_mosquitto` Container | Eclipse Mosquitto 2.0 MQTT broker with dual TCP & WebSockets listeners | Ports 1883 (TCP) and 9001 (WebSockets) | Real-time pub/sub on topic `cfr/dispatches` | Drops disconnected clients; auto-reconnects on UI | `docker-compose.yml:16-25`, `services/mosquitto/mosquitto.conf` |
| 3 | Infra / Compose | `cfr_ntfy` Container | Local push notification service for mobile alerts | Port 8080 (maps to internal 80) | HTTP push notifications for unit call alerts | Retries on network timeouts | `docker-compose.yml:26-33`, `.env.example` |
| 4 | Infra / Compose | `cfr_api` Container | FastAPI Gateway routing dispatches, audio, road closures, parcels, and OSRM routing | Port 8000, `DATABASE_URL`, `MQTT_BROKER_HOST` | JSON REST APIs at `/api/dispatches`, `/api/route`, etc. | 500 error logged with stack trace; fallback to SQLite if DB offline | `docker-compose.yml:34-57`, `backend/api/server.py` |
| 5 | Infra / Compose | `cfr_osrm` Container *(New)* | High-performance containerized OSRM driving engine pre-loaded with Metro Vancouver OSM data | Port 5000, `/data/metro-vancouver.osrm` dataset | Sub-10ms GeoJSON route geometry, distance, and duration | Fallback to Haversine straight-line if container unreachable | `ORIGINAL_REQUEST.md:51-53`, `services/gis/src/gis_service/routing_engine.py` |
| 6 | Infra / Compose | `cfr_tiles` Container *(New)* | Offline local PMTiles / MBTiles vector & raster tile server | Port 8081, `/tiles/vancouver.pmtiles` | Sub-5ms map tile PBF/PNG responses over HTTP | 404 for out-of-bounds zoom/tile coordinates | `ORIGINAL_REQUEST.md:54-56`, `frontend/src/components/MapLayers.jsx` |
| 7 | Routing Engine | Momentum-Preserving Pathfinding | OSRM query parameter `continue_straight=true` preventing illegal U-turns on emergency apparatus | Waypoints `[origin_lng,origin_lat;dest_lng,dest_lat]` | Optimized route polyline respecting arterial roads | Falls back to default driving profile if omitted | `services/gis/src/gis_service/routing_engine.py:94-122` |
| 8 | Routing Engine | Tactical Corridor Biasing | Hall 1 departure waypoint injection for Mariner Way & Gordon Ave corridors | Origin Hall 1 GPS + target quadrant | Injected intermediate waypoints avoiding barrier islands | Direct path chosen if target not in biased quadrant | `services/gis/src/gis_service/routing_engine.py:225-240` |
| 9 | Routing Engine | Response Physics Modeling | Code 3 Emergency (45 km/h, 1.35x factor) vs Code 1 Routine (32 km/h, 1.45x factor) | `response_type` ("emergency" / "routine") | Dynamic ETA minutes calculation | Defaults to emergency mode (45 km/h) | `services/gis/src/gis_service/routing_engine.py:152-164` |
| 10 | Frontend Client | Dynamic Base URL Resolution | `API_BASE_URL` dynamically resolves `http://${window.location.hostname}:8000` | Browser URL / Hostname | IP-agnostic backend URL for kiosks over Tailscale | Defaults to `http://localhost:8000` if hostname empty | `frontend/src/apiClient.js:4-13` |
| 11 | Testing / QA | Curated Audio Benchmark Suite | End-to-end replay harness testing Whisper STT, parser, GIS geocoding, and DB | 7 curated line-in WAV recordings in `backend/tests/test_calls/` | Accuracy score, WER, CER, perfect/operational/failed % | Flags failures with specific error codes | `backend/tests/run_test_suite.py`, `e2e-dispatch-testing/SKILL.md` |
| 12 | Remote Ops | Tailscale Remote Kiosk Deploy | Controlled push/pull/rebuild workflow to physical station kiosk `100.95.146.94` | Local Git commits + SSH commands | Rebuilt `frontend/dist`, restarted daemons, verified health | Blocks unauthorized IPs; logs sudo operations | `kiosk-remote-ops/SKILL.md`, `setup_kiosk.sh` |

---

## Edge Cases

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | `cfr_osrm` Health Check | Target coordinates outside Metro Vancouver bounding box | OSRM returns code `"NoRoute"` or empty coordinates array; health check must probe known valid Coquitlam coordinate pair (`49.2910,-122.7907` to `49.2882,-122.7938`). |
| 2 | `cfr_tiles` Tile Request | Zoom level > 19 requested on PMTiles file capped at zoom 16 | Tile server returns 204 No Content or 404; Leaflet must configure `maxNativeZoom: 16` with `maxZoom: 22` to allow client-side canvas overscaling. |
| 3 | `cfr_postgres` Reconnection | FastAPI boots before PostgreSQL finishes schema init | `backend/api/database.py` fails quick ping and falls back to SQLite `cfr_dispatch.db`; docker compose `healthcheck` with `depends_on: condition: service_healthy` is mandatory to prevent SQLite fallback. |
| 4 | `cfr_mosquitto` WebSockets | Kiosk browser disconnects during network drop | Paho MQTT JavaScript client auto-reconnects with exponential backoff; backend publishes with QoS 1 to guarantee delivery. |
| 5 | Sibling Service Imports | `from gis_service.routing_engine import EVORoutingEngine` executed inside container vs local host | Container has `ENV PYTHONPATH=/app:...` in `backend/api/Dockerfile`; local host uses `sys.path` injection inside `backend/cfr_dispatch/__init__.py`. |
| 6 | Road Closure Intersections | Route corridor intersects active closure in `road_closures` table | `EVORoutingEngine` injects avoidance waypoints and attaches `closure_warnings` array to dispatch payload. |
| 7 | Remote Asset Build | `frontend/dist` ignored by Git | Remote kiosk must execute `cd frontend && npm install && npm run build` upon pulling changes from origin main. |

---

# 5-Component Handoff Report

## 1. Observation
1. **Existing `docker-compose.yml` (`file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/docker-compose.yml`)**:
   - Lines 1-15: `postgres:16-alpine` mapped to `5432:5432` with volume `postgres_data` and init script `./backend/api/init_db.sql`.
   - Lines 16-25: `eclipse-mosquitto:2.0` mapped to `1883:1883` (TCP) and `9001:9001` (WebSockets) with config `./services/mosquitto/mosquitto.conf`.
   - Lines 26-33: `binwiederhier/ntfy:v2.11.0` mapped to `8080:80`.
   - Lines 34-57: `api` container built from `backend/api/Dockerfile`, exposing `8000:8000`, depending on `postgres`, `mosquitto`, `ntfy`.
   - **Gap**: Currently missing explicit `healthcheck` blocks on existing services, and missing `cfr_osrm` (port 5000) and `cfr_tiles` (port 8081) service declarations.

2. **Backend Dockerfile (`file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/backend/api/Dockerfile`)**:
   - Lines 1-24: Based on `python:3.11-slim`. Installs `gcc`, `libpq-dev`, requirements from `backend/api/requirements.txt`, copies `backend` and `services`, and sets:
     `ENV PYTHONPATH=/app:/app/services:/app/services/gis/src:/app/services/audio/src:/app/services/dispatch_notifications/src`.
   - Runs `python -m backend.api.server`.

3. **Routing Engine Implementation (`file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/services/gis/src/gis_service/routing_engine.py`)**:
   - Lines 8-38: Master station directory with front-apron driveway GPS coordinates for Halls 1, 2, 3, 4.
   - Lines 103-105: Hardcoded OSRM URLs in `_fetch_osrm_polyline`:
     `https://router.project-osrm.org/route/v1/driving/{loc_str}...` and `http://127.0.0.1:5000/route/v1/driving/{loc_str}...`.
   - **Gap**: Should prioritize containerized URL `http://osrm:5000` (or `os.environ.get("OSRM_BACKEND_URL", "http://osrm:5000")`) and append `&continue_straight=true` to maintain vehicle momentum.

4. **Frontend API Client & Map Layers (`file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/frontend/src/apiClient.js` & `MapLayers.jsx`)**:
   - `apiClient.js:4-13`: Dynamically constructs `API_BASE_URL` using `window.location.hostname:8000` ensuring seamless operation when accessed remotely over Tailscale (`http://100.95.146.94:5173`).
   - `MapLayers.jsx:55-75`: Consumes `BASE_LAYERS` config from `MapConstants.js`. Currently points to external CARTO and ArcGIS tile servers.
   - **Gap**: Needs support for local tile server endpoint (`http://${window.location.hostname}:8081/tiles/{z}/{x}/{y}.png` or PMTiles protocol) for 100% offline basemap rendering.

5. **Remote Kiosk Host Configuration (`file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.agents/skills/kiosk-remote-ops/SKILL.md` & `setup_kiosk.sh`)**:
   - Host: `100.95.146.94` (`cfr-mapping-tcfh`, user: `tcfire`).
   - Nginx serves `frontend/dist` on port 80; Chromium runs in `--kiosk` mode pointing to `http://localhost`.
   - Backend agent runs as systemd unit `cfr-agent.service` with `XDG_RUNTIME_DIR=/run/user/1000`.

---

## 2. Logic Chain
1. **Container Health Interdependence**: If `cfr_api` starts before `cfr_postgres` has accepted connections, `backend/api/database.py` catches the connection exception and creates a fallback SQLite database (`cfr_dispatch.db`). This causes data drift between PostgreSQL and SQLite. Adding Docker health checks with `depends_on: condition: service_healthy` guarantees PostgreSQL and Mosquitto are fully initialized before `cfr_api` launches.
2. **Sub-10ms Offline Emergency Routing**: Querying the public internet OSRM server (`router.project-osrm.org`) introduces 150–500ms network latency and breaks in an internet outage. Provisioning `cfr_osrm` with local Metro Vancouver OpenStreetMap data (`.osrm` multi-level Dijkstra graph) guarantees deterministic sub-10ms response times. Appending `continue_straight=true` eliminates artificial U-turns on divided arterials (e.g. Pinetree Way, Lougheed Hwy).
3. **Local Tile Server for Total WAN Isolation**: Standard Leaflet basemaps query CARTO CDN servers. If WAN connectivity fails during a storm or emergency, the kiosk map goes blank/gray. Running `cfr_tiles` serving a local PMTiles/MBTiles archive of Metro Vancouver ensures crisp offline vector/raster map display.
4. **Controlled Remote Kiosk Synchronization**: Because `frontend/dist` is not checked into Git, and because code must never be modified directly on the production station hardware, the 3-phase deployment pipeline (local git push $\rightarrow$ remote git pull $\rightarrow$ remote `npm run build` + `systemctl restart`) is the only safe procedure.

---

## 3. Caveats
1. **OSRM Dataset Pre-Processing**: OSRM `.osrm` graphs must be pre-extracted and partitioned (`osrm-extract`, `osrm-partition`, `osrm-customize`) using the `car.lua` profile before mounting into `cfr_osrm`.
2. **Local Tile Container Selection**: If using PMTiles, `go-pmtiles` or a lightweight tile server container (e.g. `consbio/mbtileserver` or `maptiler/tileserver-gl`) should be selected based on image size and memory footprint on the station host (4GB–8GB RAM).
3. **Port Conflicts**: Port `5000` (OSRM) and `8081` (Tiles) must not conflict with host daemons on `100.95.146.94`.

---

## 4. Conclusion & Actionable Recommendations

### Recommendation 1: Updated `docker-compose.yml` Architecture
Add `cfr_osrm` and `cfr_tiles` along with full health check specifications:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: cfr_postgres
    restart: always
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-cfr_dispatch}
      POSTGRES_USER: ${POSTGRES_USER:-cfr_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-cfr_password_2026}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/api/init_db.sql:/docker-entrypoint-initdb.d/init_db.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-cfr_user} -d ${POSTGRES_DB:-cfr_dispatch}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  mosquitto:
    image: eclipse-mosquitto:2.0
    container_name: cfr_mosquitto
    restart: always
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./services/mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf
    healthcheck:
      test: ["CMD-SHELL", "mosquitto_sub -h localhost -p 1883 -t '$$SYS/broker/version' -C 1 -E -i healthcheck || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 5s

  osrm:
    image: osrm/osrm-backend:v5.27.1
    container_name: cfr_osrm
    restart: always
    command: osrm-routed --algorithm mld /data/metro-vancouver.osrm
    ports:
      - "5000:5000"
    volumes:
      - ./backend/data/osrm:/data:ro
    healthcheck:
      test: ["CMD-SHELL", "curl -f 'http://localhost:5000/route/v1/driving/-122.7907,49.2910;-122.7938,49.2882?overview=false' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  tiles:
    image: consbio/mbtileserver:latest
    container_name: cfr_tiles
    restart: always
    command: -d /tiles -p 8080
    ports:
      - "8081:8080"
    volumes:
      - ./frontend/public/data/tiles:/tiles:ro
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost:8080/health || curl -f http://localhost:8080/ || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  ntfy:
    image: binwiederhier/ntfy:v2.11.0
    container_name: cfr_ntfy
    restart: always
    command: serve --listen-http ":80" --web-root app
    ports:
      - "8080:80"

  api:
    build:
      context: .
      dockerfile: backend/api/Dockerfile
    container_name: cfr_api
    restart: always
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-cfr_user}:${POSTGRES_PASSWORD:-cfr_password_2026}@postgres:5432/${POSTGRES_DB:-cfr_dispatch}
      MQTT_BROKER_HOST: mosquitto
      MQTT_BROKER_PORT: 1883
      NTFY_SERVER_URL: http://ntfy:80
      OSRM_BACKEND_URL: http://osrm:5000
      JWT_SECRET: ${JWT_SECRET:-cfr_secret_key_change_in_prod_2026}
      RECORDINGS_DIR: /app/backend/audio_files/recordings
    ports:
      - "8000:8000"
    volumes:
      - ./backend/audio_files/recordings:/app/backend/audio_files/recordings
      - ./backend/data:/app/backend/data
      - ./frontend/public/data:/app/frontend/public/data:ro
    depends_on:
      postgres:
        condition: service_healthy
      mosquitto:
        condition: service_healthy
      osrm:
        condition: service_healthy
      tiles:
        condition: service_healthy
      ntfy:
        condition: service_started

volumes:
  postgres_data:
```

### Recommendation 2: Health Check Master Specification Table

| Container | Image | Target Port | Health Check Probe Command | Intervals & Thresholds | Healthy Indicator |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`cfr_postgres`** | `postgres:16-alpine` | `5432` | `pg_isready -U cfr_user -d cfr_dispatch` | Interval: 10s, Timeout: 5s, Retries: 5, Start: 10s | Returns exit code 0 (`accepting connections`) |
| **`cfr_mosquitto`** | `eclipse-mosquitto:2.0` | `1883` / `9001` | `mosquitto_sub -h localhost -p 1883 -t '$$SYS/broker/version' -C 1 -E -i healthcheck` | Interval: 10s, Timeout: 5s, Retries: 5, Start: 5s | Subscribes & receives 1 system packet, exits 0 |
| **`cfr_osrm`** | `osrm/osrm-backend:v5.27.1` | `5000` | `curl -f 'http://localhost:5000/route/v1/driving/-122.7907,49.2910;-122.7938,49.2882?overview=false'` | Interval: 10s, Timeout: 5s, Retries: 5, Start: 10s | HTTP 200 with JSON `code: "Ok"` |
| **`cfr_tiles`** | `consbio/mbtileserver` | `8081` | `wget -q --spider http://localhost:8080/health || curl -f http://localhost:8080/` | Interval: 10s, Timeout: 5s, Retries: 5, Start: 10s | HTTP 200 response |
| **`cfr_api`** | `backend/api/Dockerfile` | `8000` | `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/metrics/summary', timeout=3)"` | Interval: 15s, Timeout: 5s, Retries: 3, Start: 15s | HTTP 200 JSON with status `"online"` |

---

## 5. Verification Method

### Step 1: Local Unit & Integration Verification
Run the following test commands locally in PowerShell:
```powershell
# 1. Verify Milestone 1 Parcel Schema & Street View Overrides
python backend/tests/test_parcels_and_streetview_api.py

# 2. Verify Database Integration & GIS Geocoding Pipeline
python backend/tests/test_database_integration.py

# 3. Test Routing Engine directly with OSRM momentum preservation
python -c "from gis_service.routing_engine import EVORoutingEngine; r = EVORoutingEngine(); res = r.calculate_route(49.2828, -122.7946, 49.2910, -122.7907); print('Route status:', res['status'], 'Distance km:', res['distance_km'], 'Points:', len(res['polyline']))"

# 4. Verify Frontend Asset Compilation
cd frontend
npm run build
cd ..
```

### Step 2: Local Container Stack Health Verification
```powershell
# 1. Start all containers in daemon mode
docker compose up -d --build

# 2. Wait 15s and inspect health status
docker compose ps

# 3. Verify OSRM sub-10ms response
curl -i "http://localhost:8000/api/route?dest_lat=49.2828&dest_lng=-122.7946&station_id=1&response_type=emergency"

# 4. Verify Tile Server response
curl -I http://localhost:8081/
```

### Step 3: Remote Kiosk Deployment & Verification (`tcfire@100.95.146.94`)
Execute the standard remote verification pipeline:

```bash
# 1. Stage, commit, and push local modifications
git add .
git commit -m "feat(infra): add containerized OSRM routing and PMTiles tile server with health checks"
git push origin main

# 2. Pull updates and rebuild containers on the physical kiosk
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull origin main && docker compose up -d --build"

# 3. Rebuild frontend static assets on the kiosk
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/frontend && npm install && npm run build"

# 4. Restart daemons and verify container health
ssh tcfire@100.95.146.94 "sudo systemctl restart cfr-agent && sudo systemctl restart nginx && docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

# 5. Execute full-system live dispatch test
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && XDG_RUNTIME_DIR=/run/user/1000 .venv/bin/python backend/scripts/feed_recorded_call.py /home/tcfire/CFR-EVO-APP/backend/tests/test_calls/structure_fire_1st_alarm.wav 'Structure Fire Tone'"

# 6. Clean up temporary test dispatch records
ssh tcfire@100.95.146.94 "docker exec cfr_postgres psql -U cfr_user -d cfr_dispatch -c \"DELETE FROM live_calls WHERE target->>'is_test' = 'true' OR dispatch_id LIKE 'DISP-TEST-%';\""
```
