# Project: Google Street View Facade Engine Overhaul & Property Table Persistence

## Architecture
- **Backend Stack**: PostgreSQL 16 (`cfr_dispatch`), FastAPI (`http://localhost:8000/api`), SQLAlchemy ORM (`ParcelModel`, `StreetViewOverrideModel`).
- **Frontend Stack**: React 18, Google Maps JS SDK (`window.google.maps.StreetViewPanorama`, `window.google.maps.StreetViewService`).
- **Persistence Layer**: Primary table `parcels` with camera vector fields (`streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, `front_lng`), fallback table `streetview_overrides`, client `localStorage`.
- **Remote Kiosk Host**: Tailscale SSH `tcfire@100.95.146.94` (`cfr-mapping-tcfh`).

## Code Layout
- `backend/api/init_db.sql`: DB initialization script with `parcels` table DDL.
- `backend/api/models.py`: SQLAlchemy ORM definitions (`ParcelModel`, `StreetViewOverrideModel`).
- `backend/api/server.py`: FastAPI server routes (`GET /api/parcels/lookup`, `POST /api/parcels/streetview`, `GET /api/streetview-overrides/{address}`).
- `backend/scripts/migrate_streetview_to_parcels.py`: Database migration script.
- `frontend/src/apiClient.js`: REST API client for backend endpoints.
- `frontend/src/components/kiosk/StreetViewPanel.jsx`: Main Street View facade inspection panel.
- `frontend/src/components/kiosk/KioskView.jsx`, `MapBoard.jsx`: Kiosk views consuming StreetViewPanel.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | `parcels` DDL in `init_db.sql` | `CREATE TABLE IF NOT EXISTS parcels` with camera vector & pre-plan columns | M1 | survey |
| 2 | `ParcelModel` ORM Fixes | Make `gis_id` nullable, ensure full column mappings | M1 | survey |
| 3 | `server.py` Import & Syntax Fix | Import `ParcelModel`, fix line 721-733 syntax error | M1 | survey |
| 4 | Unified REST Endpoints | `/api/parcels/lookup`, `/api/parcels/streetview`, `/api/streetview-overrides/{address}` | M1 | survey |
| 5 | Address Normalization | Standardize `_clean_streetview_address` to match geocoder/parser | M1 | survey |
| 6 | API Client Methods | Add `parcels` methods to `frontend/src/apiClient.js` | M2 | survey |
| 7 | Continuous Vantage Point Capture | Track `heading`, `pitch`, `zoom`, `fov`, `lat`, `lng`, `pano_id` via JS SDK listeners | M2 | survey |
| 8 | Standard JS SDK Conformance | `StreetViewPanorama` + `StreetViewService` outdoor search + lifecycle events | M2 | survey |
| 9 | Atomic Property Persistence | "Save Preferred View" writes camera vectors to `parcels` DB + `localStorage` | M2 | survey |
| 10 | Saved Vantage View Restore | Restore saved vector on call load with `[SAVED PREFERRED VIEW]` indicator | M2 | survey |
| 11 | Dark HUD Loading Skeleton | Display "Loading Street View Facade..." skeleton until tiles render | M3 | survey |
| 12 | Smooth Fade-In Transition | Fade smoothly into panorama without blank/gray canvas flashes | M3 | survey |
| 13 | WebGL Context Lifecycle | Clear JS SDK listeners, prevent container wipes & WebGL context leaks | M3 | survey |
| 14 | Local Build & Unit Testing | Python pytest / database integration tests + `npm run build` | M4 | survey |
| 15 | Remote Kiosk Deployment | Git commit/push, remote `git pull`, remote build, service restart on `100.95.146.94` | M4 | survey |
| 16 | Physical Kiosk E2E Verification | Multi-launch verification on physical kiosk display | M4 | survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend PostgreSQL `parcels` Schema & REST Overhaul | DDL, ORM models, FastAPI endpoints, syntax fix, DB migration | none | DONE |
| M2 | Frontend JS SDK Conformance & Continuous Vantage Point Capture | `StreetViewPanel.jsx`, JS SDK listeners, vantage point state, `apiClient.js`, preferred view persistence | M1 | PLANNED |
| M3 | Dark HUD Loading Skeleton & WebGL Lifecycle Safety | Skeleton overlay, smooth fade transition, WebGL leak prevention, listener cleanup | M2 | PLANNED |
| M4 | Local Automated Testing & Remote Kiosk Deployment Verification | Local unit/build tests, Git push, remote kiosk build & systemctl restart, E2E kiosk verification | M1, M2, M3 | PLANNED |

## Interface Contracts
### Backend REST API ↔ Frontend Client
- `GET /api/parcels/lookup?query={address}`: Returns `{ found: bool, parcel: { clean_address, streetview_heading, streetview_pitch, streetview_fov, front_lat, front_lng, ... } }`.
- `POST /api/parcels/streetview`: Accepts JSON `{ clean_address, front_lat, front_lng, heading, pitch, fov }`. Returns `{ status: "success", parcel: {...} }`.
- `GET /api/streetview-overrides/{address}`: Fallback compatibility returning `{ clean_address, front_lat, front_lng, heading, pitch, fov }`.
