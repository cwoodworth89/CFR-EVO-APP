# Handoff: parcel arrival points, road data, and the review queue

**Written 2026-08-29.** Read this if you are picking up the GIS/geocoder workstream.

Companion documents:
* [`docs/review_status_handoff.md`](./review_status_handoff.md) — overall system state
* [`docs/parser_audit_handoff.md`](./parser_audit_handoff.md) — the parallel parser workstream
* [`docs/city_gis_data_register.md`](./city_gis_data_register.md) — questions for City GIS
* [`docs/debug_and_qa_punchlist.md`](./debug_and_qa_punchlist.md) — live work queue
* [`CLAUDE.md`](../CLAUDE.md) — §6 and §7 are the ones that bite

---

## The one-line summary

Every parcel now has an arrival point on the street its address names, computed rather than
guessed, reproducible from the import script. What remains is a review queue of ~1,400 large
sites and the UI to work it.

---

## What shipped

| Commit | What |
|:--|:--|
| `af9e3c1` | Subset trap, hundred-block bound, honest centroid labels |
| `1adaa35` | A real civic address outranks a midpoint between roads |
| `3fb8930` | Every non-parcel location flagged; `(Street Centroid)` migrated out of the address |
| `ec10077` | Amber banner whenever the geocoder placed a location approximately |
| `677b801`/`4a9f5e8`/`b907048` | XStreets ranking, then corrected to house-number-decides |
| `302af14` | Roads import stopped discarding 242 segments |
| `c62f73b` | Every front point moved onto the street its address names |
| `cd150d0` | Shared-parcel register entry; full-city site export |
| `5576afc` | **The constraint moved into `import_parcels.py`** |

### Verified state, measured not assumed

| | |
|:--|--:|
| Parcels | 65,401 |
| With a computed arrival point | 65,401 |
| **Sitting off their addressed street** | **0** |
| No road of that name exists (City gap) | 54 |
| `public.roads` | 3,451 (was 3,214) |
| `public.intersections` | 1,995 (was 1,785) |
| Backend tests | 153 passing |

Front points went from **63.8% → 97.9%** on their own addressed street (fixed 5,000-parcel
sample), and citywide from 1,813 wrong-street to **0**.

---

## How arrival points work now

```
entrance_lat/lng   operator-verified access point   ← all NULL today, see #49
      ↓ (falls through cleanly when NULL)
front_lat/lng      computed: closest point on the road parcels.street NAMES,
                   measured to the parcel POLYGON
      ↓
lat/lng            parcel centroid, last resort
```

**The rule is a constraint, not a heuristic.** The address *states* the street;
`parcels.street` and `roads.roadname` are both municipal data. A scoring weight can be
outvoted by geometry, a filter cannot. Measuring to the polygon rather than the centroid is
what fixes large sites — 2865 Glen Dr's centroid is 135.6 m from Glen Drive, and on 177
parcels citywide the centroid falls *outside* the parcel entirely.

`import_parcels.py::backfill_parcel_frontage` recomputes **all** rows in ~9 s. It previously
selected `front_lat IS NULL OR front_lat = lat` — backfill-only, therefore a no-op once
populated, which is why nothing recomputed when the roads import gained 237 segments.

**It must never write `entrance_*`.** The comment is in the code. Human knowledge has to
survive the pipeline that regenerates computed values.

---

## Open, in the order I would take it

### 1. Punch-list #49 — access-point review UX. HIGH.
Schema and data are ready; there is no interface. All 65,401 `entrance_lat` are NULL and the
only way to set one is hand-written SQL against production. Queue is
`docs/complex_sites_for_review.csv` — 1,395 sites, 25,475 addresses; the top 100 by address
count covers 65%. Constraints are written up in the punch-list entry.

### 2. The other team's `import_parcels_PROPOSED.py` is unresolved.
They built boundary-edge scoring with a **3× street-name prior** — a weight, not a filter,
which is exactly what produced the original 1,813 wrong-street parcels. We asked for it to
become a filter (`docs/briefings/addressed_street_snapping_decision.md`). Their 24 unit tests
are good and pass. **Do not adopt the script until the prior is a filter**, and note our
`import_parcels.py` now already does the right thing, so there may be nothing left to adopt.

Also still live: `public.fn_calculate_parcel_road_snap` is registered in production and called
by nothing. Decide whether to wire it in or drop it.

### 3. `parcels_frontpoint_snapshot_20260828` should be dropped once #2 settles.
It holds the pre-correction state. Pre-*snapping* state is in
`cfr-full-20260828-031501.sql.gz`.

### 4. City GIS register has 13 open items.
`docs/city_gis_data_register.md`. Highest value: obtaining **NENA-STA-006** would turn the
first row of `docs/standards/README.md` from `NOT HELD` to `HELD` and governs exactly the
site-vs-access-point distinction this work is about.

### 5. Smaller, known
* Apostrophe normalization (`Deer's Leap` vs `Deers Leap`) is handled inline in two places;
  it belongs in `normalization.py`.
* Confidence is not calibrated — score 100 was wrong on 8% of reviewed calls, and the 81–89
  band was flawless. Punch-list #32.
* `import_parcels.py` dedupes duplicate addresses first-wins with no ordering (punch-list
  #48). 1,509 addresses span several legal parcels; 631 differ by >25 m.

---

## Where this sits against the freeze

**Operator clarification, 2026-08-29: it is a FEATURE freeze, not a code freeze. Routing was
broken, so fixing it is in scope.**

That resolves most of what follows. An earlier draft of this section assessed the work against
a code freeze and concluded the scope had drifted; under the correct premise it largely had
not. The assessment is kept below because the distinctions are still worth a reader's
attention — particularly the new schema surface, which is worth noticing under any freeze.

The test to apply: **was it broken, or is it new?** Everything in the shipped list was broken
and measurably so. The one genuine feature, the access-point review UX, was recognised as such
and deferred (#49).

### On substance: in scope

Every change fixed a defect that was **measured, not suspected**, and most were already on the
punch list. Items closed or advanced: **#19** (the `token_set_ratio` subset trap on the main
address path), **#12** (centroids reported as exact addresses), **#1** (the four live
wrong-location cases), **#42** (the roads import discarding 242 segments). Items opened with
evidence rather than speculation: **#48**, **#49**.

Nothing here was a feature. The nearest thing to one — the amber approximate-location banner —
displays a `resolution_note` the pipeline was already computing and then discarding.

### On scope: it grew, but the chain was all defect-driven

The session began as "review the punch list" and ended having rewritten how arrival points are
computed for all 65,401 parcels. Each step followed from the last: #19 exposed the wrong-street
snapping, which exposed the frozen backfill, which exposed the roads filter, which exposed the
complexes. Every link was a defect. Under a feature freeze that is
exactly the work; the only thing missing was anyone stating the chain out loud as it grew.

### On mode: review became repair, which was the point

`feedback_qa_issue_intake` records the working agreement as **log to the punch list, then
read-only characterisation, no fixes unless asked.** Every fix here *was* asked for. But the
asking followed from what surfaced, so the drift is real even though each step was authorised.

### New surface area added during a freeze

This is the part that most deserves scrutiny:

| Added | |
|:--|:--|
| Columns | `entrance_set_by`, `entrance_set_at`, `entrance_note`, `access_far_corner_m` |
| Table | `parcels_frontpoint_snapshot_20260828` (temporary, drop after adoption settles) |
| Vocabulary category | `xstreet_descriptor`, 9 rows |
| Migrations | 5 |
| Production data rewritten | parcel front points (twice), 8 dispatch records, 1 `verified_address` |

All of it is recoverable and documented, and `entrance_*` reuses columns that already existed.
But four new columns and a new vocabulary category is schema growth, and a freeze is exactly
when that should be a conscious decision rather than a consequence.

### Correctly deferred

* **The Valhalla migration** — a total routing-engine replacement, paused after review. That
  would have been genuinely off course.
* **The access-point review UX** (#49) — recognised as a feature and deferred at the
  operator's direction.
* **OSRM profile tuning** (#1) — still blocked pending documentation.

### What should happen before more work lands

1. **Settle the other team's `import_parcels_PROPOSED.py`** so there is one parcel import, not
   two candidates.
2. **Drop `parcels_frontpoint_snapshot_20260828`** once that is settled.
3. Treat **#49 as the first post-freeze feature**, not as continuing work — it is a UI that
   does not exist yet, which is the one thing here that is unambiguously new.

---

## Traps that cost time here

**Agreement is not correctness.** A metric that can only confirm its own assumption proves
nothing. Three instances in two days: the other team's `avg_snap_dist_m` measured a snapped
point's distance to the road it was snapped to (zero by construction); my "spread between unit
arrival points" made every trailer park look healthy, because 265 pads sharing one footprint
agree perfectly; and their four headline tests read the database column they had just written.

**Sample by `ORDER BY id LIMIT n` is not a random sample.** I extrapolated 524/5,000 to
"≈6,900 citywide"; the measured figure was 1,813. Paired before/after comparisons on the same
subset are still valid — the absolute extrapolation was not.

**Unnormalised diffs overstate error.** Address error looked like 30.2%, was 16.8%. Front-point
mis-snapping looked like 36.2%, was 10.5%. Bucket cosmetic vs actually-wrong before quoting a
rate.

**Check the field exists before building on it.** `Z_Level` is absent from the City roads
file, yet a proposed safety guarantee depended on it. `entrance_lat` held a copy of the
centroid. `STATUS` on roads records ownership, not service state, and filtering it as though
it meant "in service" dropped 45 streets carrying 1,918 parcels.

**Ask the operator. He is the subject-matter expert, not a stakeholder to be informed.**

Curtis has nearly 15 years of on-the-floor firefighting experience and is building this for
his own crews. On any question of fire-ground reality — how a call is dispatched, what a crew
needs on arrival, what an address means operationally, which sites are awkward — **his answer
outranks an inference from the data.**

This is not deference for its own sake. Measured across one session, he was right and I was
wrong six times, in ways no query would have reached:

| He said | What it corrected |
|:--|:--|
| Three trailer parks: 201 Cayer, 4200 Dewdney Trunk, 101 Schoolhouse | My detector scored all three as **perfectly healthy**. 265 pads sharing one footprint agree on one arrival point, so "agreement" hid a 12-hectare site. The metric was wrong. |
| "Booth is houses" | I had classified a cadastre resolution issue as a trailer park. |
| "2865 Glen Dr isn't 8 lots, it's 77 units" | My framing was misleading; the 8 were duplicate features of the bare address. |
| "Always use the addressed street unless overridden" | I tested every counterexample I could construct — corner lots, rear-lane access, campuses, flag lots — and could not break it. It became the core rule. |
| "Do we need all this complex code?" | Correct. Once the street is filtered, four of five scoring terms have nothing left to decide. |
| "The Raspberry Pi premise is right for the full deployment" | Invalidated a challenge I had raised against another team on hardware grounds. |

**The division of authority that works:** he is authoritative on the fire ground and the city;
measurement is authoritative on what the software actually does. Both have caught real defects
this week. Neither substitutes for the other — but when a measurement disagrees with him about
the world, the measurement is the thing to re-examine first.

---

## Environment

* Kiosk is the test machine; **production fleet is Raspberry Pi** — do not benchmark on the
  dev kiosk and call it representative.
* Backups: `/home/tcfire/cfr-backups` and sibling `CFR-EVO-Backups`. Verify a restore point by
  extracting a known value, not by reading the filename.
* Tailscale SSH lapses and hangs; each retry mints a *new* auth URL, so hand the user one link
  and wait.
* Long PostGIS queries exceed the 120 s tool timeout — run them backgrounded or narrow them.
* `psql` meta-commands (`\pset`) echo into piped output; use `-q -P pager=off` on the command
  line when generating CSV.
