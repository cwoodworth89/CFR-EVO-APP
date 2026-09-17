# Punch list #92 — Closures the City files on its own boundary roads are dropped by the spatial tests

| | |
|:--|:--|
| **Status** | DEPLOYED `d112cf37` 2026-09-16 23:48Z, **confirmed in part by lead** (see the log): the sync completes, the DriveBC Bypass event is served in zone 52, four City boundary records are served, one is correctly inactive (ended 09-12), MOTI is at zero. **Open:** Westwood St at Gordon Ave has no row at all — cause with GIS; DriveBC `street_name` null; sync wall time 10.7 s against ~1 s before #92 |
| **Severity** | 🔴 crew-visible — a closure on North Rd, Westwood St or the Mary Hill Bypass is on the road crews drive, and it is not on the kiosk |
| **Area** | 🗺️ GIS · ⚙️ API |
| **Origin** | [`../briefings/municipal511_coquitlam_records_2026-09-16.md`](../briefings/municipal511_coquitlam_records_2026-09-16.md), the "dropped by the spatial tests" section, read by the operator |
| **Related** | #91 · #13 (`ST_Contains` vs `ST_Intersects` cost 155 intersections their grid) · CLAUDE.md §6.2, §7.3a |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

The closure ingestion keeps a record only when its geometry **intersects `public.city_boundary`**
and **touches a `public.zones` polygon** (`backend/api/closure_spatial.py`). On 2026-09-16 those
two tests dropped seven current records that the City of Coquitlam and MOTI filed for roads
inside Coquitlam:

| Feed id | Filed by | Where | Type | Dropped because |
|:--|:--|:--|:--|:--|
| `muni_4\|77458316\|8099_0` | BC MOTI Gateway | Mary Hill Bypass at the Mary Hill Bypass onramp | Lane(s) Closed | inside the city, in no response zone |
| `muni_4\|78131841\|8096_0` | City of Coquitlam | North Rd 64 m north of Rochester St | Lane(s) Closed | outside the city boundary |
| `muni_4\|78132259\|8096_0` | City of Coquitlam | Balmoral Dr 96 m south of Guildford Dr | Lane(s) Closed | inside the city, in no response zone |
| `muni_4\|78323174\|8096_0` | City of Coquitlam | Westwood St at Gordon Ave | Lane(s) Closed | outside the city boundary |
| `muni_4\|78341457\|8096_0` | City of Coquitlam | Victoria Dr 37 m east of Mitchell St | Lane(s) Closed | outside the city boundary |
| `muni_4\|78395658\|8096_0` | City of Coquitlam | North Rd 88 m south of Foster Ave | Lane(s) Closed | outside the city boundary |
| `muni_4\|78427933\|8096_0` | City of Coquitlam | North Rd 77 m south of Foster Ave | Lane(s) Closed | inside the city, in no response zone |

**Operator, 2026-09-16:** *"These were all dropped by not being in the city... but the city is
publishing them? Those are 100% inside Coquitlam and need to be displayed accordingly. They're
on boundaries, but valid types."* And of the Bypass record: *"Inside the city, but not a
response zone? Where is it on the map. Concerning."*

North Rd is the Burnaby line; Westwood St and Victoria Dr run along the Port Coquitlam line;
the Mary Hill Bypass is a provincial highway inside the city. A road that *is* the municipal
boundary puts a closure a few metres either side of the polygon edge by construction, and a
zone layer that stops at a road edge or excludes a highway right-of-way leaves the road itself
uncovered. **Which of those it is, per record, is not yet measured** — that is the first half of
the job.

## The larger half: DriveBC

One SELECT on the kiosk after the 21:00Z sync of 2026-09-16: `public.road_closures` holds
181 rows — 71 active and 107 inactive filed by the City of Coquitlam, 3 inactive by BC MOTI
Gateway — and **not one row from DriveBC Open511, active or inactive, since the oldest row
(2026-08-18)**. The feed is reached on every sync (`sync.sources` says so), and the live feed
held 306 active events that day, including the Lougheed at Kennedy Rd and the Port Mann
approaches. As far as the table can show, the same two tests — or something earlier in the
DriveBC branch — drop **every** provincial-highway event, and the `roads[].state` mapping
deployed at 20:59Z has never had a record to act on. That is the highway-call half of this
item and probably the larger one. Cause per event to be measured, not guessed.

## Measured, 2026-09-16 (GIS, on the kiosk's live layers; the feed's own point geometries; metres on geography)

| Feed id | Where | Lat, lon | To boundary line | Nearest zone (m) | Nearest road → boundary |
|:--|:--|:--|--:|:--|:--|
| 77458316 | Mary Hill Bypass at onramp (MOTI) | 49.22695, −122.80628 | 7.8 inside | 52 (27.3) | Mary Hill By-Pass Rd, **0.0** |
| 78132259 | Balmoral Dr 96 m S of Guildford | 49.27964, −122.82379 | 0.1 inside | 69 (10.9) | Balmoral Dr, 1.1 |
| 78427933 | North Rd 77 m S of Foster | 49.25611, −122.89295 | 0.0 | 4 (1.5) | North Rd, **0.0** |
| 78131841 | North Rd 64 m N of Rochester | 49.24522, −122.89275 | 4.2 outside | 3 (9.5) | North Rd, **0.0** |
| 78395658 | North Rd 88 m S of Foster | 49.25601, −122.89295 | 0.1 outside | 4 (1.6) | North Rd, **0.0** |
| 78323174 | Westwood St at Gordon | 49.26991, −122.79061 | 0.6 outside | 68 (1.9) | Westwood St, **0.0** |
| 78341457 | Victoria Dr 37 m E of Mitchell | 49.28575, −122.74016 | 0.5 outside | 111 (touches) | Victoria Dr, 0.5 |

**Causes, measured, not guessed.** `public.city_boundary` is one polygon, no holes; all seven sit
within 7.8 m of its outer ring. **The four "outside":** the nearest `public.roads` centreline is
0.0–0.5 m from the boundary line — the road *is* the boundary, so a point on it falls either side
by construction. **The three "inside, no zone":** each is inside the city and outside the union of
all 134 zones — `public.zones`' outer edge does not follow the city boundary, leaving a strip of
city covered by no zone (271–12,229 m² of it within 150 m of each point); the Bypass has the
widest strip, zone 52's edge stopping 27 m from the closure. **Whether that strip is a deliberate
right-of-way exclusion in the City's layer cannot be told from the geometry** — a question for
`docs/standards/data_sources.md` and the operator. Victoria Dr touches zone 111 and was dropped by
the boundary test alone.

## The DriveBC half, measured — two causes, one of them systemic after all

GIS, two requests with the operator's permission, registered (`cbeb7a8c`): the feed at 23:11Z
(`status=ACTIVE&limit=500`, 286 active events) and, at 23:31Z, **the sync's own exact URL**
(`events?format=json&limit=100`).

**Cause 1 — the sync only ever sees 100 of the feed's events, chosen province-wide.**
`road_closure_service.py`'s DriveBC request carries `limit=100` and no area filter. Its 100 at
23:31Z were all active and all among the 286, spread across the province — Cariboo 20,
Vancouver Island 16, Okanagan 15, Lower Mainland 13 — so about 65% of active events never reach
the spatial tests, and which 100 arrive is the API's choice. **The one event inside Coquitlam
that day, `RIDE-100086`, was not in the sync's 100.** This is systemic: on any day the API's
first 100 do not include an in-city event, it is invisible regardless of the spatial tests.
Lead's first reading — "not the systemic drop I suspected" — was wrong about *this* cause and
right that the spatial tests alone were not it.

**Cause 2 — the zone strip.** The same cause as the three municipal "inside, no zone" records;
`eb90bcc7`'s buffer fixes it (once the regression is fixed).

**Nothing earlier in the DriveBC branch drops anything:** all 286 have an id and a Point or
LineString with coordinates; the branch has no road-name filter.

**Per event within 2 km of the city** (one read-only query of all 286 geometries; the per-event
run through the daemon's own functions timed out at 600 s over Tailscale and was not retried):

| Event | Where | State | From city | Old tests | Buffered | In sync's 100 |
|:--|:--|:--|--:|:--|:--|:--|
| RIDE-100086 | Hwy 7B, Mary Hill Bypass (49.22697, −122.80629), bridge construction | ALL_LANES_OPEN BOTH, MAJOR | inside | zone test | kept, zone 52 | **no** |
| RIDE-102450 | Hwy 17, Surrey, 545 m E of the Port Mann | ALL_LANES_OPEN W | 786 m out | boundary | boundary | yes |
| RIDE-102296 | Hwy 1A, Riverview Bridge | ALL_LANES_OPEN BOTH | 1,768 m out | boundary | boundary | yes |

The other 283 are more than 2 km out. Nothing on the Lougheed or Barnet through Coquitlam was in
the feed at 23:11Z. **Correction by lead:** the "192 / 193 / 195 on the Lougheed at Kennedy Rd"
lead cited to GIS are DriveBC *webcam* ids from the HighwayCams CSV, not events — lead conflated
the two; GIS was right that no such events exist. History before today cannot be measured
backwards; what is measured is that both causes applied on 2026-09-16.

**Fix for cause 1 — sourced, not built; it changes a production request, so it is the
operator's.** BC's own OpenAPI spec for the feed (read by lead 2026-09-16) defines a **`bbox`**
query parameter on `GET /events`: "Limits the response to events that fall within the specified
geographical bounding box. The bbox format must be '[min longitude],[min latitude],[max
longitude],[max latitude]' with WGS84 coordinates." Also `area_id`, `road_name`, `jurisdiction`,
`status`, `severity`, `event_type`, `created`, `updated`. (`limit` and `offset` are *not* in the
spec, though the live API accepts `limit`.) So the sync can ask for exactly the envelope of
`public.city_boundary` buffered 100 m — the same figure — and receive only in-area events: a
small payload, no cap, no timeout risk, and no province-wide records paying the spatial tests.
GIS's alternatives, `limit=500` with the 5 s `urlopen` timeout raised (733 KB measured vs 233 KB
now), or `offset` pagination, both keep pulling the whole province. Same host and path, so not
a new external call; §2.1's row changes. **Falsifier:** after the change, `drivebc.ca/RIDE-100086`
(while active) appears in `public.road_closures` in zone 52.

## What it should do

A closure the City files on a road inside or along Coquitlam is shown, grouped under the
nearest hall. The boundary test tolerates the boundary; the zone test supplies grouping and
does not filter.

## What decides the fix

- **The buffer figure.** The routing profile already buffers `public.city_boundary` by **100 m**
  on an operator figure (2026-09-09, `apparatus.lua`). If all seven fall within 100 m of the
  boundary and of a zone, the fix reuses that figure and says so; if any does not, the figure is
  the operator's to set, not GIS's.
- **Neighbours' records — measured: none exist.** Burnaby, Port Coquitlam, Port Moody and New
  Westminster do not publish to Municipal 511; the only non-Coquitlam publisher in the feed is
  BC MOTI Gateway. The buffer admits **exactly the seven and nothing else** (of MOTI's two records
  near the city, one — the Bypass). No domain call needed today; if a neighbour ever publishes,
  it will show up in the admin panel counts and the operator rules then.

## Falsifier

After the fix, the seven feed ids above are in `public.road_closures`, active, each with a
zone or grouped as OTHER, and the kiosk serves them. Before it, `SELECT count(*) FROM
public.road_closures WHERE closure_id IN (...)` is 0.

## Log

| Date | Event |
|:--|:--|
| 2026-09-16 | Found by the operator in the #91 review list. Opened as crew-visible. Sent to `gis-spatial-engineer`: measure each record's position against the boundary and the nearest zone and name the cause, then fix behind the existing 100 m figure only if every record falls inside it; report the neighbour-municipality count and any DriveBC events the same tests drop |
| 2026-09-16 | **Deployed 23:48:08Z (kiosk HEAD `f50d9b90`), confirmed in part by lead.** Forced sync: `SUCCEEDED`, 81 synced, 0 skipped, both reached, **10.7 s wall** (GIS's 0.82 s was inside Postgres; the same POST took ~1 s wall before #92 — with GIS to break down). Served 73: 72 City + **1 DriveBC, `RIDE-100086`, zone 52, `ALL_LANES_OPEN` BOTH, MAJOR** — the first DriveBC row the table has ever held (falsifier 2 ✓). MOTI active served 0 (falsifier 3 ✓). Of the seven: Balmoral (zone 69), Victoria Dr (111), both North Rd S of Foster (4) **served ✓**; the MOTI Bypass absent by ruling; `78131841` North Rd N of Rochester **in the table, inactive, `end_time` 2026-09-12** — correctly not served, the feed still lists an ended record; **`78323174` Westwood St at Gordon Ave has no row at all** — not ingested, though GIS measured it 0.6 m outside with zone 68 at 1.9 m and its kiosk test kept all seven. Whether it left the feed after 20:39Z or a step in `d112cf37` drops it is with GIS to measure. Also: `RIDE-100086` has `street_name` NULL though DriveBC sends `roads[].name` — the card shows `--` for a road the feed named; with GIS. Log since the rebuild: WARNING summaries only, no ERROR |
| 2026-09-16 | **Regression fixed and the ruling built, `d112cf37`** (GIS; register row `33c36ee6`). **Cause, confirmed:** `ST_DWithin(x::geography, …, 100)` has no index to use and computes a geodesic distance against the whole boundary — **39,896 vertices** — for every geometry the sync tested, **9,596 per sync** (every Transnomis client plus DriveBC); cost grows with line length, points 36–50 ms, the worst LineString **19.5 s**. GIS owned that its own 600 s timeout earlier in the day was this regression, blamed on Tailscale without measuring. **Fix** (`closure_spatial.py`): `:47` `CLOSURE_PREFILTER_DEG = 0.01` (≈ 725 m of longitude at the boundary's north edge, 49.3512°, computed, so it always covers 100 m) and `CLOSURE_METRIC_SRID = 26910` (UTM 10N covers the city); `:100` `is_within_city` = `cb.geom && ST_Expand(g, 0.01)` (index-usable) then `ST_DWithin(ST_Transform(…, 26910), …, 100)` in metres; `:159` the zone fallback in the same form ordered by metric distance; `:73` `closure_city_bbox(db)` = `ST_Envelope(ST_Transform(ST_Expand(ST_Transform(ST_Union(geom), 26910), 100), 4326))`, rounded outward to 5 dp, from the table every call, `None` on failure. Admits the **same 85 geometries** as the geography form over the full set — exact, not approximate. **Timings, measured inside Postgres on the kiosk, one statement per record:** before #92 1.02 s for 9,596 (mean 0.107 ms, worst 8.6 ms); `eb90bcc7` stopped at 257 after 161 s (worst 19,484 ms); new form over the same 9,596 2.35 s; **new form plus both pre-filters, 87 geometries + the box query (53 ms): 0.82 s.** **DriveBC asked for the area** (`road_closure_service.py:38`, `:377`): exact request `https://api.open511.gov.bc.ca/events?format=json&status=ACTIVE&bbox=-122.89492%2C49.21840%2C-122.61970%2C49.35263` (today's box; it moves with the table), no `limit`, `pagination.next_url` followed with a repeated-URL guard; **no box → DriveBC not asked → the attempt is FAILED**, no unfiltered fallback. Measured live before building on it: **3 events, 5,096 bytes, 0.22 s, including RIDE-100086** — against 100 events, 233 KB and RIDE-100086 missing. `/areas` not compared; the bbox is sourced, measured and tighter. **Municipal 511 filtered by publisher** (`:523`, before any spatial query): the issue fields are consistent — City of Coquitlam is `Source` "City of Coquitlam", OrganizationId 2074, DivisionId 8096 (83 issues); BC MOTI Gateway is Source only, DivisionId 8099, which the feed's own DivisionNames calls "DriveBC" (303 issues). Per-client files not usable: all 386 sat in one hash-named file with four Vancouver Island towns, and whether that index stays stable cannot be told from one snapshot, so every file is still fetched and filtered by `Source`, the decoder consuming skipped issues' points (tested for alignment). **MOTI dropped — operator's ruling in the GIS chat, "Drop MOTI copies", after GIS measured the duplication:** 272 of 303 MOTI issues have a description identical to an active DriveBC event and **the Bypass MOTI record is verbatim RIDE-100086** (same text, start, point); keeping MOTI would draw each highway event twice and the copy lacks road state. Accepted risk, stated: 31 of 303 had no DriveBC match across two pulls 2 h 30 min apart, so a MOTI-only record would be lost. `:53` `MUNICIPAL511_PUBLISHERS = ("City of Coquitlam",)`. The Bypass therefore comes from DriveBC now, not Municipal 511. **Verified:** 59 passed + 25 subtests — the box computed from the table, strictly larger than the boundary on every side and holding all seven (kiosk, read-only); the DriveBC URL shape, pagination, no-box → FAILED, a Florida and a MOTI issue ahead of a City issue skipped with only the City geometry reaching a spatial test on the correct path (SQLite); the earlier 16 boundary tests still pass. Not live. **Falsifiers after the rebuild:** (1) a forced sync completes in seconds with the WARNING summary in the log; (2) `SELECT closure_id, zone_id, road_state FROM public.road_closures WHERE closure_id = 'drivebc.ca/RIDE-100086';` → one row, zone 52, ALL_LANES_OPEN, while it is active; (3) `SELECT count(*) FROM public.road_closures WHERE active AND source = 'BC MOTI Gateway';` → 0 |
| 2026-09-16 | **Operator ruled cause 1, and a principle: "Instead of checking every record against is it in the city, why not ask DriveBC what do you have in Coquitlam?"** Sent to GIS with the regression fix, one rebuild for both: DriveBC requested with `bbox` = the envelope of `public.city_boundary` buffered 100 m, computed from the table at sync time and never hardcoded, `status=ACTIVE`, no `limit`; the spatial tests stay as the second pass on the handful returned (a bbox is a rectangle, the city is not). The same principle for Municipal 511: measure whether the pull can be pre-filtered on the issuing organisation (City of Coquitlam + BC MOTI Gateway, MOTI still spatially tested) before any geometry query, which alone takes the sync from ~6,500 records to ~90. The per-record query must still be fast on its own. Register §2.1 row to say how each feed is asked |
| 2026-09-16 | **DriveBC half measured by GIS** (register `cbeb7a8c`): cause 1 is the sync's `limit=100` with no area filter, province-wide — the in-city event was not among the 100; cause 2 is the zone strip. Nothing earlier in the branch drops anything. Lead read BC's OpenAPI spec again: `bbox` is a documented `/events` parameter, so the sourced fix is to request the buffered city envelope. Production request change — the operator's to rule. Lead corrected its own citation of webcam ids as events |
| 2026-09-16 | **Deployed 23:31Z; regression found on the first forced sync.** The `POST /api/road-closures/sync` that took ~1 s all day ran past three minutes. `pg_stat_activity` showed one active query — `SELECT EXISTS (SELECT 1 FROM public.city_boundary cb WHERE ST_DWithin(cb.geom::geography, ST_SetSRID(ST_GeomFromGeoJSON('{"type": "LineString"…` — at 3.75 s of execution: one record's `is_within_city`. The sync runs it per record over the full Transnomis pull (~6,500) before the city filter, so a sync is now hours; the hourly tick queues behind it and #89 cannot show FAILED because the attempt never finishes. As far as the query text and timing show, `::geography` on the boundary polygon defeats the GiST index the old geometry `ST_Intersects` used. Fix and the before/after timings are GIS's; lead did not terminate the running query. The seven are **not** confirmed served |
| 2026-09-16 | **Measured and built, `eb90bcc7`** (GIS; register row `f524a07f` for the DriveBC pull). All seven within 100 m of the boundary (max 7.8) and of a zone (max 27.3), so built behind the operator's routing figure: `backend/api/closure_spatial.py` `CLOSURE_BOUNDARY_BUFFER_M = 100`, provenance comment says *reused, not newly ruled* (verified in `backend/scripts/export_routing_polygon.py`, "use the city boundary + 100m", 2026-09-09); `is_within_city` `ST_Intersects` → `ST_DWithin(geography, 100)`; `resolve_zones_and_hall` takes the nearest zone within 100 m when none intersects, else `([], None, None)`; `road_closure_service.py` both feed branches drop the `if not affected_zones: continue`, so a record inside the buffered city with no zone in reach is kept with `zoneId` null and the sidebar already groups that as OTHER — no frontend change. The §5 Tier 2 card is untouched (a different function, `ST_Covers`, unbuffered). **Found in passing:** `public.zones.hall_id` is NULL in all 134 zones, so the resolver's hall is always None and the kiosk groups by `unit_id` from `zones.json` instead — backlog line. Tests `backend/tests/test_closure_spatial_boundary.py`, read-only against the kiosk's live layers: the unbuffered tests drop each of the seven (pins the cause, so a boundary refresh that moves the line fails loudly), the buffered tests keep each in its measured zone, a point 150 m west of the boundary is still rejected, Metrotown is rejected; with the closure suites 54 passed + 25 subtests. Not live. **Falsifier after the rebuild and first sync:** `SELECT closure_id, zone_id FROM public.road_closures WHERE closure_id LIKE 'muni_4|78131841%' OR closure_id = 'drivebc.ca/RIDE-100086';` returns rows. GIS also corrected its briefing's method — the shrink box stopped at −122.65 where the boundary reaches −122.621; re-cut from the true extent, no records added, the 71 stands |
| 2026-09-16 | Lead's SELECT after the second-round deploy: **zero DriveBC rows in the table, ever.** Amendment sent to GIS: part (b) is not "any" but, as far as the table shows, "all" — measure each DriveBC event within ~2 km of the boundary and name why it fails, including anything earlier in the DriveBC branch than the two spatial tests |
