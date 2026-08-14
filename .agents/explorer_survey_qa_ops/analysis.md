# Analysis Report: QA, Testing & Remote Ops Baseline (CFR EVO)

**Author**: Explorer 3 (QA, Testing & Remote Ops Specialist)  
**Date**: 2026-08-13  
**Working Directory**: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\explorer_survey_qa_ops\`  
**Target Architecture**: CFR EVO 100% Local Container Stack & Remote Station Kiosk (`100.95.146.94`)

---

## 1. Executive Summary & Problem Scope

This report establishes the baseline quality assurance, testing infrastructure, container stack verification, and remote deployment operational protocols for **CFR EVO**. It focuses specifically on validating the acceptance criteria for **Requirement R5 (Controlled Remote Full-Stack Verification)** and supporting the Street View Facade Inspection panel overhaul.

### Key Discoveries:
1. **Backend Testing**: Powered by Python standard `unittest` and standalone diagnostic scripts in `backend/tests/` and `backend/scripts/`. Core suites include `test_pipeline_unit.py` (unit), `test_database_integration.py` (GIS & payload integration), `run_test_suite.py` (audio/STT/parser QA dashboard), and `backtest_parser.py` (parser regression against live DB).
2. **Frontend Testing**: React 19 + Vite 7 application in `frontend/`. Static build check `cmd /c "npm run build"` compiles production assets to `dist/`. Real-time UI and map verification is conducted via Chrome DevTools browser automation (`/browser`) and synthetic MQTT event injection.
3. **Local Container Stack**: PostgreSQL 16 (`5432`), FastAPI REST Gateway (`8000`), Mosquitto MQTT Broker (`1883`/`9001` WS), and Ntfy Push (`8080`). Schema supports parcel vantage points via `parcels` table (`streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, `front_lng`).
4. **Remote Deployment Protocol**: Target kiosk host `100.95.146.94` (`cfr-mapping-tcfh`) via Tailscale SSH user `tcfire`. Requires local git push followed by remote `git pull` and `npm run build` inside `/home/tcfire/CFR-EVO-APP/frontend`.

---

## 2. Test Architecture & Execution

### 2.1 Backend Test Suites (`backend/tests/`)

| Test File / Script | Framework / Type | Target Component | Execution Command |
| :--- | :--- | :--- | :--- |
| `backend/tests/test_pipeline_unit.py` | `unittest.TestCase` | Address string cleaning, round 1 completeness checks, payload builder, session state manager | `python backend/tests/test_pipeline_unit.py` |
| `backend/tests/test_database_integration.py` | Standalone Integration | GIS shapefile geocoding (`Addresses.shp`), intersection matching, database payload JSON schema, location verification flags | `python backend/tests/test_database_integration.py` |
| `backend/tests/run_test_suite.py` | Automated QA Suite | Levenshtein STT accuracy (`thefuzz`), metadata extraction (units, incident, grid), GIS shapefile geocoding, grid bounds envelope validation | `python backend/tests/run_test_suite.py` |
| `backend/tests/test_listener.py` | `unittest` | DSP tone detection & audio signal filtering | `python backend/tests/test_listener.py` |
| `backend/tests/test_fault_injection.py` | `unittest` | Error fallback safety & missing data handling | `python backend/tests/test_fault_injection.py` |
| `backend/scripts/backtest_parser.py` | Regression Backtest | Compares production `parser.py` against alternative parsers using human-verified DB dispatches | `python backend/scripts/backtest_parser.py` |
| `backend/scripts/backtest_regression.py` | MLOps Benchmark | Word Error Rate (WER) & Character Error Rate (CER) benchmarks across audio samples | `python backend/scripts/backtest_regression.py` |

### 2.2 Test Audio Datasets (`backend/tests/test_calls/`)
The automated suite evaluates ground-truth `.wav` audio files paired with `.txt` metadata specs:
* `structure_fire_1st_alarm.wav`: 1st Alarm Multi-Engine (`E1, E2, E4, R2, L1, C6` @ Westwood St & Gordon Ave, Grid 68)
* `mvi_engine_rescue.wav`: Standard MVI Assignment (`E1, R2` @ Panorama Dr & Johnson St, Grid 78)
* `vehicle_fire_port_mann_quint5.wav`: Major Vehicle Incident (`E2, R2, Q5, C5` @ Port Mann Bridge, Grid 52)
* `alarm_high_risk_care_facility.wav`: Care Facility High Risk (`E1, E4, R2` @ 1131 Dufferin St, Grid 81)
* `gas_leak_pinetree_secondary.wav`: Commercial Hazmat (`E1` @ 3000 Pinewood Ave, Grid 85)
* `medical_cardiac_arrest_superstore.wav`: Medical Cardiac (`M1` @ 3000 Lougheed Hwy, Grid 68)
* `wildland_fire_smoldering.wav`: Wildland Smoldering (`L1` @ Westwood St & Lincoln Ave, Grid 82)

### 2.3 Frontend Build & QA Setup (`frontend/`)
* **Package Scripts (`package.json`)**:
  - `dev`: `vite` (Starts dev server on `http://localhost:5173`)
  - `build`: `vite build` (Compiles production distribution to `frontend/dist/`)
  - `lint`: `eslint .`
  - `preview`: `vite preview`
* **Local Build Execution**: On Windows PowerShell, execute via `cmd /c "npm run build"` to bypass PowerShell execution policy locks.
* **UI Verification**: Uses Chrome DevTools browser automation (`/browser`) against `http://localhost:5173` and live MQTT dispatch simulation (`publish_mqtt_dispatch` in `notification_service`).

---

## 3. Local Container Stack & REST API Verification

### 3.1 Container Architecture & Service Mapping

```
+-----------------------------------------------------------------------+
|                       LOCAL DOCKER COMPOSE STACK                       |
|                                                                       |
|  +-------------------+  +-------------------+  +-------------------+  |
|  | PostgreSQL 16 DB  |  |  FastAPI Gateway  |  |  Mosquitto MQTT   |  |
|  | Port: 5432        |  |  Port: 8000       |  |  Port: 1883 (TCP) |  |
|  | DB: cfr_dispatch  |  |  Service: cfr_api |  |  Port: 9001 (WS)  |  |
|  +-------------------+  +-------------------+  +-------------------+  |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  | Ntfy Push Server (Port: 8080)                                    |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

### 3.2 Database Schema & `parcels` Table Definition
The primary table for property persistence is **`parcels`** (SQLAlchemy model `ParcelModel` in `backend/api/models.py`):

```sql
CREATE TABLE IF NOT EXISTS public.parcels (
    id SERIAL PRIMARY KEY,
    gis_id TEXT UNIQUE NOT NULL,
    clean_address TEXT,
    full_address TEXT,
    zone_id VARCHAR(16),
    geometry JSONB,
    front_lat DOUBLE PRECISION,
    front_lng DOUBLE PRECISION,
    centroid_lat DOUBLE PRECISION,
    centroid_lng DOUBLE PRECISION,
    
    -- Preferred Street View Camera Angle
    streetview_heading DOUBLE PRECISION,
    streetview_pitch DOUBLE PRECISION,
    streetview_fov DOUBLE PRECISION,

    -- Coquitlam Tactical Property & Pre-Plan Metadata
    lock_box_notes TEXT,
    hazard_notes TEXT,
    pre_plan_pdf_url TEXT,
    entrance_lat DOUBLE PRECISION,
    entrance_lng DOUBLE PRECISION,
    construction_type TEXT,
    floor_count INTEGER,

    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.3 REST Endpoints for Street View & Property Persistence (`backend/api/server.py`)

1. **Lookup Property & Vantage Point**:
   - `GET /api/parcels/lookup?query={address}`
   - **Behavior**: Cleans address via `_clean_streetview_address()`, queries `ParcelModel` by `gis_id` or `clean_address`, and returns `streetview_camera` object (`heading`, `pitch`, `fov`) alongside property metadata.
2. **Save Parcel Vantage Point**:
   - `POST /api/parcels/streetview`
   - **Payload**: `{"gis_id": "3030 GORDON AVE", "clean_address": "3030 GORDON AVE", "front_lat": 49.2781, "front_lng": -122.8123, "heading": 185.0, "pitch": 5.0, "fov": 75.0}`
   - **Behavior**: Atomically updates `streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, and `front_lng` in `parcels` (and mirrors to legacy `streetview_overrides` table for backward compatibility).
3. **Legacy Street View Override Endpoint**:
   - `GET /api/streetview-overrides/{address}` & `POST /api/streetview-overrides`
   - **Behavior**: Queries `ParcelModel` first; if unpopulated, falls back to legacy `streetview_overrides`. Writes forward directly to `save_parcel_streetview`.

### 3.4 Local Verification Commands

```powershell
# 1. Container status check
docker compose ps

# 2. Database table verification
docker compose exec postgres psql -U cfr_user -d cfr_dispatch -c "\dt"

# 3. Query parcels table directly
docker compose exec postgres psql -U cfr_user -d cfr_dispatch -c "SELECT id, gis_id, clean_address, streetview_heading, streetview_pitch, streetview_fov FROM parcels LIMIT 5;"

# 4. Test REST API endpoints locally
Invoke-RestMethod -Uri "http://localhost:8000/api/parcels/lookup?query=3030%20GORDON%20AVE" -Method Get
```

---

## 4. Remote Kiosk Deployment & Connection Protocol

### 4.1 Connection Specifications
* **Host Address**: `100.95.146.94` (hostname: `cfr-mapping-tcfh` via Tailscale VPN)
* **SSH User**: `tcfire`
* **Remote Workspace Directory**: `/home/tcfire/CFR-EVO-APP`
* **Audio System Runtime Variable**: `XDG_RUNTIME_DIR=/run/user/1000` (required for PortAudio / audio device operations)
* **Remote Container Stack**: `cfr_postgres`, `cfr_api`, `cfr_mosquitto`, `cfr_ntfy`

### 4.2 Mandatory Deployment Pipeline

```
[Local Dev Workspace]
   │
   ├─► 1. Run local tests: `python backend/tests/test_pipeline_unit.py`
   ├─► 2. Build local frontend: `cmd /c "npm run build"`
   ├─► 3. Git commit & push: `git add . && git commit -m "..." && git push origin main`
   │
[Tailscale SSH connection to tcfire@100.95.146.94]
   │
   ├─► 4. Pull changes: `cd /home/tcfire/CFR-EVO-APP && git pull`
   ├─► 5. Rebuild kiosk assets: `cd frontend && npm run build`
   └─► 6. Restart daemon (if needed): `sudo systemctl restart cfr-agent`
```

### 4.3 Git-Ignored Files Protocol
Files listed in `.gitignore` are **not** transferred via `git pull` and must be synced manually via `scp` when updated:
* `backend/.env`
* `frontend/.env.local`
* `backend/models/*` (Whisper model weights)
* `backend/data/` (ESRI Shapefiles)

---

## 5. Verification Protocol for Requirement R5 Acceptance Criteria

Requirement R5 specifies: *"All changes must be validated locally via automated endpoint/build tests and deployed over Tailscale SSH to the physical station kiosk host (`tcfire@100.95.146.94`) for end-to-end multi-launch verification."*

### Step-by-Step Verification Procedure:

#### Phase 1: Local Automated Verification
1. **Execute Unit Tests**:
   `python backend/tests/test_pipeline_unit.py` -> Must return `OK` (5/5 tests passing).
2. **Execute Database Integration Tests**:
   `python backend/tests/test_database_integration.py` -> Must return `Verification checks: PASSED`.
3. **Execute Frontend Production Asset Build**:
   `cmd /c "npm run build"` inside `frontend/` -> Must complete without compilation errors.
4. **Verify Local API Gateway Endpoints**:
   Confirm `GET /api/parcels/lookup` and `POST /api/parcels/streetview` respond with status 200 and expected JSON payload structure.

#### Phase 2: Remote Kiosk Deployment & Full-Stack Verification
1. **Push & Deploy**:
   ```bash
   git add . && git commit -m "feat(streetview): R5 verification build" && git push origin main
   ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull && cd frontend && npm run build"
   ```
2. **Database Verification on Kiosk**:
   Verify table schema and records:
   ```bash
   ssh tcfire@100.95.146.94 "echo rescue | sudo -S docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch -c 'SELECT id, gis_id, clean_address, streetview_heading, streetview_pitch, streetview_fov FROM parcels LIMIT 5;'"
   ```
3. **Interactive Kiosk Verification Checklist**:
   - [ ] Open active dispatch call on kiosk display (`100.95.146.94`).
   - [ ] Inspect Street View panel loading HUD: Sleek dark loading skeleton ("Loading Street View Facade...") renders and smoothly transitions into panorama without canvas flash or WebGL context leaks.
   - [ ] Drag/swipe, tilt, step along road, and zoom panorama: Confirm camera orientation state updates in real time.
   - [ ] Click "Save Preferred View": Confirm request POSTs to `/api/parcels/streetview` and updates PostgreSQL `parcels` table record.
   - [ ] Exit dispatch call and re-open call: Confirm saved camera vantage point immediately reloads with `[SAVED PREFERRED VIEW]` indicator.
   - [ ] Multi-Launch Stress Test: Perform exit/reopen cycle 5 consecutive times to ensure WebGL context clean disposal and zero memory accumulation.
4. **Post-Test Database Cleanup**:
   Purge synthetic test dispatches from live calls table:
   ```bash
   ssh tcfire@100.95.146.94 "echo rescue | sudo -S docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch -c \"DELETE FROM live_calls WHERE target->>'is_test' = 'true' OR dispatch_id LIKE 'DISP-TEST-%';\""
   ```
