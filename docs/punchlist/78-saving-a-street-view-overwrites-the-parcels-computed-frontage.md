# Punch list #78 — Saving a Street View overwrites the parcel's computed frontage

| | |
|:--|:--|
| **Status** | **REPORTED, not fixed.** Mechanism confirmed in the code on both sides and corroborated on the kiosk database 2026-09-11. The fix and the data repair are the operator's call — see *The decision this needs*. |
| **Severity** | 🔴 crew-visible |
| **Area** | 🗺️ GIS / parcels · 🖼️ Street View · 🚒 Routing destination |
| **Origin** | Found 2026-09-11 while checking the operator's *"I just tried to set 1190 Pacific, but the marker didn't move"*. The arrival point was fine; the frontage underneath it was not. |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

`StreetViewPanel.handleSaveView` sends the **panorama camera's position** as `front_lat` /
`front_lng`:

```js
// frontend/src/components/kiosk/StreetViewPanel.jsx:121
const live = pano.readView();
const payload = { address: cleanAddrKey, front_lat: live.lat, front_lng: live.lng, heading: live.heading, ... };
```

and `save_parcel_streetview` writes it straight onto the existing row:

```python
# backend/api/routers/parcels.py:375
if payload.front_lat is not None:
    p.front_lat = payload.front_lat
```

So framing a Street View — a *picture* decision — silently replaces the parcel's computed
frontage, which is where a truck is sent when no arrival point is set
(`dest = entrance_lat or front_lat or centroid_lat`).

## Why this is crew-visible

The frontage is a routing destination, not a thumbnail. Nothing on the screen says it changed,
and a Street View is framed for *looking at the building* — often from across the road, up the
block, or wherever the nearest panorama happens to stand. That is not where the truck should
stop, and the crew cannot tell the difference.

## Measured, 2026-09-11 (kiosk database)

The review queue for #77 recorded each base row's frontage on 2026-09-10
([`base_site_frontage_review_queue.md`](../briefings/base_site_frontage_review_queue.md)),
which gives a **before** value to measure against. Two rows have had a Street View saved since:

| Site | Frontage on 2026-09-10 | Frontage now | Moved |
|:--|:--|:--|--:|
| `2865 Glen Dr` (201337) | 49.282752, -122.804565 | 49.282763, -122.803655 | **66.2 m** |
| `3030 Lincoln Ave` (201436) | 49.279070, -122.791199 | 49.278865, -122.792034 | **64.9 m** |

Both now carry an arrival point, which outranks the frontage — so at those two addresses the
damage is masked. The exposure is elsewhere:

* **17 rows** carry a saved Street View.
* **7 of them have no arrival point**, so their frontage *is* the destination, and it is now a
  camera position rather than the frontage algorithm's answer.

This is also why the queue's own count no longer reproduces: re-measuring its definition today
gives **74** sites at 25 m or more, not 71. Four of the five differing rows
(200865, 200882, 200883, 201357) had a Street View saved after the queue was generated; the
fifth (201337) moved below the threshold the same way. **The queue is not wrong — it is a
snapshot of values that something else has since been editing.**

## Not the cause, checked and ruled out

`set_parcel_entrance` does **not** touch `front_lat` (backend/api/routers/parcels.py:506).
The first explanation tried — that saving an arrival point moved the frontage — was wrong, and
is recorded rather than quietly dropped (CLAUDE.md §7.7). `updated_at` moving with the entrance
save is the ORM's `onupdate`, not a frontage write.

## The decision this needs

Two questions, both the operator's:

1. **Should the Street View save write a frontage at all?** On an existing parcel row, no: the
   frontage comes from `backfill_parcel_frontage` snapping the polygon to its own street, and a
   camera position is not that. But the same endpoint also *creates* a row for an address the
   municipal data does not contain, and there `front_lat` is the only coordinate it has
   (see the comment at parcels.py:399). The narrow fix is to keep the write on the create path
   and drop it on the update path.
2. **What repairs the 7 exposed rows?** `front_lat` is recomputed for every row on every parcel
   import, so a re-run of `backfill_parcel_frontage` restores them — that is the same property
   that makes a hand-copied coordinate revert. Worth confirming before relying on it.

## Falsifier

If the frontage write is removed from the update path and a Street View is then saved on a row
whose frontage is known, `front_lat` must not change. That is the check.
