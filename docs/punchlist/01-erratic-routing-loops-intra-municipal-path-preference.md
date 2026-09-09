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

### Operator rulings, 2026-09-09, on the table above

> "We have some bollards, but those would be picked as a secondary route."
>
> "We can assume all fire vehicles can ignore the same rules, and for routing we can assume
> emergency response."
>
> "Fire lanes a car can definitely use, but not park."
>
> "One-way restrictions would be an operator choice at the time of driving, not offered."
>
> "We don't have weight or height restrictions in emergency responses."

What each one does to the profile, against the vendored text
([`../standards/osrm/car.lua`](../standards/osrm/car.lua)); nothing below is applied yet:

| Ruling | Consequence | `car.lua` line |
|:--|:--|:--|
| One rule set for every apparatus; emergency response assumed | **One profile, one graph.** No per-unit or per-mode variant, so the engine question closes on OSRM as it stands. `APPARATUS_TIERS` stays staged and unapplied (§6.4) | — |
| Bollards are not offered; a crew may choose one on the day | No change. Bollards stay impassable: `barrier_whitelist` does not list them and only `bollard=rising` is excepted in `process_node`. A "secondary route" through them is not built and is not planned here | 71–80 |
| Fire lanes are drivable | `service=emergency_access` becomes routable: drop `emergency_access` from `service_tag_forbidden`, and `emergency` and `emergency_vehicle` from `access_tag_blacklist`. 13 City ways, at service speed (15 km/h) with no extra penalty, like any other service road. The 9 footways and steps tagged `access=emergency` stay unroutable: they are not roads | 96, 103, 137–139, 184 |
| One-way is never offered | No change: `oneway_handling = true` | 35 |
| No weight or height limits on an emergency response | No change to the code, and no apparatus dimensions to enter. The car's 2.0 m / 2,000 kg check binds one City way (a 1.95 m `maxheight`) and nothing else; if that one matters it is a data question. Recorded as the operator's ruling, not a measurement | 54–59 |

**Still open, and the only thing that is**: the turn-restriction relations — no left, no
right, no U-turn, only straight (`use_turn_restrictions`, line 29, all or nothing at graph
build). Under lights and siren, does a crew make a posted no-left-turn? A posted no-U-turn? The
tag does not say whether the median is painted or concrete, so "ignore them all" drives through
concrete at some junctions and "obey them all" is today's behaviour. On dispatched routes:
`no_u_turn` on Dewdney Trunk Rd (relation 8151060), `no_left_turn` Genest Way → David Ave
(9239096), `no_right_turn` Pinetree Way → David Ave (6850061), `only_straight_on` on Chilko Dr
(17449481).

### Operator ruling, 2026-09-09, turn restrictions

> "Ignore turn restrictions, we make those turns under lights and siren."

Consequence: `use_turn_restrictions = false` (`car.lua` line 29). Every restriction relation
drops out at the next graph build — all 1,080 in the City, the 21 conditionals whatever their
current state, and relation 6812366 with them, so the Pinetree/Guildford lap disappears from
our routes; the upstream retag is still the right fix for everyone else's. What this does
**not** touch: one-way (line 35), barriers (`barrier_whitelist`, lines 71–80, and
`process_node`), access tags, and the turn costs — `u_turn_penalty = 20` s (line 27) and the
`turn_penalty` function (line 37) still price a U-turn or a sharp turn, so the router prefers
not to make one; it is no longer forbidden to.

**The profile's rule set is now fully specified.** Open is only the speed table (car.lua
lines 169–188, OSRM's own figures, not measured for this city or these vehicles), which is a
measurement, not a ruling.

Sequence from here: derive `apparatus.lua` from the vendored `car.lua` with each change cited
to a line above; rebuild the graph on the kiosk at an announced moment (the brief, *The kiosk,
shared with another agent*); route the corpus against the 2026-09-09 baseline with
`tools/route_corpus_baseline.py --baseline`; the operator sees every route that moved before
it goes live.

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
