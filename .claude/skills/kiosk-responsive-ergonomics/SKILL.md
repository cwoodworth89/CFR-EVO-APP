---
name: kiosk-responsive-ergonomics
description: Layout and typography conventions for the CFR EVO station display and workstation console. Read before changing display sizing, viewport behaviour, or adding a display mode.
---

# Station Display & Workstation Ergonomics

## Current design constraint

**Members approach the screen and read it from normal reading distance.** There is no
10-foot / apparatus-bay readability requirement, and typography should not be sized for
one.

Decided 2026-08-22. Changing display type — a wall-mounted bay display, multiple screen
profiles, viewport-driven mode switching — is a **possible future feature, not a current
requirement.** Do not build sizing infrastructure for it in advance.

**The hall display is a touch-sensitive TV; the Flex 5 is the server only** (operator,
2026-09-09). Hover is not an input on it: anything carried only by a `title` tooltip or a
`hover:` state is invisible to the crew, and a control has to be sized for a finger. Phone
and tablet widths are a separate, planned surface, not this one:
[`docs/briefings/mobile_accessibility_review.md`](../../../docs/briefings/mobile_accessibility_review.md).

> [!WARNING]
> **This file previously described a system that did not exist.** It specified an
> `isKioskMode` / `isKioskView` prop, a `?mode=kiosk` URL switch, a "top 30% / bottom 70%"
> kiosk layout and 72pt typography. None of those were ever in the code. Corrected
> 2026-08-22 after verifying every claim against the source. Treat anything here as
> checkable, and check it (CLAUDE.md §7).

---

## What actually exists

### Two surfaces

**Dispatch display** (`components/kiosk/KioskView.jsx`) — shown when there is an active
call or a review replay.

```
review strip       only on a review replay: REVIEW REPLAY / EXIT REVIEW, full width
ActiveAlertBanner  (header: three cards -- the call, the units with ETAs, the hydrant)
├── notices row          only when the record carries one: pre-incident plan, operator-set arrival point
├── RouteOverviewPanel   flex-1       route map: route pill, control stack (ZOOM, SNAP TO CALL, RE-CENTRE, + -)
└── DetailStack          38.5 %, 360-740 px   PropertySatellitePanel ("AERIAL") and StreetViewPanel, each in a TileFrame header bar
```

**The header's three cards are fixed places** (operator, 2026-09-10). The hydrant has the
card the elapsed clock vacated rather than a row inside the units card, because the units
card grows downward with the unit count and would move the hydrant about the screen. The
review controls are a strip above the header, since they are never on a real dispatch.

**The call card ends in one status line** (operator, 2026-09-11: *"group Map Grid + talk
group + elapsed time together"*): `GRID · TG · response · ELAPSED`, then the auto-dismiss
state and the dismiss button on a live call. It replaced a two-level foot row that stood
50 px because its right-hand stack did, and it supersedes the 2026-09-10 placement of the
clock at bottom right — the operator's own ruling, and his to overturn. **The address line
carries the address and nothing else**: the GRID chip beside it was taking the width that
made a long intersection address wrap, 80 px against 36.

**The response word lives in that line, not as a badge.** Removing it outright was asked for
on the grounds that the 6 px coloured border already says the mode. The border does, but the
badge cost no height (it shared the incident row), so deleting it would have saved nothing
and left colour as the only channel — red against green, the worst pairing for it. Punch-list
#31 and CLAUDE.md §6.1. UNKNOWN keeps its amber chip; routine and emergency are the word in
their colour, with no pulse. **Nothing floats over the route map's lower half**: the hydrant
card used to, and covered the destination on 1132 Dufferin St.

**Built to artboard 3A of the operator's Claude Design canvas, 2026-09-09**
(`docs/design/`, the departures in `docs/briefings/mobile_accessibility_review.md` §7). The
floating details box is gone: units in the header, the hydrant on the map. The canvas's 3C
(the expand state) is not built. The cadastral block tile was dropped 2026-09-08 (SNAP TO
CALL on the route map replaces it).

**Workstation console** (`components/MapBoard.jsx`) — standby / explore.

```
Header
├── LeftSidebar          map layer toggles, target, hydrants, closure filters
├── MapContainer         main map
└── right stack          address card, PropertySatellitePanel, StreetViewPanel
```

**The console draws every hall's approach on request** (operator, 2026-09-11). `All Hall
Approaches` in MAP LAYERS turns `HallRoutesOverlay`'s `allHalls` on, which draws all four
routes instead of the home hall's alone, and puts a distance/time row per hall in the target
panel. Off by default — the route colours are the zone-fill colours, so four translucent lines
over four zone fills is a lot to read unasked. The rows stay in hall order: sorting by time
would read as a first-due order, which this view cannot know. See `docs/ux_notes.md` §3 item 7.

Both are header + main map + right-hand detail stack. See
[`docs/architecture/unified_map_surface.md`](../../../docs/architecture/unified_map_surface.md)
for the proposal to collapse them into one mode-selected surface.

### The only real sizing mechanism: `isTvMode`

`useKioskQueue` owns `isTvMode` (default **false**), toggled by the user from the alert
banner. It is consumed only by `ActiveAlertBanner`, where it bumps two headings:

| | Normal | TV mode |
|:--|:--|:--|
| Address heading | `text-3xl sm:text-4xl` | `text-4xl sm:text-5xl` |
| Secondary line | `text-xl sm:text-2xl` | `text-2xl sm:text-3xl` |

It also hides the dismiss button, so a wall display cannot be cleared by a passer-by.

**Removed 2026-09-09.** Artboard 3A demoted the toggle (*"a deployment setting, not a
per-call control"*) and the operator ruled the same day: *"We're going to move away from
tv-mode toggle and have a responsive design."* `isTvMode` and `toggleTvMode` are gone from
`useKioskQueue`; the table above records what the toggle did. Sizing is Tailwind's
responsive prefixes and nothing else.

That was the whole feature. If display-type switching is ever wanted again, a hook like it is the
hook to extend — not a new parallel mechanism.

### The phone layout (built 2026-09-09)

Below Tailwind's **`lg`** line (1024 px) both surfaces reflow for a phone or an upright
tablet; at and above it nothing changes. `hooks/useCompactViewport.js` is the same line in
JavaScript, for the decisions that are not CSS (one map mounted at a time, the search sheet
folding once an address is picked, a fit padded by a sheet's height). `md` was tried first
and measured too narrow: a landscape phone at 852 px kept the desktop columns and a 152 px map.

| Surface below `lg` | Becomes |
|:--|:--|
| `LeftSidebar` | a sheet over the bottom of the map with a handle; folds when an address is picked |
| `DetailStack` | tabs (Details, Satellite, Street View), one mounted at a time; on the console a sheet that folds to its tab bar |
| `RightSidebar` | a drawer from the right |
| `KioskView` | a column that scrolls: the three header cards, the route map at 52 dvh, then the tiles as tabs at 56 dvh (the hall display never scrolls) |
| `RouteOverviewPanel` chrome | SNAP TO CALL and RE-CENTRE only (no zoom readout or buttons; pinch does that); the hydrant card spans the map's foot |

**Fits are measured, never written.** `map/fitPadding.js` is the one place both maps get
their `fitBounds` padding from the container and whatever floats over it: on the dispatch
map, the control stack's width and the hydrant card's height (`overlays`). The literals it
replaced gave Leaflet a NaN zoom on a phone (`docs/standards/dependency-behaviour.md`).

---

## Conventions to follow

* **Tailwind responsive prefixes** (`sm:`, `lg:`) for viewport adaptation. There is no
  custom breakpoint system and none is needed. **`lg` is the phone line**; do not add a
  second one without a measurement that says where it goes.
* **`touch:`** (`@media (pointer: coarse)`, added in `tailwind.config.js`) for target sizes
  and 16 px inputs. It applies to the hall's touch TV as much as to a phone, and never to a
  mouse. `hoverOnlyWhenSupported` is on, so `hover:` never sticks after a tap.
* **Nothing crew-facing lives only in a `title` tooltip.** A touch screen never shows one;
  the flag reasons and the changed-field list open on a tap for that reason.
* **Dark slate palette** (`bg-slate-950`, `border-slate-800`) throughout. This is for
  low-light station conditions and contrast, not viewing distance, and stays regardless of
  the constraint above.
* **Priority colour coding** is semantic, not decorative: amber for warnings and
  unresolved state (CLAUDE.md §5), red for emergency response, emerald for confirmed.
* **Panels own their own layout.** The detail-stack cards are given a flex cell and size
  themselves within it; do not set their heights from the parent.
* **New size variants need a reason.** With one viewing distance, a second set of type
  scales is unjustified until the display-type feature actually exists.
* **The dispatch header's type scales with viewport height from `lg` up** (2026-09-09).
  Artboard 3A's sizes at 1920×1080 are the reference, expressed in `vh`: address 6.5 vh
  (70 px), incident 2.8 vh, first-due ETA 3.4 vh, elapsed 3.8 vh, each in a `clamp()` with a
  floor and the canvas size as the ceiling. Fixed steps left the header half of a 1000-tall
  laptop screen with an intersection address. A long address also shrinks by length
  (`--addr` scale: 1 to 16 characters, 0.8 to 24, 0.66 beyond) so it stays on one line.
  Below `lg` the phone keeps fixed small sizes.

## Testing

Run the app and resize the browser. There is no mode query parameter and no kiosk
simulation flag — the dispatch display appears when there is an active call or a review
replay, which `App.jsx` decides from `useKioskQueue`.
