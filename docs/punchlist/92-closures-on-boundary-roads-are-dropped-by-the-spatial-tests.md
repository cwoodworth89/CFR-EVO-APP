# Punch list #92 — Closures the City files on its own boundary roads are dropped by the spatial tests

| | |
|:--|:--|
| **Status** | OPEN — found 2026-09-16 by the operator reading the Municipal 511 review list; with `gis-spatial-engineer` to measure, then fix |
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

## What it should do

A closure the City files on a road inside or along Coquitlam is shown, grouped under the
nearest hall. The boundary test tolerates the boundary; the zone test supplies grouping and
does not filter.

## What decides the fix

- **The buffer figure.** The routing profile already buffers `public.city_boundary` by **100 m**
  on an operator figure (2026-09-09, `apparatus.lua`). If all seven fall within 100 m of the
  boundary and of a zone, the fix reuses that figure and says so; if any does not, the figure is
  the operator's to set, not GIS's.
- **Neighbours' records.** A buffered boundary also admits closures Burnaby, Port Coquitlam or
  Port Moody file on the same shared roads. Whether crews should see those is a domain call
  the operator has not made; GIS reports the count and the labels.

## Falsifier

After the fix, the seven feed ids above are in `public.road_closures`, active, each with a
zone or grouped as OTHER, and the kiosk serves them. Before it, `SELECT count(*) FROM
public.road_closures WHERE closure_id IN (...)` is 0.

## Log

| Date | Event |
|:--|:--|
| 2026-09-16 | Found by the operator in the #91 review list. Opened as crew-visible. Sent to `gis-spatial-engineer`: measure each record's position against the boundary and the nearest zone and name the cause, then fix behind the existing 100 m figure only if every record falls inside it; report the neighbour-municipality count and any DriveBC events the same tests drop |
