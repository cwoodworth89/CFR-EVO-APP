# Changes Log — Milestone 1 Backend Fixes

## Target File
`backend/api/server.py`

## Summary of Modifications

1. **Import `IntegrityError` from `sqlalchemy.exc`**:
   - Added `from sqlalchemy.exc import IntegrityError` to enable explicit database constraint error handling during concurrent upserts.

2. **Enhanced Address Normalization & Validation (`_clean_streetview_address`)**:
   - Updated address cleaning logic to handle inputs with leading/trailing spaces correctly while matching unit prefixes and suffixes.
   - Enhanced unit cleaning regex patterns to:
     - Match unit prefixes with punctuation (e.g. `Unit 101, 3030 Gordon Ave`, `Apt 202 - 3030 Gordon Ave`, `#303, 3030 Gordon Ave`) via `r'^(UNIT|APT|SUITE|#)\s*\d+[\w-]*[,\-\s]+'`.
     - Match trailing unit suffixes (e.g. `3030 Gordon Ave Unit 101`, `3030 Gordon Ave Apt 202`) via `r'\s+[,\-]?\s*(UNIT|APT|SUITE|#)\s*\d+[\w-]*$'`.
   - Ensured empty strings, whitespace-only inputs, or strings cleaning to empty strings return `""`.

3. **Validation & HTTP 400 Bad Request Enforcement (`save_parcel_streetview`)**:
   - Implemented strict pre-save address validation in `save_parcel_streetview` (and by extension `save_streetview_override`):
     - Checks if raw target address/gis_id is empty or whitespace-only.
     - Checks if `_clean_streetview_address(raw_target)` returns an empty string.
     - Raises `HTTPException(status_code=400, detail="Address is empty or invalid")` to prevent bad or blank records from reaching database insertion.

4. **Concurrency Race Condition Handling (`save_parcel_streetview`)**:
   - Wrapped database insertion and synchronization logic for `ParcelModel` and `StreetViewOverrideModel` inside a `try...except IntegrityError:` block.
   - On `IntegrityError` (e.g., when parallel worker threads simultaneously attempt to insert a new address record and trigger a UNIQUE constraint violation on `clean_address` or `gis_id`):
     - Executes `db.rollback()`.
     - Performs a fallback retry query to fetch the newly created row.
     - Updates existing records with camera vectors (`streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, `front_lng`).
     - Commits the session and returns HTTP 200 with updated parcel payload.
   - Eliminates HTTP 500 database crashes during concurrent upserts.

## Verification
- `.agents/challenger_m1_1/stress_test_m1.py`: 8/8 PASSED (100%)
- `.agents/challenger_m1_1/test_empty_address_save.py`: PASSED (HTTP 400 caught)
- `.agents/challenger_m1_1/test_unit_variants.py`: PASSED (100% address resolution)
- `.agents/challenger_m1_1/test_end_units.py`: PASSED (100% end-unit resolution)
- `backend/tests/test_parcels_and_streetview_api.py`: PASSED (100%)
