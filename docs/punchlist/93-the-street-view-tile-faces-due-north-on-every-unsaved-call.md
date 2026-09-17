# Punch list #93 — The Street View tile faces due north on every call with no saved view

| | |
|:--|:--|
| **Status** | DEPLOYED, and **seen live by the operator on 2985 Delehaye: the compact tile points the right way** — which confirms the kiosk key admits the metadata endpoint. Expand snap-back regression **fixed `65a50d15`**, in the bundle lead built 2026-09-16 23:07 local (state check SAFE); **operator to confirm at the display**. The replay of the 41 remains the falsifier for the aim |
| **Severity** | 🟠 operational — the tile shows the right street the wrong way; the crew can see it is wrong, but it costs them the look at the property the panel exists for |
| **Area** | 🖥️ Kiosk · 🌐 Street View |
| **Origin** | Operator, 2026-09-16: *"I find the default view is often facing away from the property. Almost always, can we check? I feel like when we ask for that static image, it should be doing a better job."* |
| **Related** | `docs/external_calls.md` §4.1 · the `google-imagery-streetview` skill · #49 (arrival points) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

A `heading` **is** sent with every Street View Static request — and it is always **0, due north.**

`defaultViewForCall` (`frontend/src/utils/streetViewGeometry.js:97–110`) puts the camera at
`call.lat/lng` and aims it at `call.target.lat/lng`. But `toActiveCall` (`dispatchModel.js:78`)
sets `lat = target.lat`, so camera and aim point are **the same coordinate**; the
`tLat !== camLat` test fails and the heading falls to `0` (`:108`). Run on the six most recent
located dispatches, shaped exactly as `toActiveCall` builds them, all six produce
`location=<target>&radius=100&source=outdoor&heading=0&pitch=5&fov=90`.

So the operator's "almost always" has a mechanism: a house on the north side of an east–west
road looks right; one on the south side looks away; on a north–south road the camera looks
along the street. It is **not** the capture car's direction of travel, which was lead's guess.

**The default case is nearly every call.** `savedViewFromParcel` (`:70`) returns null unless
`public.parcels.streetview_heading` is set, and **58 of 71,214 parcels** have one. The
interactive Expand view uses the same `view.heading`, so it opens facing north too
(`hooks/useStreetViewPanorama.js:103, :125`).

**The point sent is the right one.** `address_resolver.py:370` sets `target.lat` to the
operator-verified entrance, else the computed frontage point, else the centroid; `front_lat`
is on every parcel, so a parcel call sends the frontage point — which is why the tile usually
shows the correct street, just the wrong way.

## The number (computed from stored coordinates only; no imagery, no Google request)

Over the 41 distinct frontage-point dispatches with parcel rings in the last 60 days, the angle
between heading 0 and the bearing from the frontage point to the lot centre (mean of the ring's
vertices): **median 83°; 27% within 45°, 27% between 45° and 90°, 46% over 90°** — the camera
pointing away from the lot. A proxy: it puts the camera at the frontage point, while the real
panorama stands a few metres along the road.

## Two ways to fix it — the operator's choice

**A. Ask Google where the panorama is, then aim at the lot.** One request to the Street View
**metadata** endpoint — `GET https://maps.googleapis.com/maps/api/streetview/metadata?location=<target>&radius=100&source=outdoor&key=<key>`,
same host, parameters and key as the image — returns `pano_id` and the panorama's
`location`. Then `heading = bearing(pano → lot centre)` and the image is requested by
`pano=<pano_id>` so the picture comes from the panorama the heading was computed for. **One
extra request per call, only when no view is saved**, from the browser. **Changes the §4.1
register row, so it needs the operator's yes (ruling 2026-08-31).** Whether metadata requests
are unbilled is recollection, **unverified** — check Google's Street View Static API usage
page before building (§7.3). Failure modes: offline → the image fails anyway and the panel's
existing fallback shows; `ZERO_RESULTS` → the existing "No Street View available"; any other
error → today's `location=` request with the heading from B rather than 0.

**B. No new call: aim from the frontage point to the lot centre**, both already on the record.
No register change. Its error grows with how far the panorama sits from the frontage point,
which cannot be measured offline. Either way the interactive Expand view already receives the
panorama position from its SDK `getPanorama` call (registered) and can use the true bearing
with no extra request.

Both replace the invented `0`. B alone fixes the mechanism; A fixes it precisely.

## Two domain questions before either is built (§7.6)

1. **Aim at the lot centre?** The frontage point would face the lot's edge; the project holds
   no building footprints.
2. **Non-parcel calls** — intersections, blocks, street sections: aim at the junction point,
   or leave them facing as they do?

## Falsifier

The "before" figure is offline and above. An "after" figure from coordinates alone would prove
nothing, since the heading is derived from those coordinates. The real test is the operator's
eye: replay the 41 dispatches in review mode with the new heading (41 metadata + 41 image
requests, with his permission) and mark each tile yes or no for "faces the property". The fix
is falsified if the yes rate is not clearly above the ~54% of cases within 90° of north today.

## Log

| Date | Event |
|:--|:--|
| 2026-09-16 | Raised by the operator. Measured by `frontend-kiosk-architect` from the code and six real records: heading is 0 on every unsaved call because camera and aim point are the same coordinate; 46% of recent parcel calls face away by the proxy. Two fixes and two domain questions put to the operator; nothing built |
| 2026-09-16 | **Ruled: option A** — "Let's get A going because it's a crew facing issue." Lead's reading, flagged for the operator to overturn: the yes is to A *as proposed*, so the aim point is the **lot centre** from `target.rings`, falling back to the **target point** for non-parcel calls. Sent to `frontend-kiosk-architect`: verify the metadata endpoint's billing against Google's usage page before building (stop and report if billed); one metadata request per unsaved call; image by `pano_id`; the fallback chain as proposed with **no heading of 0 anywhere** — an aim point that cannot be computed is said on the tile, not faced north; fix the `toActiveCall` root cause; saved views still win; the §4.1 register row rewritten in the same commit. The operator's replay of the 41 dispatches is the falsifier |
| 2026-09-17 | **Operator amended the no-heading condition:** "if no heading comes back we still need to allow the user to expand the window into interactive mode, at the nearest point to look and set a future point." Relayed to the frontend agent mid-build: the compact tile says no aimed view is available (never heading 0), **Expand still opens the interactive panorama at the nearest point** via the existing SDK path, and saving from there writes the parcel's `streetview_heading` so the next call takes the saved-view path |
| 2026-09-17 | **Built, `46c0774d`.** **Billing, verified (§7.3):** Google's *Street View Image Metadata* page — "Street View Static API metadata requests are available at no charge. No quota is consumed when you request metadata." — and the pricing list: SKU *Street View Metadata* (3168-48A9-5C8C), free usage cap **Unlimited**; *Static Street View* stays 10,000/month free then $7.00 per 1,000. Also checked: the endpoint answers browsers (`Access-Control-Allow-Origin: *` on a keyless probe; `REQUEST_DENIED` returns HTTP 200 with `status`), and `StreetViewLocation.latLng` is "the latlng of the panorama". **Request:** `GET https://maps.googleapis.com/maps/api/streetview/metadata?location=<call lat>,<call lng>&radius=100&source=outdoor&key=<key>`, one per call with no saved view, only after the saved-view lookup answers; then the image by `.../streetview?size=640x400&pano=<pano_id>&heading=<computed>&pitch=5&fov=90&return_error_code=true&key=<key>`. **Geometry** (`streetViewGeometry.js`): `lotCentre` `:102` (centroid relative to the first vertex — raw coordinates cancelled and gave the wrong centre, caught by the test), `aimPointForCall` `:135`, `headingToAim` `:146` (null when there is no direction, **never 0**), `defaultViewForCall` `:166` (**root cause fixed**: camera → lot centre, null when none), `streetViewMetadataUrl` `:194`, `viewFromMetadata` `:205` (camera at the panorama, pinned by `pano_id`), `resolveStreetView` `:234` (the whole chain as one pure function), `staticStreetViewUrl` makes no request without a heading (`:276`); the embed URL no longer rounds a null heading to 0. **Panel** (`StreetViewPanel.jsx`): metadata fetch `:118`, resolution `:139`, tile states "Finding the nearest panorama…" `:220` and "Street View not aimed" `:231`. **Expand** (`useStreetViewPanorama.js:106`): aims from the SDK's own `getPanorama` `data.location.latLng` at the same aim point, no extra request; a saved view carries no aim and keeps its heading; null is never sent to the SDK as 0. **Saved views win** — `savedViewFromParcel` unchanged, returned before anything else. **The chain as built:** (1) saved view → as today, no request; (2) no usable coordinates → Tier 1 standby; (3) lookup or metadata pending → spinner "Finding the nearest panorama…", no image yet; (4) offline → "Street View needs the internet"; (5) metadata `OK` → image by `pano=`, heading panorama → lot centre; (6) `ZERO_RESULTS` → "No Street View available / Google has no imagery near this location"; (7) any other status, failed fetch or no key → today's `location=` request with heading call point → lot centre, plus a console ERROR naming the status; (8) no direction at all → amber "Street View not aimed — No parcel outline and no panorama position to face it from. **Expand to look around.**", plus a console ERROR. **Never north.** If the image itself fails, the existing switch to the interactive view still applies — the operator's amendment is met by (8) and the Expand path. **Both aim choices are the proposal's, not a separate word — either can be overturned:** lot centre (polygon centroid of `target.rings`); calls without an outline aim at the call's own point. **Register:** §4.1 row appended (endpoint, one request per unsaved call after the lookup and before the image, same key and restriction, no cost, browser-callable, what a crew sees in 4/6/7/8, saved views never re-aimed); Part B row for the four Google doc reads and the keyless probe. **Verified:** `lint:crash` 0, full eslint 0/0 on the three `src` files, `build` clean, `test:node` **70/70** — bearings on both axes and all four quadrants within 1°, the lot centre both windings, the real record shape (lot 20 m east → 90 where it was 0), no heading → no image URL, the exact metadata URL, every branch of the chain (OK gives 321° for a panorama 20 m east of a lot 25 m north), OK-but-malformed, junction with and without a panorama; **all 41 measured dispatches now get a heading — 0 null, 0 north, spread 12/11/7/11 across the quadrants.** **Not verified:** nothing rendered; no metadata request made with the real key, so whether the kiosk key's API restriction admits the metadata endpoint is unconfirmed — Google files it under the same Street View Static API, and branch (7) covers a denial visibly. **Finding, backlogged:** Google says of `pano_id` "Panoramas may change IDs over time, so don't persist this ID"; saved views persist it in `public.parcels.streetview_pano_id`. A saved view could stop resolving when Google re-IDs the panorama; the tile would fail over to the interactive view, which searches from the saved position |
| 2026-09-17 | **Amendment built, `dade8273`.** With no aimed view the tile shows, in amber, "**No aimed view available** — No parcel outline and no panorama position to face it from. Expand to look around from the nearest panorama and save the view for next time." (`StreetViewPanel.jsx:232`); no image requested, no heading of 0. `ZERO_RESULTS` keeps "No Street View available"; resolving shows the spinner. **Expand is never gated.** `resolveStreetView` now returns `expandView` beside `view` (`streetViewGeometry.js:251`; panel `:157`): whenever the call has coordinates, Expand opens the hook's existing `getPanorama` search (NEAREST, outdoor, 50 m then 100 m) on the **nearest panorama to the call point**, facing the aim point from that panorama when a direction exists, else the SDK's own starting direction with a console ERROR — never an invented 0. **Saving from there** (the save bar, admin unlock as ruled) sends heading, pitch, fov, `pano_id` and `view_lat`/`view_lng`; the backend writes `streetview_heading/_pitch/_fov/_pano_id/_lat/_lng` (`schemas.py:150`, `routers/parcels.py:399–407`); `savedViewFromParcel` needs heading and camera position and the save writes both, so **the next call for that address takes the saved branch** — no metadata request, never re-aimed; all 58 existing saves have a camera position (checked on the live table). Verified: `lint:crash` 0, full eslint 0, `build`, `test:node` 71/71 (resolving, `ZERO_RESULTS`, `REQUEST_DENIED` and a failed fetch each give a null tile with a non-null `expandView`; a saved view expands as itself; no coordinates gives neither). Not seen on screen. **Lead built the bundle on the kiosk at 20:02 local with both commits** (and `0e04af21`, the dispatch map button merge) |
| 2026-09-16 | **First live look, operator, 2985 Delehaye:** "It's pointing in the right direction" — the aim works on a real call and the key's restriction admits the metadata endpoint (the medium unknown, closed). **"But when I expand I can't move the view using the arrows to travel. It keeps bringing me back to the original spot. Same if I pan or zoom."** A regression from `46c0774d`/`dade8273`: the interactive view is being re-applied after the user moves. Sent to the frontend agent to measure the retriggering dependency from the code and restore the discipline that the resolved view is applied once when the panorama opens and never again unless the call changes; the save bar must save the current POV, not the original |
| 2026-09-16 | **Regression fixed, `65a50d15`.** **Cause, traced in code:** `useKioskQueue` ticks `elapsedSeconds` every second (`useKioskQueue.js:299`, state in `App.jsx:60`), re-rendering App → KioskView → DetailStack → StreetViewPanel, none memoised; `46c0774d` computed `resolveStreetView` inline and `viewFromMetadata` builds a new view object on every call; the hook's apply effect depended on `[view, status]`, so it fired every second, and once the operator had moved `viewsMatch` failed and it re-set the original `pano_id` and POV — the snap back within a second. `position_changed`/`pov_changed` were not the trigger (they only write refs). Pre-#93 the same effect existed but the panel memoised `view` (`StreetViewPanel.jsx:88` at `46c0774d~1`), so it applied only on a real change — the discipline #93 dropped. **Fix:** the panel memoises the resolution again (`StreetViewPanel.jsx:140`), and the hook applies a view **once per `viewKey`** (`useStreetViewPanorama.js:213`; construction counts, `:159`), the key being address | call point | the saved view's pano, heading, pitch, fov (`StreetViewPanel.jsx:165`) — so a re-render or a metadata answer arriving while Expand is open never re-aims; only a new call or a saved view arriving does; closing and reopening Expand rebuilds on the resolved view. The save bar reads the live panorama (`readView` `:243`), and after a save the key changes, the one application finds `viewsMatch` true, nothing moves (the 2026-09-08 no-snap-on-save guard intact). Verified: `lint:crash` 0, full eslint (only the pre-existing `set-state-in-effect` at `RouteOverviewPanel.jsx:314`), `build`, `test:node` 72/72; the once-per-key behaviour is not unit-testable without the SDK — **the operator at the display is the proof.** Same commit: snap-to-call centring (handoff table) |
