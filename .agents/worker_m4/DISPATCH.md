## 2026-08-14T00:04:52Z
You are Worker M4 (Remote Deployment & Verification Specialist).

Your assigned working directory is: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m4\`

Read the verbatim user request from: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`
Also review `GEMINI.md` (Git & Remote Kiosk Deployment Protocol) and `kiosk-remote-ops` skill.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Mission: Execute Milestone 4 (Local Automated Testing & Remote Kiosk Deployment Verification - R5).

Tasks:
1. **Local Test & Build Verification**:
   - Run backend test suite: `python backend/tests/test_parcels_and_streetview_api.py` and `python backend/tests/test_pipeline_unit.py`.
   - Run frontend production build: `cmd /c npm run build` inside `frontend/`.

2. **Git Commit & Push**:
   - Stage and commit all changes: `git add . && git commit -m "feat: complete Street View facade engine overhaul & property table persistence"`
   - Push to main branch: `git push origin main`

3. **Remote Kiosk Deployment over Tailscale SSH (`tcfire@100.95.146.94`)**:
   - Pull main updates on remote kiosk:
     `ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull"`
   - Rebuild frontend production assets on remote kiosk:
     `ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/frontend && npm run build"`
   - Check remote container stack status:
     `ssh tcfire@100.95.146.94 "docker ps"`
   - Verify PostgreSQL `parcels` table schema & test remote API lookup:
     `ssh tcfire@100.95.146.94 "echo rescue | sudo -S docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch -c '\d parcels'"`
     `ssh tcfire@100.95.146.94 "echo rescue | sudo -S docker exec -i cfr_api curl -s http://localhost:8000/api/parcels/lookup?query=3030+GORDON+AVE"`

Document deployment details in `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m4\deployment.md` and handoff report in `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m4\handoff.md`. Send a summary message when complete.
