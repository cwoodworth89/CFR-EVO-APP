# Punch list #35a — Google Street View panel still not working

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | operational |
| **Area** | 🖥️ Live Operation Batch, 2026-08-23 |
| **Blocks** | 3 |
| **Origin** | `debug_and_qa_punchlist.md` L2092–4431 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 35. Google Street View panel still not working
> **Status**: ⚠️ **Open — cause identified, not yet confirmed on the kiosk.**

`frontend/src/components/kiosk/StreetViewPanel.jsx:8`:

```js
const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';
```

Two hard requirements, either of which produces the blank panel seen in the screenshot:

1. **The key must be present at BUILD time.** Vite inlines `import.meta.env.*` when
   `npm run build` runs — it is not read at runtime. The key lives in `frontend/.env.local`,
   which is **git-ignored** (CLAUDE.md §3.6) and therefore *not* synced by `git pull`. If the
   kiosk's `.env.local` lacks the key, every build there produces `apiKey = ''` and the panel
   renders empty no matter how many times the code is corrected locally.
2. **It needs WAN.** `:135` gates on `isOnline`, and `:301` loads
   `https://maps.googleapis.com/maps/api/js`. Street View cannot work offline, which is a
   standing exception to the §1 offline-first rule and is worth stating explicitly somewhere
   the next reader will find it.

**Next step is a two-minute check on the kiosk**, not a code change:
`grep -c VITE_GOOGLE_MAPS_API_KEY /home/tcfire/CFR-EVO-APP/frontend/.env.local`, then confirm
the built bundle actually contains the key. If it is missing, `scp` the file and rebuild.
**Not verified from here** — the check needs the kiosk.

---

---

## 35 (revised). Street View: the API-key hypothesis was wrong
> **Status**: ⚠️ **Open — cause NOT yet identified. Needs the kiosk browser console.**

Checked directly on the kiosk. **All three prerequisites are satisfied**, so the theory
recorded in #35 above is withdrawn:

| Check | Result |
|:--|:--|
| `frontend/.env.local` present | yes — 285 bytes, dated Aug 9 |
| `VITE_GOOGLE_MAPS_API_KEY` set in it | yes |
| Key baked into the built bundle | yes — found in `dist/assets/MapBoard-*.js` |
| `maps.googleapis.com` reachable from the kiosk | yes — HTTP 200 in 0.17 s |
| Build freshness | `dist/index.html` 2026-08-23 12:26 (today) |

So the key is present at build time, the SDK host is reachable, and the bundle is current.
The blank panel is something else.

**What the code does when the key IS present** (`StreetViewPanel.jsx:466-487`): it renders an
*empty* `div` and relies on the Google SDK to inject the panorama into `containerRef`. The
`<iframe>` fallback is only rendered when `!apiKey` or `sdkError`. So any silent failure of
`new google.maps.StreetViewPanorama(...)` leaves a genuinely empty container — and the
skeleton loader is cleared unconditionally by a 3.5 s timer (`:283-285`) whether or not the
panorama ever mounted. **A failed load and a successful one look identical to the operator.**

Plausible causes, none verified: the Maps JS API key lacking Street View / billing
entitlement (Google returns an error to the console, not to the callback), the newer SDK
loader requirements, or `hasCoords` false for the call in question.

**Next step needs the operator**: open the kiosk browser console (F12) with a call active and
capture any `maps.googleapis.com` errors. That is the fastest path — the in-app browser cannot
drive an MQTT-driven kiosk view.

**Worth fixing regardless of cause**: the 3.5 s timer that clears the loading state without
checking whether the panorama mounted. An unmounted panorama should surface an explicit
"Street View unavailable" state rather than an indistinguishable black rectangle (§6.1 — the
failure is currently invisible).

---

---

## 35 (updated). Street View: offline exemption documented; root cause still unknown
> **Status**: ⚠️ **Still open on the failure itself.** The offline exemption is now
> documented as an accepted risk (operator, 2026-08-30).

**The exemption is recorded** in a header comment on
[`StreetViewPanel.jsx`](../../frontend/src/components/kiosk/StreetViewPanel.jsx) — where the next
reader will actually hit it, rather than buried in a doc. Street View is fetched live from
`maps.googleapis.com` and cannot be cached the way the municipal orthophotos are, so it is the
one surface that does not satisfy CLAUDE.md §1. Accepted because it is a pre-arrival
convenience: everything dispatch-critical (address, grid, parcel outline, satellite, routing)
is served locally and is unaffected when the panel is blank.

**The blank panel is still unexplained.** All three prerequisites were verified on the kiosk
and all pass: `.env.local` present with the key set, key inlined into `dist/assets/MapBoard-*.js`
(Vite inlines at build time), and `maps.googleapis.com` reachable — HTTP 200 in 0.17 s. The
earlier "missing API key" theory is **withdrawn**.

**Leading hypothesis, unverified**: the key lacks Street View or billing entitlement, which
Google reports to the browser console rather than to the SDK callback. **Needs the kiosk
browser console (F12) with a call active** — that is the only remaining diagnostic.

**Worth fixing regardless of cause**: a failed SDK load and a successful one are currently
indistinguishable. The loading spinner is cleared by a 3.5 s timer whether or not the panorama
mounted (`:283-285`), and the `<iframe>` fallback renders only when the key is *missing* or
`sdkError` is set — so a silent `StreetViewPanorama` failure leaves a black rectangle with no
error state (§6.1).

---

---

## 35a (update). A real 500 found and fixed — but not declared the root cause

> **Status**: ⚠️ **Still open on the blank panel. One contributing defect removed 2026-08-31.**

`GET /api/streetview-overrides` was returning **500 on every request**, confirmed against the
running kiosk before and after the fix. `backend/api/routers/streetview.py` read `r.lat` /
`r.lng`; those columns were renamed to `centroid_lat` / `centroid_lng` earlier the same day
and this call site was missed, so the endpoint raised `AttributeError` on every call. The
frontend requests it from four sites in `apiClient.js`.

Now returns **200 with 65,540 override entries**.

**This is not being claimed as the cause of the blank panel**, and the distinction matters.
This item's own history records that the API-key hypothesis was asserted and turned out to be
wrong, and that all three prerequisites were verified on the kiosk with the panel still blank.
A broken overrides endpoint would lose *camera orientation*, not the imagery itself. Whether
it also blanks the panel needs one look at the kiosk browser console with a call active —
which is what this item has needed all along.

Found by running the full backend suite, not by investigating Street View. It is the second
casualty of the `lat` → `centroid_lat` rename; the first was the parcel import's own
verification query. Both were invisible because nothing exercised them.

---

## 35a (cause). `ApiTargetBlockedMapError`: the key is not allowed to use the Maps JavaScript API

> **Status**: 🟡 **Cause confirmed 2026-09-06 in the browser. The fix is a setting on the API
> key in the Google Cloud console, which needs the operator's sign-in (passkey).**

Reproduced in Chrome against the kiosk build (`http://100.95.146.94/`, Explore mode, the
address search for 3030 Gordon Ave mounts the same `DetailStack` the kiosk uses). The console,
with `console.error` hooked before the SDK loaded:

```
Google Maps JavaScript API error: ApiTargetBlockedMapError
https://developers.google.com/maps/documentation/javascript/error-messages#api-target-blocked-map-error
Google Maps JS SDK auth failure triggered. Check Google Cloud Console 'Maps JavaScript API' status.
```

Google's page for that code, read the same day: *"This API key is not authorized to use this
service or API. Please check the API restrictions settings of your API key in the Google Cloud
console to ensure that all of the APIs and services you need to use are correctly specified in
the list of enabled APIs."* Not `ApiNotActivatedMapError` (the API is not enabled on the
project) and not `RefererNotAllowedMapError` (the kiosk's origin is not an allowed referrer):
the key exists and is accepted, and its **API restrictions** list leaves out the Maps
JavaScript API. The Maps **Embed** API is on that list, which is why the `<iframe>` fallback
renders a panorama and the panel is not blank today; what is lost is the interactive view and
the operator's *Save Preferred View*, which reads the camera from the SDK panorama.

**The fix, for the operator** (console, signed in as the project owner):
Google Cloud console → APIs & Services → Credentials → the key ending in `...XRLsY` → *API
restrictions* → add **Maps JavaScript API** (keep Maps Embed API) → Save. Takes effect within
minutes. Then reload the kiosk page with a call or a searched address: the amber
*INTERACTIVE VIEW UNAVAILABLE* strip should be gone and the console clean.

**Done in code the same day** (CLAUDE.md 6.1): the fallback used to be indistinguishable
from the real panorama, and the save button wrote the initial camera values back and reported
success. The panel now shows an amber strip naming the failure and disables the save with the
reason. `loading=async` is not set on the SDK script (a performance warning, not a defect);
one line, post-freeze.

The in-app browser could not reproduce this: it blocks the page's requests to `:8000` and
`:9001` (`ERR_BLOCKED_BY_CLIENT`), so no address ever resolves there. Real Chrome did it in
one search.

Verified in Chrome after the kiosk build (`32a4386`, bundle `index-D700fJrZ.js`): the strip
renders over the embed and the button reads *No interactive view to save*, disabled. One
thing learned on the way: nginx sends `index.html` with no `Cache-Control`, and Chrome kept
serving the previous build's `index.html` (and so the previous bundle) across a plain reload
until a cache-busting query forced it. `main.jsx` reloads once when a chunk from a previous
build fails to load, which covers the kiosk after a build in practice but not by design; one
line on the backlog.

### The preferred-view design, checked against the terms (2026-09-06)

The operator asked whether a saved view should be stored as an image. The Google Maps
Platform Terms were read the same day and the clauses vendored to
[`docs/standards/google-maps-platform-terms-excerpts.md`](../standards/google-maps-platform-terms-excerpts.md):

* **No image storage.** §3.2.3(a) forbids storing or re-hosting Google Maps Content and names
  "Street View images"; §3.2.3(b) forbids caching except where the Service Specific Terms
  allow it. The Street View Static API policy repeats it.
* **The panorama ID may be stored indefinitely** (Service Specific Terms A.3; Static API
  policy). Heading, pitch and zoom are the operator's own values.
* **§3.2.3(e)(ii): "display Street View imagery and non-Google Maps on the same screen"** is
  on the list of things a customer will not do. The kiosk does exactly that. Raised with the
  operator, who noted it the same day and deferred the ruling (separate screen, full-screen
  modal with the map hidden, or no Street View). It stays visible in the standards index
  until it is made.

So the design is: persist `pano_id` + heading + pitch + zoom per address (what the save
button already collects); on a call, render the compact tile from those parameters live
(Street View Static API, one image request, or the embed); *Expand* opens the interactive
panorama at the same view, where the operator navigates and re-saves. Nothing is cached, and
the 3.2.3(e) question decides whether the tile can sit beside the map at all.

---

## Key fixed 2026-09-06; Firefox still black

> **Status**: 🟡 **The key is fixed and the interactive panorama verified in Chrome on a live
> call. The operator's Firefox shows a black tile and an endless spinner on the same call;
> its console is the next diagnostic.**

The operator changed the key's API restrictions in the Cloud console. Checked in Chrome
against the kiosk (`?nocache=2`) while a real call was up, 2573 Diamond Cres, medical aid:
the Google panorama is mounted in the panel (`.gm-style` with three canvases), no fallback
`<iframe>`, no amber strip, *Save Preferred View* enabled, and no `MapError` or auth-failure
line in the console. Two weeks of a blank-then-embedded panel, all of it one checkbox on the
key. The amber strip and the disabled save stay in the code for the next time the key or the
billing changes underneath the kiosk.

**Not closed.** Minutes later the operator sent two screenshots from Firefox on the laptop,
same call: the compact tile black under the address bar, and the expanded modal stuck on
*Loading Street View Facade...* with no strip and no fallback. The spinner clears on
`status_changed` or a 3.5 s timer, both set inside `initPanorama`, which runs only once
`window.google.maps` exists; a spinner that never clears means the SDK never became
available in that page and `script.onerror` never fired either. Which of a blocked script,
a WebGL failure, or something else it is, Firefox's console will say; guessing is what this
item's history is made of. Ask: F12 in Firefox on the kiosk page, Console, anything naming
google, maps or WebGL.

Also seen on that call and worth its own line: the tile shows *SAVED PREFERRED VIEW (0°)* for
an address nobody has saved. `parcels.streetview_heading` defaults to 0.0 (the skill's own
schema), so every parcel presents as a saved view of 0° — a default reading as an operator's
choice (CLAUDE.md 6.1).

Left open elsewhere: the terms' same-screen clause (standards index, deferred by the
operator), `index.html` caching and `loading=async` (backlog), and the preferred-view design
with a static tile (design note above).

### Saving confirmed; two defects beside it; the tile goes static (2026-09-06 evening)

The operator set a view on 3030 Gordon Ave and asked whether the save works. It does:
`public.parcels` holds heading 214, pitch 13, front point 49.27043/-122.79163, saved
21:08 PDT. Found while checking:

* **Every parcel read as saved.** The column DEFAULTs (0 / 5 / 80) meant 71,210 rows had a
  "preferred view" nobody set, hence *SAVED PREFERRED VIEW (0°)* on every call. Migration
  `2026-09-06_streetview_override_is_null_until_saved.sql`: untouched defaults to NULL,
  defaults dropped, the model no longer supplies them. Measured before running: 71,210 untouched,
  0 touched, 3 real rows.
* **The saved "fov" was the zoom level.** The panel wrote the SDK's zoom (1) into
  `streetview_fov`, so the two real saves read *fov 1*. The relation is fov = 180 / 2^zoom;
  the migration converts the stored rows (1 → 90) and the panel now saves degrees.
* **The panorama id was dropped** by the API schema, so a save pinned only a heading from a
  point, not the exact camera. `streetview_pano_id` added end to end; the terms allow it.

**The tile is static now**, as the operator understood the design: one Street View Static
API image at the saved view (pano id when there is one), no interaction, small header
(*Street View ● 214°*); *Expand* opens the interactive panorama with the save bar. If the
image request fails, the tile falls back to the interactive view and says *Static image
unavailable*. **Needs the operator: add Street View Static API to the key's API
restrictions**, the same screen as the Maps JavaScript API fix.

Also seen: `5000 TESTING WAY`, a row the API test suite writes into the kiosk's live
`parcels` table when run with `DATABASE_URL` pointing there. One line on the backlog.

