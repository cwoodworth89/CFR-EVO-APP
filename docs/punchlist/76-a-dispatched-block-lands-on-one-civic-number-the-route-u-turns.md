# Punch list #76 — A dispatched block lands on one civic number at the block's end, and the route U-turns past it

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🗺️ Geocoder |
| **Blocks** | — |
| **Origin** | Operator's review note on DISP-2026-AF6731 (2026-09-05); the routing stream's analysis of the same call, relayed by the operator 2026-09-09 and verified here |

[← punch list index](../debug_and_qa_punchlist.md)

---

> **Status**: 🟡 **Built 2026-09-09 to the operator's ruling; live since the agent restart
> of 2026-09-10 (operator: "Go ahead and restart").** Two block calls in 609, both placed wrongly in
> a way crews cannot see. **Operator, 2026-09-09: *"A BLOCK flag should trigger a specific
> form of geocoding, which finds the middle, or average spot of a city block."*** The block
> step is in the geocoder, measured on both recorded calls (below). The block's extent is
> the stated default, civic N00–N99, until the operator says otherwise. Closes when a block
> call has come through the live pipeline, or the operator replays one and says so.

## What the operator saw

DISP-2026-AF6731, 2026-09-05 16:59, Motor Vehicle Incident, announced **"2500 Block Barnet
Hwy"**, near road *Access Rd*, map grid 69, E1 responding. The kiosk showed **2534 Barnet
Hwy** with the note *"2500 Barnet Hwy is not in City of Coquitlam address records. Routed to
2534 Barnet Hwy, the nearest civic address on this street (34 off the dispatched number)."*
The operator verified the address as *2500 Block Barnet Hwy* and wrote:

> *"So this is a block response. I think it still needs to show that the dispatch announced
> 2500 block, and if the map needs to snap to nearest parcel it should. But it should still
> SHOW the label properly. Especially for translation."*

(The same note records *"the audio clip never cut after 3 seconds"*, a separate observation
about the capture, not this item.)

## Confirmed, 2026-09-09

Every claim below was checked against the code, the database on the kiosk, or OSRM on the
kiosk (CLAUDE.md 6.6). The routing stream's account of the call held on every point.

1. **The parser sees the block and nothing reads it.** `parse_house_and_street` in
   `services/gis/src/gis_service/normalization.py` sets `has_block_indicator`, strips the
   word, and hands the geocoder `house=2500, street=Barnet Hwy`. The dataclass field carries
   its own comment: *"set by parse_house_and_street; nothing reads it yet"*.
2. **Step 3, block interpolation, found no segment.** `resolve_block` in
   `address_resolver.py` wants a road segment whose address range contains 2500. Barnet's
   westernmost pair of segments (ids 1978 and 2180, the two carriageways, 495 m each) carry
   2555–2565 on the left and 2534–2560 on the right. 2500 is below both, so the step returned
   nothing.
3. **Step 4, nearest civic, chose 2534.** The announced near road, *Access Rd*, matches no
   named road, so the house-number gap decided alone, and 2534 is the lowest number on the
   street: the western end of the block, 69 m from the Port Moody line. The resolution note
   on the record says exactly this. The pin: 49.27730, −122.82287, on the south carriageway.
4. **The U-turn is real and 600 m long.** OSRM on the kiosk, Hall 1 apron to that pin:
   4,329 m by road against 2.79 km straight-line. The route runs west along Barnet 300 m past
   the pin to the Ioco Road interchange, turns left onto Barnet Service Road, and comes back
   265 m east to arrive. E1 arrives westbound on the north carriageway and the pin is on the
   south one; the only crossing is the interchange. A midpoint would have moved the pin, not
   removed the loop.
5. **The other block call.** DISP-2026-266B57 (2026-07-19), *"1080 Block Ponderosa St"*,
   resolved to the street centroid, *"Ponderosa St, Coquitlam"*, with no block shown.
6. **The right shape already exists, end to end.** A *"<street> and <street>"* call with no
   cross street resolves to a **street section** (`resolve_street_section_in_grid`,
   `spatial_queries.py`): the geometry, every piece's endpoints, the length, and a nominal
   point marked as not the location. `payload_builder.py` carries `location_type`,
   `segment`, `endpoints` and `length_m` onto the dispatch; `routing_engine.py` routes every
   unit to whichever end is nearest its own hall and says so in `destination_note`; the
   kiosk draws it (`RouteOverviewPanel.jsx`, `StreetSectionBanner.jsx`), the workstation
   draws it (`DispatchTargetLayer.jsx`), and the review raises `STREET_SECTION_ONLY`.
7. **The hundred-block already has provenance in the code.** `address_resolver.py`, the
   substitution bound: *"the hundred-block is the addressing unit in this jurisdiction:
   Coquitlam civic numbering allocates one hundred-block per block face, and Locution
   dispatch itself announces block-level locations that way"*, citing DISP-2026-266B57.
   Nothing in `docs/standards/` governs it beyond that; a municipal-data-derived rule
   (CLAUDE.md 7.2), recorded.

## The fix, as ruled

**The block flag is its own geocoding step, and it returns the middle of the block.** When
`has_block_indicator` is set, the geocoder takes a block step before block interpolation:
the road segments of that street whose address ranges fall in the announced hundred-block,
both sides, merged; the location is the **midpoint along that stretch**; the address is the
**announced wording**, *2500 BLOCK BARNET HWY*, with the location marked as the block's
middle, approximate; and the block's geometry rides along as `segment` so both maps
highlight the extent the way they already highlight a street section. Routing goes to the
midpoint, the hydrant search runs from it, and a review flag says the pin is a block's
middle, ruled by the verified address like the others.

Where this lives: `normalization.py` (already done), `address_resolver.py` (a
`resolve_block_midpoint`), one branch in `geocoder.py` before step 3, the label in the
kiosk's details box and banner, the flag in `review_flags.py` and its frontend mirror.
About half a day, plus the two calls above replayed as the check.

**Known limit, stated before building (7.6):** on a divided highway the middle of the block
lies between the carriageways, and OSRM snaps it to the nearer one. On Barnet that may be
the south carriageway again, in which case E1's route keeps the 600 m loop. The cheapest
test is the replay of DISP-2026-AF6731 after the build: if the route still turns at Ioco
Road, the next step is to hand OSRM the midpoint of each carriageway and keep the shorter
route. The routing stream's alternative, the whole block as a section with each unit sent to
its nearer end, is recorded above and not chosen.

## Built and measured, 2026-09-09

`resolve_block_midpoint` in `address_resolver.py`, called as step 0 of `get_coordinates`,
before the exact-parcel step, whenever the parser flagged a block. Both maps draw the block
as the amber dashed stretch a street section gets; the kiosk's SNAP TO CALL fits the whole
block; the review raises `BLOCK_MIDPOINT` (ruled by the verified address) in place of
LOCATION_SUBSTITUTED. Node and Python tests: 49 pass in the three touched suites, two of
them live against the kiosk database.

| Call, as announced | Before | Now |
|:--|:--|:--|
| *2500 Block Barnet Hwy* (DISP-2026-AF6731) | 2534 Barnet Hwy, the block's west end, south carriageway | **2500 Block Barnet Hwy**, civic 2534–2599, 594 m along, pin at the middle |
| *1080 Block Ponderosa St* (DISP-2026-266B57) | the street centroid, no block shown | **1000 Block Ponderosa St**, civic 1000–1099, 283 m, pin at the middle |

**The divided-road limit, measured and answered.** The block's single middle landed on the
south carriageway and Hall 1's route still ran 429 m past it to U-turn at Ioco Road
(4,451 m). So on a divided road the step also returns the middle of each carriageway as
`endpoints`, the contract a street section already uses: `payload_builder` hands them to
routing as destination options and `routing_engine` sends each unit to the one nearer its
own hall, which is the side it arrives on. Hall 1 to the north carriageway's middle on the
kiosk's OSRM: **3,574 m, 312 s, no U-turn, no overshoot**, against 4,451 m and 400 s with
the loop. An undivided street returns no options and routes to the pin: pieces that touch
are clustered into one run first (ST_ClusterWithin, about 3 m), because two consecutive
records on Barnet's south side did not merge and would otherwise have read as a third
carriageway, and on Ponderosa as two half-blocks.

**For the routing stream, one line in its file**: `destination_note` on a block call still
reads *"Street section: routed to the nearer end of the highlighted stretch"*; on a block it
is the nearer carriageway's middle. Wording only.

## The one question left (CLAUDE.md 7.6)

**How far does "2500 block" reach?** Assumed: civic 2500–2599, both sides. On Barnet that is
the whole western pair (2534–2565, 495 m) **and** the first part of the next pair, whose
range runs 2574–2675 and so straddles the 2500 and 2600 blocks. The middle moves with the
answer: the 495 m pair only puts it near 2550; the pair plus the straddling segment cut by
interpolation at 2599 (the exact hundred-block, about 600 m) puts it near 2565; the pair
plus the whole straddling segment (905 m, over-covering to 2675) puts it near 2600.
Recommendation, and the default if unanswered: **the exact cut at the hundred-block
boundary**, because that is what the announcement says.

Answered 2026-09-09: the location is the block's middle (the operator's ruling above), so
the section-ends question and the nominal-point question are closed.

**Answered 2026-09-10.** Operator: *"I think we can find the midpoint of whatever is
available."* Read as: the middle of whatever road data the block has, no finer rule wanted.
The exact cut at the hundred-block boundary stays as built; if dispatch's "2500 block" turns
out to reach further, the cut is one number. The agent was restarted the same day on the
operator's word, so the step is live.

<!-- audit-ok: services/gis/src/gis_service/normalization.py -- exists; named for the parser step -->
