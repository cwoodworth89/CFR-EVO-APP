# Punch list #96 — A junction on a zone line carries one map grid, so the announced grid filters it out or flags it

| | |
|:--|:--|
| **Status** | APPROVED by the operator 2026-09-19 ("Yeah approved"), sent to `gis-spatial-engineer` the same day. Not built |
| **Severity** | 🔴 crew-visible on the two-crossings case (a candidate selector on a call the CAD had already resolved); a false `LOCATION_SUBSTITUTED` flag in review otherwise |
| **Area** | 🗺️ GIS · intersection resolver |
| **Origin** | #95's re-parse of `DISP-2026-A018E9` (David Ave & Genest Way, grid 88): the geocoder wrote "none of these junctions lie in map grid 88. Select the correct one." on a correctly placed call |
| **Related** | #95 · `docs/standards/dependency-behaviour.md` (`ST_Contains` excludes the boundary — the earlier form of the same fact) · `backend/migrations/2026-08-22_canonical_zone_for_point.sql` (fixed the *lookup* returning NULL on a boundary; this item is the *comparison* that still assumes one grid) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

Zone polygons are bounded by roads, so a junction on a road that is a zone line lies in two
zones. **Measured 2026-09-19: 584 of the 1,994 derived junctions (29 %) are within 1 m of two
or more zones.** A junction candidate carries one `grid`, from `public.zone_for_point`, which
picks one zone (David & Genest: 86 — it is a hair inside 86 at floating precision; `ST_Covers`
agrees; zone 88 is at 0 m). `_narrow_by_grid`
(`services/gis/src/gis_service/intersection_resolver.py:370`) keeps the candidates whose one
grid equals the announced grid. On the line, that is a coin toss against the CAD.

- **One junction for the pair** (A018E9): nothing matches, the candidates are returned
  unchanged with the note, and the call is placed correctly — but flagged `LOCATION_SUBSTITUTED`
  with "Select the correct one." A false flag, review time.
- **Two junctions for the pair** (a street meeting another twice): if the right one is on a
  line and the lookup picked the other side, the grid cannot narrow, and the crew gets the
  candidate selector for a call the CAD had resolved. That is the crew-visible case.

## The fix (as sent)

A candidate carries **every zone within 5 m** (the tolerance `zone_for_point` already uses for
slivers), and the announced grid matches if it is any of them. Recommended shape: **filter by
touch, rank by containment** — keep every candidate whose zone set holds the grid; if more than
one remains, prefer the one strictly inside the announced grid over one that only touches it.
No schema change, no curated grids; the CAD's grid stays the authority.

## What it could break — measured before sending (the operator's question)

The only way a wider match can hurt is a double crossing where the wrong junction now also
touches the announced grid: an automatic resolution becomes a selector. It can never place a
call wrongly — a false match adds a choice, not a pin. Counted: **80 street pairs have two or
more junctions; 74 of those already share a zone** (both inside the same one, e.g. Baker Dr &
Sumpter Dr, both 40 — the grid never told them apart, nothing changes); **about a dozen overlap
only by a boundary** (Briarcliffe & Lansdowne 72 vs 71/72; Cape Horn & United 47/49 vs 49;
Holly & Oak 55 vs 55/57; Lansdowne & Steeple 71 vs 71/72; Pasture Circle & Spuraway 58 vs
58/60/62; Paddock & Plateau 92/93/94 vs 94; Rochester & Walker 10/12 vs 10/11/12; Marmont &
Rochester; Foster & Robinson; Highway Ramp & United ×3). Those are where a plain touch-filter
would add a selector; the containment rank keeps them automatic. GIS is to enumerate that set
from the code, before and after, and run the parser backtest: the address column must not lose
a call.

## Log

| Date | Event |
|:--|:--|
| 2026-09-19 | Found via #95; measured 584/1,994 and the 80/74/~12 double-crossing counts; the operator approved and asked what it could break; sent to GIS with the falsifier and the backtest requirement |
