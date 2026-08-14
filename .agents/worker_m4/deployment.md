# Remote Deployment & Verification Log — Milestone 4 (R5)

**Deployment Target**: Remote Kiosk (`tcfire@100.95.146.94`, host `cfr-mapping-tcfh`)
**Timestamp**: 2026-08-13
**Git Commit**: `4c193fe` - `feat: complete Street View facade engine overhaul & property table persistence`

---

## 1. Local Automated Test Verification

- **Backend Parcels & Street View Test Harness**: `.venv\Scripts\python.exe backend/tests/test_parcels_and_streetview_api.py`
  - Result: **PASSED** (8/8 tests passed)
  - Tests verified: `test_address_normalization`, `test_parcel_model_nullable_gis_id`, `test_lookup_parcel_not_found`, `test_save_and_lookup_parcel_streetview`, `test_streetview_overrides_endpoint`, `test_legacy_streetview_override_fallback`, `test_legacy_post_streetview_overrides`, `test_migration_script_backfill`.

- **Backend Pipeline Unit Suite**: `.venv\Scripts\python.exe backend/tests/test_pipeline_unit.py`
  - Result: **PASSED** (5/5 unit tests passed in 0.015s)

- **Frontend Production Build**: `npm run build` (inside `frontend/`)
  - Result: **SUCCESS** (Vite v7.2.6 built in 3.63s, outputs `dist/assets/index-BvxfG2S9.js` and `dist/assets/index-CecTaWrE.css`).

---

## 2. Source Control & Repository Sync

- **Commit**: `git add . && git commit -m "feat: complete Street View facade engine overhaul & property table persistence"`
  - Result: Created commit `4c193fe` (123 files changed, 7718 insertions(+), 705 deletions(-)).
- **Push**: `git push origin main` -> successfully updated `https://github.com/cwoodworth89/CFR-EVO-APP.git` from `b550a16` to `4c193fe`.
- **Remote Git Pull**: `ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull"` -> successfully updated 123 files on remote kiosk host.

---

## 3. Remote Kiosk Deployment & Build Execution

- **Remote Frontend Build**: `ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/frontend && npm run build"`
  - Result: **SUCCESS** (Vite v7.2.6 built in 5.24s, outputs `dist/assets/index-BxHa_1K0.js` and `dist/assets/index-CecTaWrE.css`).

- **Remote Container Build & Restart**: `ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && docker compose up -d --build api"`
  - Result: **SUCCESS** (Rebuilt image `cfr-evo-app-api:latest` and recreated container `cfr_api`).

- **Remote Docker Container Status**: `ssh tcfire@100.95.146.94 "docker ps"`
  - Output:
    - `cfr_api`: Up & healthy (Port 8000)
    - `cfr_postgres`: Up 9 days (Port 5432)
    - `cfr_mosquitto`: Up 9 days (Ports 1883, 9001)
    - `cfr_ntfy`: Up 9 days (Port 8080)

- **Remote PostgreSQL `parcels` Table Schema Verification**:
  - Command: `ssh tcfire@100.95.146.94 "echo rescue | sudo -S docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch -c '\d parcels'"`
  - Result: **VERIFIED**
    ```
                                               Table "public.parcels"
           Column       |           Type           | Collation | Nullable |               Default               
    --------------------+--------------------------+-----------+----------+-------------------------------------
     id                 | integer                  |           | not null | nextval('parcels_id_seq'::regclass)
     gis_id             | character varying(255)   |           |          | 
     clean_address      | character varying(255)   |           | not null | 
     full_address       | character varying(255)   |           |          | 
     street_number      | character varying(50)    |           |          | 
     street_name        | character varying(255)   |           |          | 
     municipality       | character varying(100)   |           |          | 
     zone_id            | character varying(16)    |           |          | 
     geometry           | jsonb                    |           |          | 
     parcel_lat         | double precision         |           |          | 
     parcel_lng         | double precision         |           |          | 
     front_lat          | double precision         |           |          | 
     front_lng          | double precision         |           |          | 
     centroid_lat       | double precision         |           |          | 
     centroid_lng       | double precision         |           |          | 
     entrance_lat       | double precision         |           |          | 
     entrance_lng       | double precision         |           |          | 
     streetview_heading | double precision         |           |          | '0'::double precision
     streetview_pitch   | double precision         |           |          | '5'::double precision
     streetview_fov     | double precision         |           |          | '80'::double precision
     lock_box_notes     | text                     |           |          | 
     hazard_notes       | text                     |           |          | 
     pre_plan_pdf_url   | text                     |           |          | 
     construction_type  | character varying(100)   |           |          | 
     floor_count        | integer                  |           |          | 
     created_at         | timestamp with time zone |           | not null | now()
     updated_at         | timestamp with time zone |           | not null | now()
    Indexes:
        "parcels_pkey" PRIMARY KEY, btree (id)
        "ix_parcels_clean_address" UNIQUE, btree (clean_address)
        "ix_parcels_gis_id" UNIQUE, btree (gis_id)
        "ix_parcels_id" btree (id)
        "ix_parcels_zone_id" btree (zone_id)
    ```

- **Remote API Lookup Verification**:
  - Command: `ssh tcfire@100.95.146.94 "curl -s http://localhost:8000/api/parcels/lookup?query=3030+GORDON+AVE"`
  - Result: **VERIFIED**
    ```json
    {
      "found": true,
      "parcel": {
        "id": 1,
        "gis_id": "3030 GORDON AVE",
        "clean_address": "3030 GORDON AVE",
        "full_address": null,
        "street_number": null,
        "street_name": null,
        "municipality": null,
        "zone_id": null,
        "parcel_lat": null,
        "parcel_lng": null,
        "front_lat": 49.26995,
        "front_lng": -122.7919,
        "streetview_heading": 35.0,
        "streetview_pitch": 10.0,
        "streetview_fov": 80.0,
        "lock_box_notes": null,
        "hazard_notes": null,
        "pre_plan_pdf_url": null,
        "created_at": "2026-08-14T00:11:54.686919+00:00",
        "updated_at": "2026-08-14T00:11:54.686919+00:00",
        "lat": 49.26995,
        "lng": -122.7919,
        "heading": 35.0,
        "pitch": 10.0,
        "fov": 80.0
      }
    }
    ```
