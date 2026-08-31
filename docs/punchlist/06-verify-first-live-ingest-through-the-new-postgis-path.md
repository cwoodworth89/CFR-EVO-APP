# Punch list #6 — Verify first live ingest through the new PostGIS path

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🛣️ Road Closure Ingestion |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L182 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 6. Verify first live ingest through the new PostGIS path
> **Status**: ✅ **Closed 2026-08-22 — verified, every pass criterion met.**
>
> | Pass criterion | Result |
> |:--|:--|
> | `last_sync` age < 24h | 12h ✅ |
> | Active closures, same magnitude as the previous 103 | **94** ✅ |
> | `with_geometry` equals `closures` | **94 / 94** ✅ |
> | `hall_id` populated 1–4 on most rows | 93 of 94 ✅ |
>
> Distribution: hall 1 → 13, hall 2 → 22, hall 3 → 40, hall 4 → 18, null → 1. The single
> null is a boundary-straddling closure whose centroid falls outside every zone, which is
> exactly the case this item's "watch for" note anticipated — `is_within_city` admits it
> via `ST_Intersects` while centroid containment cannot place it.
>
> The 2026-08-21 snapshot that read as a total failure (0 rows with `geom`, 103 with a null
> `hall_id`) was pre-rewrite residue, as recorded below. A sync has since run against the
> new code and populates both columns.
>
> Original entry follows.
>
> ⚠️ **Open — still unverified (re-checked 2026-08-21).** Correct as written.
> The rewrite **is** live in the running container — `docker exec cfr_api grep -c
> resolve_zones_and_hall /app/backend/api/road_closure_service.py` returns 4 — but no
> ingest cycle has run against it yet.
>
> **Read the current table with care — it is pre-rewrite residue, not a failed new run.**
> Today's snapshot looks like a total failure of the new path and is not:
>
> | Measure | Now | Pass criterion |
> |:--|--:|:--|
> | `last_sync` | 2026-08-21 01:39 PDT (20 h) | < 24 h ✅ |
> | active closures | 103 | ~103 ✅ |
> | rows with `geom` | **0** | should equal 103 ❌ |
> | active rows with `hall_id IS NULL` | **103** | should be mostly 1–4 ❌ |
>
> The two failures are explained by timing, not by a bug: the `cfr_api` image was rebuilt
> at **21:21 PDT**, and the last sync ran at **01:39 PDT** — twenty hours *before* the new
> code existed on the box. Every current row was written by the old service, which had no
> `geom`/`hall_id` logic. The columns themselves exist and the new code writes them
> (`road_closure_service.py:123`, `:175`, `:355–361`).
>
> **The first sync after 2026-08-21 21:21 PDT is the real test.** Until then these two
> columns carry no information about the rewrite. Re-run the queries below afterwards.

* **What changed**: `road_closure_service.py` now resolves zones and municipal
  containment via `ST_Intersects` / `ST_Contains` against `public.city_boundary` and
  `public.zones`, instead of ray-casting over `zones.json`. Closures with unparseable
  geometry are now **dropped** rather than pinned to a placeholder coordinate.
* **How to verify** — check the ingest actually ran and succeeded:
  ```bash
  # 1. Did a sync run, and when?
  ssh tcfire@100.95.146.94 "docker logs cfr_api 2>&1 | grep -i 'differentials-synced' | tail -5"

  # 2. Freshness: updated_at should be within the last 24h (check_and_sync_if_stale
  #    uses max_age_seconds=86400)
  ssh tcfire@100.95.146.94 "docker exec cfr_postgres sh -c 'psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"
    SELECT max(updated_at) AS last_sync,
           now() - max(updated_at) AS age,
           count(*) FILTER (WHERE active) AS active_closures
    FROM public.road_closures;\"'"

  # 3. Did the new columns populate? hall_id and geom should be non-null on
  #    freshly-synced active rows.
  ssh tcfire@100.95.146.94 "docker exec cfr_postgres sh -c 'psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"
    SELECT hall_id, count(*) AS closures,
           count(geom) AS with_geometry
    FROM public.road_closures WHERE active
    GROUP BY hall_id ORDER BY hall_id NULLS LAST;\"'"
  ```
* **Pass criteria**:
  - `last_sync` age < 24h, and a `differentials-synced` line appears in the API log.
  - Active closure count is non-zero and in the same order of magnitude as the previous
    103 — a large drop would suggest the new containment check is over-filtering.
  - `hall_id` is populated (1–4) on most rows; a large `NULL` group means centroid
    containment is failing and needs review.
  - `with_geometry` equals `closures` — a shortfall means the `geom` mirror UPDATE is
    not firing.
* **Watch for**: closures legitimately spanning the city edge. `is_within_city` uses
  `ST_Intersects` (touching counts), not `ST_Contains`, so a boundary-straddling closure
  should still be admitted. If those disappear, the check is too strict.

---

## 📍 Custom Places Data Quality
