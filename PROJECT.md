# Project: CFR EVO 100% Local GIS Routing & Map Tile Stack

## Architecture
- **Local Container Stack**: 100% offline-capable Docker Compose services running on the station host (`cfr_osrm` on :5000, `cfr_tiles` on :8081, `cfr_api` on :8000, `cfr_postgres` on :5432, `cfr_mosquitto` on :1883/:9001, `cfr_ntfy` on :8080).
- **Routing Engine (`services/gis/src/gis_service/routing_engine.py`)**: Embedded EVORoutingEngine querying containerized OSRM MLD backend on `http://osrm:5000` with `continue_straight=true` for apparatus momentum preservation, tactical corridor waypoint injection for Station 1 (Town Centre), and sub-10ms response times.
- **Offline Map Tile Server (`cfr_tiles`) & Leaflet Client**: Local tile server on port 8081 serving Metro Vancouver basemap tiles. Dynamic IP resolution in `frontend/src/apiClient.js` (`TILE_BASE_URL`), consuming tiles in `MapConstants.js`, `MapLayers.jsx`, and kiosk panels (`RouteOverviewPanel.jsx`, `BlockParcelPanel.jsx`) with zero external WAN internet dependency.
- **Station Kiosk Hardware (`tcfire@100.95.146.94`)**: Physical 10-foot apparatus bay display pulling Git commits, building Vite assets locally, running daemons with XDG runtime context, and displaying live emergency dispatches over Tailscale.

---

## Feature Inventory

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | `cfr_osrm` Container Service | Containerized `osrm-backend` running MLD algorithm on Metro Vancouver road graph on port 5000 | Milestone 1 | Survey 1 & 3 |
| 2 | OSRM Momentum Preservation | Injected `continue_straight=true` query parameter to prevent abrupt U-turns for heavy apparatus | Milestone 1 | Survey 1 & 3 |
| 3 | Station 1 Tactical Response Corridors | Waypoint injection for Mariner Way (Guildford->Johnson->Mariner) & Gordon Ave (Pinetree->Lougheed->Christmas) corridors | Milestone 1 | Survey 1 |
| 4 | Local Endpoint Prioritization & Fallback | `EVORoutingEngine` prioritizes `OSRM_BACKEND_URL` / `http://osrm:5000` with 1s timeout and straight-line fallback | Milestone 1 | Survey 1 |
| 5 | `cfr_tiles` Container Service | Local tile server container on port 8081 serving Metro Vancouver basemap tiles | Milestone 2 | Survey 2 & 3 |
| 6 | Dynamic `TILE_BASE_URL` Resolution | `apiClient.js` resolves `http://${window.location.hostname}:8081` for seamless remote kiosk & local access | Milestone 2 | Survey 2 |
| 7 | Offline Leaflet Basemap Integration | `MapConstants.js` & `MapLayers.jsx` consume `TILE_BASE_URL` with graceful fallback | Milestone 2 | Survey 2 |
| 8 | Kiosk Panels Offline Tile Integration | `RouteOverviewPanel.jsx` & `BlockParcelPanel.jsx` consume local tile layers | Milestone 2 | Survey 2 |
| 9 | Container Health Checks & Interdependence | Docker health checks on `cfr_postgres`, `cfr_mosquitto`, `cfr_osrm`, `cfr_tiles` with `depends_on: condition: service_healthy` | Milestone 3 | Survey 3 |
| 10 | Frontend Build & Local Integration QA | Clean Vite build (`npm run build`) and Python backend test suite verification | Milestone 3 | Survey 3 |
| 11 | Remote Kiosk Deploy & Full-Stack Verification | Git push -> pull on `tcfire@100.95.146.94`, container rebuild, frontend build, service restart, and live dispatch simulation | Milestone 3 | Survey 3 |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Local OSRM Emergency Routing Stack | `routing_engine.py`, `docker-compose.yml` (`osrm` service), routing unit tests | None | DONE |
| 2 | Local Offline Map Tile Server & Leaflet Integration | `docker-compose.yml` (`tiles` service), `apiClient.js`, `MapConstants.js`, `MapLayers.jsx`, kiosk panels | None | DONE |
| 3 | Health Checks, Full-Stack Integration & Remote Kiosk Deployment | `docker-compose.yml` health checks & dependencies, frontend build, backend test suite, remote deployment to `100.95.146.94`, live verification | M1, M2 | DONE |

---

## Interface Contracts

### 1. Backend Routing Engine ↔ OSRM Container (`http://osrm:5000`)
- **Request**: `GET /route/v1/driving/{lng1},{lat1};{lng2},{lat2};...?overview=full&geometries=geojson&continue_straight=true&steps=true`
- **Response**: JSON with `code: "Ok"`, `routes: [{ "geometry": { "coordinates": [[lng, lat], ...] }, "distance": meters, "duration": seconds }]`
- **Error Handling**: On timeout (>1.0s) or connection error, fallback to straight-line waypoints with Haversine distance.

### 2. Frontend Map Components ↔ Tile Server Container (`http://<host>:8081`)
- **Request**: `GET /styles/{style}/{z}/{x}/{y}.png` or `GET /data/vancouver/{z}/{x}/{y}.pbf` (or `{z}/{x}/{y}.png`)
- **Response**: Image/PBF binary tile content with `Content-Type: image/png` (or `application/x-protobuf`), CORS headers `Access-Control-Allow-Origin: *`.
- **Resolution**: Dynamically resolved via `TILE_BASE_URL` in `frontend/src/apiClient.js`.

### 3. FastAPI Gateway ↔ Frontend UI
- **Endpoint**: `GET /api/route?dest_lat={lat}&dest_lng={lng}&start_lat={lat}&start_lng={lng}&station_id={id}&response_type={emergency|routine}`
- **Response**:
  ```json
  {
    "status": "success",
    "distance_km": 4.12,
    "eta_minutes": 5,
    "response_mode": "Emergency (Code 3)",
    "origin": { "lat": 49.2910965, "lng": -122.7907256 },
    "destination": { "lat": 49.2785, "lng": -122.7850 },
    "polyline": [[49.2910965, -122.7907256], [49.2847, -122.7915], ...]
  }
  ```

---

## Code Layout

- `services/gis/src/gis_service/routing_engine.py` — EVORoutingEngine implementation
- `docker-compose.yml` — Local multi-container stack definition
- `frontend/src/apiClient.js` — Client API and Tile base URL resolution
- `frontend/src/components/MapConstants.js` — Base layer definitions and styling
- `frontend/src/components/MapLayers.jsx` — Leaflet base map and vector overlay components
- `frontend/src/components/kiosk/RouteOverviewPanel.jsx` — Kiosk route overview panel
- `frontend/src/components/kiosk/BlockParcelPanel.jsx` — Kiosk block/parcel mapping panel
- `backend/tests/test_routing_engine.py` — Routing engine test suite
