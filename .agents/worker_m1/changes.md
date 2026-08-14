# Milestone 1: Backend PostgreSQL `parcels` Schema & REST Overhaul - Changes Summary

## 1. PostgreSQL Schema (`backend/api/init_db.sql`)
- Added `CREATE TABLE IF NOT EXISTS public.parcels` definition with columns:
  - `id SERIAL PRIMARY KEY`
  - `gis_id VARCHAR(255)` (nullable)
  - `clean_address VARCHAR(255) UNIQUE NOT NULL`
  - `full_address VARCHAR(255)`
  - `street_number VARCHAR(50)`
  - `street_name VARCHAR(255)`
  - `municipality VARCHAR(100)`
  - `zone_id VARCHAR(16)`
  - `geometry JSONB`
  - `parcel_lat DOUBLE PRECISION`
  - `parcel_lng DOUBLE PRECISION`
  - `front_lat DOUBLE PRECISION`
  - `front_lng DOUBLE PRECISION`
  - `centroid_lat DOUBLE PRECISION`
  - `centroid_lng DOUBLE PRECISION`
  - `entrance_lat DOUBLE PRECISION`
  - `entrance_lng DOUBLE PRECISION`
  - `streetview_heading DOUBLE PRECISION DEFAULT 0.0`
  - `streetview_pitch DOUBLE PRECISION DEFAULT 5.0`
  - `streetview_fov DOUBLE PRECISION DEFAULT 80.0`
  - `lock_box_notes TEXT`
  - `hazard_notes TEXT`
  - `pre_plan_pdf_url TEXT`
  - `construction_type VARCHAR(100)`
  - `floor_count INTEGER`
  - `created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP`
  - `updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP`
- Added index `idx_parcels_clean_address` on `public.parcels (clean_address)`.
- Added legacy table definition `public.streetview_overrides` and index `idx_streetview_overrides_clean_address`.

## 2. SQLAlchemy Model (`backend/api/models.py`)
- Updated `ParcelModel`:
  - `gis_id` set to `nullable=True`.
  - `clean_address` set to `unique=True`, `nullable=False`.
  - Configured camera vector fields: `streetview_heading`, `streetview_pitch`, `streetview_fov`.
  - Configured tactical metadata fields: `lock_box_notes`, `hazard_notes`, `pre_plan_pdf_url`.
  - Ensured `created_at` and `updated_at` timestamps match schema.

## 3. REST API Gateway (`backend/api/server.py`)
- Added explicit import for `ParcelModel` and `re` module.
- Standardized `_clean_streetview_address` to remove city/province suffixes, unit/suite prefixes, and standardize street abbreviations.
- Fixed critical syntax error in `POST /api/streetview-overrides` (lines 721-733).
- Overhauled REST endpoints:
  - `GET /api/parcels/lookup`: Searches `parcels` by cleaned address or GIS ID. Falls back to `streetview_overrides`. Returns `{ found: bool, parcel: dict }`.
  - `POST /api/parcels/streetview`: Upserts camera vector (`heading`, `pitch`, `fov`, `front_lat`, `front_lng`) into `parcels` and syncs with `streetview_overrides`. Returns `{ status: "success", parcel: dict }`.
  - `GET /api/streetview-overrides/{address}`: Returns camera vector from `parcels` or legacy `streetview_overrides`.
  - `POST /api/streetview-overrides`: Wraps `save_parcel_streetview` for backwards compatibility.

## 4. Migration Script (`backend/scripts/migrate_streetview_to_parcels.py`)
- Updated imports for flexibility and added `_clean_streetview_address` normalization.
- Verified backfill logic to copy legacy override records into `parcels` table.
- Sanitized console outputs for Windows encoding compatibility.

## 5. Test Suite (`backend/tests/test_parcels_and_streetview_api.py`)
- Created comprehensive test harness verifying schema creation, model fields, address normalization, REST lookup/upsert endpoints, legacy fallbacks, and migration script backfilling.
