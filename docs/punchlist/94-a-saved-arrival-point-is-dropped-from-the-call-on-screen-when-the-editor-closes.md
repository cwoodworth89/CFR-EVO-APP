# Punch list #94 — A saved arrival point is dropped from the call on screen when the editor closes

| | |
|:--|:--|
| **Status** | OPEN — reported 2026-09-17 by the operator with a screenshot; **a regression** (operator: "I believe it used to do that which is why I noticed it now"); with `frontend-kiosk-architect` to find the commit that changed it, then restore |
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
| 2026-09-17 | Operator: "Yes" to the intent, "I believe it used to do that" — a regression — and the editor is review-mode only. Severity corrected 🔴 → 🟠; the agent told to find the commit (tonight's `0e04af21` / `46c0774d` / `dade8273` / `65a50d15` first) and restore rather than invent a new state flow, and to verify from the code that a live call cannot reach the editor — a separate finding if it can |
| 2026-09-17 | Reported by the operator. Opened crew-visible (since corrected). Sent to `frontend-kiosk-architect`: trace the state from editor to route hook with `file:line`, then make the saved point the active call's target on screen, with the pin, the route, the wording and the Street View aim following; stop on any domain choice |
