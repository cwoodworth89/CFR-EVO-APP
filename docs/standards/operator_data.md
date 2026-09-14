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
10. **The console keeps its zone colours, and `zones.json` goes.** How the colours are sourced
    is open (§5).
11. **The Lougheed Hwy & Mariner Way manual junction is kept.** Measured the same day: the live
    resolver returns *unresolved* for that phrase without it (§5).
12. **A lot's centre point becomes its pole of inaccessibility.** Approved; applied only after
    the diff in §5 is agreed (ruling 3).
13. **Refresh diffs are reviewed through an agent.** The refresh writes a diff that an agent
    reads and summarizes for the operator.
14. **The Pinecone Burke Mtn lots are served by Harper Rd, which becomes a forest service road
    behind locked gates.** They need manual attention. The design for working lots like these
    goes to the UX agent
    ([`../briefings/needs_attention_design_request.md`](../briefings/needs_attention_design_request.md)).

---

## 1. The base-site setup, as built

**Do not lose this.** It is where the arrival points and most saved views live, and one WHERE
clause is all that protects it today.

| | |
|:--|:--|
| **What** | CFR's own row in `public.parcels` for each civic address that has more than one City row. `is_base_site = true`. 1,671 rows. |
| **Why** | The City's MASTER row is strata common property, not the site, so no City row can speak for a multi-parcel property ([`../briefings/base_site_rows_decision.md`](../briefings/base_site_rows_decision.md), 2026-08-31). |
| **Built by** | `backend/scripts/import_parcels.py` `build_base_site_rows`: `INSERT … SELECT` over City rows `GROUP BY house, street, streettype HAVING count(*) > 1`. Outline `ST_Multi(ST_Union(geom))`, centre `ST_PointOnSurface(ST_Union(geom))`, zone `public.zone_for_point()`. |
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
| Manual junctions | `intersections`, `source = 'manual'` | 1: Lougheed Hwy & Mariner Way | Yes: the rebuild deletes derived rows only |
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
| Added addresses | civic number the City does not hold | house, street, suffix, as dispatched; status `pending / active / rejected / retired`; arrival point; optional tie to a City site's address; placer, date, evidence |
| Site details | address key: a site, or a unit where one is ever needed | arrival point, Street View view, lockbox, hazards, pre-plan, construction, floors; who and when |
| Halls | hall | location, recorded by, date |
| Manual junctions | junction, if any are kept | point, reason, who, when |

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
  Ruling 10 keeps the colours and removes the file. **Two ways to source the colours:**
  * **EG1 as data.** The 134-row grid → first-due unit → hall assignment moves to the `cfr`
    schema, cited to Emergency Guideline 1 and its revision. Outlines come from `public.zones`
    through the API. The map looks exactly as it does now, and closures-by-hall starts working.
  * **Computed.** Colour each grid by the hall with the shortest OSRM drive, from each hall's
    front apron to the grid's pole of inaccessibility, on the production graph. No data to
    maintain. Measured 2026-09-13: 127 of 134 grids keep their colour. Grids 21, 23, 37, 43, 50
    and 51 turn from Hall 2 to Hall 3, and grid 131 from Hall 4 to Hall 1. Grids 21 and 43 are
    near-ties (9 s and 20 s) that could flip with a different point in the grid.
* **Map grid of a lot.** The City's property data carries no grid. `Addresses.shp` and
  `Parcel_Addresses` have `ZONETYPE1–3` (land-use zoning such as `R-1`) and `PLAN_AREA` (36
  planning areas, each spanning about 5 grids). Today a City lot's grid is the June
  `Emergency_Response_Zones.shp` polygon containing its centroid, **even when the centroid is
  outside the lot**. **Proposed:** take the grid from `zone_for_point()` on `public.zones` at the
  lot's new centre point (ruling 12), as base sites already do, and drop the shapefile path. That
  makes one source and one point. Measured 2026-09-13, it would change:
  * **11 of 69,541 City lots**, 5 of them addressed: 1046 United Blvd 14→31, 1085 Falcon Dr
    64→69, 3305 David Ave 102→96, 4124 Cedar Dr 116→118, 4300 Oliver Rd 117→118. 2 unaddressed
    lots would have no grid.
  * **3 of 1,671 base sites:** 1331 Gabriola Dr 100→102, 2885 Lansdowne Dr 79→78, 2995 Robson Dr
    88→90.
  * **No dispatch in the corpus** went to any of them, so nothing says which grid E-Comm uses for
    a lot that straddles two.
* **The lot's centre point (ruling 12, not yet applied).** The pole of inaccessibility, computed
  in metres (see [`dependency-behaviour.md`](dependency-behaviour.md)), is inside all 71,212
  outlines; the centroid is outside 233.
  * **City lots:** the point moves a median 7.2 m (p90 30.6 m, max 611.6 m); 3,498 move more than
    50 m.
  * **Base sites** (today `ST_PointOnSurface`): a median 9.0 m (p90 42.4 m, max 758.4 m); 146
    move more than 50 m.

  It is the third fallback pin, the pin for a substituted nearest number, and the input to the
  street-centre fallback. Front points and arrival points do not move. Applying it means a
  migration for the stored values plus the same computation in `import_parcels.py`, so the next
  import cannot revert it.
* **The 160 City lots with no front point.** About 116 carry no house number: water, rail, parks,
  and descriptions such as `N/O Quarry Rd`. The addressed ones are on streets with no City
  centreline: Pinecone Burke Mtn (28 rows), Coronation Cres (7) and Fremont St (5 numbers). The
  last two are [`../city_gis_data_register.md`](../city_gis_data_register.md) §3. Pinecone Burke
  Mtn is reached by Harper Rd, which becomes a forest service road behind locked gates (ruling
  14): those lots need arrival points and access notes set by hand.
* **Lougheed Hwy & Mariner Way (kept, ruling 11).** No dispatch in 641 has used it. It was added
  2026-08-22 because the fuzzy matcher sent that phrase to Lougheed & Pinetree, 4.3 km away;
  fuzzy matching is now a suggestion only (`intersection_resolver.py`). Measured with the live
  resolver on the kiosk, 2026-09-13:
  * with the row, both word orders resolve to the interchange, grid 49, at confidence 100;
  * without it, both return **unresolved**.

  The resolver removed the wrong answer, but did not replace the row.
* **The workstation's search path ignores the arrival point.** Search results carry `front_lat`
  (front point, else centroid) and only a `has_arrival_point` flag, and `MapBoard.jsx` routes to
  `front_lat || lat`. A searched address with an arrival point routes to the front point until
  one is saved in that session. Dispatch targets carry the geocoder's point and are unaffected.
  From the code; not yet seen on screen.
