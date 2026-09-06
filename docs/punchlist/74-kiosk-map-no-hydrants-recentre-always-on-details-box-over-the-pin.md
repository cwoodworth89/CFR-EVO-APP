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

> **Status**: 🟡 **Four of the operator's notes built 2026-09-06; the fifth, where the
> dispatch-details box should live, is a layout decision that is the operator's.**

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
