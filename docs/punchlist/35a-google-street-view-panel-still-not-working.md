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
