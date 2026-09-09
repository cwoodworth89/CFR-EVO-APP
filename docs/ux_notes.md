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
| **Mobile setup** | nobody yet (#60, deferred pending redesign) | `DriverStationSetup.jsx`, reached only from the console's **MOBILE SETUP** button since 2026-09-08 |

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
| *"I can get to the FoV I want and I can save it… hit save it snaps back to zoom 1. If I leave and come back, the setting is lost."* (2026-09-08) | Three faults on one value, all fixed. `z \|\| 1` in two places rewrote zoom 0 — fully zoomed out — as zoom 1, because 0 is falsy; that is what reached the database. The tracking listener wrote the *zoom level* into the *degrees* field (#35a, corrected in the save path 2026-09-06 and missed here). A zoom 1..4 clamp pulled anything wider than 90° back on every mount, so even a correct save could not survive a reload | §3.9 records the platform limit that cannot be resolved |
| *"When I switch to aerial the black labels are difficult to see."* (2026-09-08) | Zone numbers turn white with a soft shadow on the orthophoto, and stay dark on the street basemap | — |
| *"'Saved Preferred View' is taking up a lot of room, and so is the label."* | A green dot and the heading in the tile header; full wording only in the expanded view | — |
| *"I don't need to see all of those hydrants. Just the recommended ones."* | The dispatch map draws only the picks, numbered, in NFPA 291 colours | — |
| *"I don't like the pop up boxes there. It makes it hard to understand the route. … show ALL the hydrants on the main route map, but only at a certain close in zoom."* (2026-09-07) | Picks are small numbered badges, no label box; the full hydrant layer draws on the route map from zoom 16 | — |
| *"Hydrants aren't being calculated or displayed on the main screen anymore."* | Picked by the operator's rule (§4 below), listed in the details box with how each was chosen | — |
| *"I'd rather have 'unknown' rather than guesses."* (2026-09-05) | The rule behind every empty state on the kiosk: the Tier 1 card, *(as heard)*, *NO HYDRANT WITHIN 1,000 FT*, *Awaiting location* | — |
| *"I'm not sure the value of a dedicated Kiosk Mode. I think the standby situation should be what is currently called Notifications/Explore."* … *"Calls should drop back down to the homepage explore/notifications."* (2026-09-08) | The kiosk's no-call idle screen is deleted and `KIOSK: IN-STATION MODE` is off the mode select. `App.jsx` now keys on `activeCall` alone, so a finished, closed or timed-out call lands on Explore. The idle screen's *DB Sync: Connected* and *Audio Card: Listening (UCA202)* badges were hardcoded strings that would have read green with the agent stopped (§6.1); they went with it | The hall display's between-calls behaviour is now a deployment question, not a screen — §3.8 |

| *"I like it interactive for now."* (2026-09-08) | The Street View save stays on the interactive SDK panorama: drag, walk the street, save. The panel was hardened the same day into one view object, a tested arithmetic module, one SDK loader and one hook (`google-imagery-streetview` skill, §3) | The simpler design considered and declined for now: a heading dial and width slider over the static image, no SDK at all. Revisit if the SDK keeps costing time |

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
| *"The box gets a little clipped and I can't get to what I assume is save button at the bottom."* (2026-09-08) | The card scrolls and the frontage explanation gives way to the form while placing | — |
| *"I'm not sure I want this, or the street view save button to be crew facing, only admin unlocked."* (2026-09-08, "doesn't need to change or secure at this moment") | **Built 2026-09-09**: a padlock at the right end of the workstation header; unlocked with the admin password it reveals the review screen entry, the arrival-point controls and the Street View save, and the four save routes answer 401 without the token. Stays unlocked 30 days unless locked (operator). | An auto-lock is a production feature, not built. See §3 |
| *"we can get rid of driver push setups from the dropdown menu. It's handled by the button Driver Alerts. But I think the name of that button needs to change to be more intuitive. Mobile Alerting? Mobile Setup?"* (2026-09-08) | `MOBILE: DRIVER PUSH SETUP` is off the mode select; the button is **📱 MOBILE SETUP**. The screen is a one-time QR pairing page, not a live alert feed, which is what *DRIVER ALERTS* read like. The select is now two entries, Explore and Admin | The screen behind it is still the #60 placeholder, still publishing the wrong ntfy topic |
| *"the emergency zone numbers as rendered are not very centred of their polygon outline"* (2026-09-08) | They were placed by `getZoneCentroid`, which computed a bounding-box centre despite the name. Over the 134 zones that put two labels (126, 134) **outside their own polygon**, 126 by 2.0 km, the median 139 m off. Now the pole of inaccessibility (`@mapbox/polylabel`), longitude scaled by cos(lat) first so the search is not run on a shape stretched 1.5× east–west. Verified through the shipped path: 0 outside, median label moves 121 m, zone 126 moves 1.77 km | — |
| *"when I switch to aerial map view, the black labels are difficult to see"* (2026-09-08) | Zone numbers turn white with a soft shadow when the base layer is the City orthophoto, and stay near-black on the pale street basemaps. One `baseStyle` expression in `MapBoard.jsx` feeds both the basemap and the overlay, so they cannot disagree | The picked-hydrant badges are also near-black, but on a filled NFPA-coloured circle with a white ring, so they read on any base. Not raised |

| *"When I search an address it doesn't highlight the parcel the same way it does in a dispatch call … good for checking out how the screen will kinda look during a dispatch event and for pre-planning."* (2026-09-08) | The parcel lookup now carries the outline (PostGIS geometry as rings), drawn on the workstation map and in the satellite tile; the centroid target icon is gone (*"we can get rid of that target emoji"*); the kiosk route map shades the parcel soft blue too (*"the target parcel had a soft blue shading"*) | — |

An earlier note here said Enter did not pick a suggestion in the address search. Withdrawn
2026-09-08: the handler selects the highlighted row, or the first one, on Enter; what the
automated runs hit was pressing it before the suggestions had loaded.

---

## 3. Open design decisions

1. **The details box.** Three options above. The operator dislikes the current floating box;
   what they want instead has not been said. 2026-09-08: the operator is working the design
   out with Claude Design, and #74 is shelved until it lands. Build to that design, not to
   the three options.
2. **Drop the cadastral tile; snap the route map instead.** Operator, 2026-09-07: *"I'm
   thinking about getting rid of that cadastral pip in the top right corner, and instead have
   a 'Zoom to Incident' or 'Zoom to Parcel' button that snaps the main routing window to a
   close in zoom area. Then they can go back and forth quickly between snap to call and
   re-centre map."* What that costs to build is small: the route map already draws the
   cadastral overlay and, from zoom 16, every hydrant, so a *ZOOM TO INCIDENT* button beside
   RE-CENTER is a `setView` on the destination at about zoom 18, and RE-CENTER is already the
   way back. The right-hand stack would be two tiles, satellite and Street View, each taller.
   **Built 2026-09-08** on both maps as one button that flips between *SNAP TO CALL*
   (the parcel plus the picked hydrants, close in, capped at zoom 18) and *RESET VIEW* (the
   whole route). The cadastral tile was dropped the same day; the stack is two taller
   tiles, satellite and Street View.
3. **Who may save.** Built 2026-09-09 to the operator's design: *"I like the lock/unlock
   button, somewhere discreet. That would then unhide all admin controls including the
   review panel selector dropbox option. I want it to use a simple password, but also to
   carry a 30 days unlock state unless specifically locked. When I move to production,
   it'll probably have an auto-lock feature."* The padlock is `hud/AdminLock.jsx`, the one
   session is `hooks/useAdminSession.js`, the gate is `require_admin` in the auth router
   on the two saves and the two older Street View override routes; reads stay open. Found
   on the way: the client logged every browser in by itself with the password in the source,
   so there had been no locked state anywhere; gone. **Open**: the auto-lock, for production.
4. **One hydrant, not two.** Operator, 2026-09-07: *"just showing the one best hydrant.
   Secondary hydrants can be picked by the drivers and officers of the next due trucks."*
   The picker already orders them; showing one is `picks.slice(0, 1)` on the map and in the
   details box, and the full layer at zoom 16 is where the next-due crews pick theirs. The
   one case that still wants a second line is the long lay: a first choice past 500 ft along
   the route with a closer off-route hydrant beside it is a decision, not a list, and the
   operator's own rule asked for both to be shown there. Not built; for the UX pass.
5. **Street View beside the map.** The Google Maps Platform Terms §3.2.3(e)(ii) forbid
   "Street View imagery and non-Google Maps on the same screen." The kiosk does that today.
   The operator noted it and deferred the ruling. The layouts that satisfy it are a
   full-screen Street View modal with the map hidden while it is open, a separate screen, or
   no Street View. This constrains any redesign of the right-hand stack.
6. **Progressive dispatch.** The operator's design for the kiosk to pop on the tones and fill
   in layer by layer (units, call type, address, grid, near roads, talk group, spoken grid),
   with the phone push firing once a driver can act. Spec, rulings and the measurement to run
   first: [`architecture/progressive_dispatch.md`](architecture/progressive_dispatch.md).
   Post-freeze.
7. **Every responding hall's route on one map**, each in its hall's colour, the home hall's
   solid and the others translucent. Operator's idea, on the post-freeze backlog.
8. **The review rating from the kiosk** (#52a) and **the mobile setup screen** (#60): both
   need a spec before design.
8. **What the hall display does between calls.** Operator, 2026-09-08: *"In real deployment,
   I would probably have the TV go to a sleep/standby, with CEC wakeup or some other
   method."* Removing the kiosk idle screen settled the software half — the browser sits on
   Explore — and left the hardware half open. CEC wake on a dispatch is a kiosk-machine
   concern (`cec-utils` against the snap Chromium session), not a React one, and nothing has
   been measured: how long the TV takes to wake, and whether that delay lands before or after
   the phase-1 publish at 16–19 s, decides whether it is usable at all. Not built.
9. **Street View field of view: settled 2026-09-08, and worth not re-opening.** The stored
   value is the **angle in degrees**, at full precision, in `parcels.streetview_fov`. Zoom is
   derived on the way to the SDK (`fov = 180 / 2^zoom`), never stored beside it. Nothing is
   clamped on **load** — that was the original defect, a saved framing rewritten every mount.

   The awkward part is a platform contradiction rather than a preference. The Street View
   **Static API** will not draw wider than **120°**; the **JS SDK** will not go narrower than
   its own minimum, which is **viewport-dependent** — measured at 127.31° in Chrome at 971px
   and 180° in Firefox. The two limits do not nest, so at the wide end the panel and the tile
   *cannot* agree. Three resolutions were built and tried the same evening:

   | Tried | Outcome |
   |:--|:--|
   | Clamp the wheel at 120° | **Broken.** Our listener and the SDK alternated forever — `setZoom` re-fires `zoom_changed`, so neither yields. Visible only with devtools *closed*, because a docked console narrows the pane and raises the SDK's floor above ours |
   | Clamp at save, so both surfaces draw one angle | **Rejected.** *"Snapping closer than acceptable"* — pulling a 180° framing back to 120° discards the width being zoomed out for |
   | Store what was framed | **Accepted.** Above 120° the tile is narrower than the panel it was saved from |

   The asymmetry is deliberate: **the expanded panel is the framing tool and is trusted; the
   tile is a thumbnail doing its best.** The SDK behaviour is recorded with its stack traces
   in [`standards/dependency-behaviour.md`](standards/dependency-behaviour.md). Open only if
   it ever grates: showing the FoV number in the save bar, so the tile being narrower is
   visible rather than puzzling.

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
* **A saved view is applied as saved.** Nothing clamps or rounds a stored camera on the way
  back in. Where a platform limit genuinely bites it is applied at the point of use — the
  Static API's 10..120° lives on the tile's URL and nowhere else.
* **One basemap, named for what it is.** `BASE_LAYERS` is `STREET`, `SATELLITE`, `CADASTRAL`.
  It held five names for two tile sets, and callers inherited a labels decision by picking a
  style name; labels are now a boolean, so changing what "street" means is one entry
  (2026-09-08). Turning *Road Names & Addresses* on at zoom 16+ deliberately takes labels
  **off** the basemap, because that toggle draws the cadastral overlay and its own names.
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
