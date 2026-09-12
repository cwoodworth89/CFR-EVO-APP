# Punch list #78 — Saving a Street View overwrites the parcel's computed frontage

| | |
|:--|:--|
| **Status** | **CLOSED — fixed, deployed, and confirmed on the running system** 2026-09-11/12. The repair returned both recorded rows to within 4 cm, and the operator then saved a Street View *and* an arrival point at `1132 Dufferin St`: the frontage did not move, measuring **0.000 m** from its computed value. Before the fix that same save would have dragged it 32.7 m to the camera. |
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

## The ruling, and the fix

> Operator, 2026-09-11: *"I don't want the destination/arrival/calculation to change just
> because I change the street view. The default calculated point, arrival point, and
> streetview point should be separate and no change each other."*

The camera had no column of its own, which is why it was living in the frontage. It has one now:

| | Set by | Means |
|:--|:--|:--|
| `front_lat` / `front_lng` | `backfill_parcel_frontage` | the computed frontage — the polygon snapped to its own street |
| `entrance_lat` / `entrance_lng` | the operator | where the truck stops. Outranks the frontage |
| `streetview_lat` / `streetview_lng` | the Street View save | where the camera stands. Routes nothing |

* **Migration** `2026-09-11_streetview_camera_is_its_own_point.sql` adds the two columns and
  backfills them from `front_*` for the 17 rows that carry a saved view — for those rows
  today's frontage *is* the camera position, so nothing is lost and every saved view keeps
  pointing where it was left.
* **`save_parcel_streetview`** writes `streetview_*` and never `front_*`, on both the update
  and the `IntegrityError` retry path. The payload gains `view_lat`/`view_lng`;
  `front_lat`/`front_lng` are still accepted as the older spelling of the *camera*, and the
  legacy `/api/streetview-overrides` alias passes them through as such.
* **The create path** (an address the municipal data lacks) now leaves `front_*` null instead
  of filling it from the camera. Such an address resolves as Tier 1, *location unresolved*,
  which a crew can see — rather than routing to where a photographer stood, which they cannot
  (§5, §6.1). **No row has ever been created by this path** (0 measured, 2026-09-11).
* **`savedViewFromParcel`** reads the camera columns with **no fallback** to `front_lat`. The
  fallback would be the bug again in the other direction: after the frontage repair below, it
  would aim the camera at the repaired point instead of where the operator framed it.

## Deploying this

Three writes, in this order. The frontend must go **last**: it asks the API for
`streetview_lat`, and an un-migrated API does not answer with one, so saved views would read as
absent until the other two are done.

1. the migration, against the kiosk database;
2. `docker compose up -d --build cfr_api` — an `api/` change needs `--build`, not a restart;
3. `git pull && npm run build` in `frontend/`.

## Repairing the frontages the old behaviour overwrote

`backfill_parcel_frontage` is a **function inside the parcel import**
([`import_parcels.py`](../../backend/scripts/import_parcels.py)), not a command — so there was
no way to run this one step without re-running the whole import against shapefiles. It has an
entry point now:

```
docker exec cfr_api python /app/backend/scripts/import_parcels.py --frontage-only
```

`backend/scripts` is bind-mounted into `cfr_api` and `DATABASE_URL` is set there, so a
`git pull` is enough — no rebuild. It reads no shapefile: the inputs are `public.parcels.geom`
and `public.roads`, both already in the database.

### Dry run, 2026-09-11 — what it would change

Measured by running the function's own `SELECT` read-only against the kiosk before any write:

| | Rows |
|:--|--:|
| Touched | 71,053 |
| **Unchanged (<1 m)** | **71,036** |
| Move 1–24 m | 7 |
| Move 25 m or more | 10 |
| Largest move | 323 m (`2929 Barnet Hwy`) |

**All 17 movers carry a saved Street View.** Not one row without one moves. The recompute does
the repair and nothing else, which is the strongest evidence available that the Street View
save is the only thing that had been moving these points.

Nine of the seventeen have no arrival point, so the move changes where a truck is sent:
`580 Clarke Rd` 73 m, `3030 Lincoln Ave` (City row) 35 m, `1132 Dufferin St` 33 m,
`3030 Gordon Ave` 24 m, `2573 Diamond Cres` 15 m, `2865 Glen Dr` (City row) 11 m,
`602 Como Lake Ave` 8 m, `3346 Robson Dr` 8 m, `2971 Lotus Crt` 5 m. The other eight are
shielded by an arrival point, which outranks the frontage.

### The check afterwards — run 2026-09-11, passed

| Row | Expected (queue, 2026-09-10) | After the repair | Off by | Now clear of its camera |
|:--|:--|:--|--:|--:|
| `2865 Glen Dr` (201337) | 49.282752, -122.804565 | 49.282752, -122.804565 | **0.01 m** | 66.2 m |
| `3030 Lincoln Ave` (201436) | 49.279070, -122.791199 | 49.279070, -122.791199 | **0.04 m** | 64.9 m |

Across the table afterwards: **0** rows sit 1 m or more off their computed frontage, **0**
street-viewed rows still have a frontage equal to their camera, all **17** camera positions are
intact, and all **9** arrival points are on base rows.

The read path was re-checked against live data with no test injection — now that `front_lat`
and `streetview_lat` are genuinely different points, the check discriminates on its own.
At `1132 Dufferin St` the panel stands at the camera (49.279189…) and ignores the repaired
frontage (49.278896…), 33 m away.

## The write path, confirmed on the running system

The operator saved a Street View and an arrival point at `1132 Dufferin St` (id 200790) on
2026-09-12 00:30. That is the falsifier this item asked for, and it passed:

| | |
|:--|:--|
| Frontage | 49.278896, -122.804034 — **0.000 m** from its computed value |
| Camera | 49.279190, -122.804044 — 32.7 m from the frontage, heading re-framed 258° → 252° |
| Arrival point | 49.279148, -122.804355 — *"Main entrance"*, CW, 36.5 m from the frontage |

The heading change proves the save landed; the frontage sitting at exactly its computed value
proves the save no longer touches it. Before the fix, that save would have written the camera
straight into `front_lat` and moved the destination 32.7 m.

**What this run does not prove**, stated rather than glossed: the camera position was unchanged
(the same panorama, re-framed), so it cannot distinguish "wrote `streetview_lat` with the same
value" from "did not write it". A save from a *different* panorama position would settle that.
The frontage half — the half the ruling was about — is settled.

Across the table afterwards: **0** rows sit 1 m or more off their computed frontage, and all
**10** arrival points are on base rows.

## Falsifier

If the frontage write is removed from the update path and a Street View is then saved on a row
whose frontage is known, `front_lat` must not change. That is the check.
