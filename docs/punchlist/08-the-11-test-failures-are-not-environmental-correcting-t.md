# Punch list #8 — The 11 test failures are NOT environmental — correcting the record

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | hygiene |
| **Area** | 🧪 Test Suite Debt |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L338 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 8. The 11 test failures are NOT environmental — correcting the record
> **Status**: ✅ **Closed 2026-08-21.** All 11 failures fixed and verified on the kiosk:
> **82 passed, 1 xfailed, 0 failed** (from 11 failed / 72 passed). See the resolution at
> the end of this item. The diagnosis below was re-confirmed before any fix was made.
>
> ⚠️ **Open — every stated cause re-confirmed 2026-08-21 against the kiosk
> database and the working tree.** Run on the kiosk with PostGIS reachable, `librosa`
> present and `XDG_RUNTIME_DIR` set: **identical 11 failures, 72 passed.** Earlier commit
> messages this session described all 11 as "pre-existing and environmental". The
> pre-existing half was verified by stashing; **the environmental half was inferred and
> is wrong.**
>
> Confirmation of each cause below, so this can be picked up without re-deriving it:
>
> | Claim | Check | Result |
> |:--|:--|:--|
> | `public.landmarks` is gone | `to_regclass('public.landmarks')` | `NULL` — dropped ✅ |
> | a test still queries it | `test_postgis_migration.py:52–54` | still `SELECT COUNT(*) FROM public.landmarks` ✅ |
> | intersection bound is stale | `SELECT count(*) FROM public.intersections` | **6,499** vs asserted 400–2,500 ✅ |
> | shapefile constants removed | `test_fault_injection.py:65` | still imports `ADDRESS_SHAPEFILE_PATH` / `ZONES_SHAPEFILE_PATH` ✅ |
>
> `test_database_integration.py:29–30` defines those two shapefile paths as **module-level
> literals** rather than importing them, so it fails differently from `test_fault_injection.py`
> — it will not raise `ImportError`, it will look for files that the PostGIS migration
> removed. Worth fixing in the same pass.
>
> Note the ordering trap on the cascade: the six `InFailedSqlTransaction` failures are
> collateral from `test_landmarks_count` aborting the shared connection's transaction. Fix
> that one test first, then re-run before judging the rest — the remaining count will drop
> before any of them are touched.
>
> ---
>
> **Resolution (2026-08-21) — 11 failed / 72 passed → 82 passed, 1 xfailed, 0 failed.**
>
> The root cause of the cascade was **not** the stale test; it was the fixture. `conn` was
> `scope='module'`, so all 16 tests shared one connection and therefore one transaction —
> any single failing statement aborted it and every later test died with
> `InFailedSqlTransaction`. Making it function-scoped means one bad test can no longer
> manufacture six more. That is the structural fix; fixing only `test_landmarks_count`
> would have cleared the symptom and left the amplifier in place.
>
> Per test:
>
> | Test | Change |
> |:--|:--|
> | `test_landmarks_count` | Replaced by `test_dropped_tables_stay_dropped`, asserting `landmarks` **and** `custom_places` are absent, so a reintroduction is caught |
> | 6 × `InFailedSqlTransaction` | Not touched — they were never broken. Cleared by the fixture scope |
> | `test_intersections_count` | Bound relaxed to a populated-table sanity floor, **not** re-pinned to 6,499 (see below) |
> | `test_no_false_intersections` | `xfail(strict=False)` — the test is right and the *data* is wrong |
> | `test_04_unknown_address_fallback_safety` | Rebuilt on the database-backed validator; the shapefile constants are gone |
> | `test_build_dispatch_payload_option2` | `MockValidator.local_geocode` signature tracks the real one (`target_map_grid`, `cross_street_*`) |
>
> **Two judgement calls worth stating plainly, because both could have been "fixed" the
> dishonest way:**
>
> 1. **`test_intersections_count` was not re-pinned to 6,499.** Updating the bound to
>    match whatever the table currently holds would encode unaudited data as the expected
>    answer — and #13 records that this table has at least one confirmed false row and
>    apparent duplicates. There is no source for a correct count, so asserting a precise
>    one would be an unsourced constant (§6.3). It now asserts only that the import did not
>    fail or empty, with a comment saying to restore a real bound after the #13 audit.
> 2. **`test_no_false_intersections` was marked `xfail`, not weakened.** It is a *true
>    positive* — it detects the real defect in item #9. Relaxing the assertion would have
>    turned the suite green by deleting the alarm. `xfail` reports the true state, and
>    `strict=False` means it XPASSes the moment the data is fixed, so the fix will not go
>    unnoticed. **Item #9 remains open; this changed nothing about the underlying data.**
>
> One further finding: the run also needs `DATABASE_URL`, which is **not** in
> `backend/.env`. Without it `test_04` *skips* rather than passes, which reads as green in
> the summary line. Take it from the container (see the environment notes in
> `review_status_handoff.md`). With it set: 82 passed, 1 xfailed, **0 skipped**.

Actual causes:

* **1 stale test causing ~6 cascading failures.** `test_landmarks_count` queries
  `public.landmarks`, renamed to `custom_places` in Phase D and dropped entirely on
  2026-08-21. The `UndefinedTable` error aborts the transaction, so every later test on
  that connection fails with `InFailedSqlTransaction` — `test_vocabulary_units`,
  `test_vocabulary_call_types`, `test_zone_spatial_query`,
  `test_city_boundary_contains_coquitlam`, `test_city_boundary_excludes_burnaby`,
  `test_parcels_have_geometry`. Fixing the one stale test likely clears all of them.
* **`test_intersections_count`**: asserts 400–2500, actual is **6,499**. Either the
  bound is stale or the intersection set grew. `docs/development_freeze_summary.md`
  documents 3,947, which matches neither.
* **`test_fault_injection::test_04_unknown_address_fallback_safety`**: imports
  `ADDRESS_SHAPEFILE_PATH` / `ZONES_SHAPEFILE_PATH` from `cfr_dispatch.config`. Removed
  in the Phase A PostGIS migration. Stale test, not a product bug.
* **`test_pipeline_unit::test_build_dispatch_payload_option2`**: its `MockValidator`
  lacks the `target_map_grid` keyword the real `local_geocode` gained in the geocoder 2.0
  work. Stale mock signature.
