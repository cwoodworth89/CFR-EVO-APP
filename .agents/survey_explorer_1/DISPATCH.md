# Survey Explorer 1 Dispatch

## Mission
Investigate the existing routing architecture, OSRM backend requirements, `services/gis/src/gis_service/routing_engine.py`, `backend/`, existing `docker-compose.yml`, and local OSM data / routing profiles in CFR EVO.

## Specific Tasks
1. Read `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md` and `GEMINI.md`.
2. Inspect `services/gis/src/gis_service/routing_engine.py`, `docker-compose.yml`, and any other routing/GIS scripts or tests.
3. Check existing OSRM files or data in the project (e.g. `data/`, `backend/data/`, `services/gis/`).
4. Detail exact configuration needed for containerized `cfr_osrm` (`osrm-backend`) in `docker-compose.yml` on port 5000 with Metro Vancouver OSM data.
5. Detail changes required in `routing_engine.py` for routing to `http://osrm:5000` with `continue_straight=true`, sub-10ms response, and Station 1 tactical corridor support.
6. Write a comprehensive survey report to `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\survey_explorer_1\handoff.md`.
