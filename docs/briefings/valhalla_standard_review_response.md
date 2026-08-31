# Review response: Valhalla Routing & GIS Data Overhaul

**From:** CFR EVO geocoder/GIS workstream
**Re:** `docs/emergency_routing_gis_parcels_standard.md` (CFR-EVO-STD-GIS-ROUTING-2026) and
`implementation_plan.md`
**Date:** 2026-08-28
**Status:** Review complete. **Recommend: do not execute Steps 1–2 as written.** Specific
blocking items below, each with the measurement that produced it.

---

## 0. A correction to our own first pass

Our initial review challenged the hardware premise, arguing that the rejection of GraphHopper
on "constrained kiosk hardware (Raspberry Pi 5 / Intel N100)" did not hold, because the
machine we measured has 8 cores and 14.8 GB RAM.

**That challenge was wrong and is withdrawn.** We measured the current *test* kiosk, not the
target deployment. The department has confirmed the production fleet is Raspberry Pi. On that
hardware the document's reasoning stands: a 1.2–2.0 GB JVM heap is a genuine constraint, and
Valhalla's tile cache and startup profile are real advantages over GraphHopper.

We are leading with this because it cuts the other way too — the OSRM figures below were also
measured on the test kiosk, and they should be re-measured on a Pi before either side treats
them as settled.

---

## 1. What we agree with, and think should proceed

This is a substantial and largely well-constructed document. Several parts should survive
whatever happens to the rest.

**The failure modes in §2.1 are real, and we have independently measured one.** Mode E
(large campus centroid snapping) is not hypothetical here. `2865 Glen Dr` is a gated strata
complex of 8 legal lots. Our stored front point for it sits on **Guildford Way, 254 m** from
where a crew should arrive. Measured 2026-08-26.

**The diagnosis in §2.1 is correct in mechanism.** Naive nearest-road snapping fails on large
parcels. From the `2865 Glen Dr` centroid, the nearest routable ways are two unnamed internal
ways (114 m), Johnson Street (120.7 m), Guildford Way (121.4 m), and only then **Glen Drive at
135.6 m** — the street the address actually names.

**§2.2 boundary-edge decomposition is the right fix**, and our data supports it: `public.parcels`
is 99.4% `ST_Polygon` (65,023), 0.6% `ST_MultiPolygon` (377), and exactly 1 point. Boundary
decomposition is applicable to essentially the whole dataset.

**The physics in §3.5 is arithmetically sound.** We reproduced Table 3.2 independently:
`P_grav` at 12% / 50 km/h computes to 616.8 kW against the table's 616.9, and the 18% rotor
rise computes to 238.5 °C exactly as stated. This is calculated work, not generated numbers.

**Valhalla's advantages over OSRM are real** — native `exclude_polygons` and request-time
costing genuinely beat OSRM for dynamic closures and multi-apparatus profiles.

---

## 2. Blocking defects in the implementation plan

These are ordered by severity. Each was verified against the running system.

### 2.1 `ST_Buffer(geom, 50)` would exclude 11% of the Earth

Plan §3, `update_gis_data.py`: *"the script must run PostGIS `ST_Buffer(geom, 50)` to generate
the `closure_polygon`."*

**Every geometry column in this database is SRID 4326** (`city_boundary`, `hydrants`,
`intersections`, `parcels`, `road_closures`, `roads`, `zones` — verified via
`geometry_columns`). `ST_Buffer` on a 4326 geometry buffers in **degrees**, not metres.

Measured on a real 112 m road segment:

| Expression | Resulting area |
|:--|--:|
| `ST_Buffer(geom, 50)` — as written | **57,232,823 km²** |
| `ST_Buffer(geom::geography, 50)` — correct | 0.019 km² |

57 million km² is roughly 11% of the Earth's surface; PostGIS emits a coordinate-coercion
notice. Injected into Valhalla as an `exclude_polygon`, this would make **every route fail**,
on every call, silently at first — the request succeeds, the exclusion is just absurd.

**Fix:** `ST_Buffer(geom::geography, 50)::geometry`, or reproject to 26910, buffer, and
reproject back. Either way the unit must be explicit.

### 2.2 `Z_Level` does not exist in the source data

Plan §3 instructs `import_gis_data.py` to *"Extract `Z_Level` and address ranges from the
city's `Roads.shp`"*, and `derive_intersections.py` to suppress intersections where `Z_Level`
differs, *"preventing fatal routing errors off bridges."*

The complete attribute set of the City road centreline source is:

```
BUSROUTE, CLASS, DESCRIPTION, FULLNAME, FUNCTIONAL_CLASS, GIS_ID, ICE_PATROLLED,
INTER_MUNICIPAL, LEFTBEGIN, LEFTEND, LENGTH, MMS_ID, MRN_FLAG, NUM_LANES, OBJECTID,
RIGHTBEGIN, RIGHTEND, ROADNAME, ROADTYPE, SERVICE, SHAPE_Length,
SNOW_PLOWING_PRIORITY, SPEED, STATUS, SUBZONE, SURFACE, TRUCKROUTE,
YEAR_ASSET_BUILT, YEAR_LAST_PAVED
```

**There is no `Z_LEVEL`, level, or elevation attribute.** There is also no parity field for the
`parity_l` / `parity_r` columns in plan §2.

This matters beyond a missing column. A safety-critical behaviour — not routing apparatus off
an overpass — is specified against a field that does not exist. If implemented as written,
`z_level` would be uniformly NULL or 0, the suppression rule would never fire, and the system
would carry a documented safety guarantee it does not actually provide. That is the most
dangerous failure shape in this project's experience: a protection that looks present and is
inert.

**Fix:** either source Z-level from OSM (`layer`/`bridge`/`tunnel` tags, which OSRM/Valhalla
already consume), derive it from geometry, or remove the claim. Do not ship the guarantee
without the data.

### 2.3 The new address-range columns duplicate existing ones

Plan §2 adds `from_addr_l`, `to_addr_l`, `from_addr_r`, `to_addr_r` to `public.roads`.

`public.roads` already has `left_begin`, `left_end`, `right_begin`, `right_end`, populated for
3,441 of 3,451 segments and actively used by block interpolation.

This creates two columns for one fact, free to drift, with nothing reporting when they do.
This project has already been bitten by exactly this twice — the street-suffix mapping that
disagreed with `public.vocabulary`, and `TALK_GROUPS` versus the `radio_channel` vocabulary
(punch-list #20).

**Fix:** rename the existing columns if NENA naming is wanted, in one migration. Do not add
parallel ones.

### 2.4 Plan §5 targets a file and a language that do not exist

`frontend/src/components/DispatchCard.tsx` does not exist. **The frontend contains zero `.tsx`
files** and 36 `.jsx` files. Similarly, `backend/api/routers/dispatch.py` does not exist; the
routers are `dispatches.py` and `routing.py`.

Minor in itself, but it indicates the plan was not written against the current tree, which
raises the question of what else in it is aimed at an assumed structure.

### 2.5 Mixed CRS introduced into a uniformly 4326 database

Plan §2 specifies `closure_polygon GEOMETRY(Polygon, 26910)` while every other geometry column
is 4326. The standard document names EPSG:26910 as the "Primary Metric CRS", but the database
as built does not use it anywhere.

A mixed-CRS schema is workable but it is a decision that should be made deliberately and
applied consistently, not introduced by one column. Note that §2.1's buffer bug is a direct
symptom of this ambiguity.

---

## 3. A compliance claim that is measurably false

Standard §3.1 item 3 states that emergency service boundaries *"form a seamless planar
partition with **zero slivers, zero gaps, and zero overlapping polygons**."*

Measured against `public.zones` (134 polygons) and `public.city_boundary`:

| Assertion | Measured |
|:--|:--|
| zero gaps | **0.2937 km²** of the city lies in no zone |
| zero overlapping polygons | **33 overlapping zone pairs** |
| zero slivers | those overlaps total 0.0001 km² — they *are* slivers |

Two road junctions already fall in that gap and resolve to no map grid: `Lincoln Ave & Oxford
St` (19.8 m from the nearest zone) and `Lincoln Ave & Shaughnessy St` (9.1 m). Both
unambiguously belong to grid 99; the polygon edge does not reach them.

This is written as a statement of compliance. As written it asserts a property of municipal
data that the municipal data does not have. It should be restated as a **requirement or a
known gap**, not a description of the current state — otherwise downstream work will assume a
guarantee that is not there.

---

## 4. Benchmark figures that do not match this deployment

Table 1.1's OSRM column does not match the OSRM we run. Measured on the current test kiosk
(8 cores, 14.8 GB RAM), median of 10 real route requests:

| Table 1.1 claim | Measured |
|:--|:--|
| ~80 MB RAM (Metro Van) | **44.6 MiB** container RSS |
| ~110 MB graph (Metro Van) | **232 MB** in `/data` (168 MB excluding the 64 MB source `.pbf`) |
| 1.5–5.0 ms latency | **median 1.4 ms** (min 1.1, max 1.7) |

Our OSRM is lighter and faster than the document's stated floor.

**We are not claiming these figures refute the Valhalla case.** As noted in §0, they were
measured on the test kiosk, not a Raspberry Pi, and the production comparison is the one that
matters. The point is narrower: **the table's numbers were not measured on this system**, and
a benchmark table in an authoritative standard should say where its numbers came from. We
would suggest re-running both engines on the actual Pi hardware and replacing the table with
measured values.

---

## 5. Sequencing: the strongest objection

**The engine swap does not fix the problem the document opens with.**

The measured defect is *which coordinate is handed to the router*. That is decided before
routing begins. Two measurements make this concrete:

1. **OSRM's geometry matches the City centreline to 1.6 m** where both hold the road. The
   engines do not disagree about where roads are.
2. Given the `2865 Glen Dr` centroid, **Glen Drive is the 4th nearest way at 135.6 m**.

Valhalla, handed that same centroid, faces identical geometry and likewise has no address
data. The endpoint problem is not an engine problem.

Conversely, the fix in §2 is **engine-independent**. We tested the core rule — constrain
snapping to the street the address names, and measure to the parcel *polygon* rather than its
centroid — against the OSRM already in production:

| Address | Proposed arrival | Distance from parcel | vs current stored front point |
|:--|:--|--:|--:|
| **2865 Glen Dr** | `49.282748, -122.803538` | **12.9 m** | **254.2 m** |
| 210 Lebleu St | `49.238287, -122.867529` | 9.3 m | 2.4 m |
| 3025 Anson Ave | `49.277257, -122.792562` | 7.1 m | 14.8 m |
| 3030 Gordon Ave | `49.270549, -122.791911` | 9.2 m | 19.8 m |

All four land 7–13 m from the property, on the correct street, with no infrastructure change.

The scale of the existing defect, measured over a 5,000-parcel sample: **524 (~10.5%,
≈6,900 citywide)** have a stored front point snapped to a road *further away* than the
parcel's own named street. Separately, the frontage backfill only computes where
`front_lat IS NULL`, and there are zero nulls — so it has recomputed nothing since it first
ran, including after the roads re-import that added 237 segments.

**Recommendation:** deliver §2 first, against OSRM, measured over the 305-record dispatch
corpus. Then evaluate Valhalla on its own merits — dynamic closures, apparatus costing,
elevation — with a Pi-based benchmark. Executing both at once means debugging two changes
simultaneously, with the endpoint change being the one that carries the measurable benefit.

---

## 6. Two project-rule conflicts to resolve before coding

**Standards not held (CLAUDE.md §7.3, §7.4).** `docs/standards/README.md` currently records
every row as `NOT HELD`. The standard asserts compliance with `NENA-STA-006.3-2026 §3.2`,
`NENA-STA-015.2-2022`, `NFPA 1225 §18.2`, and `NFPA 1900/1901 §5.7`. We hold none of these
documents and cannot verify the clause numbers offline. The seven academic citations in Table
3.3 are likewise unverified — **we are not alleging they are wrong**, only that they have not
been checked, and §7.4 requires a citation that can be looked up before it reaches code.

If the NENA data model is genuinely being adopted, obtaining NENA-STA-006 would be the single
highest-value action in this whole plan: it would turn the first row of the standards index
from `NOT HELD` to `HELD`, and it governs precisely the SSAP-versus-access-point distinction
this work is about.

**Apparatus physics staging (CLAUDE.md §6.4).** The rule states that apparatus physics and
response-mode factors "MUST NOT be applied implicitly inside a calculation path" and must live
in a named, explicitly enabled, auditable configuration surface. `APPARATUS_TIERS` is currently
retained as staged seed data documented as *not applied*. Plan §4's dynamic apparatus profiling
would apply these implicitly on every route. That needs either an explicit enablement surface
or an agreed amendment to §6.4 — not a silent change of state.

---

## 7. Summary of requested changes

| # | Item | Severity |
|:--|:--|:--|
| 1 | `ST_Buffer(geom, 50)` on 4326 geometry — 57M km² exclusion polygon | **Blocking** |
| 2 | `Z_Level` absent from source; safety guarantee would be inert | **Blocking** |
| 3 | Zone "zero gaps/overlaps" compliance claim is false (0.2937 km², 33 pairs) | **Blocking** (correctness of the standard) |
| 4 | New address-range columns duplicate `left_begin`/`left_end`/etc. | High |
| 5 | Plan targets `.tsx` and `dispatch.py`; neither exists | High |
| 6 | Mixed CRS (26910 column in a 4326 database) | Medium |
| 7 | Table 1.1 benchmarks not measured on this deployment | Medium |
| 8 | NENA/NFPA/APCO clauses and academic citations unverified | Medium |
| 9 | §6.4 apparatus physics staging conflict | Medium |
| 10 | Sequencing: deliver §2 before the engine migration | Recommendation |

We are happy to be wrong on any of these where you have data we do not — particularly the
Pi-hardware benchmarks, where our figures are explicitly from the wrong machine. Every number
above is reproducible; ask and we will supply the exact query.

<!-- audit-ok: backend/api/routers/dispatch.py -- the sentence exists to say this path never existed -->
