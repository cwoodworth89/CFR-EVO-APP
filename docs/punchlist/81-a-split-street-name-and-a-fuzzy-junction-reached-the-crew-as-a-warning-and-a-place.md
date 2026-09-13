# Punch list #81 — A split street name raised a false warning, and a fuzzy junction passed the phase 1 gate

| | |
|:--|:--|
| **Status** | FIXED in the tree (2026-09-13), tests pass locally against the kiosk database. **Not deployed**: the worker changes need a `cfr-agent` restart, which is the operator's call. |
| **Severity** | 🔴 crew-visible |
| **Area** | 🗺️ Geocoding · 🖥️ Kiosk HUD · 📡 Pipeline |
| **Rulings** | Operator, 2026-09-13, on the review of the two calls below: street names match regardless of spaces, for every street; hold back fuzzy junctions in phase 1; the approximate-location banner is for crews ("APPROXIMATE LOCATION — VERIFY ON RUN SHEET AND MAP GRID", body only the dispatched-against-shown line); hydrants stay picked on the home hall's route; the unit list stays first due first. |
| **Origin** | Operator call review, 2026-09-13: DISP-2026-E301A3 (2973 Glen Dr) and DISP-2026-56F11A (Eagleridge Dr & Guildford Way), screenshots from the laptop kiosk. |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What the crews saw, and why

### DISP-2026-56F11A — Eagleridge Dr & Guildford Way

The pin was on the right junction (operator: "IS in the perfect spot"), under an amber
**APPROXIMATE LOCATION — VERIFY ON ARRIVAL** banner whose body read *"'Eagle Ridge Drive And
Guildford Way' does not match any intersection in the road network ... Confirm before
dispatching. Note: cross street(s) GUILDFORD WAY do not distinguish these junctions."*, and
the NEAR line read `EAGLERIDGE DRIVE (?)`.

1. **STT writes the one-word street as two words.** The raw transcript has "eagle ridge drive"
   in both rounds, as on 2 of the 3 earlier verified Eagleridge calls; the operator has always
   verified it as one word. Nothing joins it before geocoding: `sanitize_transcript` leaves it,
   the parser yields `Eagle Ridge Drive And Guildford Way`, and the intersection lookup is an
   exact key match, so it missed and offered `EAGLERIDGE DR & GUILDFORD WAY` as a suggestion.
   The one-word `eagleridge drive &` in the stored `sanitized_transcript` is not a cleanup: phase
   2 rebuilds that text from the geocoder's answer (`phase2.py`, `reconstruct_template_transcript`).
2. **Phase 2 did not re-check it.** When both phases parse the same address, phase 2 keeps
   phase 1's location result, note included; it geocodes again only when phase 1 withheld the
   location. So the banner was not phase 1 "figuring itself out" — one lookup produced it.
3. **The phase 1 gate let the suggestion through.** Rule A (#72) holds back guesses, and its
   comment says a fuzzy pair is one. But `IntersectionResolver.resolve_candidates` marks every
   non-exact result `ambiguous=True`, even a single candidate, and the gate passed any ambiguous
   junction. Here the suggestion was right; the same path publishes a wrong-street junction.
4. **"Do not distinguish these junctions" with one junction.** `_narrow_by_x_streets` emitted
   the note whenever it kept every candidate, which one candidate always is.

### DISP-2026-E301A3 — 2973 Glen Dr

5. **"NUMBER 505 NEARLY 505" stayed on screen for the whole call.** On the match path phase 2
   builds the target by spreading phase 1's and never set `subaddress`; its own parse of the full
   recording gave `Number 505` and went only into the rebuilt transcript. (Why phase 1 heard
   "Nearly" is not known: the phase 1 transcript is deleted when phase 2 finishes, and
   `tools/harness_phase1.py` did not reproduce production's chunks on either call.)
6. **The location was withheld in phase 1 by design** (#72: no parcel). 2973 Glen Dr is not in
   the City's address layer — recorded under **#64**, not here.
7. **Cross streets are not withheld** with the location: with no point and no zone they show
   "(as heard)" and flag `XSTREET_UNRESOLVED`. Phase 1 raised neither, so its parse had none.
   Not diagnosable further for the reason in 5.

### Both calls — the 3-second MQTT step

8. **Every worker publish waited 3 s for an acknowledgement nothing read.**
   `publish_mqtt_dispatch` opened a client and never started its network loop, so paho-mqtt
   2.1.0's `wait_for_publish(timeout=3.0)` could not see the PUBACK and returned silently at the
   timeout. Measured on the kiosk on a diagnostic topic: 3003 ms per call, message delivered in
   7 ms; with `loop_start()` 1 ms. The kiosk itself was probably not delayed — the API publishes
   the same INSERT when phase 1 posts the record — but Ntfy and every phase 2 publish were, and
   the phase 1 TTA figure carried the 3 s.

## Fixes (2026-09-13)

| # | Change | Where |
|:--|:--|:--|
| 1 | An intersection key also matches with the spaces inside street names ignored, when that names exactly one junction key. No two `public.intersections` keys and no two `public.roads` names collide that way (checked 2026-09-13). | `services/gis/src/gis_service/intersection_resolver.py` (`lookup`, step 1b) |
| 1 | Near roads match the same way, so the NEAR line loses its `(?)`. | `backend/cfr_dispatch/pipeline/near_roads.py` (`match_heard_road`) |
| 3 | Rule A never treats a suggested junction as solid. The house-number resolver's multi-reading candidates, which are also "ambiguous", are unchanged. | `backend/cfr_dispatch/pipeline/payload_builder.py` (`is_suggestion`) |
| 4 | Cross-street narrowing is skipped for fewer than two candidates. | `intersection_resolver.py` (`_narrow_by_x_streets`) |
| 5 | Phase 2 writes its own subaddress on the match path. | `backend/cfr_dispatch/pipeline/phase2.py` |
| 8 | The publisher runs the network loop, and a publish not acknowledged in 3 s is logged and returns False. | `services/dispatch_notifications/src/notification_service/mqtt_broker.py` |
| — | Banner header "APPROXIMATE LOCATION — VERIFY ON RUN SHEET AND MAP GRID"; the resolver's note is off the crew screen (still on the record); body is "Dispatched X · shown at Y" when they differ. | `frontend/src/components/kiosk/ApproximateLocationBanner.jsx` |

**A test pinned the old behaviour and was wrong.** `test_a_mistranscription_is_still_flagged`
required the heard "A Gate" to stay unresolved beside Agate. With spaces ignored it resolves to
Agate — and every "near a gate place" in the corpus is 2573 Diamond Cres, verified **Agate Pl**
on both reviewed calls (DISP-2026-5317C5, DISP-2026-859C77). The test now asserts that.

**Tests:** `test_payload_location_gate_db.py` gains the split-name junction (goes out exact, no
note, no substitution flag, NEAR exact) and the suggested junction (withheld). Both **fail on
the previous code** with the production symptoms — the note in the failure is word for word the
banner on the kiosk — and pass on this one.

**Not tested:** the phase 2 subaddress change has no test (the match path needs the full phase
2 run); the MQTT change was measured in isolation, not yet in the running agent.

## To confirm on the kiosk

- [ ] After the operator restarts `cfr-agent`: the next call's `[METRICS] Phase 1 TTA` shows MQTT in milliseconds.
- [ ] A split-name junction call shows no approximate banner and no `(?)`.
- [ ] A reworded banner seen on screen.
