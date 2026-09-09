# Punch list #1 — Erratic Routing Loops & Intra-Municipal Path Preference

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🧭 Routing Engine & Pathfinding Anomalies |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L36 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 2026-09-09 — reproduced on stock OSRM, at one junction, in the map data

`tools/route_corpus_baseline.py` routed the 571-call verified corpus from all four hall
aprons: 2,248 routes ([`../briefs/osrm_routing_agent.md`](../briefs/osrm_routing_agent.md),
*First hour — answered*). The geometry of 24 routes passes a node twice, and 22 of them are one
place:

* **Every Hall 1 route that turns west onto Guildford Way from Pinetree Way** loops 50 m around
  the four nodes of the junction box and leaves westbound through the node it arrived at — three
  left turns inside the intersection. Measured on Hall 1 → 1188 Condor Cres (DISP-2026-5610C6):
  geometry indices 37 and 41 are the same coordinate, 49.284914, −122.792503, OSM node
  12376791632, 700 m from the hall.
* **Why, from the extract** (pyosmium over `vancouver.osm.pbf` on the kiosk): OSM relation
  **6812366** is a `no_right_turn` from way 1419037313 (Pinetree Way southbound, 3 lanes,
  `turn:lanes=left|none|none|right`) via node 12376791632 to way 1419037312 (Guildford Way
  westbound). With the direct right turn forbidden, the cheapest legal path is around the box:
  ways 456389726 south, 390357953 east, 456385829 north, 461131152 west, then 1419037312. No
  slip lane from Pinetree southbound to Guildford westbound exists among the ways within 25 m of
  the node; a longer one was not looked for.
* **Not a profile matter.** The route is legal on the data; the data is the question. Either the
  restriction is wrong, or a channelised right-turn lane that carries the movement is missing or
  unroutable in OSM. Which it is, is a fact about the junction.

**Operator**: leaving Hall 1 southbound on Pinetree, do apparatus turn right onto westbound
Guildford at the light, or by a slip lane before it? The answer decides whether this is a
restriction to remove or a way to add — an upstream OSM data fix either way (CLAUDE.md §6.2),
and a new extract is one deliberate event shared with the basemap stream.

The other two repeated-node routes are 3100 Ozada Ave from Halls 1 and 4: the route turns around
in an unnamed way off Inlet St to come back along Ozada on the other side. Separately, 180 of the
2,248 routes carry a U-turn step: 135 in the last two steps, at an arrival point on one
carriageway of a divided road (Barnet, Lougheed, Guildford, Mariner); 19 in the first two steps
leaving Hall 2 up Mariner Way. Each is listed by dispatch id and hall in the baseline CSV and in
the `routing` row of `public.evaluation_history`; whether a crew drives them is the operator's
answer, not a setting.

The original report's own path, Hall 1 → 428 Nelson St, routes clean: 9.78 km, 15.1 min,
Pinetree → Barnet → Mariner → Como Lake → Linton → Austin → Nelson, no node twice, no U-turn.

---

## 1. Erratic Routing Loops & Intra-Municipal Path Preference
> **Status**: ⚠️ **Still open — re-examined 2026-09-09, above: one junction, in the map data.** Turn-by-turn
> routing functions, but the OSRM Lua profile arterial-vs-alleyway weighting has not been
> re-tuned. No new evidence was gathered this pass; the description below is as originally
> reported and the loops have **not** been re-observed since routing moved to stock OSRM.
> Re-confirm the behaviour still reproduces before spending time on profile tuning.
* **Incident / Path**: `1300 Pinetree Way` (Town Centre Fire Hall / Hall 1) $\rightarrow$ `428 Nelson St`.
* **Reported Behavior**:
  * The calculated apparatus route exhibits erratic pathing with unnatural loops, parking lot / back-alley cut-throughs, and unnecessary detours (see visual trace below).
  * The route leaves optimal arterial corridors and may exit municipal bounds unnecessarily.
* **Root Cause Investigation Needed**:
  * Inspect OSRM Lua emergency profile weighting (`osrm/profiles/emergency.lua` or local OSRM graph).
  * Check OSM road classification weights (e.g. `service`, `parking_aisle`, `residential` vs `primary`/`secondary`/`tertiary`).
  * Check snap distance / nearest-road snapping logic for origins and destinations near complex driveways or hall aprons.
  * Evaluate weighting penalty for crossing municipal boundaries: prioritize staying inside Coquitlam city limits on intra-city calls where possible.
* **Visual Reference Trace**:
  ```
  Origin: 1300 Pinetree Way (Hall 1 Apron)
  Target: 428 Nelson St
  Issue: Bizarre loops, erratic turns, sub-optimal road class snapping
  ```

---
