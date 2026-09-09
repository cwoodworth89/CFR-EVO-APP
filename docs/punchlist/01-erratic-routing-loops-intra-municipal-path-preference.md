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

### Measured, 2026-09-09: `apparatus.lua` against the baseline

[`backend/osrm/profiles/apparatus.lua`](../../backend/osrm/profiles/apparatus.lua) is the
vendored `car.lua` with the four hunks above, each citing its ruling
(`diff docs/standards/osrm/car.lua backend/osrm/profiles/apparatus.lua`). Built on the kiosk as
`apparatus.osrm` beside the served graph by
[`backend/scripts/build_osrm_graph.sh`](../../backend/scripts/build_osrm_graph.sh) (ten seconds
on this extract; `apparatus.build.txt` records the image digest, profile md5 and command) and
served on port 5001 by the container `cfr_osrm_trial`. The corpus was routed against it and
diffed against the stock baseline with `tools/route_corpus_baseline.py --baseline`; the second
`routing` row in `evaluation_history` (git `afa05f2`) is the record. **Not deployed.**

| | stock `car.lua` | `apparatus.lua` |
|:--|--:|--:|
| routes returned | 2,248 of 2,248 | 2,248 of 2,248 |
| routes that pass a node twice | 24 | **0** |
| routes with a U-turn step (from a hall that responded) | 180 (48) | 185 (44) |
| dispatched median | 2.39 km, 3.9 min | 2.39 km, 3.8 min |
| routes that moved | | 820 (216 from a hall that responded) |

What the 820 are:

* **562 are every Hall 2 route, and they are the fire-lane ruling at the hall's own door.** OSM
  maps Hall 2's apron as way 1271180042, `service=emergency_access` with `access=no`. The car
  profile could not use it, so every Hall 2 route began 9.6 m away on the nearest routable way;
  the apparatus profile departs from the apron itself onto Mariner Way (snap 0.6 m). 544 of the
  562 differ only in that first step, at +3.9 s.
* **The Pinetree/Guildford right turn.** With relation 6812366 no longer applied, 26 dispatched
  Hall 1 routes to Johnson St and Pacific St run Pinetree → Guildford instead of Pinetree → Glen
  Dr, and every lap of the junction box is gone.
* **The turnarounds.** 3100 Ozada Ave no longer turns around in a driveway off Inlet St (−48 s
  from Hall 1 and from Hall 4); 1163 Pinetree Way no longer circles Lincoln Ave (−27 s); 2986
  Guildford Way no longer detours by Town Centre Blvd (−26 s); 2601 Lougheed Hwy from Hall 3 no
  longer turns around by Colony Farm Rd (−21 s), and from Hall 2 −20 s. U-turns on Barnet Hwy
  and Lougheed Hwy move to the nearer break on 31 dispatched routes.
* **No fire lane beyond the hall is used.** A first check said the emergency access off Mary
  Hill Bypass (ways 640030541/3/5, 49.22623 −122.80855 to 49.22841 −122.80962) carried three
  routes to United Blvd; it did not. That check matched route coordinates against the lane's
  nodes, and the lane's first node is on the bypass itself, so a route driving past on the
  highway matched. The steps show the route leaving the bypass at the off-ramp 450 m west. The
  −43 s to 39 United Blvd is the U-turn on United Blvd moving from 374 m past the address to
  76 m past it. The Hall 2 apron above was checked the same way and is real: the trial route
  departs on the apron way for 10 m and turns onto Mariner Way. Corrected 2026-09-09, the same
  day, after the operator asked for the lane's coordinates.
* **Nothing got slower by more than 11 s.** Six routes to 3007 Glen Dr take the direct turn at
  Pinetree Way and Glen Dr instead of the slip lane they used before, 11 s slower by duration:
  OSRM chooses by weight, and a penalised way is cheap in time and dear in weight
  ([`../standards/dependency-behaviour.md`](../standards/dependency-behaviour.md), *routes are
  chosen by weight*). The remaining +4 s are the Hall 2 apron.

Duration change over the 820, in seconds: min −48, median +4, p90 +4, max +11. Distance: min
−1,996 m, median +9 m, max +88 m. The full list, largest change first with the road sequence
before and after, went to the operator on 2026-09-09 and is reproducible from the two recorded
rows.

### Operator rulings, 2026-09-09, on the two places above

> On the emergency access off Mary Hill Bypass (ways 640030541/3/5): "That's an emergency fire
> access to the Colony Farm psychiatric facility. We would never use that."
>
> On the Hall 2 apron way: "Yes, that's the end of the Hall 2 apron. Funny enough for the
> longest time the routing CAD software that E-Comm used refused to recognize the trucks could
> make a left turn there. So they were penalized heavily when they were determining the nearest
> unit, and heat mapping the city. I think it's been fixed or overwritten now."

The Colony Farm lane is on no route today, so nothing changes now; it is the first candidate
for a per-way exclusion if a route ever reaches for it. The Hall 2 apron departure is confirmed
as the truck leaving from its own door, and the E-Comm history is the same defect on the other
system: a rule at one node penalising a whole hall.

**To deploy**, at a moment the operator picks (restarting `osrm` drops routing on every kiosk for
the seconds the graph takes to load): in `docker-compose.yml` the `osrm` command's
`/data/vancouver.osrm` becomes `/data/apparatus.osrm`; `git pull` on the kiosk; `docker compose
up -d osrm`; then one route on port 5000 and one on the kiosk. `vancouver.osrm.*` stays on disk
as the rollback, the same edit reversed. Remove `cfr_osrm_trial` afterwards. Until then the trial
container keeps running on 5001 and nothing a crew sees has changed.

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
