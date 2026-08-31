# Decision: the addressed street is authoritative for snapping

**Re:** `import_parcels_PROPOSED.py` street-name prior *(script deleted 2026-08-31; this decision shipped in `import_parcels.py::backfill_parcel_frontage` instead)*
**Date:** 2026-08-29
**From:** CFR EVO operations / GIS workstream

---

## The decision

**A parcel's front point is always placed on the street its address names.** The only thing
that displaces it is an explicit operator override.

The street name stops being a scoring input and becomes a filter.

---

## Why

The address *states* which street the property is on. `parcels.street` is municipal data and
`roads.roadname` is municipal data — this is a recorded fact, not an estimate to be weighed
against geometry.

The current `(1.0 + 2.0 * I_name)` prior gives the correct road a 3× advantage and then lets
parallelism, edge length, road classification and distance decay outvote it. **That is a weight
overruling a fact**, and it is measurable: 1,813 of 65,399 parcels ended up on a street their
address does not name.

We looked for cases where overruling the address would be right, and did not find one that an
override does not handle better:

| Case | Should geometry overrule the address? |
|:--|:--|
| Corner lot on two streets | No — the number is posted on the addressed street |
| Property accessed from a rear lane | No — that is an override, and should be recorded as one |
| Campus whose driveway is off a side street | No — override, so the reason is visible to crews |
| Flag lot set back from the road | No — the addressed street is where the driveway meets it |
| Divided highway | No — that is a side-of-street question, not a which-street question |

In every case the answer is either "the address is right" or "a human needs to record why it
isn't." Neither is a scoring problem.

---

## What changes, and what does not

**Changes:** one condition. Where a road matching the addressed street exists, score only that
street's edges.

**Does not change:** the scoring itself. Angular parallelism, logarithmic length weighting,
classification hierarchy, distance decay and micro-edge filtering all stay exactly as built, and
all still matter — because:

> **The address determines *which* road. The scoring determines *where along it*.**

That second question is real work. A parcel with 200 m of frontage, an L-shaped lot, or a
faceted cul-de-sac curve all need edge decomposition to place the point sensibly. That is what
your algorithm is good at, and none of it is lost. It is simply applied inside the correct
street rather than being allowed to choose a different one.

---

## The two legitimate exceptions

**1. No road of that name exists.** 54 parcels, all tracked in
`docs/city_gis_data_register.md` — genuine gaps in the municipal roads layer, plus one
normalisation issue on our side. Here the filter has no input, so fall through to the scored
geometry and flag the result as approximate. Never invent a street.

**2. An operator override is recorded.** A company officer knows the Knox box is off the rear
lane, or the only apparatus-width entrance is on the side street. That belongs in a dedicated
override table — Tier 1 of your own standard's hierarchy — authored by a human, dated,
attributable, and visible on the kiosk as the reason the pin is where it is.

Note this table does **not** exist yet. `streetview_overrides` is the existing precedent for the
pattern. Building it is a separate, sanctioned piece of work; the important thing is that the
exception path is *explicit and recorded*, not inferred by a weight.

---

## Current state and what we need

After our corrective migration, **zero parcels sit off their addressed street where such a
street exists** (331 report a different nearest road, but 277 of those lie on the addressed
street within 1 m — another road simply passes closer — and the remaining 54 are the no-road
cases).

So the data is already correct. What is missing is enforcement in the code: **a re-import today
would reintroduce all 1,813.**

To sign off on replacing `import_parcels.py`:

1. Change the 3× name prior to a filter, with fallback only when no matching road exists.
2. Re-run the benchmark from a clean re-import, so it measures the script alone rather than the
   script plus our correction.
3. Expect the result to be: 0 parcels off their addressed street, 54 flagged approximate.

That is a single conditional, and it turns a good algorithm into a correct one.
