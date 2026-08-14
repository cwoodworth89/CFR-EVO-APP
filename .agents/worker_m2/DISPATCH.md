## 2026-08-14T00:03:22Z
You are Worker M2 (Frontend Street View Facade Engine & SDK Specialist).

Your assigned working directory is: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m2\`

Read the verbatim user request from: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`
Also review `GEMINI.md` for workspace rules and `google-imagery-streetview` skill.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Mission: Implement Milestone 2 (Frontend Street View Facade Engine JS SDK Conformance & Continuous Vantage Point Capture - R1 & R3).

Tasks:
1. `frontend/src/apiClient.js`:
   - Add `apiClient.parcels` helper methods:
     - `lookup: async (query)` -> calls `GET /api/parcels/lookup?query={query}`
     - `saveStreetView: async (payload)` -> calls `POST /api/parcels/streetview`

2. `frontend/src/components/kiosk/StreetViewPanel.jsx`:
   - Strictly conform to official Google Maps JS SDK (`window.google.maps.StreetViewPanorama`, `StreetViewService`).
   - Implement continuous vantage point tracking in ref (`currentPovRef`) capturing full camera vector:
     `heading` (0-360°), `pitch` (-90 to +90°), `zoom`/`fov` (1-4), `lat`, `lng`, `pano_id`.
   - Bind JS SDK event listeners: `pov_changed`, `position_changed`, `pano_changed`, `zoom_changed`, `status_changed`.
   - On load: Fetch saved parcel override via `apiClient.parcels.lookup(cleanAddress)` / `apiClient.streetviewOverrides.get(cleanAddress)` and check `localStorage` (`cfr_sv_override_${cleanAddress}`).
   - If a saved preferred view exists, set panorama POV and position to saved coordinates/heading/pitch/fov and render a high-visibility `[SAVED PREFERRED VIEW]` indicator badge in HUD header.
   - On "Save Preferred View" button click:
     - Read active camera vector from `currentPovRef.current`.
     - Atomically post payload `{ clean_address, front_lat, front_lng, heading, pitch, fov, pano_id }` to `/api/parcels/streetview`.
     - Save to `localStorage` under `cfr_sv_override_${cleanAddress}`.
     - Update UI state so `[SAVED PREFERRED VIEW]` badge appears immediately.

3. Build Verification:
   - Run `cmd /c npm run build` inside `frontend/` directory to ensure zero JSX or syntax errors.

Document changes in `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m2\changes.md` and handoff report in `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m2\handoff.md`. Send a summary message when complete.
