# Punch list #93 — The Street View tile faces due north on every call with no saved view

| | |
|:--|:--|
| **Status** | RULED 2026-09-16 — **option A**, the operator's word: "Let's get A going because it's a crew facing issue." With `frontend-kiosk-architect` to build; the metadata endpoint's billing is verified first, and the §4.1 register row changes in the same commit |
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
