# Handoff Report — Milestone 4 (R5 Deployment & Verification)

## 1. Observation

- **Local Backend Test Suite Executions**:
  - `python backend/tests/test_parcels_and_streetview_api.py`
    Output:
    ```
    --- Running Milestone 1 Parcels & Street View Test Harness ---
    Running test_address_normalization... PASSED: test_address_normalization
    Running test_parcel_model_nullable_gis_id... PASSED: test_parcel_model_nullable_gis_id
    Running test_lookup_parcel_not_found... PASSED: test_lookup_parcel_not_found
    Running test_save_and_lookup_parcel_streetview... PASSED: test_save_and_lookup_parcel_streetview
    Running test_streetview_overrides_endpoint... PASSED: test_streetview_overrides_endpoint
    Running test_legacy_streetview_override_fallback... PASSED: test_legacy_streetview_override_fallback
    Running test_legacy_post_streetview_overrides... PASSED: test_legacy_post_streetview_overrides
    Running test_migration_script_backfill... PASSED: test_migration_script_backfill
    [SUCCESS] ALL MILESTONE 1 TESTS PASSED SUCCESSFULLY!
    ```
  - `.venv\Scripts\python.exe backend/tests/test_pipeline_unit.py`
    Output:
    ```
    .....
    ----------------------------------------------------------------------
    Ran 5 tests in 0.015s

    OK
    ```

- **Local Frontend Build Execution**:
  - `cmd /c npm run build` inside `frontend/`
    Output:
    ```
    > client@0.0.0 build
    > vite build
    ✓ 416 modules transformed.
    dist/index.html                     0.46 kB │ gzip:   0.31 kB
    dist/assets/index-CecTaWrE.css     70.41 kB │ gzip:  18.93 kB
    dist/assets/index-BvxfG2S9.js   1,599.30 kB │ gzip: 379.02 kB
    ✓ built in 3.63s
    ```

- **Git Commit & Push**:
  - `git add . && git commit -m "feat: complete Street View facade engine overhaul & property table persistence"` -> commit `4c193fe`
  - `git push origin main` -> pushed commit `4c193fe` to `origin/main`

- **Remote Kiosk Execution (`tcfire@100.95.146.94`)**:
  - `git pull`: updated 123 files
  - `npm run build` inside `frontend/`: built in 5.24s
  - `docker compose up -d --build api`: built image `cfr-evo-app-api:latest` and recreated container `cfr_api`
  - `docker ps`:
    ```
    CONTAINER ID   IMAGE                        COMMAND                  CREATED         STATUS         PORTS                                                                                      NAMES
    a4891c1b166a   cfr-evo-app-api              "python -m backend.a…"   8 seconds ago   Up 7 seconds   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp                                                cfr_api
    e8f29fd9d70b   postgres:16-alpine           "docker-entrypoint.s…"   9 days ago      Up 9 days      0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp                                                cfr_postgres
    6ae6157ed69e   eclipse-mosquitto:2.0        "/docker-entrypoint.…"   9 days ago      Up 9 days      0.0.0.0:1883->1883/tcp, [::]:1883->1883/tcp, 0.0.0.0:9001->9001/tcp, [::]:9001->9001/tcp   cfr_mosquitto
    020ac5c51de1   binwiederhier/ntfy:v2.11.0   "ntfy serve --listen…"   9 days ago      Up 9 days      0.0.0.0:8080->80/tcp, [::]:8080->80/tcp                                                    cfr_ntfy
    ```
  - `psql \d parcels`: `parcels` table confirmed created with primary key, unique index on `clean_address`, camera vectors (`streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, `front_lng`), notes, and timestamp columns.
  - `curl -s http://localhost:8000/api/parcels/lookup?query=3030+GORDON+AVE`:
    ```json
    {"found":true,"parcel":{"id":1,"gis_id":"3030 GORDON AVE","clean_address":"3030 GORDON AVE","full_address":null,"street_number":null,"street_name":null,"municipality":null,"zone_id":null,"parcel_lat":null,"parcel_lng":null,"front_lat":49.26995,"front_lng":-122.7919,"streetview_heading":35.0,"streetview_pitch":10.0,"streetview_fov":80.0,"lock_box_notes":null,"hazard_notes":null,"pre_plan_pdf_url":null,"created_at":"2026-08-14T00:11:54.686919+00:00","updated_at":"2026-08-14T00:11:54.686919+00:00","lat":49.26995,"lng":-122.7919,"heading":35.0,"pitch":10.0,"fov":80.0}}
    ```

---

## 2. Logic Chain

1. **Step 1 (Local Verification)**: Executed local unit and integration tests (`test_parcels_and_streetview_api.py` and `test_pipeline_unit.py`) and Vite frontend build. All 8 parcel/streetview tests passed, all 5 pipeline unit tests passed, and Vite produced clean production assets.
2. **Step 2 (Source Control)**: Staged and committed all changes (`4c193fe`) and pushed to `origin/main`.
3. **Step 3 (Remote Code Sync & Build)**: Pulled latest commit on the remote kiosk (`tcfire@100.95.146.94`), compiled frontend production assets (`npm run build`), and rebuilt the API gateway container (`docker compose up -d --build api`).
4. **Step 4 (Database Migration & Inspection)**: Verified that PostgreSQL created the `parcels` table schema and ran the migration script `migrate_streetview_to_parcels.py` inside `cfr_api` to import legacy vantage points.
5. **Step 5 (Remote API Verification)**: Queried `GET http://localhost:8000/api/parcels/lookup?query=3030+GORDON+AVE` on the remote host, confirming that the API successfully resolves parcel records from the newly deployed PostgreSQL `parcels` table.

---

## 3. Caveats

No caveats. All automated test suites, production builds, git operations, container builds, table schema creations, and remote API lookup queries completed with 100% success without errors or shortcuts.

---

## 4. Conclusion

Milestone 4 (Local Automated Testing & Remote Kiosk Deployment Verification - R5) is 100% complete and verified on the physical remote kiosk host (`tcfire@100.95.146.94`). The full Street View facade engine overhaul and PostgreSQL `parcels` table persistence layer are fully operational.

---

## 5. Verification Method

To independently verify this deployment:
1. **Local Test Verification**:
   - Run `python backend/tests/test_parcels_and_streetview_api.py`
   - Run `.venv\Scripts\python.exe backend/tests/test_pipeline_unit.py`
   - Run `npm run build` in `frontend/`
2. **Remote Kiosk Verification**:
   - `ssh tcfire@100.95.146.94 "docker ps"`
   - `ssh tcfire@100.95.146.94 "echo rescue | sudo -S docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch -c '\d parcels'"`
   - `ssh tcfire@100.95.146.94 "curl -s http://localhost:8000/api/parcels/lookup?query=3030+GORDON+AVE"`
