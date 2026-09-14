# Design request: working the lots and addresses that need a person

**For:** the UX agent. **From:** the GIS data review, 2026-09-13, at the operator's request.
**Asked for:** a design proposal: screens and flow. **Not asked for:** code. The project is in
a feature freeze, and the store this would write to is not built.

## The problem

Some places cannot get a usable point from City data and computation alone. Today they are
scattered across the database with no single place to see them, and an operator fixing one has
to know it exists first. Figures were measured on the kiosk on 2026-09-13.

| Group | How many | Why the system cannot do it | What a person supplies |
|:--|:--|:--|:--|
| **Lots with no front point, on streets no City road carries** | Pinecone Burke Mtn 28 lots · Coronation Cres 7 · Fremont St 9 (5 numbered) | The front point is measured to the centreline of the street the address names; these streets have none | An arrival point; for Pinecone Burke Mtn, access via **Harper Rd, which becomes a forest service road behind locked gates** (operator) |
| **Dispatched addresses no City source holds** (punch-list #82) | 24 real addresses, seven on Lougheed Hwy | Not in the City's address records, live layer or locator | A placed point; optionally a tie to the lot it sits inside (`2973 Glen Dr` → the `2963 Glen Dr` lot); evidence |
| **Multi-parcel sites without an arrival point** (#49) | 1,660 of 1,671 base sites | The computed front point of a large site can land on the wrong frontage | An arrival point where the computed one is wrong |
| **After each City refresh** (future) | — | Hand data whose address the City dropped (orphans); added addresses the City now holds (retirements) | Keep, move or retire |

About 116 more lots with no front point carry no house number (water, rail right-of-way, parks,
descriptions such as `N/O Quarry Rd`). They are not dispatch targets and need no queue.

## What already exists

* **Console Explore search, with admin unlocked:** find an address and see its lot outline, front
  point and Street View.
* **Arrival point placement** (`frontend/src/components/hud/ArrivalPointSection.jsx`,
  `useArrivalPoint`): a draft pin, a placer name, a note. Routes follow the draft before saving.
* **Street View save:** stores the camera position, heading, pitch and zoom as parameters, never
  imagery.
* **The station kiosk** shows the result during a call. It is not where data is edited.

## Rulings the design must honour (operator, 2026-09-13)

From [`../standards/operator_data.md`](../standards/operator_data.md) and #82:

1. **Everything a person enters is attributed:** who, when, and at least one piece of evidence (a
   dispatch that used the address, the City's label point, Street View).
2. **Nothing is accepted automatically.** The system may suggest; a person places.
3. **No coordinates from a script or a geocoder** for an added address, and **no alias** to a
   neighbouring City address.
4. **Units fall under their base site.** A civic number a person adds is its **own entry**,
   visible and editable on its own.
5. **An added address starts as a point** and may be tied to the lot it sits inside.
6. **On the kiosk, a placed address shows at once in phase 1** with a quiet "placed by the
   operator" note, not the amber approximate-location banner.

## Questions for the design to answer

* Where the queue lives on the console, and how it is reached. Admin only.
* How one item is worked end to end: map, Street View and evidence side by side; place, note,
  save. How a gated access ("Harper Rd FSR, locked gate") is recorded so a crew sees it.
* How the statuses read: pending, placed, rejected (with the reason), retired.
* How a tie to a lot is shown, so nobody mistakes the tied lot's outline for the added address's
  own.
* How the refresh's orphans and retirements join the same queue later without a second screen.
* What the kiosk shows for each kind of placed data. Follow the existing ergonomics conventions
  (`kiosk-responsive-ergonomics` skill).

## Constraints

* **The storage is not built.** It is a proposed `cfr` schema keyed by civic address. Design the
  flow, not the tables, and don't assume column names.
* Offline-first (CLAUDE.md §1). No new external calls; Street View is the one existing exception.
* Every value that could be unknown shows as unknown (CLAUDE.md §6.1).
