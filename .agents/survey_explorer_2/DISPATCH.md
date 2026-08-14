# Survey Explorer 2 Dispatch

## Mission
Investigate offline map tile serving requirements, frontend Leaflet integration (`frontend/src/components/MapBoard.jsx`, `frontend/src/apiClient.js`), existing tile assets (PMTiles/MBTiles in `backend/data/` or `data/`), and local tile server container options (`cfr_tiles` on port 8081).

## Specific Tasks
1. Read `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md` and `GEMINI.md`.
2. Inspect `frontend/src/components/MapBoard.jsx` and `frontend/src/apiClient.js`.
3. Check existing map tile assets, vector/raster MBTiles, PMTiles, or tile server configurations across the codebase.
4. Detail the container setup for `cfr_tiles` in `docker-compose.yml` on port 8081 (e.g. tileserver-gl, go-pmtiles, or static python/node tile server).
5. Detail changes required in `MapBoard.jsx` to consume local basemap tiles via `API_BASE_URL` without external internet dependencies.
6. Write a comprehensive survey report to `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\survey_explorer_2\handoff.md`.
