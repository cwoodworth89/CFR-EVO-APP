## 2026-08-13T23:44:43Z

You are the Project Orchestrator.

Your working directory is: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\orchestrator_r1\`
Read the verbatim user request from: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`

Your mission is to manage the end-to-end implementation and verification of:
# Complete Google Street View Facade Engine Overhaul & Property Table Persistence

## Key Directives:
1. Review workspace instructions in `GEMINI.md` and read all relevant skills in `.agents/skills/` (e.g., `google-imagery-streetview`, `local-stack-orchestrator`, `kiosk-remote-ops`, `kiosk-ui-audit`, `e2e-dispatch-testing`).
2. Create and maintain `plan.md` and `progress.md` in your working directory (`c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\orchestrator_r1\`).
3. Decompose the project into clear milestones covering R1 to R5:
   - R1: Continuous vantage point capture (position + orientation + zoom/fov).
   - R2: Unified `parcels` PostgreSQL table & migration, camera vector persistence, normalized address lookup endpoints (`GET /api/parcels/lookup?query={address}` and `/api/streetview-overrides/{address}`).
   - R3: Standard Google Maps Platform JS SDK conformance.
   - R4: Dark HUD loading skeleton, smooth transition, robust rendering lifecycle without gray/blank canvas flashes or WebGL context leaks across multi-launch.
   - R5: Controlled local automated testing AND remote full-stack deployment/verification over Tailscale SSH (`tcfire@100.95.146.94`).
4. Dispatch specialist subagents (workers/reviewers) to execute tasks according to your team strategy.
5. Continuously update `progress.md` as tasks complete.
6. When all acceptance criteria are fully met and verified both locally and on the physical kiosk host (`tcfire@100.95.146.94`), send a victory claim message back to Sentinel (`parent`).
