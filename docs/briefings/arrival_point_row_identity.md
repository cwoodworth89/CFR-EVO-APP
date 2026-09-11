# The arrival point is written to one parcel row and read from another

**Written 2026-09-11**, handing off from the UX work on the dispatch display. The operator's
words that started it: *"When I click save arrival point, the new marker disappears and I
don't think it is setting"*, then *"still didn't save"*, then — on seeing the measurements —
*"I think this is bigger than you as the UX implementer. I think this needs to go over to the
debugger."*

It is. The layout half is done and deployed. What is left is a data-model question about what
identifies "an address" in `public.parcels`, and a domain ruling only the operator can give.

**Nothing here is a live routing error today.** See §3. The system routes to the same
coordinates it always did; it is the arrival-point feature that does not connect.

---

## 1. What was reported, and what was actually happening

The save was never failing. `POST /api/parcels/entrance` answered **200 OK** on both of the
operator's attempts (kiosk API log, 2026-09-10). The ruling was written — to the wrong row.

```sql
SELECT gis_id, address, entrance_lat, entrance_note, entrance_set_by
FROM public.parcels WHERE entrance_set_at > now() - interval '6 hours';
--  !4200373 | 2929 Barnet Hwy 1202 | 49.27998702791689 | Mall main fire annunciator | CW
```

The operator meant Coquitlam Centre, `2929 Barnet Hwy`. It landed on suite 1202.

Two things then made it look like a silent loss rather than a misplaced write: the failure
path was a 10 px red line under the form, and closing the arrival-point card cancels the
placement and takes the draft pin with it.

## 2. The measurements

All on the kiosk database, 2026-09-11, via the read-only `cfr-postgres` connection.

| What | Figure |
|:--|--:|
| Rows in `public.parcels` | 71,212 |
| Distinct `gis_id` | 27,855 |
| `gis_id` values covering more than one address | 2,451 |
| Rows sharing a `gis_id` with a *different* address | **43,842 (62 %)** |
| Largest group under one `gis_id` | **1,671 rows** |
| Duplicated `address` values | 2,170 |
| Rows at `2929 Barnet Hwy` (house 2929, street Barnet) | 236 |

**`public.parcels` is one row per ADDRESS, not per parcel.** Neither `gis_id` nor `address`
identifies a row on its own. There is a `bigint id` primary key and a `parcel_uuid`, and
`serialize_parcel()` already returns both.

## 3. The two halves disagree about which row is "the address"

**The save** (`backend/api/routers/parcels.py`, `set_parcel_entrance`) built
`target = gis_id or address` and ORed four conditions with `.first()`. With a `gis_id`
supplied it therefore searched by `gis_id` alone and took an arbitrary member of a
1,671-row group. **Fixed `d4989cd`**: the client sends `parcel_id`, the API writes that row,
and an ambiguous match is refused with a 409 naming how many rows matched. Deployed and the
API rebuilt; `ParcelEntranceSchema` on the running instance carries `parcel_id`.

**The resolver** (`services/gis/src/gis_service/address_resolver.py`) is *not* fixed and was
not touched. It selects `WHERE house = :house`, scores the street name, and takes
`scored[0][0]` — the first row of the top-scoring set under `ORDER BY street, streettype, id`:

```sql
SELECT address, unit FROM public.parcels
WHERE house='2929' AND upper(street)='BARNET'
ORDER BY street, streettype, id LIMIT 1;
--  2929 Barnet Hwy 2112 | 2112
```

So a dispatch to `2929 Barnet Hwy` reads suite **2112**'s row, while the operator's ruling is
saved on the base row. The ruling is stored where nothing reads it.

**Why this is not a live routing error.** All 236 rows share one frontage point:

```sql
SELECT count(*), count(DISTINCT (round(front_lat::numeric,6), round(front_lng::numeric,6)))
FROM public.parcels WHERE house='2929' AND upper(street)='BARNET';
--  236 | 1
```

`dest = entrance_lat or front_lat or centroid_lat`. Since every row's `front_lat` is the same
and `entrance_lat` is null on all but one, the destination is identical whichever row wins.
Only `entrance_lat` is per-row, which is precisely the feature that fails. **Do not "fix" the
resolver's row choice expecting routes to move; they will not, until an arrival point exists.**

## 4. The ruling that is blocked, and why the obvious answer is wrong

The operator proposed the cascade himself: *"Check for a default base building arrival point,
but if there is also a sub-address arrival point that can be used for further accuracy?"* —
with the example *"if it specifically said London Drugs, I would choose another spot."*

The model is right. The **key** is the problem. Of 617 dispatches, 289 carry a `subaddress`
across 151 distinct values:

| Shape | Count | Examples |
|:--|--:|:--|
| Contains a number | 138 | `Number 201`, `Number 1404`, `Number 189 Parkwood Manor` |
| Pure name, no digits | 151 | `Rain City Housing`, `Coquitlam Center Mall`, `Number Basement` |

Zero are a bare number. `public.parcels.unit` holds the suite (`2112`), so a **unit-keyed**
cascade is mechanical. But the operator's own example, London Drugs, is a **name**, and names
are the larger half. A name has nowhere to live:

> **`public.custom_places` does not exist in the database.** CLAUDE.md §1 names it as
> authoritative and `backend/tests/test_postgis_migration.py:146` asserts against it. The only
> other code reference is a comment in `frontend/src/components/map/layerIcons.js` recording
> its *removal*. Establish what actually happened to it before designing on top of it
> (CLAUDE.md §6.6: the records lag the system).

### The three questions for the operator

1. Does a unit with no arrival point fall back to the building's? (Presumed yes — that is the
   cascade he described, but it has not been said.)
2. Do **named** places get their own arrival point, or is a name only a label on the
   building's point? This is the expensive one: it needs a table that is not there.
3. When no unit is announced, should the **base** row win? Today an arbitrary suite does.

## 5. Loose ends left deliberately

* **A stray ruling is live.** `2929 Barnet Hwy 1202` still carries `entrance_lat`
  49.27998702791689 with the note *Mall main fire annunciator*, set by CW. It is the
  operator's real judgement on the wrong row. Clearing it needs the admin token, so it was
  left for him. It is harmless-to-helpful if a call ever comes to that suite, and invisible
  otherwise.
* **The Street View save has the same shape but not the same bug.** `save_parcel_streetview`
  matches on the address for three of its four OR conditions, so it does not take the
  `gis_id`-only path. That it still ends in `.first()` over a possibly-duplicated address
  (2,170 of them) is untested and unfixed.
* **The console lookup is also `.first()`** over an OR (`lookup_parcel`). Once the save is by
  `parcel_id` the lookup and the save agree by construction, because the id comes from the
  lookup's own answer. The resolver is the one that still chooses independently.

## 6. What is already done, and safe to build on

| | |
|:--|:--|
| `d4989cd` | The save writes the row the caller names; ambiguity is a 409, not a guess. API rebuilt on the kiosk and verified serving. |
| `b067a94` | The one-line record in [`post_freeze_backlog.md`](../post_freeze_backlog.md). |
| Frontend | `hooks/useArrivalPoint.js` sends `parcel_id`; the arrival-point card is in the review strip on the dispatch display. A refused save now renders a red **NOT SAVED** block naming the padlock. |
| Untouched | `address_resolver.py`, the Street View save, the lookup, and every routing path. |

See also [`mobile_accessibility_review.md`](mobile_accessibility_review.md) §7 for the UX work
this came out of, and [`../ux_notes.md`](../ux_notes.md) §2 for the arrival-point history.
