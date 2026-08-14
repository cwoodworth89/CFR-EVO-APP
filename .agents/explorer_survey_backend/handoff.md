# Handoff Report: Explorer Survey Backend (Property Intelligence & Street View Persistence)

## 1. Observation

### Observation 1: Database Initialization Script (`backend/api/init_db.sql`)
- Lines 1–82 of `backend/api/init_db.sql` define `live_calls`, `evaluation_history`, and `dispatch_uploads` tables.
- `CREATE TABLE parcels` is completely absent from `init_db.sql`.

### Observation 2: FastAPI Server Imports (`backend/api/server.py`)
- Lines 44 & 48 of `backend/api/server.py` state:
  ```python
  from backend.api.models import LiveCallModel, EvaluationHistoryModel, DispatchUploadModel, RoadClosureModel, StreetViewOverrideModel
  ```
- `ParcelModel` is omitted from these top-level imports.
- Line 52 calls `Base.metadata.create_all(bind=engine)`. Because `ParcelModel` is not imported, SQLAlchemy metadata does not include `parcels`, so `create_all` does not create the `parcels` table in PostgreSQL on application startup.

### Observation 3: Python Syntax Error in `backend/api/server.py`
- Lines 721–733 of `backend/api/server.py` state:
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
- The function body contains invalid unclosed syntax on lines 729–733.

### Observation 4: ORM Model Definition (`backend/api/models.py`)
- Lines 97–127 define `ParcelModel` with columns: `id`, `gis_id` (unique, index, `nullable=False`), `clean_address`, `full_address`, `zone_id`, `geometry`, `front_lat`, `front_lng`, `centroid_lat`, `centroid_lng`, `streetview_heading`, `streetview_pitch`, `streetview_fov`, `lock_box_notes`, `hazard_notes`, `pre_plan_pdf_url`, `entrance_lat`, `entrance_lng`, `construction_type`, `floor_count`, `updated_at`.

### Observation 5: Legacy Table & Migration Script
- Lines 130–143 of `backend/api/models.py` define `StreetViewOverrideModel` (`streetview_overrides` table).
- `backend/scripts/migrate_streetview_to_parcels.py` (lines 1–64) queries `StreetViewOverrideModel` and copies camera attributes into `ParcelModel`.

---

## 2. Logic Chain

1. **Premise 1 (Observation 1 & 2)**: Since `init_db.sql` lacks `parcels` table definition and `server.py` omits `ParcelModel` from top-level imports prior to calling `Base.metadata.create_all(bind=engine)`, any fresh deployment of PostgreSQL or database container will NOT contain the `parcels` table.
2. **Premise 2 (Observation 3)**: `backend/api/server.py` has a Python SyntaxError in `save_streetview_override` (lines 721–733). Calling or importing this route will throw a `SyntaxError` at runtime.
3. **Premise 3 (Observation 4 & 5)**: `ParcelModel` contains all required camera vector fields (`streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, `front_lng`) and property intelligence fields (`lock_box_notes`, `hazard_notes`, `pre_plan_pdf_url`). Legacy table `streetview_overrides` exists and can be backfilled into `parcels` via `migrate_streetview_to_parcels.py`.
4. **Conclusion**: To fulfill R2, the backend implementation must add `parcels` table creation to `init_db.sql`, import `ParcelModel` in `server.py`, fix the syntax error on line 729–733, update `POST /api/parcels/streetview` & `GET /api/parcels/lookup`, and run the backfill migration.

---

## 3. Caveats

- **Live DB State**: The inspection was conducted via codebase files (`init_db.sql`, `models.py`, `server.py`, `docker-compose.yml`, `migrate_streetview_to_parcels.py`). The live container DB instance on remote kiosk host (`tcfire@100.95.146.94`) may have legacy `streetview_overrides` rows created by earlier manual runs of `update_streetview.py`.
- **Read-Only Scope**: Per instructions, Explorer 1 did not modify application source files.

---

## 4. Conclusion

The backend architecture is ready for unified `parcels` persistence once the following 5 fixes are applied by the implementer:
1. Include `parcels` table schema in `backend/api/init_db.sql`.
2. Import `ParcelModel` in `backend/api/server.py` before `Base.metadata.create_all()`.
3. Fix SyntaxError in `backend/api/server.py` line 721–733 (`POST /api/streetview-overrides`).
4. Ensure `POST /api/parcels/streetview` atomically persists `heading`, `pitch`, `fov`, `front_lat`, `front_lng` to `parcels`.
5. Run `python /app/scripts/migrate_streetview_to_parcels.py` inside the container.

---

## 5. Verification Method

To verify the findings and subsequent implementer fixes:
1. **Syntax Check**:
   ```powershell
   python -m py_compile backend/api/server.py
   ```
2. **Database Table Verification**:
   ```bash
   docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch -c "\d parcels"
   ```
3. **API Endpoint Test**:
   ```powershell
   curl.exe http://localhost:8000/api/parcels/lookup?query=3030%20GORDON%20AVE
   ```
4. **Invalidation Condition**: If `python -m py_compile backend/api/server.py` fails on line 731, the server will not start.
