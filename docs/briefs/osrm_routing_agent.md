# Brief: OSRM routing development

**For a fresh agent, written 2026-09-08.** Read `CLAUDE.md` first, then
[`../review_status_handoff.md`](../review_status_handoff.md). This brief is the scope, the
starting facts, the rules of the road on the shared kiosk, and the boundary with the other
stream running at the same time ([`vector_basemap_agent.md`](vector_basemap_agent.md)).

## What this stream is for

Routing today is **stock OSRM** on the OSM extract, deliberately reset to basics on
2026-08-30 after an invented "apparatus physics" model steered it wrong (standards index,
the two CAUTION blocks). It works: ETAs come from OSRM's own `distance` and `duration`, the
route line is OSRM's geometry, and the operator has not seen a bad route since. The work now
is to make routing **right for fire apparatus and right for this city**, on evidence:

1. **Reproduce before tuning.** Punch-list #1 (loops, alley cut-throughs) has never been
   re-observed since stock OSRM. First job: the operator names a call with a bad route, or
   the item is closed as not reproducible. `tools/verify_snapping_corpus.py` and the
   `routing_metrics` stored on every dispatch are the corpus to measure against.
2. **The profile, with its source held.** `osrm-backend` ships `profiles/car.lua`; the
   installed image's copy is the authoritative text (CLAUDE.md §7.3a). Any change to how
   roads are weighted for an engine or a ladder cites the line it changes and the reason
   from the operator or a measurement. The standards index row *Apparatus routing profile*
   is NOT HELD until that text is vendored under `docs/standards/`.
3. **Operator designs waiting** (`../post_freeze_backlog.md`): every responding hall's route
   on one map in hall colours; hydrants along the route are already built on the frontend
   from the route geometry and need nothing from this stream unless the geometry changes.
4. **Arrival points.** The resolver sends OSRM the operator-verified arrival point when one
   exists (`entrance → front → centroid`). Snapping the destination to the road that the
   address names, not the nearest road, is the open question from
   [`../briefings/addressed_street_snapping_decision.md`](../briefings/addressed_street_snapping_decision.md).

## Where things are

| | |
|:--|:--|
| Container | `osrm` in `docker-compose.yml` (`ghcr.io/project-osrm/osrm-backend` pinned by digest, `osrm-routed --algorithm mld /data/apparatus.osrm` since 2026-09-09; `vancouver.osrm` is the stock graph kept for rollback), port 5000 |
| Data | kiosk `backend/data/osrm/`: `vancouver.osm.pbf` (a BBBike extract, map data of 2026-08-07, file of 2026-08-14, git-ignored) and the `.osrm` graph built from it by OSRM v26.8.0 with the stock `car.lua` — answered 2026-09-08, below |
| Profile | `backend/osrm/profiles/apparatus.lua`, the vendored `car.lua` (`docs/standards/osrm/`) with the operator's rulings, each hunk cited; `backend/scripts/build_osrm_graph.sh` builds a graph beside the served one and records what built it |
| Service code | `services/gis/src/gis_service/routing_engine.py` (OSRM client, hall apron departure, staged `APPARATUS_TIERS` — staged, not applied, §6.4) |
| API | `backend/api/routers/routing.py`; the frontend's `RoutingOverlay.jsx` calls `/api/route` |
| Frontend | `frontend/src/components/RoutingOverlay.jsx`, `frontend/src/utils/EVORoutingEngine.js` (ETAs per unit from OSRM metrics), the kiosk's `RouteOverviewPanel.jsx` and the workstation's `DispatchTargetLayer.jsx` consume the route |
| Halls | `frontend/src/components/MapConstants.js` `STATIONS`; the hall apron coordinates in `routing_engine.py` |
| Skill | `.claude/skills/emergency-routing-engine/SKILL.md` |

## Rules that bind this stream

* **§6.2**: OSRM's distance and duration are the answer. No speed × distance estimates, no
  turn-count guesses, no re-derived ETAs.
* **§6.3 / §7**: every weight, penalty or speed carries its source. If the source does not
  exist in the project, stop and raise it with the operator; do not improvise a default.
* **§6.5**: test with real dispatches (review replay), never fabricated calls.
* **Measure before deploying** a profile change: the same corpus routed before and after,
  distance and duration per call, the ones that changed listed by dispatch id, and the
  operator shown the routes that moved. A profile change that moves routes the operator
  did not ask to move is a regression until they say otherwise.
* **The OSM extract is shared** with the basemap stream. Do not replace or re-download it
  without telling the other agent and the operator; a newer extract changes both the
  routing graph and the tiles at once, and that should be one deliberate event. Measured
  2026-09-09 by both streams: the graph rebuilds in 10 s (`backend/scripts/build_osrm_graph.sh`),
  the vector tiles in about 55 s plus a tile-server restart. The basemap stream works from its
  own copy of the extract under `/home/tcfire/basemap-trial/` and its trial containers on
  8082–8084; routing's trial router is `cfr_osrm_trial` on 5001. Once the vector layer is live
  under `cfr_tiles`, an extract swap needs both rebuilt in the same window.

## The kiosk, shared with another agent

* Deploy by `git pull` on the kiosk. **Never restart `cfr-agent`**; the operator picks the
  moment (`tools/kiosk_capture_state.sh` first, always).
* An OSRM graph rebuild (`osrm-extract` / `osrm-partition` / `osrm-customize`) is minutes
  of all cores and a container restart on port 5000. Announce it, do it when no capture is
  running, and never while the basemap stream is generating tiles.
* Restarting the `osrm` container drops routing for every kiosk for the duration; the API
  returns no route and the kiosk shows no ETA rather than a guess. Short, and announced.

## Working in parallel

* Own branch and worktree: `git worktree add ../CFR-EVO-APP-routing -b routing` from
  `main`. Stage by name, never `git add -A`; another session may be committing.
* Files this stream owns: the `osrm` compose service, `backend/data/osrm/` (with the caveat
  above), `routing_engine.py`, `routing.py`, `RoutingOverlay.jsx`, `EVORoutingEngine.js`,
  the routing skill. Files it must not touch: `MapLayers.jsx`, `MapSurface.jsx`,
  `MapConstants.js` `BASE_LAYERS`, the tile server, the crawl and compile scripts.
* Merge to `main` when a change is measured and the operator has seen it; small merges,
  often. Pull `main` into the branch daily; the basemap stream's merges do not touch the
  files above.

## First hour — answered 2026-09-08

1. **The profile.** The graph was built by OSRM **v26.8.0** (the fingerprint inside
   `vancouver.osrm.properties`), the version in the image the kiosk runs
   (`ghcr.io/project-osrm/osrm-backend@sha256:3ac496ff…`, created 2026-08-01), with the **stock
   `car.lua` shipped in that image**, unmodified as far as the evidence reaches. The text is
   vendored with its md5 sums, the evidence, and what it does not prove, at
   [`../standards/osrm/README.md`](../standards/osrm/README.md); the standards index row is
   HELD as text and still NOT HELD as a fire-apparatus authority. No build command was recorded
   anywhere and the build container is gone. The extract is a BBBike custom extract whose
   header says the map data is from **2026-08-07T23:00Z**; the file is dated 2026-08-14.
2. **The baseline** is `tools/route_corpus_baseline.py`: every verified dispatch, the arrival
   point resolved as production resolves it, routed from all four hall aprons with production's
   query; `--json` before, `--baseline` after, `--record` as the `routing` stage. Recorded
   2026-09-09 as the `routing` row labelled *stock car.lua, osrm v26.8.0, extract 2026-08-14*
   (`tools/harness_history.py --stage routing`): **571 calls, 562 placed, 9 unresolved,
   2,248 of 2,248 routes returned; the dispatched routes' median is 2.39 km / 3.9 min.** Per
   hall, median and p90: Hall 1 2.24 / 4.30 km, Hall 2 3.74 / 6.62 km, Hall 3 8.58 / 11.51 km,
   Hall 4 5.52 / 6.88 km. Two things the geometry reports, for the operator to rule on before
   anyone touches the profile:
   * **24 routes pass a node twice.** 22 of them are the same place: every Hall 1 route that
     turns west onto Guildford Way from Pinetree Way loops 50 m around the four nodes of that
     junction and leaves through the node it entered, because OSM relation 6812366 forbids the
     right turn there (`no_right_turn`, Pinetree southbound → Guildford westbound via node
     12376791632). One junction, in the map data, not the profile; the evidence and the question
     for the operator are in punch-list #1. The other two are 3100 Ozada Ave from Halls 1 and 4:
     the route turns around in an unnamed way off Inlet St to come back along Ozada on the
     other side.
   * **180 routes carry a U-turn step** (48 of them from a hall that responded). 135 are in
     the last two steps: the arrival point sits on one carriageway of a divided road (Barnet,
     Lougheed, Guildford, Mariner) and OSRM turns at the next break to be on it. 20 are in the
     first two steps, 19 of them Hall 2, which drives up Mariner Way and turns back. Whether a
     crew does either is the operator's answer; neither is a profile setting.
3. **Punch-list #1's named path**, Hall 1 apron → 428 Nelson St front point, routed
   2026-09-08 on the kiosk: 9.78 km, 15.1 min, Pinewood Ave → Pinetree Way → Barnet Hwy →
   Mariner Way → Como Lake Ave → Linton St → Austin Ave → Nelson St; no node passed twice, no
   U-turn step. The loops the item describes are not on that path; the one place they are is
   the Pinetree/Guildford junction above. The operator ruled on it the same day: the sign is
   no right on red, the relation is mistagged, and the fix is upstream in OSM. Their rulings
   on what the profile may change are quoted in punch-list #1, turn restrictions included
   (ignored: the turns are made under lights and siren). `backend/osrm/profiles/apparatus.lua`
   is that rule set on the vendored `car.lua`, built beside the served graph by
   `backend/scripts/build_osrm_graph.sh` and **measured 2026-09-09 against the baseline: 820 of
   2,248 routes moved, 562 of them the Hall 2 apron (a fire lane in OSM), all 24 loops gone,
   nothing slower by more than 11 s** — the second `routing` row, and the table in punch-list
   #1. **Deployed 2026-09-09 12:30 PDT** on the operator's word: `cfr_osrm` serves
   `apparatus.osrm`, image pinned by digest, the stock graph on disk as the rollback. The speed
   table is the one thing still unsourced. The item closes on the operator's word, or stays
   open on any dispatch id they name with a route they would not drive.

## First hour, as originally written

1. On the kiosk: `docker exec cfr_osrm ls /data`, the `.osrm.timestamp`, and which profile
   built it (the `.osrm.properties` file records it). Write the answer into this brief.
2. Route the verified corpus once as the baseline: every dispatch with a verified address,
   hall → arrival point, distance and duration into a CSV under the scratchpad, and a row in
   `public.evaluation_history` if the harness fits, so there is a "before".
3. Ask the operator for one bad route, by dispatch id, or close #1.

<!-- audit-ok: backend/data/osrm/vancouver.osm.pbf -- git-ignored, kiosk only -->
<!-- audit-ok: backend/data/osrm/ -- git-ignored, kiosk only -->
<!-- audit-ok: backend/data/tiles/ -- git-ignored, kiosk only -->
