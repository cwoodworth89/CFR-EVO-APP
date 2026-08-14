# Reviewer 1 (Milestone 1): OSRM Emergency Routing Stack Review Report

## Review Summary

**Verdict**: **APPROVE**  
**Integrity Assessment**: **CLEAN (Zero Integrity Violations)**  
**Adversarial Challenge Risk Assessment**: **LOW**

---

## 1. Observation

1. **Endpoint Ordering & Container Prioritization (`services/gis/src/gis_service/routing_engine.py:94-118`)**:
   ```python
   def _get_osrm_endpoints(self, loc_str: str) -> List[str]:
       """Constructs prioritized candidate endpoints with continue_straight=true."""
       query_params = "overview=full&geometries=geojson&continue_straight=true&steps=true"
       
       candidates = []
       for env_key in ("OSRM_BACKEND_URL", "OSRM_ROUTER_URL", "OSRM_URL"):
           env_val = os.environ.get(env_key)
           if env_val and env_val.strip():
               candidates.append(env_val.strip().rstrip("/"))
       
       # Local container & localhost fallbacks, then public WAN fallback
       candidates.extend([
           "http://osrm:5000",
           "http://127.0.0.1:5000",
           "http://localhost:5000",
           "https://router.project-osrm.org"
       ])
   ```
   - Prioritizes environment variables (`OSRM_BACKEND_URL`, etc.), then container hostname `http://osrm:5000`, local host `127.0.0.1:5000` / `localhost:5000`, before finally falling back to public WAN (`https://router.project-osrm.org`).
   - Deduplicates candidate endpoints preserving order.
   - Enforces 1.0s timeout for local endpoints and 2.5s for WAN fallback (`routing_engine.py:129-130`).

2. **Momentum Preservation (`routing_engine.py:96`)**:
   - Injected query parameter `continue_straight=true` prevents abrupt U-turns across divided arterials, conforming to apparatus handling profiles.

3. **Tactical Response Corridors (`routing_engine.py:245-259`)**:
   - For Hall 1 departures heading southwest (`dest_lat < 49.280 and dest_lng < -122.800`), injects Mariner Way corridor:
     - `[49.2847, -122.7915]` (Pinetree & Guildford)
     - `[49.2845, -122.8055]` (Guildford & Johnson St)
     - `[49.2785, -122.8125]` (Johnson St & Mariner Way)
   - For Hall 1 departures heading south (`49.275 <= dest_lat <= 49.285 and -122.795 <= dest_lng <= -122.780`), injects Gordon Ave corridor:
     - `[49.2785, -122.7915]` (Pinetree & Lougheed)
     - `[49.2785, -122.7850]` (Lougheed & Christmas Way)
   - Corridors align exactly with specifications in `emergency-routing-engine` skill.

4. **Robust Offline / Error Handling (`routing_engine.py:145-148`, `264-270`)**:
   - Catches all exceptions during endpoint polling without raising unhandled errors.
   - Falls back gracefully to straight-line corridor waypoints with Haversine distance $\times$ road factor (1.35x for Code 3 Emergency, 1.45x for Code 1 Routine).

5. **Unit Test Suite Execution (`backend/tests/test_routing_engine.py`)**:
   - Command: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_routing_engine.py -v`
   - Result: `20 passed in 0.44s`.
   - Verified tests:
     - `TestFireHallsAndApparatusMapping`: 3 tests (fire halls directory, apparatus classification, station ID extraction).
     - `TestOSRMUrlConstructionAndPriorities`: 4 tests (default endpoint ordering, momentum query parameters, env var overrides, empty/single waypoint handling).
     - `TestTacticalCorridors`: 3 tests (Station 1 Mariner corridor, Station 1 Gordon corridor, non-Hall 1 passthrough).
     - `TestResponsePhysicsAndETAs`: 3 tests (Code 3 vs Code 1 physics, unit metrics calculation, Haversine distance accuracy).
     - `TestOSRMResponsesAndFallback`: 7 tests (mocked success polyline, offline URLError fallback, malformed JSON fallback, HTTP 500 error fallback, multi-unit calculation, edge cases & deduplication, custom start coordinates).

---

## 2. Logic Chain

1. **Zero Integrity Violations**:
   - Inspected source code in `services/gis/src/gis_service/routing_engine.py` and `backend/tests/test_routing_engine.py`.
   - No hardcoded test responses or fake assertions.
   - `EVORoutingEngine` implements genuine GeoJSON parsing, coordinate transformation (`[lng, lat]` $\to$ `[lat, lng]`), Haversine trigonometric distance calculations, and endpoint fallback loops.
   - Unit tests use standard `unittest.mock` mocking to simulate network states and verify real control flow.

2. **Requirements Satisfaction**:
   - **R1 (Local OSRM Routing)**: `routing_engine.py` queries `http://osrm:5000` as primary local endpoint with `continue_straight=true`.
   - **Tactical Corridors**: Correctly injected for Hall 1 departures into Mariner Way and Gordon Ave sectors.
   - **Physics & Response Modes**: Emergency (Code 3: 45 km/h, 1.35x factor) and Routine (Code 1: 32 km/h, 1.45x factor) correctly calculated and reflected in ETA calculations.
   - **Offline Resilience**: When OSRM is offline or unreachable, engine falls back to straight-line waypoints with road multiplier distance calculation, guaranteeing zero 500 crashes.

3. **Adversarial & Edge Case Stress Testing**:
   - Invalid `station_id="999"` $\to$ safely defaults to Hall 1 (`Town Centre Fire Hall`).
   - Coordinate `(0.0, 0.0)` $\to$ calculates Haversine distance without divide-by-zero or math domain errors.
   - Empty responding units list `[]` $\to$ returns empty list `[]`.
   - Unknown unit abbreviation `"UNKNOWN99"` $\to$ classifies as `Apparatus`, routes from Hall 1 without exception.
   - All tests pass deterministically in sub-second time (0.44s).

---

## 3. Caveats

- **OSRM Backend Runtime Dependency**: On live deployment, the `cfr_osrm` container requires `metro-vancouver.osrm` dataset mounted at `/data/metro-vancouver.osrm`. When data is not yet mounted, Docker container health check remains active and the Python engine gracefully falls back to straight-line coordinates.
- **Scope Boundary**: Review was scoped strictly to Milestone 1 (`routing_engine.py`, `test_routing_engine.py`, and `docker-compose.yml` `osrm` service). Map tile server integration (`cfr_tiles`) is managed in Milestone 2.

---

## 4. Conclusion

**Verdict: APPROVE**

The Milestone 1 OSRM Emergency Routing Stack implementation is well-architected, robust, fully tested, and meets all functional, architectural, and safety criteria.

---

## 5. Verification Method

To independently verify the implementation:

1. **Run Routing Engine Test Suite**:
   ```bash
   .\.venv\Scripts\python.exe -m pytest backend/tests/test_routing_engine.py -v
   ```
   *Expected Output*: `20 passed in ~0.45s`

2. **Run Interactive Fallback Test**:
   ```bash
   .\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'services/gis/src'); from gis_service.routing_engine import EVORoutingEngine; r = EVORoutingEngine(); res = r.calculate_route(dest_lat=49.2785, dest_lng=-122.7850, station_id='1'); print('Status:', res['status'], 'Distance:', res['distance_km'], 'Points:', len(res['polyline']))"
   ```
   *Expected Output*: `Status: success Distance: 2.43 Points: 4` (or 100+ points when OSRM is online).
