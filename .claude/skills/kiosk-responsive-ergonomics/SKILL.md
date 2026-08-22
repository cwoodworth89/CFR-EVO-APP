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
└── detail stack         col-span-4   BlockParcelPanel
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

---

## Conventions to follow

* **Tailwind responsive prefixes** (`sm:`, `lg:`) for viewport adaptation. There is no
  custom breakpoint system and none is needed.
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
