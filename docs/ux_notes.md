# UX Notes for Future Development

**Written 2026-09-07 from the operator's own reactions during a day of live and replayed calls
on the kiosk.** This is the brief for the next UX pass (the operator intends to consult Claude
Design). It records what the operator said, what was changed in response, what is still open,
and the conventions the interface has settled into, so a redesign starts from evidence rather
than taste. Quotes are the operator's, 2026-09-06 unless dated.

The system is in a feature freeze; nothing here is a request to build. It is the list to
decide from.

---

## 1. The surfaces

| Surface | Who looks at it | Where it lives |
|:--|:--|:--|
| **Kiosk view** | the crew, for the minutes between the tones and rolling out | `frontend/src/components/kiosk/KioskView.jsx`: banner, route map with a floating details box, a three-panel stack on the right |
| **Workstation / Explore** | the operator at a desk: searching an address, setting an arrival point, a Street View | `MapBoard.jsx` with the left controls and the `DetailStack` on the right |
| **Review screen** | the operator verifying calls, which feeds the training data and the hotwords | `DispatchReview.jsx`, `review/*` |
| **Driver station setup** | nobody yet (#60, deferred pending redesign) | `DriverStationSetup.jsx` |

The kiosk runs snap Chromium in kiosk mode on Wayland on the hall machine; the operator also
opens the same pages in Firefox and Chrome on a laptop. Screenshots from the day are
1,916 × 1,000 px. Whether the hall display is touch or mouse is not recorded here; ask.

---

## 2. What the operator said, and what was done about it

### Kiosk view

| Said | Done | Left |
|:--|:--|:--|
| *"I don't like the floating dispatch details box as it is right now. Look, it covers up the destination."* | The route fit now pads its left edge by the box's width, so the pin is never under it | **Where the box should live** is undecided: floating but collapsed by default, folded into the header strip beside the ETA badges, or a slim bar under the map (#74) |
| *"Re-centre route always appears, even by default."* | A programmatic fit no longer counts as a pan; the button appears only after a real drag or wheel | — |
| *"The pip windows are VERY busy. The worst offender is the streetview one."* | Street View tile: lower bar removed, header shrunk to *Street View ● 214°* | The cadastral and satellite tiles keep their header pill, a *100% Local* badge and *Expand*. Nothing specific was asked; they are the next candidates |
| *"The option to save a view should only be inside the expanded window."* | Done | — |
| *"I thought the PiP mode was going to be static serve, with the expand allowing interactive mode."* | The compact tile is a static image at the saved view; Expand opens the interactive panorama with the save bar | Needs *Street View Static API* on the key; until then the tile falls back to interactive and says so |
| *"'Saved Preferred View' is taking up a lot of room, and so is the label."* | A green dot and the heading in the tile header; full wording only in the expanded view | — |
| *"I don't need to see all of those hydrants. Just the recommended ones."* | The dispatch map draws only the picks, numbered, in NFPA 291 colours | — |
| *"I don't like the pop up boxes there. It makes it hard to understand the route. … show ALL the hydrants on the main route map, but only at a certain close in zoom."* (2026-09-07) | Picks are small numbered badges, no label box; the full hydrant layer draws on the route map from zoom 16 | — |
| *"Hydrants aren't being calculated or displayed on the main screen anymore."* | Picked by the operator's rule (§4 below), listed in the details box with how each was chosen | — |
| *"I'd rather have 'unknown' rather than guesses."* (2026-09-05) | The rule behind every empty state on the kiosk: the Tier 1 card, *(as heard)*, *NO HYDRANT WITHIN 1,000 FT*, *Awaiting location* | — |

### Review screen

| Said | Done | Left |
|:--|:--|:--|
| *"Can I rule one way or another and the system won't flag anymore?"* | A flag is ruled by the verified column that answers it; ruled flags show struck through with the ruling and stop counting (#75) | Nothing tells the operator *which field* rules a flag; the sidebar wording could |
| Calls from July were missing | The list fetched 500 rows of 569; now 5,000 | The screen needs a hard reload after a build; nginx sends `index.html` without `Cache-Control` (backlog) |
| *"We need to pivot to checking the review button … on the physical kiosk display"* and a rating from the kiosk (#52a, 2026-08-23) | Not started | A feature request with no spec |

### Workstation

| Said | Done | Left |
|:--|:--|:--|
| *"It would be nice to see hydrants to a given address."* | A searched address shows its picks and the arrival-point section | — |
| Arrival points could only be set by SQL (#49) | *Set arrival point* on the target card: click the map, note, name, save; attributed | The worst-first review queue is a CSV, not a screen |

Observed, not yet raised with the operator: in the address search, **Enter does not pick the
suggestion**; the row has to be clicked. Every automated run of the search hit this.

---

## 3. Open design decisions

1. **The details box.** Three options above. The operator dislikes the current floating box;
   what they want instead has not been said.
2. **Street View beside the map.** The Google Maps Platform Terms §3.2.3(e)(ii) forbid
   "Street View imagery and non-Google Maps on the same screen." The kiosk does that today.
   The operator noted it and deferred the ruling. The layouts that satisfy it are a
   full-screen Street View modal with the map hidden while it is open, a separate screen, or
   no Street View. This constrains any redesign of the right-hand stack.
3. **Progressive dispatch.** The operator's design for the kiosk to pop on the tones and fill
   in layer by layer (units, call type, address, grid, near roads, talk group, spoken grid),
   with the phone push firing once a driver can act. Spec, rulings and the measurement to run
   first: [`architecture/progressive_dispatch.md`](architecture/progressive_dispatch.md).
   Post-freeze.
4. **Every responding hall's route on one map**, each in its hall's colour, the home hall's
   solid and the others translucent. Operator's idea, on the post-freeze backlog.
5. **The review rating from the kiosk** (#52a) and **the driver station setup** (#60): both
   need a spec before design.

---

## 4. Conventions the interface has settled into

Keep these unless a redesign deliberately changes them; each came from a defect.

* **An unknown is shown as an unknown.** `--`, `--:--`, the amber Tier 1 card, *Awaiting
  location*. Never a default coordinate, ETA, unit list or channel (CLAUDE.md §6.1).
* **Amber is a warning or an unknown; green is a human ruling.** *NO HYDRANT WITHIN 1,000 FT*
  and *INTERACTIVE VIEW UNAVAILABLE* are amber; *OPERATOR-SET*, *● saved*, and a ruled flag
  are green.
* **Say how a value was obtained, next to the value.** *(as heard)* and *(?)* on near roads;
  *FROM ADDRESS* on a phase-1 grid; *before arrival, on the route* / *within a 50 ft roll* /
  *supply lay* on hydrants; *straight-line* on a distance that is one.
* **The tile is the picture.** A compact panel shows the thing and a small header; controls
  live in the expanded view.
* **Only the recommended, until zoomed in.** The dispatch map draws the picked hydrants as
  numbered badges at every zoom and the whole inventory only from zoom 16; the workstation
  keeps the full layer behind a toggle. No label boxes on the map: they hide the route.
* **A failure states itself.** A failed image or SDK load shows a labelled fallback, never a
  black rectangle that looks like a working panel (the weeks of #35a).
* **The marker is where the truck stops** — the city-to-private transition. Distances to it
  are distances the crew will walk or lay hose.

### Hydrants, as ruled

A hydrant within 50 ft of the marker, any direction, first ("we carry short, 50ft supply line
rolls"); then along the route of travel within the 1,000 ft supply lay, the last one passed
first, a lay past 500 ft marked LONG LAY with the closer off-route option beside it ("we'd lay
300–500 feet of supply line all day. It's when it gets further we need to think about relay
pumping, or finding something closer"); then within 300 ft of the address straight-line; then
anything within 1,000 ft; else the warning. Two picks, numbered on the map.

---

## 5. Things a designer will need

* The real screens: the operator takes screenshots readily; the review replay of any past
  call reproduces the kiosk view without waiting for a dispatch.
* The browser to test in is real Chrome or Firefox against `http://100.95.146.94/`; the
  in-app browser blocks the API port. Reload with `?nocache=N` after a build.
* The timings that shape the kiosk: phase 1 publishes at 16–19 s, the address arrives later on
  multi-unit calls, phase 2 lands at the end of the broadcast (about 45–75 s), auto-dismiss is
  5 minutes and pauses during a replay.
* The hall display's size, viewing distance and input method: not recorded, ask the operator.
* Everything on screen must survive with no internet except Street View, which is the one
  accepted exception and is labelled as such.
