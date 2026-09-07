# Punch list #74 — Kiosk map: no hydrants, RE-CENTER always on, details box over the pin, Street View tile buried

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🖥️ Kiosk view |
| **Blocks** | — |
| **Origin** | Operator, 2026-09-06, reviewing DISP-2026-5317C5 on the kiosk view |

[← punch list index](../debug_and_qa_punchlist.md)

---

> **Status**: 🟡 **Built 2026-09-06, including the operator's hydrant rule (along the route
> first); open on one thing only, where the dispatch-details box should live.**

The operator's notes, verbatim in substance:

1. *"Hydrants aren't being calculated or displayed on the main screen anymore."*
2. *"Re-centre route always appears, even by default."*
3. *"I don't like the floating dispatch details box as it is right now. Look, it covers up the
   destination."*
4. *"The pip windows are VERY busy. The worst offender is the streetview one. The option to
   save a view should only be inside the expanded window. That whole lower bar can go for the
   static window so we can actually see the view."*

### 1. Hydrants — built

The dispatch map never asked for them. `MapSurface` has carried a hydrant layer since the
decomposition (`64a41be`), with the nearest-city and nearest-private calculation inside it,
but `RouteOverviewPanel` did not set `showHydrants` and passed no target, so the layer drew
nothing and the details box printed *Nearest hydrant not computed* — the honest line #24 put
there when the invented *D-165 (42m)* was removed. Now the dispatch map shows the hydrants
from zoom 12, pulses the nearest City and nearest private ones, and the layer reports them up
to the details box: **id · distance straight-line · NFPA 291 class**, *No operating City
hydrant within 800 m* when there is none, *Awaiting location* under rule A.

Provenance gap carried forward, not new: the layer's 800 m (City) and 400 m (private) search
thresholds in `MapLayers.jsx` have no cited source (CLAUDE.md 6.3). The distance shown is
measured; only the cut-off is unsourced. Row for `docs/standards/README.md`.

### 2. RE-CENTER — built

A programmatic `fitBounds` fires the same `zoomstart` a scroll wheel does, so the button
appeared on every call before anyone touched the map. The fit now raises a flag for its
duration and the listener ignores zoom events while it is up; a drag is always the user.

### 3. The details box over the destination — half built, the rest is yours

The route fit now pads its left edge by the box's width, so the whole route, pin included,
sits to the right of it. That stops the covering. Where the box should *live* is not decided
here: the choices are (a) leave it floating, collapsed by default (one tap opens it), (b) move
it into the header strip beside the ETA badge, or (c) a slim bar under the map. Say which.

### 4. Street View tile — built

The address-and-save bar is gone from the compact tile and stays in the expanded view; the
tile is the picture and its header. The same bar was where the save button wrote back the
default angle during the weeks the SDK was rejected (#35a), so it is also the right place for
it to be the only save.

### Not touched

The cadastral and satellite tiles' headers and *Expand* buttons, which the note also called
busy: no specific change was asked for, and the freeze says wait for one.

### 1b. Hydrants by the operator's rule — built the same evening

Operator, 2026-09-06, after the straight-line version above: *"what matters most is choice
#1 and #2. Ideally along the route picked. So just go with that. If there's no hydrant within
300ft of the route, check if there is one (sometimes it's just past the address). If nothing
within 300ft warn the driver."* And: *"Our trucks carry 1000ft of supply hose, but there
aren't many places in the city that would be needed."*

That is department operational policy (CLAUDE.md 6.3, provenance 4) and is now the one
implementation for both views, `frontend/src/utils/routeHydrants.js`:

| Tier | Rule | Shown as |
|:--|:--|:--|
| 0 | A hydrant within 50 ft (15.2 m) of the address marker, any direction, comes first regardless of the route: *"we carry short, 50ft supply line rolls"* (operator, later the same evening). The route then supplies #2. Measured from the marker, which is where the truck stops (operator: *"the truck is going to stop at the marker, not the door"*); the assumption is that the marker is the arrival point on the street, and a large parcel placed at its centroid (#49) is the case that breaks it | *N m from the address, within a 50 ft roll* |
| 1 | Hydrants within 30 m of the OSRM route line and within the 1,000 ft (304.8 m) supply lay of arrival, measured along the route; the last one passed is #1, the one before it #2. **Was 300 ft** until the 808 Miller Ave replay the same evening (below) | *N m before arrival, on the route* |
| 2 | None there: hydrants within 300 ft of the address, straight-line, any direction (the one "just past the address") | *N m from the address, none on the approach within 1,000 ft* |
| 3 | None there: the nearest within 1,000 ft (304.8 m), the supply hose carried | *N m, within the 1,000 ft supply lay* |
| — | Nothing within 1,000 ft | **⚠️ NO HYDRANT WITHIN 1,000 FT** |

`NOT READY` hydrants (the City's status) never count. The 30 m band is measured, not
chosen: 2,837 OPERATING hydrants sit p50 8.4 m, p90 11.9 m, p95 35 m from the nearest
`public.roads` centreline (2026-09-06), the p95 tail being lanes the roads table lacks.
Assumption stated (7.6): the hydrants a crew would call "along the route" lie within 30 m of
the route line; the falsifier is a call whose crew caught a hydrant farther off it.

Wired: the kiosk's route panel takes the drawn route from `RoutingOverlay` and lists the
picks in the details box; the workstation's search view uses the same picker (its
Alpha-segment version with three unsourced constants is gone) and its target card says how
each pick was chosen; the map layer pulses exactly the picks. Six `node --test` cases
(`npm run test:node`) cover the four tiers, the NOT READY exclusion and the no-route case.
The previous 800 m / 400 m thresholds remain only in the layer's fallback for callers that
pass no picks.

Untested live: needs a call. Chrome shows the search view; the route panel needs a dispatch
or a replay.

Operator, on the marker (2026-09-06): *"That marker point is where we transition from city
to private so drivers have to take precautions about private hydrants. It's acceptable and a
good system."* So the marker is the right origin for the 50 ft roll by definition, and a
hydrant on the private side of it is the case the amber **PRIVATE** label on a pick exists
for. Accepted as built.

### 1c. 808 Miller Ave: the window was too tight, and the map was drawing every hydrant

Replay of DISP-2026-A92117 (report of smoke, high risk), 2026-09-06 evening. Two things on
the operator's screenshot:

*"I don't need to see all of those hydrants. Just the recommended ones."* The full layer
with a target set draws from zoom 12, which at a city-wide route is every hydrant in
Coquitlam. The dispatch map now draws only the picks, numbered and pulsing
(`map/PickedHydrantsLayer.jsx`); the workstation keeps the full layer behind its toggle and
its target layer draws the picks as before.

*"The recommended ones are not on the route of travel. I-029 on the corner of Grant and
Miller would have been the hydrant of choice."* Measured: the OSRM route reaches the marker
down Grant St and east on Miller; I-029 sits 19 m off that line and **95 m (312 ft) before
arrival** along it, four metres outside the 300 ft window. The two picks, I-030 (64 m, past
the address on the far side) and I-074 (73 m, down Adiron), were off-route hydrants measured
straight-line. The operator's choice says an on-route hydrant beats an off-route one beyond
300 ft, so the along-route window is now the 1,000 ft supply lay (`ROUTE_WINDOW_M`), with
300 ft kept for the straight-line look around the address once the route has nothing. The
case is a test (`808 Miller Ave` in `frontend/tests/routeHydrants.test.mjs`). If 1,000 ft
back along the route is too far to prefer over a hydrant across the street, the operator
names the number and it is one constant.

Operator, on the window (2026-09-06): *"we'd lay 300-500 feet of supply line all day. It's
when it gets further we need to think about relay pumping, or finding something closer."*
Built as: an on-route pick beyond 500 ft (`ROUTINE_LAY_M`) is marked **LONG LAY**, and the
closest hydrant to the address within 300 ft, if there is one, is listed beside it as the
closer option, so the crew weighs relay pumping against the shorter lay themselves. Two more
tests.

### 2026-09-07: no label boxes, and every hydrant at close zoom

Operator, on the 2573 Diamond Cres replay: *"I don't like the pop up boxes there. It makes it
hard to understand the route. Also, I think we should show ALL the hydrants on the main route
map, but only at a certain close in zoom."* Done: the picks are 22 px numbered badges in the
NFPA class colour with nothing else on the map (id, class and distance on hover and in the
details box), and the route map now carries the full hydrant layer with no target passed, so
it draws from zoom 16 — neighbourhood scale — and pulses the picks. At the route's own zoom
only the badges show.

