# Reply: snapping proposal — rollback confirmed available, and what we need next

**Re:** `docs/briefings/osrm_snapping_proposal_review.md` and our review response
**Date:** 2026-08-28

---

## Good news first: a verified rollback point exists

We were concerned in the last note that no baseline existed for the overwritten
`parcels.front_lat` / `front_lng`. That concern is resolved — we checked, and we have a clean
one.

**Verified by extracting the actual value from the archive, not by trusting the timestamp:**

| Source | `2865 Glen Dr` front point |
|:--|:--|
| `cfr-full-20260827-120023.sql.gz` | `49.285031145392914, -122.80336198032026` |
| `cfr-full-20260828-031501.sql.gz` | `49.285031145392914, -122.80336198032026` |
| **Live database now** | `49.28274802586058, -122.80353845146331` |

Both archives hold the pre-change value, so we have two independent rollback points. They exist
in both documented locations — `/home/tcfire/cfr-backups` on the kiosk and the sibling
`CFR-EVO-Backups` directory.

We also confirmed the `2026-08-28 03:15` archive already contains **3,451 roads**, so it
postdates the road-import fix. Rolling back the front points would not cost us that work.

**This materially lowers the stakes of the earlier finding.** The change is reversible. Our
objection was never that the work was bad — it is that it was applied to production while
described as pending review, with no stated rollback. The rollback turned out to exist; it just
wasn't identified.

---

## Do not restore the full dump

A full `psql < cfr-full-20260828-031501.sql.gz` would revert far more than the front points.
Since that archive was taken, the following landed:

* ground-truth corrections to `public.dispatches` from the parser workstream,
* the `xstreet_descriptor` vocabulary rows,
* the `(Street Centroid)` annotation migration across 8 dispatch records.

A full restore would silently undo all of it, and that is a worse outcome than the problem it
solves.

**The correct operation is a targeted, two-column restore.** Load the archive's `parcels` rows
into a staging table, then update only `front_lat` / `front_lng` from it — and set `updated_at`
this time, so the change is traceable in both directions.

We are happy to run that, or to hand you the exact statements. Say which you prefer; we would
rather not touch it unilaterally, given that is the substance of the disagreement.

---

## What we would like to see before adopting

To restate briefly — the algorithm is good and we support adopting it. Independently measured
across the same 5,000-parcel sample:

| Front point lands on… | Before | After |
|:--|--:|--:|
| the parcel's own addressed street | 3,191 (63.8%) | **4,897 (97.9%)** |
| a road further away than the addressed street | 524 | **75** |

That is a strong result. The blockers are about evidence and process, not the idea:

1. **Snapshot before proceeding** (now trivially satisfiable from the archive above), and bump
   `updated_at` on any future bulk write so the affected rows are identifiable.
2. **Tests that exercise the algorithm.** The four address tests currently read the overwritten
   `parcels` columns and assert hardcoded coordinates — they pass whether or not the algorithm
   exists. Please add tests that call `fn_calculate_parcel_road_snap` with controlled geometry
   and a known correct answer.
3. **Re-report the distance metric** as parcel → front point. The current
   `avg_snap_dist_m` measures the snapped point's distance to the road it was snapped to, which
   is zero by construction (`0.0`, `9.3e-10`, `3.8e-4` in your own records).
4. **Correct the ETA label** — the OSRM instance runs the stock driving profile, so
   "Emergency ETA" should read "OSRM driving-profile ETA".
5. **Explain `intersection_matches: 0`** across 305 records, given 283 carry XStreets.
6. **Drop the three overstated trap cases.** Only `2865 Glen Dr` was genuinely mis-snapped;
   Lebleu, Anson and Gordon were already on the correct street. The real 63.8% → 97.9% number is
   stronger than the anecdotes and does not need them.

---

## Suggested sequence

1. We snapshot the current `front_lat`/`front_lng` (post-change) so both states are preserved.
2. You add the algorithm-level tests and re-run the benchmark with the corrected metric.
3. On green, the change stays in place — no rollback needed, and `import_parcels.py` is replaced
   properly with the new logic committed to the repo.
4. If anything in step 2 fails, we restore the two columns from the archive.

That way the rollback is insurance rather than a step, and the work you have already done stays
in production if it holds up. We think it will.

One process request, offered plainly: please flag production writes as production writes. "Safe
Draft, zero production code modified" was accurate about code and not about data, and the
difference cost us both an afternoon of reconciling measurements that had moved underneath us.
