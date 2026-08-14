# Orchestration Plan: Google Street View Facade Engine Overhaul & Property Table Persistence

## Objective
Deliver a complete overhaul of the Google Street View Facade Inspection panel and `parcels` property database persistence across backend (PostgreSQL 16 / FastAPI) and frontend (React / Google Maps JS SDK), verified both locally and remotely on the physical station kiosk host (`tcfire@100.95.146.94`).

## Strategy
Following the Project Pattern:
1. **Phase 0: Technical Survey**
   - Dispatch 3 parallel Explorers to investigate:
     - Explorer 1 (Backend/DB): Current PostgreSQL schema, migration setup, `parcels` vs `streetview_overrides` tables, FastAPI routes (`/api/parcels/lookup`, `/api/streetview-overrides`), models, services.
     - Explorer 2 (Frontend/SDK): `StreetViewPanel.jsx` / related frontend components, Google Maps JS SDK integration, `pov_changed`, `position_changed`, `pano_changed` events, UI skeleton/HUD, state management.
     - Explorer 3 (QA/Kiosk/Ops): Test suites, DB container setup, SSH remote deployment protocol on `tcfire@100.95.146.94`, remote kiosk environment, script helpers.
2. **Phase 1: Feature Inventory & Decomposition**
   - Merge findings into `PROJECT.md`.
   - Define clear milestones M1-M4 with interface contracts and verification criteria.
3. **Phase 2: Milestone Iteration Loop Execution**
   - M1: Backend DB Migration & REST Endpoints (`parcels` schema, lookup & override persistence).
   - M2: Frontend Street View Engine (JS SDK conformance, continuous vantage point tracking, heading/pitch/zoom capture, save view).
   - M3: Dark HUD Loading Skeleton, Lifecycle & WebGL Flash/Leak Prevention.
   - M4: Automated E2E Testing, Remote Deployment to `100.95.146.94`, Full Stack Kiosk Verification.
4. **Phase 3: Verification & Victory Claim**
   - Verify all acceptance criteria locally and on remote kiosk host.
   - Send victory claim to Sentinel (`parent`).
