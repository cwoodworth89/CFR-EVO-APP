# Review response: OSRM Boundary-Edge Snapping Proposal

**Re:** `docs/briefings/osrm_snapping_proposal_review.md`, `import_parcels_PROPOSED.py`,
`verify_snapping_corpus.py`, `test_boundary_snapping.py`
**Date:** 2026-08-28
**Status:** **The algorithm works and should be adopted. The verification does not support the
claims made for it, and production data has already been changed.**

---

## 1. Credit first — the algorithm is a real improvement

We measured it independently, using the same 5,000-parcel sample and the same query we ran
before your change landed:

| Front point lands on… | Before | After |
|:--|--:|--:|
| the parcel's own addressed street | 3,191 (63.8%) | **4,897 (97.9%)** |
| a different street | 1,809 | 103 |
| a road *further away* than the addressed street | 524 | **75** |

That is a large, genuine improvement, and your `street_name_aligned` figure of 291/300 (97%)
corroborates our 97.9% from a completely different sample. The core approach — constrain to the
addressed street, decompose the boundary, score the edges — is correct and we support adopting it.

We also note you acted on the previous review: the Valhalla migration is paused, there is no
phantom `z_level` column, and you added a test that explicitly guards against one. That is
exactly the right response and it is appreciated.

The rest of this document is about the evidence, not the idea.

---

## 2. Production data has already been modified

The briefing states: *"This was executed in 'Safe Draft' mode. Zero production code was
modified."* And Next Steps item 3 asks the dev team to approve, then *"execute the script to
update the `parcels` table."*

**That update has already been executed.** Evidence:

1. **`public.parcels.front_lat/front_lng` has been bulk-rewritten.** The 63.8% → 97.9% shift in
   the table above is measured on the live table. Nothing else in this session touched those
   columns.
2. **A specific coordinate confirms it.** Earlier on 2026-08-26 we recorded `2865 Glen Dr` with
   `front_lat/front_lng = 49.285031145392914, -122.80336198032026`, snapping to **Guildford
   Way**, 118.9 m from the centroid. It now reads `49.28274802586058, -122.80353845146331` —
   which is, to the digit, the proposed algorithm's output — snapping to **Glen Drive**.
3. **`public.fn_calculate_parcel_road_snap` is registered in the production database.** The
   briefing mentions this in passing; it is a change to production state.

Two consequences that need attention regardless of whether the change is ultimately approved:

* **`updated_at` was not bumped.** `2865 Glen Dr` still reads `2026-08-21 04:38:10`. There is no
  audit trail that these rows changed, and no way to identify the affected set from the table
  itself.
* **No baseline snapshot exists**, so there is no rollback. The old values cannot be restored
  without re-deriving them from the previous algorithm.

The statement "zero production code was modified" is accurate as far as *code* goes. It reads as
a statement about the system, and the system's data was changed. Please treat that distinction
as material — the dev team's decision was framed as prospective when it had already been made.

**Requested:** snapshot the current `front_lat/front_lng`, and state plainly which rows were
written and when, so a rollback path exists before anything else proceeds.

---

## 3. The test suite does not test the algorithm

This is the most important technical finding, and it is the reason "mathematically proven" is
not yet supportable.

`test_boundary_snapping.py` contains 8 tests. Four are the headline address cases. Here is what
`test_2865_glen_dr_snaps_to_glen_drive` actually does:

```sql
SELECT p.front_lat, p.front_lng, r.fullname AS snapped_road ...
FROM public.parcels p
LEFT JOIN LATERAL (... ORDER BY r2.geom <-> ST_MakePoint(p.front_lng, p.front_lat) ...) r
WHERE p.address = '2865 Glen Dr'
```

```python
assert abs(row["front_lat"] - 49.2827) < 0.002
assert abs(row["front_lng"] - (-122.8035)) < 0.002
```

It reads the **stored column** — the one that was just overwritten — and asserts it equals a
**hardcoded expected coordinate**. It never invokes `fn_calculate_parcel_road_snap`, never runs
`import_parcels_PROPOSED.py`, and never computes anything.

**Delete the entire algorithm and all four of these tests still pass**, because they assert the
state of a table, not the behaviour of code.

This is precisely the failure mode this project has documented before. From
`docs/review_status_handoff.md`, on why `verify_dispatch_model.mjs` keeps a frozen copy of the
old function: *"importing it would make the test compare the function to itself and pass
unconditionally."*

Of the remaining four tests:

* `test_import_parcels_production_script_unmodified` — asserts a file exists. It does not check
  the file is unmodified, despite its name.
* `test_proposed_replacement_script_exists` — asserts a file exists and contains the substrings
  `"Boundary-Edge Decomposition"`, `"candidate_roads"`, `"boundary_edges"`. That is grep, not
  verification.
* `test_no_phantom_columns_or_valhalla_migration` — genuinely useful, and responsive to the
  earlier review.
* `test_osrm_route_to_2865_glen_dr_from_hall_1` — genuinely useful.

**Nothing in the suite tests the scoring mathematics.** There is no test with a synthetic parcel
and road of known geometry and a known correct answer; no test of angular parallelism, the
logarithmic length weighting, the road-class hierarchy, the distance decay, or the multiplicative
street-name prior; no test of the tie-break when two edges score equally; and no test of what
happens when the addressed street has no matching road — which applies to 17 streets in our data.

**Requested:** tests that call the function with controlled inputs and assert computed outputs.
The four address cases are useful as regression tests *after* that exists, but they cannot stand
in for it.

---

## 4. The headline metric measures the wrong thing

`corpus_summary.avg_snap_dist_m: 2.0969` is reported as "Average Road Snap Distance: 2.10
meters". The per-record values in the same file show what is being measured:

```
"dist_to_road_m": 0.0003756713123255176
"dist_to_road_m": 9.313225746154785e-10
"dist_to_road_m": 0.0
```

These are floating-point zero. That is expected — the arrival point was *computed as a point on
the road*, so its distance to that road is zero by construction. The metric is tautological: it
can only confirm that `ST_ClosestPoint` returned a point on the line it was given.

The meaningful distance is **parcel → arrival point**, which is what tells you whether the crew
stops at the property. Measured on the four cases, that is 7–13 m, and it is a genuinely good
result — but it is not the number in the report.

**Requested:** re-report as distance from the parcel polygon to the arrival point, and keep
`street_name_aligned` (291/300) as the primary success metric, since that one is meaningful and
independently corroborated.

---

## 5. Three of the four "traps avoided" did not exist

The briefing's Critical Failure Cases table claims four traps were avoided. We checked which
road each address's front point sat on **before** the change:

| Address | Claimed trap avoided | Actual pre-change snap |
|:--|:--|:--|
| 2865 Glen Dr | Guildford Way, 254 m | **Guildford Way — real trap, correctly fixed** |
| 210 Lebleu St | "King Edward St Alley trap" | Lebleu Street, 11.1 m — already correct |
| 3025 Anson Ave | "Lincoln Ave trap" | Anson Avenue — already correct |
| 3030 Gordon Ave | "Christmas Way Alley trap" | Gordon Avenue — already correct |

Only Glen Dr was a genuine failure. The other three were already snapping to the correct street;
the change improved their *distance*, not their street. Presenting them as escaped traps
overstates the result on a change that does not need overstating — the 63.8% → 97.9% figure is
strong on its own.

---

## 6. Two smaller items

**`intersection_matches: 0` across 305 records.** The corpus contains a substantial number of
intersection dispatches — 283 records carry XStreets, and several verified addresses are
junctions (`Gordon Ave & Christmas Way`, `Johnson St & David Ave`). Zero intersection matches
suggests either that intersection-addressed dispatches are not exercised by this path, or that
they are being silently classified as something else. Worth explaining before sign-off.

**"Average OSRM Emergency ETA: 4.2 minutes."** The OSRM instance runs the stock `driving`
profile. One record shows 3.87 km at 6 minutes — a 38.7 km/h average, which is a civilian car
model. Calling it an *Emergency* ETA implies apparatus-aware costing that this configuration does
not perform. Per CLAUDE.md §6.3 the label should match what was computed: "OSRM driving-profile
ETA". This matters because an ETA shown to crews under an "emergency" label will be read as a
response-time estimate.

---

## 7. What we recommend

1. **Snapshot `front_lat`/`front_lng` now** and document which rows changed. Establish rollback
   before anything further.
2. **Rewrite the four address tests to invoke the algorithm**, and add unit tests of the scoring
   function against controlled geometry with known answers.
3. **Re-report the benchmark** using parcel → arrival distance.
4. **Correct the ETA label** and the three overstated trap cases.
5. **Explain `intersection_matches: 0`.**
6. **Then adopt it.** With the above addressed, this replaces `import_parcels.py`. The approach
   is right and the measured improvement is real.

We want to be explicit that none of the above is an argument against the change. The algorithm is
better than what it replaces, by a margin we independently confirmed. The objection is that the
evidence package asserts more than it demonstrates, and that the production database was changed
while the briefing described the change as pending review.

Every figure in this document is reproducible; ask and we will supply the exact query.
