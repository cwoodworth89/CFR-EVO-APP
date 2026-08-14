# Backend & Database Analysis: Property Intelligence & Street View Persistence

## Executive Summary
The `parcels` table is defined as an ORM model (`ParcelModel` in `backend/api/models.py`), but **does not exist in PostgreSQL schema initialization** (`backend/api/init_db.sql`) and is **omitted from FastAPI startup model imports** (`backend/api/server.py`), preventing automatic table creation on database startup. Furthermore, a critical **Python SyntaxError** exists on lines 729–733 of `backend/api/server.py` in the `POST /api/streetview-overrides` route handler.

---

## 1. PostgreSQL `parcels` Table Existence & Column Definitions

### A. Table Existence & Creation Flaws
* **`backend/api/init_db.sql`**: The SQL initialization script mounted into PostgreSQL container `/docker-entrypoint-initdb.d/init_db.sql` creates `live_calls`, `evaluation_history`, and `dispatch_uploads`, but **does NOT contain a `CREATE TABLE parcels` definition**.
* **`backend/api/server.py`**: Server startup invokes `Base.metadata.create_all(bind=engine)` at line 52. However, lines 44 & 48 only import `LiveCallModel`, `EvaluationHistoryModel`, `DispatchUploadModel`, `RoadClosureModel`, and `StreetViewOverrideModel`. **`ParcelModel` is omitted from top-level imports**, meaning SQLAlchemy metadata never registers `ParcelModel` and table auto-creation never runs for `parcels` on fresh database startup.

### B. ORM Model Definition (`backend/api/models.py`, lines 97–127)
```python
class ParcelModel(Base):
    __tablename__ = "parcels"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    gis_id = Column(String, unique=True, index=True, nullable=False)
    clean_address = Column(String, index=True, nullable=True)
    full_address = Column(String, nullable=True)
    zone_id = Column(String(16), index=True, nullable=True)
    
    geometry = Column(SafeJSON, nullable=True)
    front_lat = Column(Float, nullable=True)
    front_lng = Column(Float, nullable=True)
    centroid_lat = Column(Float, nullable=True)
    centroid_lng = Column(Float, nullable=True)

    # Preferred Street View Camera Angle
    streetview_heading = Column(Float, nullable=True)
    streetview_pitch = Column(Float, nullable=True)
    streetview_fov = Column(Float, nullable=True)

    # Coquitlam Tactical Property & Pre-Plan Metadata
    lock_box_notes = Column(Text, nullable=True)
    hazard_notes = Column(Text, nullable=True)
    pre_plan_pdf_url = Column(Text, nullable=True)
    entrance_lat = Column(Float, nullable=True)
    entrance_lng = Column(Float, nullable=True)
    construction_type = Column(String, nullable=True)
    floor_count = Column(Integer, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### C. Constraint Issue: `gis_id` `nullable=False`
When camera vectors are saved by address (e.g. `clean_address = "3030 GORDON AVE"`) without a known `gis_id`, PostgreSQL rejects insertion if `gis_id` is set to `nullable=False`. The code currently works around this by setting `gis_id = target_id` (`clean_addr`), but `gis_id` in `ParcelModel` should be made `nullable=True` or auto-populated cleanly.

---

## 2. Legacy `streetview_overrides` Table Structure & Usage

### A. Structure (`backend/api/models.py`, lines 130–143)
```python
class StreetViewOverrideModel(Base):
    """Deprecated: Legacy table. Use ParcelModel fields instead."""
    __tablename__ = "streetview_overrides"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    clean_address = Column(String, unique=True, index=True, nullable=False)
    front_lat = Column(Float, nullable=False)
    front_lng = Column(Float, nullable=False)
    heading = Column(Float, default=0.0, nullable=False)
    pitch = Column(Float, default=5.0, nullable=False)
    fov = Column(Float, default=80.0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### B. Usage Across Codebase
1. **`backend/api/server.py`**:
   - `POST /api/parcels/streetview` (lines 639–650): Synchronizes duplicate writes into `StreetViewOverrideModel`.
   - `GET /api/streetview-overrides` (lines 664–676): Fetches all rows from `StreetViewOverrideModel`.
   - `GET /api/streetview-overrides/{address}` (lines 679–718): Queries `ParcelModel` first; if missing `streetview_heading`, falls back to `StreetViewOverrideModel`.
   - `POST /api/streetview-overrides` (lines 721–733): Wraps `save_parcel_streetview` (currently broken by syntax error).
2. **`backend/scripts/migrate_streetview_to_parcels.py`**:
   - Migration script that reads rows from `streetview_overrides` and backfills `streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, and `front_lng` into `parcels`.
3. **`backend/scripts/update_streetview.py`**:
   - Maintenance CLI script updating both `streetview_overrides` and `parcels` tables.
4. **`frontend/src/apiClient.js`**:
   - `apiClient.streetView` methods query `/api/streetview-overrides` endpoints.
5. **`frontend/src/components/kiosk/StreetViewPanel.jsx`**:
   - Contains a client-side hardcoded object `STREETVIEW_OVERRIDES` (line 7) as an offline JS fallback.

---

## 3. FastAPI Route Locations

All property lookup and Street View endpoints are defined in **`backend/api/server.py`**.
`services/gis` is a core library module containing spatial calculation helpers (`geocoder.py`, `routing_engine.py`, `shapefile_loader.py`), but does not expose standalone HTTP route endpoints.

---

## 4. Current Endpoints & Syntax Error Audit

| Endpoint | Method | File Location | Status / Behavior |
| --- | --- | --- | --- |
| `/api/parcels/lookup` | `GET` | `backend/api/server.py:576` | **Functional**. Searches `ParcelModel` by `gis_id`, exact `clean_address`, or ilike `%clean_addr%`. Returns full parcel metadata & camera object. |
| `/api/parcels/streetview` | `POST` | `backend/api/server.py:611` | **Functional**. Upserts camera vectors (`heading`, `pitch`, `fov`, `front_lat`, `front_lng`) into `ParcelModel` and dual-writes to legacy `StreetViewOverrideModel`. |
| `/api/streetview-overrides` | `GET` | `backend/api/server.py:664` | **Functional**. Returns dictionary of legacy camera overrides. |
| `/api/streetview-overrides/{address}` | `GET` | `backend/api/server.py:679` | **Functional**. Queries `ParcelModel` first; falls back to `StreetViewOverrideModel`. |
| `/api/streetview-overrides` | `POST` | `backend/api/server.py:721` | ❌ **CRITICAL SYNTAX ERROR**. Unclosed function body on lines 729–733 (`"pitch": existing.pitch` dangling syntax). |

### Verbatim Syntax Error Snippet (`backend/api/server.py:721–733`)
```python
@app.post("/api/streetview-overrides")
def save_streetview_override(payload: StreetViewOverrideSchema, db: Session = Depends(get_db)):
    return save_parcel_streetview(
        ParcelCameraOverrideSchema(
            clean_address=payload.clean_address,
            front_lat=payload.front_lat,
            front_lng=payload.front_lng,
            heading=payload.heading,
            pitch=payload.pitch,
            fov=payload.fov
        "pitch": existing.pitch,
        "fov": existing.fov
    }
```

---

## 5. Address Normalization Logic & Discrepancies

### A. Implementations
1. **`backend/api/server.py` (`_clean_streetview_address`)**:
   - Strips cities/provinces (`COQUITLAM`, `PORT COQUITLAM`, `PORT MOODY`, `BC`, `BRITISH COLUMBIA`).
   - Strips unit/suite prefixes (`UNIT 105`, `APT 2`, `SUITE B`, `#3`).
   - Standardizes street types: `AVE`, `RD`, `ST`, `DR`, `HIGHWAY` (for `HWY`), `BLVD`, `WAY`, `CRT`, `PL`.
2. **`services/gis/src/gis_service/geocoder.py` (`local_geocode`)**:
   - Cleans unit numbers and block numbers (`1000 blk of ponderosa`).
   - Standardizes street types: `crescent` -> `CRES`, `highway` -> `HWY`, `street` -> `ST`, `avenue` -> `AVE`, `court` -> `CRT`, `place` -> `PL`, `drive` -> `DR`, `boulevard` -> `BLVD`, `lane` -> `LN`, `road` -> `RD`.
   - Special landmark overrides for `3080 GORDON AVE` (redirects to `3030 GORDON AVE`), `2900 BARNET`, `PORT MANN`, `RIVERVIEW`.
3. **`backend/cfr_dispatch/parser.py` (`normalize_street_suffix`)**:
   - Title Case mapping: `Cres`, `Hwy`, `St`, `Ave`, `Crt`, `Pl`, `Dr`, `Blvd`, `Ln`, `Rd`.

### B. Discrepancy Alert
* `server.py` maps `HWY` to `HIGHWAY`, whereas `geocoder.py` and `parser.py` map `highway` to `HWY`/`Hwy`.
* Addressing this normalization discrepancy ensures `2900 BARNET HWY` / `2900 BARNET HIGHWAY` matches identically across API endpoints, GIS geocoding, and DB queries.

---

## 6. Files Requiring Modification for R2

1. **`backend/api/init_db.sql`**: Add `CREATE TABLE IF NOT EXISTS public.parcels` and indexes (`idx_parcels_clean_address`, `idx_parcels_gis_id`, `idx_parcels_zone_id`).
2. **`backend/api/models.py`**: Update `ParcelModel` (`gis_id` `nullable=True`, explicit column indexing).
3. **`backend/api/server.py`**:
   - Add `ParcelModel` to top-level imports (lines 44 & 48).
   - Fix SyntaxError in `POST /api/streetview-overrides` (lines 721–733).
   - Ensure camera vectors (`streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, `front_lng`) are updated atomically in `parcels`.
   - Harmonize `_clean_streetview_address` normalization logic.
4. **`backend/scripts/migrate_streetview_to_parcels.py`**: Verify/update backfill migration script for container execution.
5. **`frontend/src/apiClient.js`**: Add explicit `parcels` namespace methods.
6. **`frontend/src/components/kiosk/StreetViewPanel.jsx`**: Update camera vector save/load hooks to pass and persist exact `heading`, `pitch`, `fov`, `front_lat`, `front_lng`.
