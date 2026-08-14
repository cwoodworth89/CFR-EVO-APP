# Forensic Audit & Handoff Report — Milestone 1

---

## Forensic Audit Report

**Work Product**: `services/gis/src/gis_service/routing_engine.py`, `backend/tests/test_routing_engine.py`  
**Integrity Mode**: Demo (from `ORIGINAL_REQUEST.md`)  
**Profile**: General Project / Forensic Auditor  
**Verdict**: **CLEAN**

### Phase Results
- **Hardcoded Output Detection**: **PASS** — No hardcoded test strings, fake coordinates, or short-circuit mock checks exist in production code.
- **Facade Implementation Detection**: **PASS** — Real trigonometric Haversine algorithms, dynamic URL builders with `continue_straight=true`, tactical corridor bounding-box logic, and resilient fallback calculations are fully implemented.
- **Pre-populated Artifact Detection**: **PASS** — No stale or fabricated test logs or outputs exist.
- **Behavioral & Test Execution**: **PASS** — 20 of 20 unit tests execute and pass independently in `0.48s`.
- **Dependency & Architecture Conformance**: **PASS** — Uses Python standard libraries (`urllib.request`, `json`, `math`, `re`, `os`) cleanly without forbidden external dependency bypasses.

---

## 1. Observation

1. **Production Code Analysis (`services/gis/src/gis_service/routing_engine.py`)**:
   - **Endpoint Construction (`_get_osrm_endpoints`, lines 94–118)**:
     ```python
     query_params = "overview=full&geometries=geojson&continue_straight=true&steps=true"
     ```
     Dynamically queries environment variables (`OSRM_BACKEND_URL`, `OSRM_ROUTER_URL`, `OSRM_URL`), followed by local container endpoints (`http://osrm:5000`, `http://127.0.0.1:5000`, `http://localhost:5000`) before falling back to WAN (`https://router.project-osrm.org`).
   - **Tactical Corridors (lines 244–259)**:
     - Detects Hall 1 departure via proximity checks or `station_id == "1"`.
     - Mariner Way Sector (`dest_lat < 49.280 and dest_lng < -122.800`): Injects `[49.2847, -122.7915]` (Pinetree & Guildford), `[49.2845, -122.8055]` (Guildford & Johnson St), and `[49.2785, -122.8125]` (Johnson St & Mariner Way).
     - Gordon Ave Sector (`49.275 <= dest_lat <= 49.285 and -122.795 <= dest_lng <= -122.780`): Injects `[49.2785, -122.7915]` (Pinetree & Lougheed) and `[49.2785, -122.7850]` (Lougheed & Christmas Way).
   - **Mathematical Logic (lines 83–92, 168–176, 236–242)**:
     - Genuine Haversine distance using spherical trigonometry ($R = 6371.0\text{ km}$).
     - Emergency (Code 3): speed $45.0\text{ km/h}$, road factor $1.35\times$.
     - Routine (Code 1): speed $32.0\text{ km/h}$, road factor $1.45\times$.
   - **OSRM Fetch & Fallback Handling (lines 120–148, 261–272)**:
     - Sets local timeout to $1.0\text{s}$ and WAN timeout to $2.5\text{s}$.
     - Accurately converts GeoJSON coordinate ordering from `[lng, lat]` to Leaflet `[lat, lng]`.
     - Catches all connection exceptions, `HTTPError`, and JSON parsing errors, returning straight-line corridor points with calculated Haversine distance $\times$ road factor.

2. **Test Suite Analysis (`backend/tests/test_routing_engine.py`)**:
   - Contains 20 granular tests organized into 4 test classes:
     - `TestFireHallsAndApparatusMapping` (3 tests)
     - `TestOSRMUrlConstructionAndPriorities` (4 tests)
     - `TestTacticalCorridors` (3 tests)
     - `TestResponsePhysicsAndETAs` (3 tests)
     - `TestOSRMResponsesAndFallback` (7 tests)
   - Every test executes genuine assertions against actual inputs/outputs without tautological or self-certifying mock assertions.

3. **Independent CLI Execution**:
   - Command: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_routing_engine.py -v`
   - Result:
     ```
     ============================= test session starts =============================
     platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
     rootdir: C:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\backend
     configfile: pyproject.toml
     collected 20 items

     backend\tests\test_routing_engine.py::TestFireHallsAndApparatusMapping::test_fire_halls_master_directory PASSED [  5%]
     backend\tests\test_routing_engine.py::TestFireHallsAndApparatusMapping::test_get_unit_type PASSED [ 10%]
     backend\tests\test_routing_engine.py::TestFireHallsAndApparatusMapping::test_get_unit_station_id PASSED [ 15%]
     backend\tests\test_routing_engine.py::TestOSRMUrlConstructionAndPriorities::test_osrm_default_endpoints_ordering PASSED [ 20%]
     backend\tests\test_routing_engine.py::TestOSRMUrlConstructionAndPriorities::test_osrm_query_parameters_momentum_preservation PASSED [ 25%]
     backend\tests\test_routing_engine.py::TestOSRMUrlConstructionAndPriorities::test_osrm_env_variable_prioritization PASSED [ 30%]
     backend\tests\test_routing_engine.py::TestOSRMUrlConstructionAndPriorities::test_fetch_osrm_polyline_empty_or_single_waypoint PASSED [ 35%]
     backend\tests\test_routing_engine.py::TestTacticalCorridors::test_station_1_mariner_corridor_injection PASSED [ 40%]
     backend\tests\test_routing_engine.py::TestTacticalCorridors::test_station_1_gordon_corridor_injection PASSED [ 45%]
     backend\tests\test_routing_engine.py::TestTacticalCorridors::test_non_hall_1_no_corridor_injection PASSED [ 50%]
     backend\tests\test_routing_engine.py::TestResponsePhysicsAndETAs::test_code3_vs_code1_physics PASSED [ 55%]
     backend\tests\test_routing_engine.py::TestResponsePhysicsAndETAs::test_unit_metrics_calculation PASSED [ 60%]
     backend\tests\test_routing_engine.py::TestResponsePhysicsAndETAs::test_haversine_distance_calculation PASSED [ 65%]
     backend\tests\test_routing_engine.py::TestOSRMResponsesAndFallback::test_osrm_mocked_success_polyline PASSED [ 70%]
     backend\tests\test_routing_engine.py::TestOSRMResponsesAndFallback::test_osrm_offline_fallback_handling PASSED [ 75%]
     backend\tests\test_routing_engine.py::TestOSRMResponsesAndFallback::test_osrm_malformed_json_fallback PASSED [ 80%]
     backend\tests\test_routing_engine.py::TestOSRMResponsesAndFallback::test_osrm_error_status_code_fallback PASSED [ 85%]
     backend\tests\test_routing_engine.py::TestOSRMResponsesAndFallback::test_calculate_units_routing_multi_units PASSED [ 90%]
     backend\tests\test_routing_engine.py::TestOSRMResponsesAndFallback::test_calculate_units_routing_edge_cases PASSED [ 95%]
     backend\tests\test_routing_engine.py::TestOSRMResponsesAndFallback::test_custom_start_coordinates PASSED [100%]

     ============================= 20 passed in 0.48s ==============================
     ```

---

## 2. Logic Chain

1. **Verification of Primary Deliverable**:
   - The user request and Milestone 1 specification mandate that `services/gis/src/gis_service/routing_engine.py` route emergency requests to `http://osrm:5000` with `continue_straight=true`, respect Station 1 tactical corridors, and fallback to straight-line waypoints with Haversine distance when offline.
   - Observations 1.1–1.4 prove that each required capability is directly implemented in production code with genuine mathematics and network logic.

2. **Absence of Integrity Violations**:
   - No hardcoded string checks or lookup tables exist in `routing_engine.py` to bypass calculations.
   - All distance calculations use genuine trigonometric computations ($R \times 2 \times \text{atan2}$).
   - All OSRM query URLs include `continue_straight=true`, `steps=true`, `overview=full`, `geometries=geojson`.
   - The fallback behavior returns true geometric path coordinates rather than null/error responses.

3. **Behavioral Integrity**:
   - Observation 3 confirms that all 20 tests in `test_routing_engine.py` pass without warnings or errors.
   - Adversarial stress tests (zero distance, duplicate unit identifiers, unlisted station IDs, malformed inputs) execute cleanly without unhandled exceptions.

---

## 3. Caveats

- **Docker OSRM Dataset Mounting**: The containerized `osrm-backend` service in `docker-compose.yml` expects a pre-compiled `.osrm` dataset at `./backend/data/osrm/metro-vancouver.osrm`. When the dataset is not yet present, `docker-compose.yml` executes an automated fallback loop and `routing_engine.py` gracefully provides straight-line tactical corridor fallback routing. Full end-to-end container integration will be tested in Milestone 3.

---

## 4. Conclusion

The Milestone 1 work product by Worker M1 (`services/gis/src/gis_service/routing_engine.py` and `backend/tests/test_routing_engine.py`) is **GENUINE, ROBUST, and FULLY COMPLIANT** with all requirements in `ORIGINAL_REQUEST.md`, `PROJECT.md`, and `GEMINI.md`.

**Verdict**: **`CLEAN`**

---

## 5. Verification Method

To independently reproduce this forensic audit:

1. **Run Routing Engine Test Suite**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest backend/tests/test_routing_engine.py -v
   ```
   *Expected*: `20 passed in < 1.0s` with exit code 0.

2. **Verify Python Syntax & Bytecode Compilation**:
   ```powershell
   .\.venv\Scripts\python.exe -m py_compile services/gis/src/gis_service/routing_engine.py backend/tests/test_routing_engine.py
   ```
   *Expected*: Exit code 0, no stdout/stderr output.

3. **Adversarial Direct Python Evaluation**:
   ```powershell
   .\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'services/gis/src'); from gis_service.routing_engine import EVORoutingEngine; r = EVORoutingEngine(); res = r.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id='1'); assert res['status'] == 'success' and len(res['polyline']) >= 4; print('Verified: OK')"
   ```
   *Expected*: `Verified: OK`.
