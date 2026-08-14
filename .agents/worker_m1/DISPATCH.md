## 2026-08-13T23:48:31Z
You are Worker M1 (Backend PostgreSQL & REST Specialist).

Your assigned working directory is: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1\`

Read the verbatim user request from: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`
Also review `GEMINI.md` for workspace rules and `google-imagery-streetview` skill.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Mission: Implement Milestone 1 (Backend PostgreSQL `parcels` Schema & REST Overhaul).

Tasks:
1. `backend/api/init_db.sql`: Add `CREATE TABLE IF NOT EXISTS parcels` DDL with columns:
   - `id SERIAL PRIMARY KEY`
   - `gis_id VARCHAR(255)` (nullable)
   - `clean_address VARCHAR(255) UNIQUE NOT NULL`
   - `street_number VARCHAR(50)`
   - `street_name VARCHAR(255)`
   - `municipality VARCHAR(100)`
   - `parcel_lat DOUBLE PRECISION`
   - `parcel_lng DOUBLE PRECISION`
   - `front_lat DOUBLE PRECISION`
   - `front_lng DOUBLE PRECISION`
   - `streetview_heading DOUBLE PRECISION DEFAULT 0.0`
   - `streetview_pitch DOUBLE PRECISION DEFAULT 5.0`
   - `streetview_fov DOUBLE PRECISION DEFAULT 80.0`
   - `lock_box_notes TEXT`
   - `hazard_notes TEXT`
   - `pre_plan_pdf_url TEXT`
   - `created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`
   - `updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`
   Create index on `clean_address`.

2. `backend/api/models.py`:
   - Update `ParcelModel` to ensure `gis_id` is `nullable=True`.
   - Ensure all camera vector and pre-plan fields match the schema.

3. `backend/api/server.py`:
   - Explicitly import `ParcelModel` from `models.py`.
   - FIX CRITICAL SYNTAX ERROR in lines 721-733 (`POST /api/streetview-overrides`).
   - Standardize `_clean_streetview_address` to cleanly handle address normalization.
   - Implement/overhaul REST endpoints:
     - `GET /api/parcels/lookup`: Lookup `parcels` table by cleaned query string. Fallback to `streetview_overrides`. Return `{ found: bool, parcel: dict }`.
     - `POST /api/parcels/streetview`: Upsert camera vector (`clean_address`, `front_lat`, `front_lng`, `heading`, `pitch`, `fov`) into `parcels` table. Fallback/sync to `streetview_overrides` if needed. Return `{ status: "success", parcel: dict }`.
     - `GET /api/streetview-overrides/{address}`: Fetch saved camera vector from `parcels` (or `streetview_overrides` fallback). Return `{ clean_address, front_lat, front_lng, heading, pitch, fov }`.

4. Migration Script: Check `backend/scripts/migrate_streetview_to_parcels.py` to ensure legacy override records are backfilled.

5. Test Verification:
   - Run local test commands (e.g. `python backend/tests/test_database_integration.py` or pytest / python test runners).
   - Verify table creation, syntax validity, and REST endpoint execution.

Document all changes in `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1\changes.md` and handoff report in `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1\handoff.md`.

Update `progress.md` in your working directory as you work. Send a summary message back to orchestrator when finished.
