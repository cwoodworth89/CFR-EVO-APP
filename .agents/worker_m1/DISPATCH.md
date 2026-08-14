# Worker M1 Dispatch: Local OSRM Emergency Routing Stack

## Mission Objective
Implement the local containerized OSRM routing engine logic in `services/gis/src/gis_service/routing_engine.py` and provide comprehensive unit tests in `backend/tests/test_routing_engine.py`.

## Mandatory Reading
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\PROJECT.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\GEMINI.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\survey_explorer_1\handoff.md`

## Write Ownership
- `services/gis/src/gis_service/routing_engine.py`
- `backend/tests/test_routing_engine.py`

## Specific Requirements
1. In `services/gis/src/gis_service/routing_engine.py`:
   - Prioritize `OSRM_BACKEND_URL` / `OSRM_ROUTER_URL` / `OSRM_URL` env vars, followed by local container endpoints (`http://osrm:5000`, `http://127.0.0.1:5000`, `http://localhost:5000`) before public WAN fallback.
   - Always append `continue_straight=true&steps=true` and `overview=full&geometries=geojson` to OSRM query URLs to preserve vehicle momentum and prevent illegal U-turns.
   - Set a fast timeout (1.0s) for local queries.
   - Preserve Station 1 tactical corridor waypoint injection (Corridor A: Mariner Way via Guildford->Johnson->Mariner; Corridor B: Gordon Ave via Pinetree->Lougheed->Christmas).
   - Implement robust fallback to straight-line waypoints with Haversine distance if OSRM is unreachable.
   - Avoid unhandled imports or missing dependencies.
2. In `backend/tests/test_routing_engine.py`:
   - Add unit tests verifying:
     - Endpoint priority list and URL construction with `continue_straight=true`.
     - Tactical corridor waypoint injection for Station 1 destinations (Mariner Way and Gordon Ave).
     - Response physics (Emergency Code 3 vs Routine Code 1 speed and ETA).
     - Fallback handling when OSRM is offline.
     - Distance and ETA calculation accuracy.
3. Run the test suite using Python / pytest to verify everything passes cleanly.
4. Write your completion report to `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1\handoff.md`.

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
