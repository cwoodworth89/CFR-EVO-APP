# Punch list #94 — A saved arrival point is dropped from the call on screen when the editor closes

| | |
|:--|:--|
| **Status** | BUILT `ce7d4417`, in the bundle lead built on the kiosk 2026-09-16 23:18 local (state check SAFE). **Nothing seen rendered — the operator repeats his steps.** **Not a regression — a ruling change** (see the log): the replay never moved the pin; the console's Explore editor has since 09-06. One question open for the operator: the header's recorded ETAs after a move |
| **Severity** | 🟠 operational — the arrival-point editor is **review-mode only** (operator: "Crews aren't/shouldn't be able to edit an arrival point from the live call mode, only review mode"), so what reverts is the operator's replay view; the next live call takes the saved entrance from the parcel as before. The operator cannot see in review what the next call will do, which is what review is for. Lead first filed it crew-visible; corrected on the operator's word |
| **Area** | 🖥️ Kiosk · 🗺️ Routing |
| **Origin** | Operator, review replay of 1145 Heffley Cres (Medical Aid – Overdose), arrival point "Main Lobby entrance" set and saved |
| **Related** | #49 (arrival points) · #72 (verified grid history) · #93 (the Street View aim follows the target) · `address_resolver.py:370` (the verified entrance is used on the *next* call) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

**Operator, 2026-09-17:** *"When I set an arrival point, the new route shows. And it saves.
But when I close the arrival point window through the banner button, the route jumps back. I
noticed the yellow pin never moved, just the route and a green dot."*

His screenshot: the arrival-point editor open ("ARRIVAL POINT — Applies to the next call at
this address", OPERATOR-SET · CW · 2026-09-17, "Main Lobby entrance"); on the map a green dot
"Arrival point (saved)" on Heffley Crescent north of the lot with the route ending at it, and
**the yellow call pin still on the south frontage**. Closing the editor with CLOSE ARRIVAL
POINT drops the route back to the frontage.

The save itself works — the entrance goes to `public.parcels`, which is what the resolver
uses for the **next** call at that address (`address_resolver.py:370`). What is on screen
diverged from it: the route was drawn against a preview of the arrival point, the active call's
own target was never updated, and once the preview went the route hook re-computed against the
original target. The trace, file by file, is the first half of the job.

## What it should do (the operator's intent, read from "bug")

A saved arrival point applies to the call on screen **now**, and to future calls. After the
save: the yellow pin moves to the arrival point, the route to it stays when the editor closes,
the panel's wording says so, and the Street View aim follows the new target once. The green
"saved" dot stays only if it still means something once the pin is there.

## Not decided — goes to the operator if the fix needs it

Whether clearing an arrival point snaps the pin and route back to the frontage on the current
call, and anything about the route's origin. The frontend agent stops and asks rather than
choosing.

## Falsifier

The operator repeats his steps on the same replay: set the arrival point, save, CLOSE ARRIVAL
POINT. The pin is at the entrance and the route still ends there. Then reload the display: the
same, from the saved parcel.

## Log

| Date | Event |
|:--|:--|
| 2026-09-17 | **History read by the agent — not a regression.** None of tonight's four commits touched the arrival flow (diffs read for `arrival`, `routeDest`, `showArrival`, `arrivalOpen`; the only hits are comment and test text in `46c0774d`). On the dispatch display: `0799d469`/`47d77862` (09-10) gave the replay the editor with the route and pin on the recorded point; **`350c16d6` (09-14 22:15, "a saved arrival point stays on the replay map, and the routes follow it") is the first time the replay's route followed the point, and its message bounded the scope deliberately** — "the replay passes `arrival` only while its arrival panel is open … so closing the panel returns the routes to where the recorded call went", "the call's own pin does not move". Nothing changed it before `ce7d4417`. **What the operator remembers is the console:** Explore mode's `MapBoard.jsx:204–216` (`useArrivalPoint`'s `onSaved`) has moved the target itself since `01755db0` (09-06), so the pin, route and hydrants follow and stay. `ce7d4417` therefore gives the replay the console's existing behaviour — same precedence as `MapBoard` and `address_resolver.py:370` — and **reverses `350c16d6`'s bound on the operator's ruling tonight.** Recorded as a ruling change, not a bug fix. **Live calls cannot reach the editor:** `App.jsx:67` mounts `KioskView` for any active call and `MapBoard` only in standby; in `KioskView` the review strip and its button render only when `isReviewMode || activeCall?.isReview` (`:219`, `:230`), the editor and the map's `arrival` prop only when `showArrival = isReview && arrivalOpen`, and the hook looks up nothing outside review (`:90`). **One other mount, unchanged and surfaced:** the console's `TargetAddressCard.jsx:56` — Explore with a searched address and no call, `canEdit={adminUnlocked}` — the admin-unlocked pre-planning editor the operator built on 09-06; whether the "review mode only" rule means to keep it is his to say |
| 2026-09-17 | **Built, `ce7d4417`.** **The trace, every hop read:** the saved point lived only in `useArrivalPoint`'s `parcel` state — `save` → `POST /api/parcels/entrance` (writes `public.parcels.entrance_*`, `routers/parcels.py:563–573`) → `setParcel(saved)` (`useArrivalPoint.js:76`); `KioskView.jsx` passed `arrival={showArrival ? arrival : null}` to the route panel with `showArrival = isReview && arrivalOpen` (`:81`, **so the editor is review-mode only, as the operator said**); the banner button (`:230`) ran `arrival.cancel()` (clears draft and placing state only) and set `arrivalOpen` false, so `arrival` reached the map as null; `routeDest` (`RouteOverviewPanel.jsx:160`) took draft → `arrival.parcel.entrance_*` → `destination`, and `destination` is the recorded call's `lat/lng` (`:139–151`) — the route fell back; the pin *is* `destination` and was never touched; the green dot was drawn from `arrival.parcel` (`:436`). The comment at `:153–158` documented this as design ("closing it returns the routes to where the recorded call went. The call's own pin never moves"); the operator has called it a bug and it is rewritten. **The change:** new pure module `frontend/src/utils/arrivalTarget.js` — `resolverTargetFromParcel(saved)` gives the destination the resolver would give the next call from the returned row (entrance → computed frontage → centroid, the `address_resolver.py:370` precedence); `applyArrivalToCall(call, target)` moves `lat/lng` and `target.lat/lng/arrival_point/entrance_note`, leaves everything else as recorded, does nothing on an ambiguous junction. `KioskView.jsx`: `onArrivalSaved` (`:87`) stores the applied point per call; `displayCall` (`:93`) is the recorded call with that destination, used only while the call is the same one; the route panel (`:353`), `DetailStack` (`:368`, so the aerial and Street View tiles) and the arrival notice and Tier-1 check (`:140`, `:203`) read `displayCall`; **`dispatches` is never written.** The green dot (`RouteOverviewPanel.jsx:441`) is drawn only where the saved entrance differs from the pin — after a save the pin sits on it and the dot goes; it still shows when the parcel holds an entrance from an earlier session this replay has not taken. **Wording** (`KioskView.jsx:377`): "Applies to this call now and to every future call at this address". **Choices stated:** a cleared point sends the pin to the computed frontage by the same precedence (what the next call would get), not necessarily the recorded point; before any save or clear on this screen the replay shows the call as recorded even if the parcel already holds an entrance — the conservative reading. **Open for the operator:** the header's unit ETAs are the recorded `routing_metrics` to the old destination and are untouched, while the map's route pill shows OSRM's live figures to the new point — as recorded (it is a replay), or `--` once the destination has moved? Verified: `lint:crash` 0, full eslint (only the pre-existing `set-state-in-effect`, now `:315`), `build`, `test:node` 75/75 (precedence including a clear back to the frontage; the move changes only the destination fields, original not mutated; null, `0,0` and an ambiguous junction leave the call unchanged). Nothing rendered. Lead built the bundle 23:18 local |
| 2026-09-17 | Operator: "Yes" to the intent, "I believe it used to do that" — a regression — and the editor is review-mode only. Severity corrected 🔴 → 🟠; the agent told to find the commit (tonight's `0e04af21` / `46c0774d` / `dade8273` / `65a50d15` first) and restore rather than invent a new state flow, and to verify from the code that a live call cannot reach the editor — a separate finding if it can |
| 2026-09-17 | Reported by the operator. Opened crew-visible (since corrected). Sent to `frontend-kiosk-architect`: trace the state from editor to route hook with `file:line`, then make the saved point the active call's target on screen, with the pin, the route, the wording and the Street View aim following; stop on any domain choice |
