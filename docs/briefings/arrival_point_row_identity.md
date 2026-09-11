# The arrival point is written to one parcel row and read from another

**Written 2026-09-11**, handing off from the UX work on the dispatch display. The operator's
words that started it: *"When I click save arrival point, the new marker disappears and I
don't think it is setting"*, then *"still didn't save"*, then — on seeing the measurements —
*"I think this is bigger than you as the UX implementer. I think this needs to go over to the
debugger."*

It is. The layout half is done and deployed. What is left is a data-model question about what
identifies "an address" in `public.parcels`. **The operator ruled on the behaviour the same
day (§4); what is open is not what it should do but which key makes it true**, and the three
hazards in §4 are the ones that will bite whoever writes it.

Tracked as **[punch list #77](../punchlist/77-an-arrival-point-is-saved-to-one-parcel-row-and-read-from-another.md)**, crew-visible.

> [!IMPORTANT]
> **Resolved 2026-09-10 (`ec34d27`), and two findings below are wrong.** Read the punch item
> for the current state; this brief is kept as the record of the investigation.
>
> **1. The 1,671 null-`gis_id` rows are not an accidental bucket — they are the `base_site`
> rows.** §2 and §4 read them as *"1,671 unrelated addresses"* and concluded no key could
> group a site. They are CFR's own master rows, one per multi-parcel property, built since
> 2026-08-31 and unique per address by partial index. `gis_id IS NULL` is their signature:
> they carry no City handle because they are not City rows. The base row for `2929 Barnet Hwy`
> is one of them. All three hazards in §4 dissolve against that — there is no grouping key to
> choose, "the main one" is already unique, and nothing is copied so nothing needs a marker.
> What was missing was the *read* side: `ParcelModel` never declared the column, so no ORM
> lookup could prefer it.
>
> **2. §3's "Fixing the resolver's row choice will move no routes" is false beyond this one
> address.** True at 2929 Barnet, where all 236 rows share a footprint. Across all 1,671
> base_site sites: 1,543 unchanged, 57 move 1–24 m, **71 move 25 m or more, worst 397 m**.
> Review queue: [`base_site_frontage_review_queue.md`](base_site_frontage_review_queue.md).
>
> The operator ruled on 2026-09-10 that the `base_site` row is the master row the whole system
> reads and he curates, and that suites are out of scope for now — so §4's propagation design,
> and the named-tenant question, were not built. See the punch item's *Deliberately not done*.

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
| `gis_id` values covering more than one address | 2,450 |
| Rows sharing a `gis_id` with a *different* address | **43,842 (62 %)** |
| Largest group under one real `gis_id` | 646 rows (`!4200300`, 1158 The High St) |
| **Rows with no `gis_id` at all** | **1,671**, across 1,671 distinct house+street pairs |
| Duplicated `address` values | 2,170 |
| Rows at house 2929, street Barnet | 236 (235 under `!4200373`, one with none) |
| Rows addressed exactly `2929 Barnet Hwy` | **2** (id 182135 `!4200373`, id 201357 no gis_id) |

> **Correction, 2026-09-11.** The first version of this brief said one Coquitlam Centre
> `gis_id` covered 1,671 suites. That was wrong, and it was asserted from the largest
> `GROUP BY gis_id` count without looking at which group it was. 1,671 is the number of rows
> with **no** `gis_id`, spanning 1,671 different addresses on 265 streets; Coquitlam Centre's
> `gis_id` covers 235. The 62 % figure is unaffected (`q.gis_id = p.gis_id` is false for
> nulls, so those rows were never in it). Recorded rather than quietly edited, per
> CLAUDE.md §7.7.

**`public.parcels` is one row per ADDRESS, not per parcel.** Neither `gis_id` nor `address`
identifies a row on its own. There is a `bigint id` primary key and a `parcel_uuid`, and
`serialize_parcel()` already returns both.

## 3. The two halves disagree about which row is "the address"

**The save** (`backend/api/routers/parcels.py`, `set_parcel_entrance`) built
`target = gis_id or address` and ORed four conditions with `.first()`. With a `gis_id`
supplied it therefore searched by `gis_id` alone and took an arbitrary member of the
235-row Coquitlam Centre group. **Fixed `d4989cd`**: the client sends `parcel_id`, the API writes that row,
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

## 4. The ruling, and the three hazards the data puts in its way

**Ruled by the operator, 2026-09-11**, after seeing the measurements:

> *"We decided to keep all of the suites in the database, but the main one should be the one
> pulled by the parser. And the base building arrival point should be propagated to all the
> suites, and if the suite has an arrival point different from default (set manually), leave
> it alone. So all 1600+ rows should have the same arrival point, unless otherwise set."*

That settles all three open questions: the base row wins for the parser, a suite inherits the
building's point, and a suite's own point outranks the inherited one. It chooses **propagation
at write time** (store a copy on every row) over a cascade at read time (store once, derive on
read). Both give the operator the behaviour he described; the choice decides where the
complexity sits, and the data below decides how much of it there is.

Note that the earlier worry about *named* places — his own London Drugs example, and the 151
pure-name sub-addresses in the corpus — is **not** settled by this ruling. It is about suites
and units. A named tenant inside a mall still has no row of its own to carry a point.

### Hazard 1 — `gis_id` cannot be the grouping key

The base row the operator saves to, `2929 Barnet Hwy`, has **`gis_id = NULL`**. Its 235 suites
have `!4200373`. So a fan-out keyed on `gis_id` would write all 235 suites and **miss the one
row the ruling calls the main one**. Worse, the null bucket is not a building: 1,671 rows on
265 streets share it, so treating null as a group would propagate one site's arrival point
across 1,670 unrelated addresses.

House + street groups differently again: 236 rows match house 2929 on Barnet, which is the 235
plus the null-gis_id base row. **Whatever key is chosen has to be stated and tested, because
the two obvious ones disagree about membership at the very address that started this.**

### Hazard 2 — "the main one" is not unique either

Two rows are addressed exactly `2929 Barnet Hwy`, ids 182135 and 201357, both with a null
`unit` and the same `front_lat`. The lookup returns 182135; the resolver reaches
`2929 Barnet Hwy 2112` (id 181939, the lowest id in the group). "The main one" needs a
definition that picks one of these deliberately — the row with a null `unit`, the lowest id,
the one carrying the gis_id — rather than whichever a query happens to return.

### Hazard 3 — a copy needs to know it is a copy

The ruling requires telling an inherited point from a deliberate one, so that re-propagating
the building's point does not overwrite a suite someone set by hand. Nothing records that
today: `entrance_set_by`, `entrance_note` and `entrance_set_at` are written identically either
way. Without a marker, the second propagation silently destroys the first manual suite ruling,
and the only evidence is a truck going to the wrong door.

This is CLAUDE.md §6.6 and `standards/dependency-behaviour.md` verbatim: *if `X` is computed
from `Y`, name what recomputes `X` when `Y` moves — or do not store `X`.* Storing the point on
1,900-odd rows is storing `X`. The cheapest honest options, for the debugging session to weigh:

* a column recording where a point came from (`entrance_inherited_from`, or a boolean), so a
  propagation pass can skip rows that were set for themselves;
* or keep one stored point per site and resolve the fallback on read, which needs no marker
  and no fan-out but is the design the ruling did not choose.

Either way, **what re-runs the propagation when the base point changes** has to be named
before any of it is written.

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
