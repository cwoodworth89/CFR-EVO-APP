# Progress - Worker M4

Last visited: 2026-08-13T17:05:50Z

## Status
- [x] Environment setup & BRIEFING.md creation
- [ ] Task 1: Local Test & Build Verification
  - [ ] Run backend test `python backend/tests/test_parcels_and_streetview_api.py`
  - [ ] Run backend test `python backend/tests/test_pipeline_unit.py`
  - [ ] Run frontend production build `cmd /c npm run build` inside `frontend/`
- [ ] Task 2: Git Commit & Push
  - [ ] Stage and commit changes: `git add . && git commit -m "feat: complete Street View facade engine overhaul & property table persistence"`
  - [ ] Push to main branch: `git push origin main`
- [ ] Task 3: Remote Kiosk Deployment over Tailscale SSH (`tcfire@100.95.146.94`)
  - [ ] Git pull on remote kiosk: `ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull"`
  - [ ] Rebuild frontend production assets on remote kiosk: `ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/frontend && npm run build"`
  - [ ] Check remote container stack status: `ssh tcfire@100.95.146.94 "docker ps"`
  - [ ] Verify PostgreSQL `parcels` table schema on remote kiosk
  - [ ] Test remote API lookup: `curl -s http://localhost:8000/api/parcels/lookup?query=3030+GORDON+AVE`
- [ ] Documentation & Handoff
  - [ ] Write `deployment.md`
  - [ ] Write `handoff.md`
  - [ ] Send summary message to parent agent
