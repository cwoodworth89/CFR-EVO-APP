# Mobile accessibility review of the frontend

**Written 2026-09-09** at the operator's request (*"making this front end more mobile device
accessible"*). Written as a review and a plan under the feature freeze (CLAUDE.md §4); the
operator answered the questions the same day and then promoted the phone surface (*"right now
I want to get my android phone working"*), so **Phases 1 to 3 were built 2026-09-09 on branch
`claude/mobile-accessibility-review-v8cih3`: §7 records what was built and how it was
checked.** The rulings are recorded first, the plan in §4 is scoped to them, and §6 holds
what is still open. Phase 4 (the public endpoint) is not built.

Two sources of evidence, kept separate below because they carry different weight:

* **Read from the code** — every claim carries a `file:line`.
* **Measured on the built bundle** — `npm run build`, served by `vite preview`, rendered in
  the Chromium that ships with Playwright (build 1194) at six viewport sizes with touch and
  mobile emulation on. No API, tile server or broker was reachable from the machine that did
  this, so the hatch (#40) and the *COQUITLAM GIS OFFLINE* badge in the screenshots are the
  expected offline state, not findings. **The dispatch display was not rendered**: it needs a
  real call (CLAUDE.md §6.5) and the API is on the kiosk. Its findings are code-read only,
  and the way to see it on a phone is the review replay against `http://100.95.146.94/`
  (`kiosk-ui-audit` skill, §4).

---

## Rulings, 2026-09-09 (the operator's answers to §6 questions 1–6)

Quotes are the operator's. Each one changed the plan; the change is stated beside it.

| Asked | Ruled | What it changes |
|:--|:--|:--|
| Which surface | *"Ideally for crew members looking at call details, looking up cadastral details or property information. it critical."* and *"possibly having a small tablet mounted in the truck for helping parcel info and routing."* | **The crew's phone is the primary surface**, for two jobs: the current call's details, and looking up a property (parcel outline, hydrants by the operator's rule, arrival point, satellite). That is the console's Explore mode and the dispatch display together, phone first. A mounted in-cab tablet is a possible second surface, for the parcel and the route. |
| Devices | *"I'm developing on Android but the city uses apple products."* | **iOS Safari is the target; Android Chrome is the bench.** Every iOS-specific fact in §3 (input zoom, `dvh`, safe areas, wake lock, audio after a tap) is on the critical path, and the verification list in §4 needs a real iPhone and iPad, not only the emulator. |
| The hall display | *"flex is just a server. the screen will be touch sensitive tv."* | **Surface C is a touch TV.** The hover-only flag reasons and changed-field list (§3.1) are live crew-visible defects on the hall display, not phone findings, and promote under CLAUDE.md §7.1. Also corrects §1 row C: the Flex 5 is the server, not the screen. Recorded in `ux_notes.md` §1, §5 and the `kiosk-responsive-ergonomics` skill. |
| Network | *"the crews will be on wifi or data. I'll have a pubic facing end points"* | **Phones reach the system over the internet, not Tailscale.** This is a bigger change than a layout: see §3.6. It contradicts the row in [`ntfy_server_access_and_qr_spec.md`](../ntfy_server_access_and_qr_spec.md) §1 that records public exposure as *considered and rejected*; the operator's later statement is the plan of record, and that row should be rewritten when the exposure is designed, not silently. |
| What a phone shows first | *"Right now it would just be the ntfy push leading to Google maps. if it was a crew tablet, then address and route is important."* | The push is untouched. **The tablet's first screen is the address and the route**, large; everything else is second. |
| The push's map link | *"the push being google maps is fine for now"* | No external-call change; no `external_calls.md` row. Phase 4 no longer includes redirecting the push. |
| The access model on the public endpoint (§6 question 1, asked after the first six) | *"it'll probably be a per phone password to access. We have truck phones that each have their own login for ArcGIS Survey, we'll probably copy something similar not sure."* | **Provisional: one account per truck phone, with its own password, on the model of the department's existing per-phone Survey123 logins.** Phase 2's first screen on a phone is a sign-in that persists on the device the way the admin unlock does. Phase 4 item 3 is written to it below, with the two facts about the existing login that it has to change (§3.6). "Not sure" is recorded as such: the model can still move, and nothing is built on it. |
| Does the hall display keep reading without a login? | *"yeah that sounds like a good plan"* | **Ruled: reads stay open from the LAN and Tailscale, where `is_allowed_network` already draws the line, and a device token is required only from outside it.** The hall display never signs in and cannot log itself out mid-call. Phase 4 item 3 is built to this. |
| The in-cab tablet | *"it'll probably be an iPad, but this is theory."* | **Deferred.** Phase 3's tablet breakpoint and the in-truck type-size measurement wait until there is a tablet. The layout below `lg` already serves an iPad held upright (§7). |
| The freeze | *"right now I want to get my android phone working"* | **The phone surface is promoted; Phases 1 to 3 built the same day** (§7). Android Chrome is the bench as ruled; the iOS checks in §7 are still to run on a real iPhone. |
| Who reads the dash phone, and when (§8) | *"Driver before rolling."* | **The phone is read stationary, at arm's length, by the driver, in the seconds between the tones and rolling.** So: the alert is a confirmation screen, not a glance from across a cab, and normal reading sizes hold; the order of the choices is the driver's order, route first, then the parcel and its hydrants, which are the pump operator's business at the hydrant; nothing on it needs to be legible while moving, so no in-truck type-size measurement is owed for the phone. What is still open is whether the call stays on the phone until dismissed, since the same driver is at the hydrant on arrival. |
| Does the call stay on the phone? | *"Stay until cleared. another call would wait underneath"* | **Ruled and built:** below `lg` the five-minute clock is off (`useKioskQueue({ autoDismiss: false })`), the banner reads *Stays until cleared* and the button *Clear call*; a later call queues beneath with the existing *N New Calls Queued, Tap to View Next* banner, which is the hall display's queue unchanged. The restore window after a reload stays five minutes on both surfaces: a call from hours ago brought back as active would show an elapsed clock that reads as real (CLAUDE.md §6.1). |

---

## 1. "Mobile" is three different surfaces, and they cost different amounts

Nothing in the tree says which one is meant. Each has a different user, a different first
screen, and a different amount of work behind it.

| | Who | What they open | What exists today |
|:--|:--|:--|:--|
| **A. A crew member's phone, after the push** | drivers, officers, chiefs off site | the ntfy notification | The push carries the address, units, grid and talk group as text; its *Open Map Navigation* action opens **Google Maps over the WAN** ([`ntfy_broker.py:65-85`](../../services/dispatch_notifications/src/notification_service/ntfy_broker.py#L65)). No page of ours is involved. |
| **B. The operator's own phone or tablet** | one person | the console: search an address, set an arrival point, save a Street View, replay a call | The same `MapBoard` the kiosk shows, at whatever width the phone has. §3 is what that looks like. |
| **C. The hall display** | the crew in the hall | the dispatch display | **A touch-sensitive TV; the Flex 5 is the server only** (operator, 2026-09-09). The hardware spec's Pi option was a 10.1" 1280×800 capacitive touch display ([`hardware_specification.md:54`](../hardware_specification.md)); the 14" folding touchscreen in [`laptop_kiosk_setup.md:41`](../laptop_kiosk_setup.md) describes the server's own lid, not the crew's screen. |

The touch findings in §3.1 (hover-only information, target sizes) apply to **C as ruled**:
the hall screen is touched. The layout findings apply to A and B, which the rulings merge
into one phone-first surface for the crew.

---

## 2. What was measured

Six viewports: two phone orientations, two iPad orientations, the 10.1" kiosk display from the
hardware spec, and the 1,916×1,000 the operator's own screenshots use. The console in its
standby state, sidebar open, no address searched.

| Viewport | Left sidebar | Map | Interactive controls under 44 px | Header |
|:--|--:|--:|--:|:--|
| Phone portrait 393×852 | 320 px | **73 × 788 px** | 14 of 18 | wraps to three lines; mode select, MOBILE SETUP, ROAD CLOSURES and the padlock are **off the right edge** |
| Phone landscape 852×393 | 320 px | 532 × 329 px | 14 of 18 | fits |
| iPad portrait 820×1180 | 320 px | 500 × 1116 px | 14 of 18 | fits |
| iPad landscape 1180×820 | 320 px | 860 × 756 px | 16 of 18 | fits |
| Kiosk touch 1280×800 | 320 px | 960 × 736 px | 16 of 18 | fits |
| Operator 1916×1000 | 320 px | 1596 × 936 px | 16 of 18 | fits |

Three things the table says at once. **Nothing changes with width** except what gets cut
off: the sidebar is 320 px at every size because it is `w-80`, not a fraction. **The 44 px
column is the same at every size**, because the controls are sized in `text-xs` and `py-1.5`,
so this is a touch finding, not a phone finding, and it applies to the kiosk touchscreen as
it stands. And the **phone in portrait is unusable rather than cramped**: a 73 px strip of
map beside a sidebar that cannot be dismissed except by a 24 px tab.

The one screen that adapts is **MOBILE SETUP** (`DriverStationSetup.jsx`), which carries the
tree's only `md:` grid and reads correctly on a phone. It is also the #60 placeholder,
publishing a topic nothing writes to, and is deferred pending redesign.

The 44 px figure is a check, not a rule the project holds. **Recollection, not provenance
(CLAUDE.md §7.3)**: WCAG 2.2 SC 2.5.8 *Target Size (Minimum)* asks for 24×24 CSS px at level
AA; Apple's Human Interface Guidelines say 44×44 pt; Material says 48×48 dp. None of these
is in [`docs/standards/README.md`](../standards/README.md). If a minimum is adopted it needs
to be verified against the published text and added there as a row (§7.5). The counts above
used 44 because it is the strictest of the three and the one gloves argue for.

---

## 3. Findings

### 3.1 Across the whole tree

**There is effectively no responsive layout.** 18 uses of a Tailwind breakpoint prefix in
six files, most of them the address heading's `text-3xl sm:text-4xl` and the MOBILE SETUP
grid. Zero in `MapBoard.jsx`, `Header.jsx`, `LeftSidebar.jsx`, `RightSidebar.jsx`,
`KioskView.jsx`, `DetailStack.jsx`. The `kiosk-responsive-ergonomics` skill says to use
`sm:`/`lg:` for viewport adaptation; the convention is right and almost nothing follows it,
because until now there was one display.

**The chrome is fixed-width, and the widths are written down twice.**

| What | Width | Where |
|:--|--:|:--|
| Left sidebar (standby / with a dispatch) | 320 / 400 px | [`LeftSidebar.jsx:175`](../../frontend/src/components/hud/LeftSidebar.jsx#L175) |
| Right sidebar (road closures) | 320 px | [`RightSidebar.jsx:157`](../../frontend/src/components/hud/RightSidebar.jsx#L157) |
| Detail stack (console, address searched) | 380 px | [`MapBoard.jsx:513`](../../frontend/src/components/MapBoard.jsx#L513) |
| Dispatch details box floating on the route map | 288 / 320 px | [`RouteOverviewPanel.jsx:370`](../../frontend/src/components/kiosk/RouteOverviewPanel.jsx#L370) |
| Header mode select | min 220 px | [`Header.jsx:54`](../../frontend/src/components/hud/Header.jsx#L54) |
| Review table | min 800 px | [`ReviewTable.jsx:167`](../../frontend/src/components/review/ReviewTable.jsx#L167) |
| Verification sidebar | 448 px | [`VerificationSidebar.jsx:169`](../../frontend/src/components/review/VerificationSidebar.jsx#L169) |

The second copy is the one that bites. The route fit on the console pads the map by the
sidebar widths as literals, `paddingTopLeft: [340, 80], paddingBottomRight: [400, 80]`, in
[`MapBoard.jsx:342`](../../frontend/src/components/MapBoard.jsx#L342) and again in
[`MapViewControls.jsx:83`](../../frontend/src/components/map/MapViewControls.jsx#L83) and
[`:94`](../../frontend/src/components/map/MapViewControls.jsx#L94). **On a 393 px map that is
740 px of padding on a 73 px container.** Leaflet does not refuse. **Measured against the
installed Leaflet 1.9.4 in headless Chromium (§7.3a)**: the same two points and the same
padding give zoom 14 on a 1,596 px container and **`getZoom()` of `NaN` on a 73 px one**,
with nothing thrown. A map at zoom `NaN` requests no tiles; it is a blank pane that looks
like the tile-server failure the #40 hatch was painted to rule out. The threshold is wherever
the container is narrower than the two paddings added together, 740 px, so an iPad in
portrait with the sidebar open (500 px of map) crosses it too. Recorded in
[`standards/dependency-behaviour.md`](../standards/dependency-behaviour.md). This is a
functional defect on any narrow screen, not a cosmetic one, and the padding is the same 340
with the sidebar collapsed to 0, so the fit is off-centre on the kiosk today as well. The dispatch
map already does this correctly: it measures the details box (`panelRef.current.offsetWidth`,
[`RouteOverviewPanel.jsx:64`](../../frontend/src/components/kiosk/RouteOverviewPanel.jsx#L64))
rather than assuming it. Same pattern, one place, is the fix.

**The page is sized in `100vh`.** `h-screen w-screen` on the root
([`App.jsx:106`](../../frontend/src/App.jsx#L106)), `h-[calc(100vh-4rem)]` on the console body
([`MapBoard.jsx:411`](../../frontend/src/components/MapBoard.jsx#L411)). On a phone browser
`100vh` is the height with the address bar *hidden*, so while the bar is showing the bottom
of the layout sits under it. The dynamic unit `100dvh` follows the bar. **Verified against
the installed `caniuse-lite`, not memory (§7.3a)**: `viewport-unit-variants` fully supported
from Chrome 108, iOS Safari 15.4, Samsung Internet 21. The kiosk's snap Chromium is well past
108. Also absent: `viewport-fit=cover` on the `<meta viewport>`
([`index.html:5`](../../frontend/index.html#L5)) and any `env(safe-area-inset-*)` padding, so
on a phone with a notch or a home bar the 6 px call-status border and the bottom controls
sit under hardware.

**Two pieces of crew-facing information exist only on hover.** 56 `title=` attributes carry
text, and most are decoration. Two are not: the **reasons a call is flagged** are the
`title` of the *⚠️ N Flags* badge
([`ActiveAlertBanner.jsx:93`](../../frontend/src/components/hud/ActiveAlertBanner.jsx#L93)),
and the **list of fields that changed** is the `title` of the *⚡ UPDATED* badge
([`:103`](../../frontend/src/components/hud/ActiveAlertBanner.jsx#L103)). A touch screen has no
hover, so on the Flex 5 a crew member who taps the badge gets nothing. The badge says the
call has three flags and cannot say what they are. **This is live today if anyone touches
the hall screen, which is why §6 asks.** If they do, it is crew-visible under CLAUDE.md §7.1
and promotes ahead of the rest of this review. Everything else `title=` carries is either
repeated on screen or is help text.

**Targets are small everywhere.** Checkboxes are `w-4 h-4`, 16 px
([`LeftSidebar.jsx:372`](../../frontend/src/components/hud/LeftSidebar.jsx#L372) and the six
below it); the sidebar collapse tabs are `w-6 h-16`, 24 px wide
([`LeftSidebar.jsx:472`](../../frontend/src/components/hud/LeftSidebar.jsx#L472),
[`RightSidebar.jsx:269`](../../frontend/src/components/hud/RightSidebar.jsx#L269)); the close
× on the address card is `w-6 h-6`
([`TargetAddressCard.jsx:135`](../../frontend/src/components/hud/TargetAddressCard.jsx#L135)).
The checkboxes are the easy case: each already sits inside a `<label>`, so a `min-h` on the
label gives a full-row hit area without touching the box.

**Inputs are 12 px.** The address search
([`LeftSidebar.jsx:257`](../../frontend/src/components/hud/LeftSidebar.jsx#L257)), the admin
password ([`AdminLock.jsx:64`](../../frontend/src/components/hud/AdminLock.jsx#L64)) and the
arrival-point note and name
([`TargetAddressCard.jsx:94`](../../frontend/src/components/hud/TargetAddressCard.jsx#L94)) are
all `text-xs`. **Recollection (§7.3)**: iOS Safari zooms the page when a focused input's
font size is under 16 px, and the zoom does not undo itself on blur. The fix is 16 px on the
input, not `maximum-scale=1` on the viewport, which disables pinch zoom for everyone. Verify
on a real iPhone before relying on the number.

**Animations ignore `prefers-reduced-motion`.** Twenty-six `animate-pulse` / `animate-ping` /
`animate-bounce`, none behind Tailwind's `motion-safe:` prefix. Cheap to fix; a pulse on a
red EMERGENCY badge is a design choice worth keeping under `motion-safe:` rather than
removing. Related hygiene: `frontend/src/App.css` is Vite's template stylesheet, is
imported by nothing (`main.jsx` imports `index.css` only), and can go.

**A phone reaches four ports.** The page on :80, the API on :8000
([`apiClient.js:10`](../../frontend/src/apiClient.js#L10)), tiles on :8081
([`:44`](../../frontend/src/apiClient.js#L44)), the broker on :9001
([`useMqttListener.js:15`](../../frontend/src/hooks/useMqttListener.js#L15)). nginx proxies
`/api/` only ([`laptop_kiosk_setup.md`](../laptop_kiosk_setup.md), the server block). This is
not a layout finding but it decides whether a phone can use the app at all: every port has
to be open across Tailscale, and a phone on the hall Wi-Fi needs the kiosk's LAN address.
The MQTT hook already has a `wss://<host>/mqtt` branch for the SSL case, so someone
anticipated a same-origin proxy. Proxying `/tiles/` and `/mqtt` through nginx would make it
one port and one hostname, which is also what a QR code can encode.

### 3.2 The console (`MapBoard`) at phone width — measured

* **The header clips.** `h-16` with `justify-between` and no wrapping rule
  ([`Header.jsx:23`](../../frontend/src/components/hud/Header.jsx#L23)). At 393 px the hall
  label breaks across three lines and the mode select, MOBILE SETUP, ROAD CLOSURES and the
  padlock are pushed past the right edge, where the root's `overflow-hidden` hides them. The
  admin unlock is therefore unreachable on a phone in portrait. Landscape fits.
* **The sidebar is the screen.** 320 of 393 px. Collapsed, the map is the screen and the
  search is gone. On a phone the sidebar has to sit *over* the map as a sheet, not beside it.
* **The detail stack is three maps.** Searching an address mounts `DetailStack` at 380 px:
  the address card, a Leaflet satellite map, and Street View, each a third of the height.
  On a phone that is 97 % of the width and two live map instances plus an iframe or SDK
  panorama. One at a time, on tabs, is the phone shape.
* **The bottom-right corner is contested.** Leaflet's attribution, the build watermark
  ([`MapViewControls.jsx:148`](../../frontend/src/components/map/MapViewControls.jsx#L148)) and
  the *no map data* legend overlap below about 500 px.

### 3.3 The dispatch display (`KioskView`) — read from the code, not rendered

* **The grid is 8/4 at every width.** `grid grid-cols-12` with `col-span-8` / `col-span-4`
  ([`KioskView.jsx:220-236`](../../frontend/src/components/kiosk/KioskView.jsx#L220)). At 393 px
  that is a 262 px route map beside two 131 px tiles. Stacking below a breakpoint, map first,
  is the obvious shape; the question in §6 is what the crew needs first.
* **The banner is three columns that do not wrap.** Left (units, talk group), centre
  (address, incident), right (timers, Dismiss, TV mode) under `flex justify-between`
  ([`ActiveAlertBanner.jsx:57`](../../frontend/src/components/hud/ActiveAlertBanner.jsx#L57)).
  The address is the only element with a breakpoint. On a phone the address has to be the
  first row on its own, units the second, and the timer strip small.
* **The details box covers the map.** 288 px absolute at the map's top-left
  ([`RouteOverviewPanel.jsx:370`](../../frontend/src/components/kiosk/RouteOverviewPanel.jsx#L370)),
  and the fit pads by its width, so on a 262 px map the route is fitted into nothing. The
  operator dislikes this box on the kiosk too (#74, shelved while its home is designed in
  Claude Design). **A phone layout is a constraint on that design, not a second design**:
  whatever the box becomes has to collapse to a strip on a narrow screen.
* **Banners do not wrap.** The queued-call and Tier 1 banners are single `text-sm uppercase`
  lines ([`KioskView.jsx:167-193`](../../frontend/src/components/kiosk/KioskView.jsx#L167)).
* **Street View on a phone is cleaner than on the kiosk.** The Google terms forbid Street
  View and a non-Google map on one screen (`docs/standards`, §3.2.3(e)(ii); open on the
  kiosk). A phone that shows one tile at a time, full screen, satisfies it by construction.
* **Two phone-only behaviours to decide, not build yet.** A phone screen sleeps mid-call
  (the kiosk relies on the OS never sleeping; a page can ask for a screen wake lock, which is
  recollection and needs a browser-support check). And the queued-call chime is an
  `AudioContext` ([`useKioskQueue.js:75`](../../frontend/src/hooks/useKioskQueue.js#L75)),
  which mobile browsers keep silent until the page has had a tap.
* **Fine as they are**: the expand modals (`fixed inset-0 p-4 sm:p-8`) and the
  `onClick={resetTimeoutClock}` on the root, since a tap fires `click`.

### 3.4 The review screen (`DispatchReview`)

Desktop by construction: an 800 px minimum table beside a 448 px sidebar in a `flex gap-5`
row ([`DispatchReview.jsx:666`](../../frontend/src/components/DispatchReview.jsx#L666)), and
60 font sizes under 11 px in the verification sidebar. iPad landscape (1180) is below the
1,316 px the row wants, so even there the table scrolls sideways. **Recommendation: declare
it desktop-only in the screen itself** rather than half-fit it, and treat tablet landscape as
its floor. It is the operator's tool, not the crew's.

### 3.5 MOBILE SETUP (`DriverStationSetup`)

Renders correctly on a phone and is the #60 placeholder. If surface A is chosen its job
changes: the QR pairs the phone to the push topic *and* is where a phone learns the address
of the call page. The topic has to come from configuration, read once, for the reason #60
records.

### 3.6 The public endpoint (added after the rulings)

The operator will expose endpoints to the internet so crews on Wi-Fi or data can reach them.
What the frontend needs from that is small and specific; what the system exposes is not,
and it is recorded here so the decision is made with it in view.

**What is open today, without a login.** Every `GET` in the API: the dispatch list with
addresses, transcripts and units ([`dispatches.py:69`](../../backend/api/routers/dispatches.py#L69)),
the recordings (`/api/audio/{filename}`), parcels, hydrants, road closures, routing,
vocabulary, metrics. Only the four saves take `require_admin`
([`parcels.py:236`](../../backend/api/routers/parcels.py#L236),
[`:346`](../../backend/api/routers/parcels.py#L346),
[`streetview.py:83`](../../backend/api/routers/streetview.py#L83),
[`:126`](../../backend/api/routers/streetview.py#L126)). CORS is `allow_origins=["*"]`
([`server.py:136`](../../backend/api/server.py#L136)). Mosquitto is `allow_anonymous true`
([`mosquitto.conf:5`](../../services/mosquitto/mosquitto.conf#L5)), so anyone who can reach the
WebSocket port receives every dispatch as it is published. ntfy is plain HTTP by design
(`ntfy_server_access_and_qr_spec.md` §1). [`privacy.md`](../privacy.md) §2 takes the position
that all of this is public record, broadcast on open radio and published by the City; that is
the argument for exposure being acceptable, and it is the operator's argument to make, not
this review's. What this review says is only that **a public endpoint publishes the whole
archive to anyone who finds the URL unless an access model is chosen first**, and that the
access model decides the shape of the phone surface (a login screen, a shared code, a link
that carries a token, or nothing).

**What the existing login is, since "copy something similar" starts from it.** One
password, from `ADMIN_PASSWORD`, one role, and any username: `/api/auth/login` accepts
whatever `username` is sent and issues a 30-day JWT with `role: admin`
([`auth.py:77-104`](../../backend/api/routers/auth.py#L77), `TOKEN_LIFETIME` at
[`:28`](../../backend/api/routers/auth.py#L28)). There is no user table and no second role.
And **login is refused from any address that is not loopback, RFC 1918 or Tailscale**
([`auth.py:51-63`](../../backend/api/routers/auth.py#L51), enforced at
[`:70-75`](../../backend/api/routers/auth.py#L70)); nginx forwards the real client address, so
a truck phone on data would be answered 403 today before its password was read. A
per-phone account therefore needs, in the API: an accounts store (username, password hash,
role `device`, enabled flag, so a lost phone can be turned off); the role carried in the
token; a `require_login` dependency for the reads distinct from `require_admin`, which stays
on the four saves; and the network filter relaxed for device logins at the public origin
while the admin login keeps it. On the phone it is the same `apiClient` token path the
padlock uses, with a sign-in screen where the token is absent or expired.

**The reads and the hall display.** If every read requires a token, the hall kiosk on the
LAN needs one too, and a display that logs itself out mid-call is a crew-facing failure of
the kind CLAUDE.md §1 exists to forbid. The plan therefore assumes **reads stay open from
the LAN and Tailscale, exactly as `is_allowed_network` already draws that line, and require
a device token only from outside it.** The kiosk is untouched; the phone signs in. **Ruled
2026-09-09** (operator: *"yeah that sounds like a good plan"*).

**The phone does not need the broker.** A truck phone is woken by the ntfy push; the page
fetches the current dispatch from the API when it opens or returns to the foreground. That
removes Mosquitto from the phone path entirely, so anonymous WebSockets need not be exposed
publicly at all, and the one-origin work in Phase 4 shrinks to the API and the tiles. The
in-cab tablet, if it is to update live while mounted, is the one device that would want the
socket, and that decision waits on what the tablet is.

**What the frontend needs from it, whichever way that goes.**

1. **One HTTPS origin.** A phone page served over `https://` cannot open `ws://` or
   `http://host:8000` (mixed content is blocked), and the wake lock in §3.3 needs a secure
   context. So the API, the tiles and the broker have to be reachable as paths on the page's
   own origin: `/api/`, `/tiles/`, `/mqtt`. nginx already proxies `/api/`; the MQTT hook
   already has the `wss://<host>/mqtt` branch
   ([`useMqttListener.js:15`](../../frontend/src/hooks/useMqttListener.js#L15)); the tile base
   does not ([`apiClient.js:44`](../../frontend/src/apiClient.js#L44)). The clean rule is:
   **when the page is `https:`, derive same-origin paths; when it is `http:` on the LAN, keep
   the ports**, so one build serves the hall and the phones. The `VITE_*_BASE_URL` overrides
   are build-time and would force two builds.
2. **The kiosk stays offline-capable.** CLAUDE.md §1 is about the hall: the display must
   work with no WAN. A public endpoint is an additional way in for phones, not a dependency
   the kiosk acquires. Nothing in the hall path should start resolving a public hostname.
3. **A home-screen install for the mounted tablet**, so it opens full screen without
   browser chrome. iOS supports this through its own meta tags and a partial manifest
   (`caniuse-lite` marks `web-app-manifest` unsupported on iOS Safari; the install path is
   *Add to Home Screen*, which is recollection and needs checking on the device). Also
   needs HTTPS.

**Support facts, from the installed `caniuse-lite` 1.0.30001757, not memory:**

| Feature | iOS Safari | Chrome |
|:--|:--|:--|
| Screen Wake Lock (`navigator.wakeLock`) | 16.4 | 85 |
| Dynamic viewport units (`dvh`) | 15.4 | 108 |
| `env(safe-area-inset-*)` | 11.3 | 69 |
| `@media (pointer: coarse)` | 13.2 | 55 |
| Web Share | 14.0 | 128 |
| Web App Manifest | not supported (iOS uses its own install path) | 39 |

---

## 4. Action plan, scoped to the rulings

Phased so each phase is useful on its own. Sizes are S / M / L, one sitting to several days;
hours would be invented. **Order of value after the rulings: Phase 1 item 4 (the touch TV),
then Phase 2 (the phone property lookup, "critical"), then Phase 3, then Phase 4 once the
access model is chosen.**

### Phase 0 — record (S)

1. The target-size minimum and the viewport-unit facts go into
   [`docs/standards/README.md`](../standards/README.md) as rows, verified against the
   published text first (§7.3, §7.5). Nothing else here produces an operational value;
   layout is judgement (§7.1).
2. The public-exposure row in `ntfy_server_access_and_qr_spec.md` §1 is rewritten to the
   operator's plan when the exposure is designed.

### Phase 1 — foundation, every surface, no visible change on the hall display (S–M)

1. **Hover-only information becomes tappable.** The flag reasons and the changed-field list
   render as a tap-to-open list, or inline when there are three or fewer. **Crew-visible on
   the touch TV as ruled; the one item that may run ahead of the freeze.**
2. **Fit padding measured, not written.** One `useLayoutInsets` (or refs, as the dispatch
   map already does) feeding `fitTo` on the console and `MapViewControls`; delete the
   `[340, 80] / [400, 80]` literals. Fixes the `NaN` zoom on any container under 740 px and
   the off-centre fit with the sidebar collapsed.
3. **`100dvh`** with `100vh` as the fallback line before it; `viewport-fit=cover` and
   `env(safe-area-inset-*)` padding on the root and the call-status border.
4. **Touch targets.** `min-h-11` on the layer-toggle labels, 44 px wide sidebar tabs, 44 px
   close buttons. Cite the standard from Phase 0 in the class comment.
5. **16 px inputs** on the search, password and arrival-point fields, at least under
   `pointer: coarse`. This is the iOS focus-zoom fix and iOS is the target.
6. **Header reflow.** Below `md:` the hall label shortens to `Hall 1`, the mode select and
   the two buttons move into one overflow menu, the padlock stays visible.
7. **`motion-safe:`** on the twenty-six animations. Delete `App.css`. Consider Tailwind's
   `hoverOnlyWhenSupported` so `hover:` states do not stick after a tap on the TV.
   **Verified in the installed Tailwind 3.4** (`corePlugins.js:204`): with the flag on,
   `hover:` compiles to `@media (hover: hover) and (pointer: fine) { &:hover }`; off, it is a
   bare `&:hover`, which a touch tap sets and nothing clears.
8. **A viewport smoke test** in `frontend/tests/`, run with `node --test` against
   `vite preview` the way this review was done: no horizontal overflow, header controls
   inside the viewport, map at least 60 % of the width at 393 px, no interactive control
   under 24 px. It needs no dispatch, so it fabricates nothing (§6.5).

### Phase 2 — the crew's phone: property lookup (M) — "critical"

The console below `md:` (768 px), phone first, iOS Safari first. Above `md:` nothing changes.

* **A device sign-in first**, on the phone only: username and password for the phone's
  account, stored the way the admin token is, shown again only when the token is absent or
  expired. The hall display never sees it (§3.6, the reads and the hall display).
* **Search is the screen.** The address field sits at the top over the map; the layer list
  and basemap toggle live in a bottom sheet, closed by default. A crew member types an
  address, the map snaps to the parcel with the picked hydrants (the existing SNAP TO CALL),
  and the address card opens as a sheet from the bottom: address, building name, arrival
  point as set and why, the hydrant picks with how each was chosen. Read-only unless the
  padlock is unlocked, exactly as on the console.
* **One detail tile at a time.** Satellite and Street View are tabs in the sheet, one map
  mounted at a time; Street View full screen only, which also satisfies the Google terms on
  that surface.
* **Road closures** as a drawer, same data, no filter controls (a crew member should not be
  able to hide a closure; the dispatch map already applies this rule).
* Everything on it is the same components on a different frame: `DispatchTargetLayer`,
  `PickedHydrantsLayer`, `TargetAddressCard`, `DetailStack`. The work is the frame, the sheet,
  and the measured fit from Phase 1.

### Phase 3 — the crew's phone and the in-cab tablet: the call (M, blocked on #74)

* **Phone:** `grid-cols-1` below `md:`; the address and incident first, the unit and ETA
  chips second, the route map third at about 55 % of the height, then one detail tile at a
  time. The queued-call and Tier 1 banners wrap. The details box collapses to a strip.
  **Built to the #74 design, not ahead of it.**
* **Tablet (address and route, as ruled):** at tablet width the map takes the screen with
  the address and incident as a large banner; the detail tiles are behind a tab, not beside
  the map. This is a second breakpoint (`lg:`), and it is the one that decides whether a
  mounted 8–11" tablet in landscape reads at arm's length in a moving cab. Nothing in the
  project records that viewing distance; it is a measurement to take in the truck before the
  type sizes are chosen (§7.6), not a number to pick.
* **Behaviour on a phone**, to decide in §6: whether the five-minute auto-dismiss and the
  queue apply, and whether the phone shows the current call only or a list of recent calls.
* **Keep the screen on** with the wake lock (iOS 16.4+) once the page is HTTPS; and the
  chime plays only after a tap, which on a phone means never unless the page asks for one.

### Phase 4 — public-endpoint readiness (L, blocked on the access model)

1. **Same-origin derivation** in `apiClient.js` and `useMqttListener.js`: `https:` pages use
   `/api/`, `/tiles/`, `/mqtt` on their own origin; `http:` pages keep today's ports. One
   build for the hall and the phones.
2. **nginx proxies `/tiles/`** beside `/api/` (the tile server is `GET`/`OPTIONS` only and the
   `mbtiles-tile-server` skill has the constraints). `/mqtt` only if the in-cab tablet is to
   update live; the phone polls the API on open and does not need the broker (§3.6).
3. **Per-phone accounts** (provisional ruling): the accounts store, the `device` role in
   the token, `require_login` on the reads from outside the LAN and Tailscale, the login
   network filter relaxed for device accounts at the public origin, and a way to disable
   one phone's account. On the phone, the sign-in screen from Phase 2 and nothing else.
4. **Home-screen install** for the tablet: iOS meta tags and a manifest, full-screen, a
   named icon, and the stale-chunk failsafe checked under that mode (a home-screen app has
   no reload button; the #44b card's *Ctrl+Shift+R* advice does not apply).
5. The exposure itself (TLS, hostname, rate limits, what ntfy does over HTTPS) is
   infrastructure and is the operator's, not this plan's.

### Verification

Phase 1 and 2 are checked by the smoke test above, then on a real iPhone and iPad against
the public endpoint once it exists, or against `http://100.95.146.94/` on Tailscale until
then (the in-app browser blocks the API port; use Safari, `ux_notes.md` §5). Android Chrome
is the bench, not the sign-off. Phase 3 is checked by the review replay on those devices,
which is a real call through the live path. The touch TV is checked on the touch TV.

---

## 5. What this rests on, and what would prove it wrong (§7.6)

| Assumption | The cheapest thing that falsifies it |
|:--|:--|
| A crew member's phone is an iPhone at about 390–430 CSS px wide, in portrait | The department's phones turn out to be something else, or are used landscape in a cradle. Ask before Phase 2 chooses its breakpoint. |
| The mounted tablet is an iPad-class device, 8–11", landscape | It is a small Android tablet or a phone-sized unit. Phase 3's `lg:` line moves. |
| Crews will reach the system over a public HTTPS origin | The exposure is not built, or is VPN-only after all. Then Phase 4 shrinks to item 1 and the tablet install. |
| Per-phone accounts, on the Survey123 model | Ruled provisionally 2026-09-09 ("not sure"). If it moves to a shared code or a link-carried token, Phase 4 item 3 shrinks and the sign-in screen goes. |
| Reads stay open from the LAN and Tailscale; a token is required only from outside | Ruled 2026-09-09. No longer an assumption. |
| The hall screen is a touch TV | Ruled 2026-09-09. No longer an assumption. |
| The `dvh`, wake-lock, safe-area and target-size facts | `caniuse-lite` (checked, table in §3.6), the WCAG 2.2 text and an actual iPhone (not yet checked). |
| The 8/4 grid and the banner are the shape to keep above `lg:` | The #74 design lands with a different layout. Then Phase 3 is written against that. |
| `lg` (1024 px) is the right line for the phone layout | A device between 1024 and about 1100 px wide turns up: it gets the desktop columns and a map about 300 px wide. Measured 2026-09-09: `md` (768) left a landscape phone a 152 px map and an upright iPad 120 px, which is why the line moved. |

---

## 6. Questions still open, in the order they gate the plan

Answered 2026-09-09 and recorded above: which surface, which devices, whether the hall
screen is touched, how crews reach the system, what a phone shows first, the push's map
link, (provisionally) per-phone accounts, and that the hall display never signs in. Still
open, and asked one at a time:

1. **Can the Android phone reach `http://100.95.146.94/` today**, over Tailscale or the
   hall Wi-Fi? That is how §7 gets checked on the real device before the public endpoint
   exists. The API port must be reachable too; the in-app browsers block it (`ux_notes.md` §5).
2. **On a crew phone, is it the current call only, or a list of recent calls too?** And do
   the five-minute auto-dismiss and the queue apply, or does a call stay until closed?
3. **The details box (#74) is with Claude Design.** Should the phone layout wait for that
   design, or should "collapses to a strip on a narrow screen" be a requirement handed to it?
4. **Is the review screen ever wanted on a phone**, or is a tablet in landscape its floor?
   May it say so on screen?
5. **The freeze.** Review-only until it lifts, or Phase 1 on this branch now? Item 1 (the
   touch TV's hover-only information) is the one that may deserve promoting on its own.
6. **Anything beyond screen size?** Colour vision against the green routine and red
   emergency pair and the four hall colours, text size, gloves, a bright cab in daylight
   against the dark palette.
7. **A screenshot of the console on your own phone today**, to sit beside the emulated ones.

---

## 7. What was built, 2026-09-09

Phases 1 to 3 as scoped in §4, on the branch named at the top. Every change is either
below the `lg` line (1024 px), under a coarse pointer (`touch:`), or a fit that now measures
what it used to assume. **Above `lg` with a mouse, the console renders byte-for-byte as
before**: the 1,916 px screenshot after the change differs from the one before by the build
stamp only. The dispatch display above `lg` keeps every class it had.

### The line, and the variant

* **`lg`, not `md`.** The plan said `md` (768 px). Measured on the first build: a landscape
  phone at 852 px and an iPad held upright at 820 px got the desktop columns and were left a
  152 px and a 120 px map. The columns need about 1,000 px to leave a map worth having, so
  the line is Tailwind's `lg`, and `hooks/useCompactViewport.js` says the same thing in
  JavaScript for the decisions that are not CSS.
* **`touch:`** is a Tailwind variant added in `tailwind.config.js` for `@media (pointer:
  coarse)`: the hall's touch TV, a phone, a tablet. It sizes targets and inputs and changes
  nothing under a mouse. `hoverOnlyWhenSupported` is on, so a tap on the TV no longer leaves a
  button lit.

### Phase 1, the foundation

| Item | Where |
|:--|:--|
| Flag reasons and changed fields open on a tap, inline under the badges | `hud/ActiveAlertBanner.jsx` |
| Fit padding measured from the map and the floating box, clamped so Leaflet can never see a negative fit area; the console and the dispatch map share it | `map/fitPadding.js`, tested in `tests/fitPadding.test.mjs` (8 cases) |
| `h-dvh` with a `100vh` fallback, `viewport-fit=cover`, safe-area padding on both roots | `index.html`, `index.css`, `App.jsx`, `main.jsx`, `MapBoard.jsx`, `KioskView.jsx` |
| Targets: layer-toggle rows 44 px tall under `touch:`, sidebar tabs 36 px wide, close and expand buttons taller | `LeftSidebar.jsx`, `RightSidebar.jsx`, `TargetAddressCard.jsx`, the two tiles |
| 16 px inputs under `touch:` (the iOS focus-zoom rule) | search, home hall, admin password, arrival-point note and name |
| Header on one row at every width; the padlock reachable on a phone | `hud/Header.jsx` |
| The 26 animations behind `motion-safe:`; `App.css` deleted (Vite's template, imported by nothing) | tree-wide |

### Phase 2, the phone console

Below `lg` the left sidebar is a sheet over the bottom of the map with a handle, open on
arrival with the search at the top, and it folds to the handle when an address is picked so
the parcel is the screen. The detail stack is a sheet with tabs, Details, Satellite and
Street View, one map mounted at a time, and it folds to its tab bar. Road closures are a
drawer from the right. The floating controls move clear of the sheets; the build watermark
goes.

### Phase 3, the dispatch display on a phone

Below `lg` the 8/4 grid is a column: the banner stacked with the address first, the route
map at just over half the height, then the detail tiles as tabs. The details box spans the
top of the map and starts folded; the fit pads by its height instead of its width. The
queued-call and Tier 1 banners wrap. TV mode is hidden, being the hall's control. **Built to
the code, not rendered**: see below.

### Checked

* `npm run lint:crash`, `npm run build`, `npm run test:node` (28 tests, the 8 new ones among
  them): all pass.
* `frontend/scripts/viewport_smoke.mjs` against the built bundle in headless Chromium at five sizes,
  393×852, 852×393, 820×1180, 1280×800 and 1916×1000, with touch and mobile emulation: no
  horizontal overflow, no control off screen, the map at least 60 % of the width below `lg`,
  a real zoom after the fit, no page errors. The property lookup was driven end to end with
  the address search answered by the app's own known-buildings table, so nothing was invented
  (CLAUDE.md §6.5). Screenshots were reviewed by eye at each size.
* **Not checked here, to be checked on the device:** the dispatch display on a phone (needs a
  real call: replay one on the phone), iOS Safari (the sandbox has Chromium only; the bench
  is Android as ruled), the touch TV.

### Seen on the way, not fixed

* The satellite tile's Leaflet zoom control sits under its header pill at every size, so its
  `+` is covered. Pre-existing; one line to move the control to the bottom right.
* `animate-in`, `fade-in` and `slide-in-from-*` appear throughout and do nothing: they are
  from a Tailwind plugin that is not installed. Harmless; the transitions they name never ran.

---

## 8. The driver's phone on the dash: the operator's design (2026-09-09)

Stated after §7 was built, for the phone mounted on the truck dash. Quoted whole, because the
shape is the ruling and the contents are not yet:

> *"For receiving a dispatch to a driver's phone, mounted on the truck dash, I think it
> should pop up with a dispatch alert with the information, and then they can choose*
> *Show Route (navigate from inside pushes to Google maps) / Show street view / Show
> satellite view (with cadastral) / Show parcel information (with cadastral and hydrants) /
> Show dispatch details.*
> *the exact contents and details tbd, open to suggestions. I don't want to cram everything
> on a small screen"*

**What this is, in the code's terms.** An alert screen that is the call's home, and five
full-screen views one tap away, each with a strip at the top carrying the address and the
way back. Four of the five exist as components today; the frame and the alert are new.

| Choice | What exists | What it needs |
|:--|:--|:--|
| Show Route | `RouteOverviewPanel` (the route from the hall, closures, picked hydrants) and the NAVIGATE (GPS) link in the console, already a registered Google Maps hand-off | The details box off the map; NAVIGATE as the one button on the view |
| Show street view | `StreetViewPanel` expanded, full screen | Nothing; and alone on the screen it satisfies the Google terms (§3.2.3(e)(ii)) that the kiosk layout does not |
| Show satellite view (with cadastral) | `PropertySatellitePanel`: the City orthophoto with the parcel outline | The cadastral lines are on the main map, not on this tile; adding the overlay is the one change |
| Show parcel information (with cadastral and hydrants) | SNAP TO CALL on the route map (parcel, cadastral, numbered hydrant picks at zoom 18) plus the address card and the hydrant list with how each was chosen | A screen of its own rather than a state of the route map |
| Show dispatch details | The banner and the details box: units and ETAs, talk group, grid and its source, cross streets, flags, the pre-plan PDF, the timers | Laid out as a list instead of a banner |

**Suggestions, not rulings.**

1. **The alert holds what the run sheet reads out and nothing else**: address, incident,
   units, grid, talk group, large, with the choices as full-width buttons below. The
   elapsed time and the flags are on Details. That is the "don't cram" rule made concrete.
2. **Two ways in, one screen.** A phone left open on the dash can pop the alert itself the
   way the hall display does, since the app already switches to the call when one arrives,
   and a wake lock keeps it lit. A phone in a pocket is woken by the ntfy push, whose tap
   opens the same call screen. The push then carries one action, *Open dispatch*, beside the
   Google Maps one it has now; ntfy's limit on action buttons is recollection (three) and is
   checked against the pinned v2.11.0 before it is relied on.
3. **Satellite and parcel may be one view with a basemap toggle**, aerial or street, both
   with the cadastral lines, the parcel outline and the hydrant picks. The kiosk dropped its
   cadastral tile for the same reason (SNAP TO CALL showed the same thing). Four choices
   instead of five, if the operator agrees; kept as five if the aerial view is wanted with
   nothing drawn on it.
4. **Order the buttons by when they are needed**: Route first, then Parcel, Street View,
   Satellite, Details.
5. **Everything but Street View and the Google Maps hand-off is served by the kiosk.** Over
   the hall Wi-Fi or Tailscale this works now; in the truck on data it needs the public
   endpoint (Phase 4, §3.6). The design can be built and tested on the operator's phone
   before that exists.

**Ruled 2026-09-09: the driver, before rolling** (the rulings table). So the alert is read
stationary at arm's length and may ask for a read, not a glance; the choices are in the
driver's order, Route first, then Parcel, whose hydrant pick is the same person's business at
the hydrant on arrival.

**Ruled 2026-09-09: the call stays until cleared, and a later call waits underneath**
(built; the rulings table). **Open, in order:** whether satellite and parcel are one view or
two; the current call only or recent calls too (§6).

<!-- audit-ok: frontend/src/App.css -- deleted 2026-09-09; the text above records the deletion -->
