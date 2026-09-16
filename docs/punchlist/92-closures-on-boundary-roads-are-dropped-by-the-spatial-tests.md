# Punch list #92 — Closures the City files on its own boundary roads are dropped by the spatial tests

| | |
|:--|:--|
| **Status** | BUILT `eb90bcc7` (register row `f524a07f`), **not deployed — one more `--build api`, no migration.** Every record measured; fix behind the operator's existing 100 m figure, reused not newly ruled. Falsifier below runs after the first post-rebuild sync |
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

## The DriveBC half, measured — lead's hypothesis was mostly wrong

One request to the live feed (operator's permission in the GIS chat, registered): 286 active
events, **only two anywhere near Coquitlam.** `RIDE-100086`, Highway 7B — the Mary Hill Bypass —
at 49.22697, −122.80629, the same spot as the MOTI record, `ALL_LANES_OPEN` BOTH: the old tests
dropped it (inside, no zone); the fix keeps it in zone 52 as informational. `RIDE-101452`,
Highway 7, is 3.45 km outside the city and stays out. Nothing on the Lougheed or Barnet in this
pull. So the table's "no DriveBC row ever" is mostly because DriveBC rarely has an event inside
Coquitlam — **not** the systemic drop lead suggested — but the one event that was inside was
dropped, by the same cause as the seven.

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
| 2026-09-16 | **Measured and built, `eb90bcc7`** (GIS; register row `f524a07f` for the DriveBC pull). All seven within 100 m of the boundary (max 7.8) and of a zone (max 27.3), so built behind the operator's routing figure: `backend/api/closure_spatial.py` `CLOSURE_BOUNDARY_BUFFER_M = 100`, provenance comment says *reused, not newly ruled* (verified in `backend/scripts/export_routing_polygon.py`, "use the city boundary + 100m", 2026-09-09); `is_within_city` `ST_Intersects` → `ST_DWithin(geography, 100)`; `resolve_zones_and_hall` takes the nearest zone within 100 m when none intersects, else `([], None, None)`; `road_closure_service.py` both feed branches drop the `if not affected_zones: continue`, so a record inside the buffered city with no zone in reach is kept with `zoneId` null and the sidebar already groups that as OTHER — no frontend change. The §5 Tier 2 card is untouched (a different function, `ST_Covers`, unbuffered). **Found in passing:** `public.zones.hall_id` is NULL in all 134 zones, so the resolver's hall is always None and the kiosk groups by `unit_id` from `zones.json` instead — backlog line. Tests `backend/tests/test_closure_spatial_boundary.py`, read-only against the kiosk's live layers: the unbuffered tests drop each of the seven (pins the cause, so a boundary refresh that moves the line fails loudly), the buffered tests keep each in its measured zone, a point 150 m west of the boundary is still rejected, Metrotown is rejected; with the closure suites 54 passed + 25 subtests. Not live. **Falsifier after the rebuild and first sync:** `SELECT closure_id, zone_id FROM public.road_closures WHERE closure_id LIKE 'muni_4|78131841%' OR closure_id = 'drivebc.ca/RIDE-100086';` returns rows. GIS also corrected its briefing's method — the shrink box stopped at −122.65 where the boundary reaches −122.621; re-cut from the true extent, no records added, the 71 stands |
| 2026-09-16 | Lead's SELECT after the second-round deploy: **zero DriveBC rows in the table, ever.** Amendment sent to GIS: part (b) is not "any" but, as far as the table shows, "all" — measure each DriveBC event within ~2 km of the boundary and name why it fails, including anything earlier in the DriveBC branch than the two spatial tests |
