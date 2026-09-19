# Punch list #96 — A junction on a zone line carries one map grid, so the announced grid filters it out or flags it

| | |
|:--|:--|
| **Status** | BUILT `92ed4aa0` (GIS, 2026-09-19), pushed; **needs a `cfr-agent` restart only** (the resolver and its junction cache live in the agent; `backend/api` never imports the geocoder). Not deployed; held for the operator's bundle after lead's checkpoint audit. 0 losses on the geocode harness, 6 gains, 0 automatic resolutions turned into selectors |
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
| 2026-09-19 | **Built, `92ed4aa0`.** GIS re-measured first: 584 within 1 m of 2+ zones, **610 within 5 m**, 4 with no zone within 5 m; David & Genest `zone_for_point` 86, within 5 m {86, 88}. **Change:** `geocoder.py:32` `ZONE_TOUCH_M = 5.0` citing the `zone_for_point` migration's edge tolerance; `:35` box prefilter; `:100` the loader adds `zone_ids` (index `&&` then `ST_DWithin` in UTM 10N, the #92 form); `:112` each candidate carries `grids`, `grid` unchanged. `intersection_resolver.py:370` `_narrow_by_grid`: `:409` filter by touch (announced ∈ grids ∪ {grid}), `:413` rank by containment (prefer `grid` == announced). No match still returns the candidates with the note; x-street cascade still first; the dispatch's derived grid untouched. **Lead's rank confirmed by measurement, the alternative rejected:** over all 80 multi-junction pairs × every grid their junctions touch — rank by `zone_for_point` (built): **18 outcomes change, all from the false note; 10 become automatic, 8 become a selector without the note, 0 automatic → selector.** Rank by "no other zone within 5 m" (GIS's first idea): 35 changes, **12 regressions** (Cypress & Foster, Aberdeen & Lansdowne, King Albert & Poirier, Lorraine & Mundy, Foster & Macintosh, Rochester & Walker, Marmont & Rochester — both junctions on one line, `zone_for_point` is what separates them today). The 18: → automatic: Foster & Robinson 5, 9; Holly & Oak 57; Lansdowne & Steeple 72; Lougheed & Westwood 60; Lougheed & Woolridge 30; Paddock & Plateau 92, 93; Pasture Circle & Spuraway 60, 62; Rochester & Walker 11. → selector, note gone: Burnside & Eagleridge 70; Daybreak & Lazy A 62; Foster & Robinson 8; Highway #1 & King Edward 29; Kugler & Mundy 46; Marmont & Quadling 27; Marmont & Rochester 17. Unchanged by design: the shared-grid pairs lead named, and every single-zone double crossing. **Backtests:** `backtest_parser_corpus.py` unchanged (145 → 145 address wrong) — it replays the parser and its address column never reaches the resolver, so it cannot see this; **`tools/trace_geocode_corpus.py`, the harness that does: 642 calls, 6 gains, 0 losses, every accuracy bucket identical, ambiguous replays 14 → 8** — `A018E9` and `448E74` (David & Genest, exact), `014B79`, `A3C887`, `8B7476`, `21E6F9` (cosmetic). `harness_chain.py --skip-stt` not run. **Tests:** `backend/tests/test_intersection_grid_touch.py`, 7 on the kiosk's measured shapes; with the orchestrator suite 25 passed (`PYTHONPATH=services/gis/src;backend`). **Found, not fixed — backlogged:** `GRID_MISMATCH` (`review_flags.py:131`) still compares the announced grid with phase 1's single `derived_map_grid`, so A018E9 (88 announced, 86 published) would still raise it; same root cause, out of this job's scope by lead's instruction |
| 2026-09-19 | **Checkpoint audit (lead, Fable) raised the loader's per-row `ST_Transform` as a startup cost; GIS measured and the premise did not hold.** `EXPLAIN ANALYZE` on the kiosk, full loader over 1,994 junctions, two runs: pre-#96 0.52 / 0.48 s; **`92ed4aa0` 0.62 / 0.61 s (+0.1 s)**; zones transformed once in a CTE 0.89 / 0.83 s; geography `ST_DWithin` 0.93 / 0.94 s. The `&&` box passes only the one to three zones touching each junction, so the per-row transform runs on a handful of polygons. All three forms give identical sets on all 1,994 rows. Left as built, no commit. Round trip and the Python cache build not timed, same before and after |
