# Adversarial Challenge Report — Milestone 1 (Backend PostgreSQL & REST Overhaul)

## Challenge Summary

**Overall risk assessment**: HIGH

Empirical stress testing of `backend/api/server.py` and `backend/api/models.py` confirmed core functionality for standard addresses, extreme floating-point camera vectors, sequential upserts, and nullable `gis_id` support. However, adversarial stress testing revealed **two high-impact failure modes**:
1. **Concurrency Race Condition**: Concurrent HTTP `POST /api/parcels/streetview` requests for new addresses fail with an unhandled database `IntegrityError` (HTTP 500).
2. **Address Normalization Regex Gaps**: Address variants with unit numbers containing punctuation (`Unit 101, 3030 Gordon Ave`, `Apt 202 - 3030 Gordon Ave`) or unit suffixes (`3030 Gordon Ave Unit 101`) fail normalization and parcel lookup. In addition, whitespace-only addresses (`"   "`) bypass input checks and insert empty string records into PostgreSQL.

---

## Challenges

### [High] Challenge 1: Concurrency Race Condition in `POST /api/parcels/streetview`

- **Assumption challenged**: Sequential DB check-then-insert (`SELECT` followed by `INSERT`) is safe for upserting streetview camera vectors.
- **Attack scenario**: Multiple apparatus kiosks or clients submitting saved preferred streetview camera angles for the same new property at the same instant (10 concurrent workers tested in `stress_test_m1.py`).
- **Blast radius**: The non-atomic read-then-write pattern causes 2 out of 10 concurrent threads to crash with `(sqlite3.IntegrityError / psycopg2.errors.UniqueViolation) UNIQUE constraint failed: parcels.clean_address`, returning HTTP 500 Internal Server Error to the client.
- **Mitigation**: Use atomic PostgreSQL/SQLAlchemy upsert semantics (`ON CONFLICT (clean_address) DO UPDATE`), or catch `IntegrityError` in `save_parcel_streetview` and retry/query the existing row.

### [Medium] Challenge 2: Address Normalization Regex Failures for Common Unit & Punctuation Patterns

- **Assumption challenged**: `_clean_streetview_address` handles real-world CAD/dispatch address inputs with unit numbers and punctuation.
- **Attack scenario**:
  1. Dispatch feeds or kiosk queries containing comma or hyphen unit separators (`Unit 101, 3030 Gordon Ave`, `Apt 202 - 3030 Gordon Ave`, `#303, 3030 Gordon Ave`).
  2. Addresses with trailing unit specifications (`3030 Gordon Ave Unit 101`, `3030 Gordon Ave #303`).
  3. Whitespace-only addresses (`"   "`).
- **Blast radius**:
  - Addresses with commas/hyphens after unit numbers retain unit prefix artifacts (`UNIT 101, 3030 GORDON AVE` or `- 3030 GORDON AVE`), causing `lookup_parcel` to return `found: False`.
  - Trailing unit specifications are untouched (`3030 GORDON AVE UNIT 101`), failing exact and partial lookup against canonical `3030 GORDON AVE`.
  - Whitespace strings (`"   "`) pass `if not raw_target` (as `"   "` is truthy in Python), clean to `""`, and insert dirty rows into `parcels.clean_address`.
- **Mitigation**:
  - Update `_clean_streetview_address` regex to match unit prefixes ending in optional punctuation (`[,\-\s]+`).
  - Add regex strip for trailing unit patterns (`\s+(UNIT|APT|SUITE|#)\s*\d+[\w-]*$`).
  - Strip whitespace prior to `if not raw_target` validation check (`if not raw_target or not raw_target.strip():`).

---

## Stress Test Results

| Test Scenario | Expected Behavior | Actual Behavior | Pass/Fail |
|---|---|---|---|
| **Special Characters in Address** (`3030 'GORDON' AVE`, `GORDÓN AVÉ`, `3030-B`, `3030 & MARINER`, `%`, `_`) | Clean and persist cleanly; lookup returns matching parcel | Parcel saved and resolved cleanly without SQL error or injection | **PASS** |
| **Whitespace & Formatting Variants** (`\t1234 MARINER WAY\n`, `1234 MARINER WAY, COQUITLAM, BC`) | Strip excess whitespace and city suffixes; lookup canonical record | Successfully resolved to `1234 MARINER WAY` | **PASS** |
| **Missing House Numbers / Street-Only** (`LOUGHEED HWY`) | Match partial street address via ILIKE fallback | Resolved `500 LOUGHEED HIGHWAY` correctly | **PASS** |
| **Extreme Floating Point Vectors** (`heading=359.99`, `720.5`, `pitch=-89.9`, `fov=120.0`, `0.00001`, `-10.0`) | Persist extreme floats with exact precision in `parcels` and `streetview_overrides` | Preserved float values to 5+ decimal places without clipping | **PASS** |
| **Rapid Repeated Upserts (50x)** | Update existing row without creating duplicate entries | 50 rapid sequential updates completed in 0.226s; row count remained 1 | **PASS** |
| **Concurrent Threaded Upserts (10 Workers)** | All 10 threads handle new address upsert gracefully without crashing | 8/10 threads succeeded; 2 threads crashed with `IntegrityError` (HTTP 500) | **FAIL** |
| **Nullable `gis_id` Multi-Row Insertion** | Multiple parcels with `gis_id=None` co-exist in DB | 3 parcels with `gis_id=None` created successfully | **PASS** |
| **Address Normalization Unit & Punctuation** (`Unit 101, 3030 Gordon Ave`, `Apt 202 - 3030 Gordon Ave`, `"   "`) | Clean to canonical street address; reject whitespace string | `Unit 101,` cleaned to `UNIT 101, 3030 GORDON AVE` (lookup failed); `"   "` saved as `""` | **FAIL** |

---

## Unchallenged Areas

- **PostgreSQL 16 High-Volume Database Load**: Tests executed using local database session bindings; PostgreSQL container daemon under multi-gigabyte load was out of local scope.
- **Frontend HUD WebGL Rendering Lifecycle**: Visual rendering and skeleton HUD lifecycle are handled in `frontend` components (Milestone 2 & 4 scope).
