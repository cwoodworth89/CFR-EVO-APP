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

### Operator ruling, 2026-09-09

> "No rights on red, but you're allowed to make a right."

So relation 6812366 is mistagged. The sign is *no right turn on red*, whose OSM tag is
`no_right_turn_on_red`, and OSRM v26.8.0 **ignores every restriction value ending `_on_red`**
(`RestrictionParser::TryParse` at the pinned tag, recorded in
[`../standards/dependency-behaviour.md`](../standards/dependency-behaviour.md)). Retagging the
relation upstream removes the loop at the next extract with no profile change. Until then the
kiosk draws the loop on every westbound Hall 1 response.

The operator's framing, and the question it leaves: some restrictions are physical (islands,
barriers) and bind an apparatus; some are legal and an apparatus responding emergency may set
aside (a right on red); some are legal and still not to be broken (the wrong way on Highway 1).
What the router is applying inside the City box (49.20–49.39, −122.92 … −122.70), read from
the extract on 2026-09-09:

| Layer | In the City | What `car.lua` does with it | The apparatus question |
|:--|:--|:--|:--|
| Physical: a divided road is two one-way ways; no connecting way, no turn | 4,294 one-way ways of 49,344 highway ways | geometry — no setting involved | none; a median is a median |
| Physical: barrier nodes | 707 gates, 707 bollards (155 `removable`, 45 `fixed`, 365 untagged), 26 jersey barriers, 14 height restrictors | bollard, block, jersey barrier: impassable; gate: 60 s; only `bollard=rising` is excepted, `removable` is not (car.lua `process_node`) | which bollards a crew drops or holds a key for |
| Legal: turn-restriction relations | 1,080 — 381 no left, 230 no right, 209 no U-turn, 141 only straight, 58 only right, 23 only left, 16 no straight; 21 conditional (weekday peaks); 22 `except` (psv, bicycle, bus, hgv, police, staff — none `emergency`); 30 `implicit` | all applied to the car, except where `except` names motorcar / motor_vehicle / vehicle; `_on_red` values ignored; conditionals only if the graph was built parsing them (unknown) | which classes an apparatus sets aside under lights and siren, and which never. A `no_u_turn` across a painted median and one at a concrete median carry the same tag |
| Legal: access on ways | 2,003 private, 1,411 `access=no`, 257 customers, 20 destination, 18 delivery, 16 permit; 22 emergency-only (13 `service=emergency_access`, 9 footway/steps) | private, customers, delivery, destination, permit: routable with a penalty; `access=no` and the emergency-only ways: unroutable | the fire lanes (`emergency_access`) are exactly the ways an apparatus may use and a car may not |
| Legal: one-way | 4,294 ways | never driven against | none proposed — the operator's Highway 1 rule |
| Dimensions | 114 ways carry `maxheight` (75 `default`; the rest 1.95 m to 8.4 m, six of them under 4.6 m); 1 `maxweight` (Gaglardi Way, 15 t) | compared with a 2.0 m, 1.9 m, 4.8 m, 2,000 kg car, so nothing is ever too low or too light | the one place the car profile is *too permissive*: a ladder's height and weight are the operator's to supply (CLAUDE.md §7.2) |

Also found: relation 17957326 has its time window written into the plain `restriction` tag
(`no_right_turn @ (Mo-Fr 07:00-09:00,16:00-18:00)`, via 49.25084, −122.86907); the value starts
with `no_`, so OSRM applies it all day. A second upstream retag.

**Operator**: of the legal classes above, which does an apparatus set aside on an emergency
response, and which never? That list is the specification the profile work has been missing;
nothing in `car.lua` moves until it exists (§7.2). The right-on-red case needs no ruling: it is
a mapping error, and the fix is in OSM.

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
