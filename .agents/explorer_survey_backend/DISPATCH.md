## 2026-08-13T23:45:00Z
Investigate the backend database schema, migration scripts, models, and API routes relating to property intelligence and Street View.

Investigate and document:
1. Does `parcels` table exist in PostgreSQL (`cfr_dispatch` DB)? What columns currently exist (`streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, `front_lng`, `lock_box_notes`, `hazard_notes`, `pre_plan_pdf_url`, address indexing, etc.)?
2. Are there legacy tables like `streetview_overrides`? How are they structured and where are they used in code?
3. Where are backend FastAPI routes defined for property lookups and streetview overrides? Check `backend/` and `services/`.
4. What endpoints currently exist: `GET /api/parcels/lookup`, `POST /api/parcels/streetview`, `GET /api/streetview-overrides/{address}`?
5. Address normalization logic (e.g. `3030 GORDON AVE`).
6. Identify all files that need modification for R2 (Unified `parcels` PostgreSQL table & migration, camera vector persistence, normalized address lookup endpoints).
