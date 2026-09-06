# Progressive dispatch: the kiosk fills in as the announcement is heard, and the phones are told when a driver can act

**Status:** design for post-freeze development, set down 2026-09-05 from the operator's
description. Not built. More design to come; the rulings below are settled, the open questions
are listed, and the measurement that should shape the build is named.

**Operator, 2026-09-05:** *"Push the ntfy with units, call type, address plus subaddress,
calculated map grid. Phase 2 publishes additional details and corrections; ntfy only fires
again if needed. Populate the kiosk as info is confirmed: tones detected, pop up the screen in
dispatch mode and fill in the units list as it's heard, then the call type, then the address
and subaddress with all the routing and mapping plus the calculated map grid, then cross
streets, talk group, map grid confirmation."*

## Why

Phase 1 today is one shot (`backend/cfr_dispatch/pipeline/phase1.py`). From 10 seconds into
the capture, and every 3 seconds after, the worker transcribes everything recorded so far and
asks one question: units, a call type, something address-shaped, and a grid or the units
repeated? The first chunk that passes is published as the preliminary payload, once. Publishing
is three things at the same moment: the record is written through the API, an MQTT INSERT
tells the kiosk to draw it, and the ntfy push goes to phones. Phase 1 never runs again for that
call. Phase 2 runs on the whole recording at the end of capture (silence or 75 s), corrects the
record and sends an MQTT UPDATE, which the kiosk redraws from. Phase 2 does not push to ntfy.
It did once; the operator's recollection is that the corrections were not done properly, and
the path was removed.

Measured on 507 recordings replayed in the listener's own chunks (`tools/harness_phase1.py`,
2026-09-05, punch list #72):

- Phase 1 fires at 16 s on 179 calls and 19 s on 164. A single-unit medical call has ten words
  before the street; a call with four or more units has seventeen, twenty-two on the slowest
  tenth. So the longest unit lists, the most serious calls, are the ones most often published
  before the street has been spoken: 14 % of multi-unit calls against 8 % of single-unit ones,
  and the single-unit misses are mostly mishearings, not timing.
- What went to the phones on those: a six-unit report of smoke published at 22 s with the
  address *"Response Coquitlam"* (verified 712 Townley St); another six-unit call at 25 s with
  *"Coquitlam"* (1054 Dansey Ave); three-unit alarm calls with *"18"*, *"29506"* and
  *"Bycoquitlam"*.
- The grid in the chunk was the model's completion on 314 of 448 calls. Closed the same day by
  publishing the placed parcel's own zone instead (#72); that is the "calculated map grid"
  below.

A flat 30-second minimum would fix the multi-unit case at the cost of 11 to 14 seconds on
every routine call, most of which already have the address at 16 s. The design below keeps the
early signal and holds only what is not yet real.

## The layers

Each layer is one MQTT event and one API write. The kiosk redraws what changed; everything not
yet heard renders as unknown, the way it already does for a missing location (CLAUDE.md §5,
§6.1).

| Layer | Trigger | What goes out |
|:--|:--|:--|
| 0. Tones confirmed | DSP, before any transcription | INSERT: `dispatch_id`, tone, time, `status: capturing`. The kiosk pops to dispatch mode with every field unknown. |
| 1. Units | each chunk that hears more | the list as heard so far, marked *still listening* |
| 2. Call type | the first chunk that parses one | |
| 3. Address and subaddress | the first chunk where the address resolves to a parcel or an intersection (the location gate, rule A in #72) | pin, parcel outline, routing and ETAs, the calculated map grid marked *from address* |
| 4. Near roads, talk group | as parsed | |
| 5. Grid confirmation | phase 2, the spoken grid from the full recording | replaces the calculated grid; `GRID_MISMATCH` when they differ (built, #72) |
| 6. Audio and corrections | phase 2 | final UPDATE with the recording, verification, review flags |

**ntfy** fires once, at the first moment layers 1, 2 and 3 are all present: units, call type,
address with subaddress, calculated map grid. That is what a driver needs: the units say who is
going, the address says where, and the grid names the laminated map to grab. It fires again
only when phase 2 changes the address, the units or the call type, and says so in the message.

## Rulings, 2026-09-05

1. **No resolvable address by the end of phase 2:** the push goes anyway, with the location as
   *unknown* and the words *check runsheet*. A call the crew does not know about is worse than
   one with an unknown location.
2. **Intersections:** they sit on zone lines by construction, so a single containing zone is a
   coin toss (611 of the 1,995 junctions in `public.intersections` touch two or more zones
   within 5 m). Precompute the zone set per junction at extraction time and carry it on the
   row; the calculated grid for an intersection call is that set ("82 or 83"), confirmed to one
   by the spoken grid at phase 2. Never one zone picked by sort order.
3. **Units as heard** may change between chunks as the model re-hears earlier words; a unit
   that appears and then disappears is acceptable while the list is marked *still listening*.
   Phase 2's list is final.
4. **Calculated grid for a parcel** is the parcel's own zone (`public.parcels.zone_id`), which
   agrees with the announced grid on 96.3 % of exact placements (#72). It is labelled, never
   presented as the announced grid.

## What has to change

- **Phase 1 becomes a per-call state machine.** It keeps a record of what it has published
  and, on each chunk, publishes only the layers that became available or changed. The phase-1
  session store (`PostgresSessionStore`) already holds the phase-1 result for phase 2's
  comparison; it grows to hold the layer state. The one-shot `is_round_1_complete_check`
  becomes the ntfy gate, redefined as units + call type + solid address + grid.
- **The tones INSERT** needs a `status` the kiosk understands (`capturing`, `preliminary`,
  `final`) and a listener that can publish before the worker has transcribed anything.
- **The kiosk** needs dispatch mode on an INSERT with empty fields, a *still listening* mark on
  the unit list, and *from address* on the grid (the last exists). The Tier 1 card already
  covers an unknown location.
- **Phase 2** adds the conditional re-notification: address, units or call type changed →
  ntfy with a *CORRECTION* prefix and what changed.
- **`public.intersections`** gains the zone set per junction; `extract_all_intersections_from_gis.py`
  computes it with `ST_DWithin` against `public.zones`, not `ST_Contains` (CLAUDE.md §7.3a).
- **The API and MQTT contracts** carry the new fields; anything not in the schema is dropped
  silently by the update path (see the note in `payload_builder.py` on `review_flags`).

## Measure first

One extension to `tools/harness_phase1.py`, then one corpus run (about two hours on the kiosk):

- for every recording, the chunk at which each layer first becomes available: units, call type,
  solid address, near roads, talk group; and the chunk where the ntfy gate would open;
- the ntfy moment by unit count (1, 2-3, 4+), and how many calls never reach it inside the
  recording (ruling 1 applies to those);
- how often the unit list shrinks between chunks (ruling 3's cost, made visible);
- for the intersection calls, how many carry one zone and how many two (ruling 2's cost).

Those four numbers decide whether "units at 13 s, address at 22 s, push at 25 s" is the typical
six-unit call or the exception, and they are the acceptance test for the build.

## Open design

- How *still listening* looks on the display, and whether a unit that vanished needs a mark.
- The ntfy message with a subaddress and a two-zone grid in it; the *check runsheet* wording.
- What the review screen shows for a call that was corrected after the push.
- Whether layer 1 should wait for two consecutive chunks to agree before the first unit list
  goes out (the simulator can price that).
- A restart during a capture still loses the call (#70); a graceful stop is a prerequisite for
  a pipeline that publishes six times per call.

## Related

#72 (the parcel-zone grid, closed), #70 (graceful stop, open), the rule A line in
`post_freeze_backlog.md`, `call_structure.md` (the announcement's order, which is what makes
the layers arrive in this sequence), `ntfy_server_access_and_qr_spec.md` (the push channel).
