# Reply: tests accepted, one root cause found, one attribution correction

**Re:** `docs/briefings/snapping_proposal_tests_response.md`
**Date:** 2026-08-29
**Status:** Tests accepted. **One change still required before `import_parcels.py` is replaced.**

---

## 1. Verified, and accepted

We checked each claim rather than taking it on trust.

**"Zero database rows were modified during this iteration" — confirmed.** The wrong-street
count is unchanged at 331 / 277 / 54, and the only parcel writes in the last 24 hours are the
1,759 rows from our own corrective migration at 06:00 UTC. Nothing moved under us this time.
Thank you.

**24/24 tests pass — confirmed by running them.** More importantly, they now test the right
thing. `test_parallelism_cardinal_and_intermediate_angles`,
`test_length_weighting_monotonicity_and_strict_30m_clamp`,
`test_road_classification_hierarchy_ratios`, `test_distance_exponential_decay_rates`,
`test_concave_l_shaped_parcel_decomposition`, `test_cul_de_sac_faceted_curved_frontage`,
`test_sub_half_meter_micro_edge_filtering` — these exercise the algorithm against controlled
geometry with known answers. That fully answers our objection. The previous suite would have
passed with the algorithm deleted; this one would not.

**Metric corrected — accepted.** `avg_snap_dist_m` now measures parcel boundary to arrival
point (7.18 m), which is the number that means something.

**ETA label corrected — accepted.**

**`intersection_matches: 0` resolved — accepted.** 22 junction snaps out of 305 is a plausible
figure and the four-way split sums correctly.

This was a good turnaround and we want to say so plainly.

---

## 2. The root cause of the 1,813 wrong-street points

We found why the algorithm put 1,813 parcels on a street their address does not name. It is a
single design choice, and it is fixable:

```
backend/scripts/import_parcels_PROPOSED.py:15
  name prior (1.0 + 2.0 * I_name) to eliminate naive centroid snapping failure modes
```

**The addressed street is a 3× multiplicative prior, not a constraint.** A road carrying the
right name gets weighted three times higher — but a wrong-named road that scores better on
parallelism, length, classification and proximity can still outvote it. Your own
`test_street_name_prior_3x_multiplier` confirms the intent.

That is exactly what happened on 1,813 parcels citywide.

**The requested change:** where a road matching the addressed street name exists, make it a
**filter**, not a weight — score only among that street's edges. Fall back to the full scored
geometry only when no road of that name exists (54 parcels, all tracked in
`docs/city_gis_data_register.md`).

The justification is that the street name is not an estimate. `parcels.street` is municipal
data and `roads.roadname` is municipal data; the address *states* which street it is on. A
weight lets geometry overrule a fact. Every other scoring term — parallelism, length,
classification, decay — remains exactly as you built it, applied within the correct street.

**Until that change lands, `import_parcels.py` must not be replaced.** The current production
data is correct only because we corrected it after the fact. Adopting the proposed script and
re-running it would reintroduce all 1,813.

---

## 3. An attribution correction on the new benchmark

Your benchmark JSON is stamped `2026-08-29T14:57:04Z`. Our corrective migration ran at
`2026-08-29T06:00Z`. **The benchmark therefore measured your algorithm plus our 1,759-row
correction, not your algorithm alone.**

This does not make the numbers wrong — the database really is in that state — but it means:

* `street_name_aligned: 292/305` reflects both changes, not one.
* The `63.8% → 97.9%` improvement is a joint figure. Your algorithm alone produced 1,813
  wrong-street points out of 65,399; ours corrected 1,759 of them.
* The benchmark as run cannot separate the two contributions, so it cannot yet demonstrate that
  the proposed script is safe to re-run on its own.

Once the name-as-filter change is in, re-running the benchmark from a clean re-import would
measure the script by itself. That is the number that should decide adoption.

---

## 4. Two small items

**The trap table.** It still lists "Avoided Lincoln Ave trap" (3025 Anson Ave), "Avoided
Christmas Way alley trap" (3030 Gordon Ave), and "Avoided rear alley trap" (210 Lebleu St).
We measured each before the change: they snapped to **Anson Avenue**, **Gordon Avenue** and
**Lebleu Street** respectively — the correct streets. Only `2865 Glen Dr` was genuinely
mis-snapped, to Guildford Way.

This is the third time we have raised it, so we will be blunt about why it matters rather than
just repeating the correction: a results table that credits fixes for failures that never
happened makes the whole table unreliable, including the one entry that is true and important.
The real result — 1,813 wrong-street points identified and the mechanism found — is a stronger
story than four anecdotes. Please just remove the three rows.

**"No Database Dependency: all live database queries were removed."** Not quite —
`test_postgis_parallel_vs_perpendicular_edge_scoring` and
`test_postgis_synthetic_glen_dr_centroid_trap_avoidance` use PostGIS as a geometry engine. That
is a good design decision, not a problem: synthetic geometry evaluated by the real spatial
engine is stronger than a Python reimplementation. Just describe it accurately, because the
suite does require a database connection to run.

---

## 5. Where this stands

| Item | Status |
|:--|:--|
| Algorithm-level tests | ✅ Accepted |
| Distance metric | ✅ Accepted |
| ETA label | ✅ Accepted |
| `intersection_matches` | ✅ Accepted |
| No unauthorised DB writes | ✅ Verified |
| Street name as filter, not 3× prior | ⛔ **Required before adoption** |
| Benchmark re-run measuring the script alone | ⛔ Required |
| Trap table corrected | ⚠️ Requested |

Two further housekeeping items on our side to close out, for your awareness:

* `public.fn_calculate_parcel_road_snap` is still registered in the production database and is
  not called by any application code. Once the script is finalised, either wire it in or drop it.
* `parcels_frontpoint_snapshot_20260828` holds the post-snapping / pre-correction state. We will
  keep it until adoption is settled, then remove it.

Make the street name a filter and re-run the benchmark from a clean import, and we will sign off
on replacing `import_parcels.py`. The rest of the work is good and we are glad to have it.
