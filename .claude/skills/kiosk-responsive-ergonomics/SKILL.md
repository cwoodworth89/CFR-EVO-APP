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
ActiveAlertBanner  (header: address, units, incident, timers)
├── RouteOverviewPanel   col-span-8   main route map
└── detail stack         col-span-4   PropertySatellitePanel (the cadastral block tile was dropped 2026-09-08; SNAP TO CALL on the route map replaces it)
                                      PropertySatellitePanel
                                      StreetViewPanel
```

**Workstation console** (`components/MapBoard.jsx`) — standby / explore.

```
Header
├── LeftSidebar          map layer toggles, target, hydrants, closure filters
├── MapContainer         main map
└── right stack          address card, PropertySatellitePanel, StreetViewPanel
```

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

That is the whole feature. If display-type switching is ever wanted, `isTvMode` is the
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
| `KioskView` grid | a column: banner (address first), route map at 52 dvh, then the tabs |
| `RouteOverviewPanel` details box | across the top of the map, folded by default |

**Fits are measured, never written.** `map/fitPadding.js` is the one place both maps get
their `fitBounds` padding from the container and whatever floats over it. The literals it
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

## Testing

Run the app and resize the browser. There is no mode query parameter and no kiosk
simulation flag — the dispatch display appears when there is an active call or a review
replay, which `App.jsx` decides from `useKioskQueue`.
