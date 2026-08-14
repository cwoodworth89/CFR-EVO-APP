# Milestone 1 Code & Security Review Report

**Reviewer**: Reviewer 2 (Critic & Code Reviewer)  
**Target**: Milestone 1 (Backend PostgreSQL `parcels` Schema & REST Overhaul)  
**Date**: 2026-08-13  
**Verdict**: **APPROVE**

---

## 1. Executive Summary

Worker M1 implemented the backend database schema changes, ORM model updates, FastAPI REST endpoint overhauls, database backfill migration script, and test suite for Milestone 1.

An independent code inspection, SQL injection security audit, FastAPI endpoint evaluation, fallback logic verification, integrity check, and adversarial stress test were conducted. All core requirements and acceptance criteria have been met with high quality, genuine implementation logic, and 100% parameter binding.

---

## 2. Review Dimensions

### A. SQL Injection Safety & Parameter Binding
- **Observation**: Inspected all ORM filter operations in `backend/api/server.py` and `backend/scripts/migrate_streetview_to_parcels.py`.
- **Finding**: All database queries utilize SQLAlchemy ORM filter constructs (e.g. `ParcelModel.clean_address == clean_addr`, `.ilike(...)`) which compile to parameterized SQL queries with bound variables. No raw SQL string formatting (`f"SELECT..."` or `%`) is present in application queries.
- **Adversarial Verification**: Tested 5 SQL injection attack vectors (`' OR '1'='1`, `3030 GORDON'; DROP TABLE parcels; --`, `1 UNION SELECT 1,2,3--`, `%' AND 1=1 --`, `\'; SELECT pg_sleep(5); --`). All inputs were handled safely as string literals, returning clean 404/not-found responses without database syntax errors or side effects.
- **Pass/Fail**: **PASS**

### B. FastAPI Error Handling, Status Codes & Schemas
- **Observation**: Examined route handlers in `server.py`:
  - `GET /api/parcels/lookup`: Returns `200 OK` with `{"found": false, "parcel": null}` for missing queries/unmatched addresses, or `{"found": true, "parcel": {...}}` on match.
  - `POST /api/parcels/streetview`: Validates payload via `ParcelCameraOverrideSchema`. Raises `400 Bad Request` if both `clean_address` and `gis_id` are missing. Returns `200 OK` with `{"status": "success", "parcel": {...}}`.
  - `GET /api/streetview-overrides/{address}`: Raises explicit `404 Not Found` if address is not in `parcels` or `streetview_overrides`.
  - `POST /api/streetview-overrides`: Validates via `StreetViewOverrideSchema`, delegates to `save_parcel_streetview`, and returns `200 OK`.
- **Response Structure**: The returned `parcel` dictionary includes primary schema fields (`clean_address`, `front_lat`, `front_lng`, `streetview_heading`, `streetview_pitch`, `streetview_fov`) as well as top-level shortcut properties (`lat`, `lng`, `heading`, `pitch`, `fov`) required by the frontend Street View viewer.
- **Pass/Fail**: **PASS**

### C. Fallback Logic Between `parcels` and Legacy `streetview_overrides`
- **Observation**:
  - `lookup_parcel`: First queries `ParcelModel`. If not found, falls back to `StreetViewOverrideModel`. If found in legacy overrides, constructs a synthetic parcel dictionary so legacy clients receive expected schema structure without errors.
  - `get_streetview_override`: First checks `ParcelModel` for saved heading/pitch/fov camera vectors. If missing, falls back to `StreetViewOverrideModel`.
  - `save_parcel_streetview` & `save_streetview_override`: Upserts into `parcels` and simultaneously syncs to `streetview_overrides`. Handles cases where coordinates (`front_lat`/`front_lng`) are omitted by defaulting legacy table values to `0.0`.
- **Pass/Fail**: **PASS**

### D. Integrity & Anti-Cheating Verification
- Checked for hardcoded test results, facade implementations, or shortcuts.
- All database queries interact with active database sessions (`SessionLocal`).
- DDL in `init_db.sql` matches SQLAlchemy models in `models.py`.
- No fake/mock responses exist in endpoint handlers.
- **Pass/Fail**: **PASS — 100% Genuine Implementation**

---

## 3. Findings

### [Minor] Finding 1: Address Normalization Regex Edge Case for Leading Hyphens
- **Location**: `backend/api/server.py`, line 564 (`_clean_streetview_address`)
- **Description**: `re.sub(r'^(UNIT|APT|SUITE|#)\s*\d+[\w-]*\s+', '', s, flags=re.IGNORECASE)` removes prefix unit tags. For strings like `"Apt 12B - 700 Mariner Way"`, removing `"Apt 12B "` leaves `"- 700 MARINER WAY"`.
- **Impact**: Low. Standard addresses parsed from CAD dispatch transcripts typically follow `"3030 GORDON AVE"` or `"UNIT 101 3030 GORDON AVE"`. Substring ILIKE fallback matches the address regardless.
- **Suggestion**: Consider stripping leading non-alphanumeric characters (e.g. `re.sub(r'^[\s\W]+', '', s)`) after prefix removal in future refactoring.

---

## 4. Verified Claims

| Claim | Verification Method | Result |
|---|---|---|
| All 8 Milestone 1 unit/integration tests pass | Ran `python backend/tests/test_parcels_and_streetview_api.py` | **PASS** |
| Parameterized query protection against SQLi | Code audit & adversarial execution of 5 SQLi payloads | **PASS** |
| `parcels` table schema & DDL alignment | Inspected `init_db.sql` and `models.py` | **PASS** |
| Legacy fallback to `streetview_overrides` | Automated test `test_legacy_streetview_override_fallback` | **PASS** |
| Backfill migration script logic | Executed `migrate_overrides()` test backfill | **PASS** |

---

## 5. Adversarial Stress-Test Results

| Scenario | Input | Expected Output | Actual Output | Status |
|---|---|---|---|---|
| SQLi in Parcel Lookup | `' OR '1'='1` | `found: False, parcel: None` | `found: False, parcel: None` | **PASS** |
| SQLi DDL Injection | `3030 GORDON'; DROP TABLE parcels; --` | `found: False, parcel: None` | `found: False, parcel: None` | **PASS** |
| Streetview Override 404 | `NONEXISTENT_LOCATION_99` | HTTP 404 | HTTP 404 | **PASS** |
| Omitted Lat/Lng Save | `heading=270.0, pitch=-5.0, fov=60.0` | `status: success` (lat/lng 0.0 in legacy) | `status: success` (lat/lng 0.0 in legacy) | **PASS** |

---

## 6. Verdict Rationale

The backend changes implemented in Milestone 1 fulfill all functional, architectural, and security requirements. Test coverage is complete, database operations are secure against SQL injection, fallback mechanisms protect legacy API compatibility, and no integrity violations were detected.

**Final Verdict**: **APPROVE**
