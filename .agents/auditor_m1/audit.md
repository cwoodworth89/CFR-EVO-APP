# Forensic Audit Report — Milestone 1: Backend PostgreSQL & REST Overhaul

**Work Product**: Milestone 1 Deliverables (`backend/api/init_db.sql`, `backend/api/models.py`, `backend/api/server.py`, `backend/scripts/migrate_streetview_to_parcels.py`, `backend/tests/test_parcels_and_streetview_api.py`)  
**Integrity Mode**: Benchmark  
**Verdict**: CLEAN  

---

## 1. Forensic Verification Phase Results

| Check # | Verification Item | Status | Details |
|---|---|---|---|
| 1 | Hardcoded test results / Fake responses | **PASS** | Checked all API handlers (`lookup_parcel`, `save_parcel_streetview`, `get_streetview_override`, `save_streetview_override`). All handlers perform dynamic queries against the database session (`Session`) and return real queried/upserted data. |
| 2 | Facade detection | **PASS** | Every class and function (`_clean_streetview_address`, `ParcelModel`, `StreetViewOverrideModel`, `migrate_overrides`) implements genuine operational logic without dummy `return` constants or stubbed bodies. |
| 3 | Pre-populated artifacts | **PASS** | No pre-existing logs, result files, or fake attestation artifacts predate auditor testing. |
| 4 | Schema & DDL / ORM model alignment | **PASS** | PostgreSQL 16 DDL in `init_db.sql` defines `public.parcels` with `clean_address VARCHAR(255) UNIQUE NOT NULL`, `gis_id VARCHAR(255)` (nullable), camera vectors (`streetview_heading`, `streetview_pitch`, `streetview_fov`), and pre-plan fields. SQLAlchemy model `ParcelModel` in `models.py` is 100% aligned with DDL column types, nullability, unique constraints, and index declarations. |
| 5 | FastAPI routing & DB persistence | **PASS** | `server.py` uses standard FastAPI `@app.get` and `@app.post` routing, injected database sessions via `Depends(get_db)`, proper transaction handling (`db.commit()`, `db.refresh()`), and dual-table synchronization between `parcels` and legacy `streetview_overrides`. |
| 6 | Test suite authenticity | **PASS** | `backend/tests/test_parcels_and_streetview_api.py` runs real database operations via `SessionLocal()`, tests normalization regex, verifies nullable `gis_id`, tests 404/not-found states, verifies upserts, tests fallback logic when `ParcelModel` record is missing, tests legacy wrapper endpoint, and runs `migrate_overrides()`. |
| 7 | Benchmark Mode Conformance | **PASS** | Implementation uses standard framework tools (`FastAPI`, `SQLAlchemy`, `Pydantic`). No external core logic borrowing, static mocks, or prohibited dependencies found. |

---

## 2. Empirical Verification Results

Independent test run command executed by auditor:
```bash
python backend/tests/test_parcels_and_streetview_api.py
```

Raw Execution Output:
```text
--- Running Milestone 1 Parcels & Street View Test Harness ---
Running test_address_normalization...
PASSED: test_address_normalization
Running test_parcel_model_nullable_gis_id...
PASSED: test_parcel_model_nullable_gis_id
Running test_lookup_parcel_not_found...
PASSED: test_lookup_parcel_not_found
Running test_save_and_lookup_parcel_streetview...
PASSED: test_save_and_lookup_parcel_streetview
Running test_streetview_overrides_endpoint...
PASSED: test_streetview_overrides_endpoint
Running test_legacy_streetview_override_fallback...
PASSED: test_legacy_streetview_override_fallback
Running test_legacy_post_streetview_overrides...
PASSED: test_legacy_post_streetview_overrides
Running test_migration_script_backfill...
[MIGRATE] Found 4 legacy Street View override records to migrate...
[OK] Migration complete! Updated 3 existing parcels, created 1 new parcel records.
PASSED: test_migration_script_backfill

[SUCCESS] ALL MILESTONE 1 TESTS PASSED SUCCESSFULLY!
```

Return Code: `0`

---

## 3. Findings & Code Inspection Details

1. **`backend/api/init_db.sql`**:
   - `public.parcels` table DDL includes `id SERIAL PRIMARY KEY`, `gis_id VARCHAR(255)`, `clean_address VARCHAR(255) UNIQUE NOT NULL`, `streetview_heading`, `streetview_pitch`, `streetview_fov`, `lock_box_notes`, `hazard_notes`, `pre_plan_pdf_url`.
   - Index `idx_parcels_clean_address` created on `public.parcels (clean_address)`.

2. **`backend/api/models.py`**:
   - `ParcelModel` maps correctly to `parcels`. `gis_id` is `nullable=True`, `clean_address` is `nullable=False, unique=True`. Camera angles default to `0.0`, `5.0`, and `80.0`.

3. **`backend/api/server.py`**:
   - `_clean_streetview_address` strips unit/apt prefixes, removes city/province suffixes, normalizes abbreviations (`AVE`, `RD`, `ST`, `DR`, `HIGHWAY`, `BLVD`, `CRT`, `PL`).
   - `GET /api/parcels/lookup` queries `ParcelModel` first (by exact match or `ilike`), falling back to `StreetViewOverrideModel` if absent. Returns comprehensive parcel dictionary with camera angles.
   - `POST /api/parcels/streetview` atomically updates `ParcelModel` and syncs/upserts into `StreetViewOverrideModel`.
   - `GET /api/streetview-overrides/{address}` checks `ParcelModel` camera fields first before falling back to `StreetViewOverrideModel`.
   - `POST /api/streetview-overrides` forwards to `save_parcel_streetview` ensuring backward compatibility and single source of truth.

4. **`backend/scripts/migrate_streetview_to_parcels.py`**:
   - Backfills legacy `StreetViewOverrideModel` rows into `ParcelModel` by matching address or creating a new parcel row if none matches. Handled with explicit commit/rollback and UTF-8 / ASCII safe logging.

5. **`backend/tests/test_parcels_and_streetview_api.py`**:
   - Authentic integration test suite verifying DB creation, CRUD operations, address normalization, migration backfill, and fallback logic without using static mocks.

---

## 4. Final Audit Verdict

`VERDICT: CLEAN`
