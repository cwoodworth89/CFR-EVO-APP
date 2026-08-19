# Dispatch History

## 2026-08-18T14:54:04Z

Root-cause diagnosis and clean restoration of the authentic Coquitlam Cadastral property/address overlay layer, ensuring 100% local offline operation with zero synthetic black-box badges or ad-hoc visual hacks.

## Requirements
1. Root Cause Architecture Diagnosis: Investigate why the authentic municipal Cadastral overlay (property parcel boundary polygons, zoning, and address numbering) failed to display in the UI, auditing MapLayers.jsx, MapBoard.jsx, DashboardHUD.jsx, and local GIS endpoints.
2. Authentic Cadastral Vector Layer Restoration: Restore the authentic municipal Cadastral overlay using local offline GIS authority (local shapefiles, PostgreSQL/FastAPI vector endpoints, or vector MBTiles), rendering clean, thin parcel boundary lines and crisp numeric labels matching standard municipal GIS specifications.
   - Must NOT introduce ad-hoc DivIcon black badges or clumsy visual overrides.
   - Must operate 100% offline without relying on external WAN servers.
3. Toggle Contract & Cross-Basemap Integration: Ensure the Cadastral overlay toggle operates cleanly and deterministically across all basemap modes (Street with labels, Street no-labels, and 7.5cm Satellite) from Zoom 14 through Zoom 20.

## Project Rules & Constraints (GEMINI.md)
- 100% Local Container Stack & Offline Survival: Zero external WAN / ArcGIS cloud dependencies.
- Frontend API Endpoint Resolution: Import and use `API_BASE_URL` and `TILE_BASE_URL` from `frontend/src/apiClient.js`. Never hardcode `localhost` or use raw relative URLs.
- Verification: Must run `npm run build` and relevant tests. Verify locally and deploy/verify on remote kiosk (`100.95.146.94`) per deployment protocol.
- Deliver `handoff.md` in your working directory when finished.
