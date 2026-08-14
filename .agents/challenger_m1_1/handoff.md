# Handoff Report — Milestone 1 (Backend PostgreSQL & REST Overhaul) Challenge

## 1. Observation

- **Worker Test Execution**: Executed `python backend/tests/test_parcels_and_streetview_api.py`.
  Command output:
  ```text
  --- Running Milestone 1 Parcels & Street View Test Harness ---
  Running test_address_normalization... PASSED
  Running test_parcel_model_nullable_gis_id... PASSED
  Running test_lookup_parcel_not_found... PASSED
  Running test_save_and_lookup_parcel_streetview... PASSED
  Running test_streetview_overrides_endpoint... PASSED
  Running test_legacy_streetview_override_fallback... PASSED
  Running test_legacy_post_streetview_overrides... PASSED
  Running test_migration_script_backfill... PASSED
  [SUCCESS] ALL MILESTONE 1 TESTS PASSED SUCCESSFULLY!
  ```

- **Challenger Stress Test Harness**: Created and executed `.agents/challenger_m1_1/stress_test_m1.py`, `.agents/challenger_m1_1/test_unit_variants.py`, and `.agents/challenger_m1_1/test_empty_address_save.py`.

- **Observed Failures**:
  1. **Concurrent Upsert Race Condition** (`backend/api/server.py:683-700`):
     - Command: `python .agents/challenger_m1_1/stress_test_m1.py`
     - Verbatim error output during 10-worker parallel upsert of new address `"5000 CONCURRENT ST"`:
       ```text
       (sqlite3.IntegrityError) UNIQUE constraint failed: parcels.clean_address
       [SQL: INSERT INTO parcels (gis_id, clean_address, ...) VALUES (?, ?, ...)]
       ```
     - Result: 2 out of 10 concurrent threads failed with unhandled database exception.
  2. **Address Normalization Regex Failure on Unit Separators** (`backend/api/server.py:564`):
     - Line 564 in `server.py`: `s = re.sub(r'^(UNIT|APT|SUITE|#)\s*\d+[\w-]*\s+', '', s, flags=re.IGNORECASE)`
     - Command: `python .agents/challenger_m1_1/test_unit_variants.py`
     - Verbatim test output:
       ```text
       Variant: 'Unit 101, 3030 Gordon Ave' -> Cleaned: 'UNIT 101, 3030 GORDON AVE' -> Found: False
       Variant: 'Apt 202 - 3030 Gordon Ave' -> Cleaned: '- 3030 GORDON AVE' -> Found: False
       Variant: '#303, 3030 Gordon Ave' -> Cleaned: '#303, 3030 GORDON AVE' -> Found: False
       ```
  3. **Whitespace Address Bypassing Validation** (`backend/api/server.py:676-680`):
     - Line 676 in `server.py`: `raw_target = payload.clean_address or payload.gis_id`
     - Command: `python .agents/challenger_m1_1/test_empty_address_save.py`
     - Verbatim output when passing `clean_address="   "`:
       ```text
       Whitespace clean_address & None gis_id: {'status': 'success', 'parcel': {'id': 26, 'gis_id': '', 'clean_address': '', ...}}
       ```
     - Result: Whitespace strings pass validation because `"   "` is truthy in Python, leading to clean_address `""` inserted into DB.

## 2. Logic Chain

1. **Concurrency Failure**: In `backend/api/server.py:683-700`, `save_parcel_streetview` performs `db.query(ParcelModel).filter(...).first()`. When two requests execute this query simultaneously before either commits, both receive `None`. Both attempt to call `db.add(p)` and `db.commit()`. The second commit fails the `clean_address` UNIQUE constraint, raising an uncaught `IntegrityError` that aborts the HTTP request with 500.
2. **Normalization Failure**: The regex `r'^(UNIT|APT|SUITE|#)\s*\d+[\w-]*\s+'` requires trailing spaces (`\s+`). When a unit number is followed by a comma (`,`) or hyphen (`-`), the trailing space match fails. Consequently, address variations like `Unit 101, 3030 Gordon Ave` clean to `UNIT 101, 3030 GORDON AVE` rather than `3030 GORDON AVE`, breaking property resolution in `lookup_parcel`.
3. **Whitespace Validation Failure**: `payload.clean_address` is not stripped before checking `if not raw_target`. A string containing only spaces `"   "` evaluates to `True`, passing validation and calling `_clean_streetview_address("   ")`, which returns `""`. This inserts empty string records into `parcels.clean_address`.

## 3. Caveats

- **SQLite vs PostgreSQL Concurrency Behavior**: Local stress tests were executed using SQLAlchemy against the local test database session. While PostgreSQL handles locking differently than SQLite, PostgreSQL will also throw `psycopg2.errors.UniqueViolation` when concurrent transactions insert duplicate values into a `UNIQUE NOT NULL` column without `ON CONFLICT` handling.
- **Frontend Fallback Handling**: If frontend clients always pre-sanitize addresses or retry HTTP 500 responses, the end-user impact is mitigated, but the backend REST API contract remains vulnerable.

## 4. Conclusion

While Worker M1 successfully implemented the PostgreSQL schema, nullable `gis_id`, legacy table migration, and standard camera vector persistence, empirical stress testing surfaced **critical concurrency and edge-case normalization flaws** in `backend/api/server.py`.

Worker M1 must apply the following fixes:
1. Wrap the upsert logic in `save_parcel_streetview` (`server.py`) with `try...except IntegrityError` block to catch duplicate key collisions and fall back to updating the existing record, or use atomic database upserts.
2. Update `_clean_streetview_address` regex in `server.py`:
   - Match optional punctuation after unit prefixes: `r'^(UNIT|APT|SUITE|#)\s*\d+[\w-]*[,\-\s]+'`
   - Match trailing unit suffixes: `r'\s+(UNIT|APT|SUITE|#)\s*\d+[\w-]*$'`
   - Strip input before empty check: `raw_target = (payload.clean_address or payload.gis_id or "").strip()`
3. Re-run `.agents/challenger_m1_1/stress_test_m1.py` to confirm 100% pass rate across all 8 stress tests.

## 5. Verification Method

Run the empirical stress test harness from workspace root:
```bash
python .agents/challenger_m1_1/stress_test_m1.py
```
Expected output upon fix completion:
```text
SUMMARY: 8 PASSED, 0 FAILED out of 8 tests.
```

VERDICT: REQUEST_CHANGES
