# BRIEFING — 2026-08-14T05:29:25Z

## Mission
Build and orchestrate a 100% local, containerized GIS routing and map tile stack for CFR EVO (sub-10ms offline OSRM routing, local PMTiles/MBTiles tile server on 8081, health checks, MapBoard.jsx integration, and full-stack remote kiosk verification).

## 🔒 My Identity
- Archetype: project_orchestrator
- Roles: [orchestrator, user_liaison, human_reporter, successor]
- Working directory: c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\orchestrator_r2\
- Original parent: parent
- Original parent conversation ID: 7456a5ed-504f-4481-bac9-c06719afdf8e

## 🔒 My Workflow
- **Pattern**: Project Pattern (Explorer Survey -> Milestones -> Workers -> Reviewers -> Challengers -> Auditor)
- **Scope document**: c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\PROJECT.md
1. **Decompose**: Survey full scope with 3 Explorers, synthesize into PROJECT.md feature inventory & milestones.
2. **Dispatch & Execute**:
   - Milestone 1: Local OSRM Emergency Routing Container (`cfr_osrm`) & `routing_engine.py` integration with `continue_straight=true` [IN-PROGRESS]
   - Milestone 2: Local Offline Map Tile Server (`cfr_tiles`) & `MapBoard.jsx` Leaflet integration with local PMTiles/MBTiles endpoints [PENDING]
   - Milestone 3: Health Checks, Docker Stack Integration, E2E Verification & Remote Kiosk Deployment (`tcfire@100.95.146.94`) [PENDING]
3. **On failure**: Retry -> Replace -> Skip -> Redistribute -> Redesign
4. **Succession**: At 20 spawns, write handoff.md, spawn successor.
- **Work items**:
  1. Survey & Architecture Mapping [DONE]
  2. Milestone 1: OSRM Routing Stack [IN-PROGRESS]
  3. Milestone 2: Offline Tile Server Stack [PENDING]
  4. Milestone 3: Health Checks & Remote Verification [PENDING]
- **Current phase**: Milestone 1 Execution
- **Current focus**: Worker M1 executing `routing_engine.py` & unit tests

## 🔒 Key Constraints
- NEVER write, modify, or create source code files directly.
- NEVER run build/test commands yourself — require workers to do so.
- NEVER investigate or explore the problem at the code level — dispatch Explorers.
- Write only to your own .agents/orchestrator_r2/ folder (or PROJECT.md / ORIGINAL_REQUEST.md).
- Follow GEMINI.md rules: 100% local container stack, API_BASE_URL resolution, remote kiosk verification over Tailscale SSH.

## Current Parent
- Conversation ID: 7456a5ed-504f-4481-bac9-c06719afdf8e
- Updated: 2026-08-14T05:29:25Z

## Key Decisions Made
- Initiated Project Pattern with 3 parallel Survey Explorers. Completed Phase 0 Survey and created PROJECT.md.
- Dispatched Worker M1 to implement `routing_engine.py` and test suite.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|-------|------|-----------|--------|---------|
| survey_explorer_1 | teamwork_preview_explorer | Survey OSRM & Routing | completed | 6286e1a3-692c-4a76-b589-c1c43ed5823e |
| survey_explorer_2 | teamwork_preview_explorer | Survey Offline Map Tiles | completed | 47b95b9f-94bf-4ce6-900f-f150e206739e |
| survey_explorer_3 | teamwork_preview_spec_miner | Survey Infra & Deployment | completed | 430a2ca8-34af-4a3d-bd86-904279dc3aa1 |
| worker_m1 | teamwork_preview_worker | Implement M1 OSRM Routing Engine | in-progress | 854eb51a-85d3-4790-aeac-2cb643d46938 |

## Succession Status
- Succession required: no
- Spawn count: 4 / 20
- Pending subagents: 854eb51a-85d3-4790-aeac-2cb643d46938
- Predecessor: none
- Successor: not yet spawned

## Active Timers
- Heartbeat cron: e1e3b83e-229d-4daa-984a-1ac449027ff3/task-11
- Safety timer: none

## Artifact Index
- c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md — Authoritative User Request
- c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\orchestrator_r2\DISPATCH.md — Parent dispatch log
- c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\orchestrator_r2\progress.md — Progress and heartbeat tracking
- c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\PROJECT.md — Global architecture and milestone plan
