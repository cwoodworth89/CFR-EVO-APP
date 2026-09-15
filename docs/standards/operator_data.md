# Operator data: what people enter, where it lives, and how it survives a refresh

**Started 2026-09-13.** [`data_sources.md`](data_sources.md) records what the City gives us. This
file records what **we** add: arrival points, Street View views, base sites, hall locations and
the rest. The City can re-issue its data; this data exists nowhere else if we lose it.

Everything below was checked against the kiosk database and the code on 2026-09-13 unless it is
marked **not built** or **proposed**.

---

## Operator rulings, 2026-09-13

1. **Everything a person enters lives in its own schema, `cfr`.** This extends #82 ruling 4 from
   placed addresses to all hand-entered data. **Not built.**
2. **Hand data attaches to the civic address as dispatched**, normalized. The City's lot ID
   (`GIS_ID`) is kept beside it as a check, not used as the key (measurement in §4).
3. **A City refresh is semi-manual.** Download, stage, show the differences and what they do to
   hand-entered data, have an operator agree or disagree, then apply. Nothing is dropped silently.
4. **One GIS refresh script, with a flag per layer.** Road closures stay separate: they are a live
   feed, not a City layer copy.
5. **Units fall under their base site.** A civic number a person adds is its own entry, visible
   and editable on its own.
6. **An added address starts as a point, and may be tied to the City lot it sits inside.**
   `2973 Glen Dr` ties to the `2963 Glen Dr` lot: it takes that lot's outline and City attributes,
   and keeps its own arrival point and Street View view. This amends the #82 design line that gave
   a placed address no lot.
7. **The hall locations were recorded by the operator**, and are marked so where they are defined.
8. **`KNOWN_BUILDINGS` is removed** (punch-list #84).
9. **The front point stays: lot outline to the centreline of the street the address names.** The
   front point is computed; the arrival point is hand-curated. They do not change each other
   (#78).
10. **The console keeps its zone colours, and `zones.json` goes.** The colours come from the
    Emergency Guideline 1 assignment stored as data (ruling 15).
11. **The Lougheed Hwy & Mariner Way junction row is removed** (applied 2026-09-13). It was
    labelled `manual`, but a script generated its point and nobody confirmed it. Operator: *"I
    hate that it's called manual as if I did it."* See §5.
12. **A lot's centre point is its pole of inaccessibility** (applied 2026-09-13, §5).
13. **Refresh diffs are reviewed through an agent.** The refresh writes a diff that an agent
    reads and summarizes for the operator.
14. **The Pinecone Burke Mtn lots are served by Harper Rd, which becomes a forest service road
    behind locked gates.** They need manual attention. The design for working lots like these
    goes to the UX agent
    ([`../briefings/needs_attention_design_request.md`](../briefings/needs_attention_design_request.md)).
15. **The grid → first-due unit → hall assignment is stored as data**, cited to Coquitlam
    Fire/Rescue **Emergency Guideline 1, edition of 2025-01-09** (the latest). Not built. Before
    it is stored, the 134 rows from `zones.json` are to be checked against that edition (§5).
16. **A lot's map grid is `zone_for_point()` on `public.zones` at its centre point** (applied
    2026-09-13, §5). The June `Emergency_Response_Zones.shp` is no longer read.
17. **A junction a person pins lives with the other hand-entered locations** in the `cfr`
    schema, attributed to whoever placed it. `public.intersections` holds derived junctions only.
18. **Initials are required; evidence is optional.** An operator may review or place an address
    without a call having used it first. Operator: *"it's don't require an incident to trigger a
    review."* This relaxes #82 ruling 2's "at least one piece of evidence". Recorded with the UX
    design in [`../briefings/needs_attention_design.md`](../briefings/needs_attention_design.md).
19. **A tied lot is drawn on the kiosk dispatch display**, dashed and labelled with the lot's own
    address, so the tie can be reviewed (same design document).
20. **The 1,660 base sites without an arrival point are reviewed slowly over time**, not worked
    as a queue. A locked gate is recorded in the arrival point's note (same design document).
21. **Build map-grid retention**, so a grid you verified on past calls is what the next call to
    that address shows first. Operator: *"We should build out the map grid retention so the
    system gets better over time."* The agreement figure will fall as more calls are compared,
    since comparison is recent. Design and backtest in §5; not built.

---

## 1. The base-site setup, as built

**Do not lose this.** It is where the arrival points and most saved views live, and one WHERE
clause is all that protects it today.

| | |
|:--|:--|
| **What** | CFR's own row in `public.parcels` for each civic address that has more than one City row. `is_base_site = true`. 1,671 rows. |
| **Why** | The City's MASTER row is strata common property, not the site, so no City row can speak for a multi-parcel property ([`../briefings/base_site_rows_decision.md`](../briefings/base_site_rows_decision.md), 2026-08-31). |
| **Built by** | `backend/scripts/import_parcels.py` `build_base_site_rows`: `INSERT … SELECT` over City rows `GROUP BY house, street, streettype HAVING count(*) > 1`. Outline `ST_Multi(ST_Union(geom))`, centre the union's pole of inaccessibility (since 2026-09-13; `ST_PointOnSurface` before), zone `public.zone_for_point()` at that centre. |
| **Key** | Partial unique index `parcels_base_site_address_uniq ON public.parcels (address) WHERE is_base_site`. |
| **Refresh** | `ON CONFLICT (address) WHERE is_base_site DO UPDATE` sets only `house, street, streettype, address_normalized, geom, centroid_lat, centroid_lng, zone_id, updated_at`. City rows are deleted with `DELETE FROM public.parcels WHERE NOT is_base_site`. The hand-entered columns survive because neither statement names them. |
| **Read first** | The geocoder orders `is_base_site DESC` (`services/gis/src/gis_service/address_resolver.py`, exact-parcel step). Every API address lookup goes through `_address_row` with `_BASE_SITE_FIRST` (`backend/api/routers/parcels.py`), so a save and a read land on the same row (#77). |
| **Hand data on it** | 11 arrival points (`entrance_lat/lng`, `entrance_set_by`, `entrance_set_at`, `entrance_note`) and 10 Street View views (`streetview_heading/pitch/fov/pano_id/lat/lng`). |

**Where it leaks today:**

* A single-lot address has no base site, so an arrival point or view saved there is written to a
  City row, which the next parcel import deletes. **9 views are on City rows now**, and 6 of them
  exist nowhere else.
* A Street View save for an address with no parcel creates a row flagged as City
  (`gis_id = address`), which the import also deletes. `888 MIGRATION ST` is one: a test fixture
  in the production database.

**How it is saved:**

* **Nightly at 03:15**, `backend/scripts/backup_db.sh` writes a full dump (7 kept), which contains
  it, and a long-retention "critical" dump, which **does not**: that tier lists whole tables, and
  `parcels` is not among them.
* **Snapshot, 2026-09-13:** `/home/tcfire/cfr-backups/operator-data-20260913/` on the kiosk.
  It holds every base-site row and every row carrying hand data (1,680 rows with geometry as
  GeoJSON), the manual intersection, the vocabulary and `zones.json`, with `SHA256SUMS`.

---

## 2. Everything entered by a person, 2026-09-13

| What | Where it lives | Count | Survives the next refresh? |
|:--|:--|:--|:--|
| Arrival points | `parcels.entrance_*` on base sites | 11, all by CW, 2026-09-09 to 09-12 | Yes (§1). The API can also target a City row. |
| Street View views | `parcels.streetview_*` | 19: 10 base, 9 City | Base yes; City rows **no** |
| Added addresses | not built (#82) | 24 waiting | — |
| Lockbox, hazards, pre-plan, construction, floors | `parcels` columns | 0; nothing writes them | — |
| Manual junctions | none: the one `source = 'manual'` row was script-generated and removed 2026-09-13 | 0 | — |
| Vocabulary | `vocabulary` | 320 rows; 20 learned or operator-added | Yes: imports only add |
| First-due unit per grid | `frontend/public/data/zones.json`; `zones.unit_id/station/hall_id` | 134 in the file, **0 in the database** | The database copy is emptied by every zones import (`TRUNCATE`, last 2026-08-26) |
| Hall locations | code: `routing_engine.py` `FIRE_HALLS`, `MapConstants.js` `STATIONS`, a Hall 1 default in `RouteOverviewPanel.jsx` | 4 | Yes, as code |
| Rail crossings | code: `railroadCrossings.js` | 4, display only | Yes, as code |
| Known buildings | code: `KNOWN_BUILDINGS` | 8 | Being removed (#84) |
| Call corrections | `dispatches.verified_*` | 641 dispatches | Untouched by GIS imports; in the critical backup |

**Lockbox and hazard notes must never be committed to git.** They belong in the database and its
backups.

---

## 3. What each refresh does today

| Script | Writes | Effect on hand data |
|:--|:--|:--|
| `backend/scripts/import_parcels.py` | Deletes every City row, re-inserts from `Addresses.shp`, upserts base sites, recomputes front points | Loses whatever sits on City rows (§1) |
| `backend/scripts/import_gis_data.py` | `TRUNCATE` zones, roads, road names, city boundary; deletes derived intersections; step 9 fills empty front points by a second, centroid-based method | Emptied the first-due columns on 2026-08-26 |
| `import_gis_data.py` step 10 | `ALTER COLUMN geom TYPE GEOMETRY(Point) USING ST_Centroid(geom)` on `parcels` unless `--skip-parcels` | Would turn every lot outline, and so every base-site outline, into a point. From the code, not run. No view depends on the column, so nothing in the database would block it. |
| `backend/scripts/sync_hydrants.py` | Upsert | None |
| `backend/scripts/update_gis_data.py` | Replaces shapefiles on disk; no database writes; never run on the kiosk | None |

No runbook covers a parcel refresh ([`../post_freeze_backlog.md`](../post_freeze_backlog.md),
2026-09-13, #82 line).

---

## 4. Proposed design: not built

**Proposed, awaiting the operator's agreement on the read-time cascade.**

### Where hand data goes

A `cfr` schema in the same database, holding only what people enter:

| Table (names open, #82 ruling 6) | One row per | Holds |
|:--|:--|:--|
| Added addresses | civic number the City does not hold | house, street, suffix, as dispatched; status `pending / active / rejected / retired`; arrival point; optional tie to a City site's address; placer's initials (required), date, evidence (optional, ruling 18) |
| Site details | address key: a site, or a unit where one is ever needed | arrival point, Street View view, lockbox, hazards, pre-plan, construction, floors; who and when |
| Halls | hall | location, recorded by, date |
| Placed junctions | junction a person pins (ruling 17) | point, reason, initials, when, evidence (optional) |

Each refresh runs under a database role with **no privilege on `cfr`**, so the protection comes
from the database rather than from a WHERE clause.

### How it links

The key is the **address**: house, street and suffix normalized by the canonical rules
(`frontend/src/utils/addressUtils.js`, matched backend-side), plus the unit where there is one.
The site key has no unit.

A lookup cascades, first answer wins, and every value keeps its origin:

1. **Place.** A City lot or base site by address. Otherwise an active added address; if it is
   tied, it takes the tied site's outline, zone and City attributes.
2. **Details.** The address's own site-details row, then its base site's, then the computed
   values (front point, then the lot's centre point).

`2973 Glen Dr` under this design: an added address tied to `2963 Glen Dr`, with its own
site-details row for the arrival point and Street View view. Everything else comes from the 2963
site at read time.

### Why a cascade and not injection into City rows

Injecting hand data into City rows on import is the current pattern in all but name, and it is
the pattern that loses data. It also leaves a City row carrying values the City never gave, so
the table stops being what its register row says it is ([`data_sources.md`](data_sources.md),
rule 1), and every diff-reviewed refresh would have to tell our values from theirs. The cascade
keeps each value's origin visible, so the kiosk can say "placed by the operator" (#82 ruling 3).
The cost is that the geocoder and the lookups read through views instead of the table.

### The refresh, semi-manual

For each flagged layer: download to `backend/data/staging/<layer>_<date>/`, then diff against the
live table (added, removed, changed) and against hand data:

* **orphans:** hand data whose address the new copy no longer holds;
* **retirements:** added addresses the City now holds;
* **moved computed points:** front points that move.

The diff is written to a file that an agent reads and summarizes (ruling 13). The operator
agrees or disagrees, the apply runs in one transaction, and the layer's row in
[`data_sources.md`](data_sources.md) gets its new copy date in the same commit.

### The key, measured

Our 2025-06-22 copy against the City's live `Parcel_Addresses` layer, 2026-09-13:

| | |
|:--|:--|
| Lot IDs (`GIS_ID`) across 69,542 City rows | 27,856: an ID names a lot, not an address |
| Still present 15 months later | 27,791 (99.8%); 65 gone, 111 new |
| IDs unique on both sides whose address changed | 24 of 25,316, some in spelling only (`DEER'S LEAP` → `DEERS LEAP`, `1374` unit `B` → `1374B`) |
| Civic addresses (house, street, unit) no longer in the live layer | 402 of 65,381 (0.6%); 4,122 new |

Neither key is fully stable, which is why a refresh reports orphans rather than dropping them.

---

## 5. Open

* **First-due unit per grid.** Coquitlam Fire/Rescue Emergency Guideline 1 is the authority. The
  kiosk's first due is the shortest OSRM ETA among responding units
  (`frontend/src/components/hud/ActiveAlertBanner.jsx`), not the grid assignment. Today the
  assignment is used for:
  * hall colours on the console's zone overlay, from `zones.json`;
  * closures grouped by hall, from `zones.hall_id`, which is empty.

  `zones.json` is not an old map: its 134 grids match `public.zones` with areas within 0.33%
  (median; worst 2.2%, grid 68) and centres within 5 m, simplified to 2,090 vertices from 20,461.
  **Decided (rulings 10, 15):** the assignment is stored as data in the `cfr` schema, cited to
  EG1 of 2025-01-09. Grid outlines come from `public.zones` through the API, the console looks as
  it does now, closures-by-hall starts working, and `zones.json` is deleted. Not built.
  **Blocked on:** checking the 134 `zones.json` rows against that edition. Start with the seven
  grids where the shortest OSRM drive disagrees with the file (measured 2026-09-13, from each
  hall's front apron to the grid's pole of inaccessibility): 21, 23, 37, 43, 50 and 51 (file:
  Hall 2, shortest drive: Hall 3) and 131 (file: Hall 4, shortest drive: Hall 1). The considered
  alternative, colouring by shortest drive, was not chosen.
* **Centre point and map grid: applied 2026-09-13** (rulings 12 and 16), by
  `backend/migrations/2026-09-13_lot_centre_is_pole_of_inaccessibility.sql`. The import computes
  the same values (`set_lot_centres_and_grids`, `build_base_site_rows`), so a re-run cannot
  revert them. The City's property data carries no grid of its own: `ZONETYPE1–3` is land-use
  zoning, and `PLAN_AREA` is 36 planning areas of about 5 grids each.
  * **Before:** the GeoPandas centroid, outside 233 City lots. The grid came from the June
    zones shapefile at that point; base sites used `ST_PointOnSurface`.
  * **After:** the pole of inaccessibility, computed in metres
    ([`dependency-behaviour.md`](dependency-behaviour.md)), and `zone_for_point()` on
    `public.zones` at it.
  * **Checked after applying**, against the rollback copy
    `/home/tcfire/cfr-backups/operator-data-20260913/parcels_centre_and_grid_before_2026-09-13.csv`:
    * 0 centres outside their outline.
    * Centre points moved a median 7.2 m for City lots (p90 30.6 m) and 9.0 m for base sites.
    * **14 grids changed**, exactly as measured beforehand. The 11 City lots are 1046 United Blvd
      14→31, 1085 Falcon Dr 64→69, 3305 David Ave 102→96, 4124 Cedar Dr 116→118, 4300 Oliver Rd
      117→118, and six unaddressed: Braid St and Brunette Ave 1→14, three Deboville Slough lots
      123→118, Dewdney Trunk Rd 65→66. The 3 base sites are 1331 Gabriola Dr 100→102,
      2885 Lansdowne Dr 79→78, 2995 Robson Dr 88→90.
    * Two lots fall in no zone, as before.
    * Front points, arrival points and Street View views are untouched.
  * **The centre point is never a default for placing a pin.** Many addresses can share one lot:
    all 28 Pinecone Burke Mtn addresses are on one 24 ha lot with one centre. The needs-attention
    design shows the centre as a suggestion only. At dispatch it is still the geocoder's last
    resort, and the kiosk shows it with no notice (punch-list #85).
  * **Wrong grids in past dispatches are not fixed by this.** None of the 14 lots was ever
    dispatched to. Of the 29 dispatches whose system grid differs from the verified one:
    * 12 (July–August) show the verified number missing its last digit;
    * 1300 Pinetree Way (twice) and 3501 David Ave calculate 87 and 112 where E-Comm said 86 and
      111, and the new centre gives the same answer;
    * 2 are addresses no City source holds.
* **E-Comm's grid against the lot's grid, and whether a correction persists.** Measured
  2026-09-13 on the 465 verified dispatches matched to a lot: E-Comm's grid is the lot's grid on
  447 (96.1%).
  * **Not a boundary-street rule.** Of the 108 whose front point sits within 3 m of another grid,
    E-Comm used the lot's grid 92 times and the neighbouring grid 14 times.
  * **The 18 disagreements fall on 10 addresses, and E-Comm repeats itself where it has
    repeated:** 1300 Pinetree Way 86 on 6 of 6 (lot 87, entirely inside it), 1210 Pinetree Way
    86 on 2 of 2 (lot 85), 2960 Walton Ave 87 on 2 of 2 (lot 85). 2601 Lougheed Hwy looks
    inconsistent (55, 53, 55, 55, 53; lot 55) but follows the unit: `Number 24` was 53 both
    times, `Number 29` 55 both times, no unit 55. **E-Comm's grid can differ by unit within one
    site.** The other six addresses have one dispatch each.
  * **Where E-Comm's grid comes from is not known.** The cheapest check is whether EG1's map
    puts 1300 Pinetree Way in 86 or 87.
  * **A correction now persists (2026-09-15).** The review screen writes
    `dispatches.verified_map_grid` for that one call, and phase 1 reads that same column at call
    time (`pipeline/grid_history.py`), so a grid corrected in review is what phase 1 shows on the
    next call to that address. Before this, the next call showed the lot's grid in phase 1
    (`parcel-zone`), then the spoken grid in phase 2 with `GRID_MISMATCH`.
  * **Map-grid retention (ruling 21, built 2026-09-15 in `pipeline/grid_history.py`):**
    * **Evidence** is the grids you verified (`dispatches.verified_map_grid`), never the parsed
      grid, which is where the missing-digit errors came from.
    * **Keyed by the dispatched address and its unit.**
    * **Phase 1 order:** the unit's verified history, then the site's, then the lot's grid. Phase
      2 is unchanged: the spoken grid wins.
    * **Computed from the dispatch records at read time**, not copied into a table, so it
      improves the moment a call is verified and cannot go stale (§6.6).
  * **Backtest, 2026-09-13.** The 465 verified calls on a lot, in time order, each allowed only
    the calls verified before it:
    * the lot's grid is right on 447;
    * "earlier verified grid first, when those earlier calls all agree" is right on **454**;
    * it makes **0** wrong that the lot's grid had right;
    * 3 calls had earlier calls that disagreed and fall back to the lot's grid.

    That run keyed by site with any unit removed. Keyed by unit, 2601 Lougheed Hwy's two units stop
    conflicting.
  * **Settled before building (operator, 2026-09-14):** one verified call is enough; when the
    calls consulted disagree there is no answer and phase 1 keeps the lot's grid; the kiosk shows
    a retained grid bare — "the audio and the label will match no need to label", and phase 2
    raises `GRID_MISMATCH` when it does not.
  * **Measured on the corpus at build time, 2026-09-15** (569 dispatches with a numeric
    `verified_map_grid`, 290 address keys, replayed in time order with each call allowed only the
    calls verified before it): 233 calls across 70 addresses take a retained grid, 114 by unit and
    119 by address. It differs from the lot's grid on 8 calls across 4 addresses — 1300 Pinetree
    Way, 1210 Pinetree Way, 2960 Walton Ave and one `Number 24` at 2601 Lougheed Hwy. One address
    has verified grids that disagree: 2601 Lougheed Hwy, which the unit scope resolves.
  * **The "missing last digit" grids (12, 2026-07-18 to 08-31) are a different stage.** In 5 the
    raw transcript already has the short number; in 2 the transcript has the full number and the
    parsed grid kept one digit. None since 2026-08-31.
* **The 160 City lots with no front point.** About 116 carry no house number: water, rail, parks,
  and descriptions such as `N/O Quarry Rd`. The addressed ones are on streets with no City
  centreline: Pinecone Burke Mtn (28 rows), Coronation Cres (7) and Fremont St (5 numbers). The
  last two are [`../city_gis_data_register.md`](../city_gis_data_register.md) §3. Pinecone Burke
  Mtn is reached by Harper Rd, which becomes a forest service road behind locked gates (ruling
  14): those lots need arrival points and access notes set by hand.
* **Lougheed Hwy & Mariner Way: removed 2026-09-13** (ruling 11), by
  `backend/migrations/2026-09-13b_remove_unconfirmed_lougheed_mariner_junction.sql`.
  * **Origin.** Added 2026-08-22 because the fuzzy matcher sent that phrase to Lougheed &
    Pinetree, 4.3 km away. Its point was a script-computed midpoint between the centrelines,
    "NOT operationally confirmed".
  * **Live resolver, measured before removal:** with the row, the interchange midpoint, grid 49,
    confidence 100; without it, **unresolved**, so a call naming it shows the amber card and the
    announced grid.
  * **Scale of the problem.** No dispatch in 641 named it, and all 19 distinct junctions ever
    dispatched resolve to derived rows. Fuzzy matching is now a suggestion only
    (`intersection_resolver.py`), so the 4.3 km error cannot recur.
  * **Restart.** The geocoder caches intersections at start, so a running `cfr-agent` keeps the
    row until its next restart.
* **The workstation's search path ignores the arrival point.** Search results carry `front_lat`
  (front point, else centroid) and only a `has_arrival_point` flag, and `MapBoard.jsx` routes to
  `front_lat || lat`. A searched address with an arrival point routes to the front point until
  one is saved in that session. Dispatch targets carry the geocoder's point and are unaffected.
  From the code; not yet seen on screen.
