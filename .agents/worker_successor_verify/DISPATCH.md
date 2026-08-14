## 2026-08-14T00:13:32Z

You are a worker assigned to complete the final polish and verification tasks for the Google Street View Facade Engine Overhaul & Property Table Persistence project.

Working directory for your metadata/logs: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_successor_verify\`
Your original request path: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Skills to consult:
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\skills\kiosk-remote-ops\SKILL.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\skills\kiosk-ui-audit\SKILL.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\skills\google-imagery-streetview\SKILL.md`
- `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\skills\local-stack-orchestrator\SKILL.md`

Tasks:
1. (Minor Polish Check):
   Check `frontend/src/components/kiosk/StreetViewPanel.jsx`. Verify if `google.maps.event.clearInstanceListeners(panoramaRef.current)` (or `window.google.maps.event.clearInstanceListeners`) is explicitly included in the `useEffect` cleanup function when unmounting the panorama component. If not present or if listeners are only partially cleared, add `if (window.google?.maps?.event && panoramaRef.current) { window.google.maps.event.clearInstanceListeners(panoramaRef.current); }` in the cleanup callback.

2. Build & Test Locally:
   - Run local frontend build (`npm run build` inside `frontend/`).
   - Run local backend pytest or api checks in `backend/` to ensure 0 errors.

3. Git & Remote Sync (if modified or to ensure host sync):
   - If any file was modified, `git add . && git commit -m "polish: ensure explicit clearInstanceListeners on StreetViewPanel unmount"` and `git push origin main`.
   - On remote kiosk `tcfire@100.95.146.94`: `ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull && cd frontend && npm run build"`
   - Verify Docker containers / FastAPI service health on local and remote kiosk.

4. 100% Comprehensive Verification of Requirements R1-R5:
   Validate all acceptance criteria from `ORIGINAL_REQUEST.md`:
   - R1: Vantage point capture (heading, pitch, zoom/fov, lat, lng, pano_id) tracked in real-time.
   - R2: Unified PostgreSQL `parcels` table created, indexed by clean address, REST lookup and POST endpoints operational (`/api/parcels/lookup`, `/api/parcels/streetview`, `/api/streetview-overrides`).
   - R3: Standard Google Maps Platform JS SDK conformance (`StreetViewPanorama`, `pov_changed`, `position_changed`, `pano_changed`).
   - R4: Multi-launch rendering lifecycle with dark HUD loading skeleton ("Loading Street View Facade...") and smooth fade transition without gray/blank canvas flashes or WebGL context leaks.
   - R5: Controlled remote full-stack verification on physical kiosk `tcfire@100.95.146.94` and local environment.

Write your final findings and handoff report to `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_successor_verify\handoff.md` and send a summary message back when complete.
