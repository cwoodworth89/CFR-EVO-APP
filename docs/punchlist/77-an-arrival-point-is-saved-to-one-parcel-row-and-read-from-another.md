# Punch list #77 — An arrival point is saved to one parcel row and read from another

| | |
|:--|:--|
| **Status** | FIXED `ec34d27` — code on the kiosk, **awaiting a restart to take effect** |
| **Severity** | 🔴 crew-visible |
| **Area** | 🗺️ GIS / address resolver · 🖥️ Kiosk view |
| **Ruling** | Operator, 2026-09-10: the `base_site` row is the master row the whole system reads and the operator curates. Suites stay in the table, unread. |
| **Origin** | Operator, 2026-09-10: *"When I click save arrival point, the new marker disappears and I don't think it is setting"*, then *"still didn't save"* |

[← punch list index](../debug_and_qa_punchlist.md)

**Full brief, with every measurement and its query:**
[`briefings/arrival_point_row_identity.md`](../briefings/arrival_point_row_identity.md)

---

## Why this is crew-visible

The operator sets an arrival point because the computed frontage is wrong for that site — a
gated lane, a lobby round the back, a mall's fire annunciator. When the ruling is written to a
row nothing reads, the truck goes to the frontage anyway and **the screen still says the point
was saved**. Nobody can tell from the display that the ruling is not in force. That is the
§7.1 test: a plausible wrong answer a crew cannot see through.

**Four of the operator's five arrival points are filed on a row that is not the property's
master row** (measured 2026-09-10). An earlier version of this table judged them against the
old resolver's arbitrary pick, which made three look stranded and two look live; against the
base row — the definition the operator has since ruled — the count is four:

| Address as saved | Row it sits on | | The property's base row | After `ec34d27` |
|:--|--:|:--|--:|:--|
| `1800 Austin Ave` | 201131 | is the base row | 201131 | ✅ read |
| `3030 Lincoln Ave` | 163422 | a City row | **201436** | needs re-setting |
| `2865 Glen Dr` | 163590 | a City row | **201337** | needs re-setting |
| `602 Como Lake Ave 2606` | 198562 | a City suite | **201792** | needs re-setting |
| `2929 Barnet Hwy 2112` | 181939 | a City suite | **201357** | needs re-setting |

## The cause

`public.parcels` is one row per **address**, not per parcel: 71,212 rows over 27,855 `gis_id`
values, 43,842 rows (62 %) sharing a `gis_id` with a different address, and 2,170 duplicated
addresses. Neither key identifies a row.

* **The save** built `target = gis_id or address` and ORed four conditions with `.first()`, so
  with a `gis_id` it searched by `gis_id` alone and took an arbitrary member of the group.
* **The resolver** (`services/gis/src/gis_service/address_resolver.py`) selects
  `WHERE house = :house`, scores the street, and takes `scored[0][0]` — the first of the tied
  set under `ORDER BY street, streettype, id`.

The two therefore choose different rows for the same address, and neither choice is stated
anywhere as the definition of "the address".

> [!CAUTION]
> **Correction, 2026-09-10 — the answer was already in the table.** This item and its brief
> both read the 1,671 rows with no `gis_id` as an accidental bucket of *"1,671 unrelated
> addresses"*, and concluded that no key could group a site. That was wrong, and it is why
> this looked hard.
>
> Those 1,671 rows **are** the `base_site` rows — CFR's own master row, one per multi-parcel
> property, built by `import_parcels.build_base_site_rows` since 2026-08-31 and unique per
> address via `parcels_base_site_address_uniq`. `gis_id IS NULL` is their *signature*, not a
> defect: they are CFR rows, so they carry no City handle. The base row for `2929 Barnet Hwy`
> is one of them, which is exactly why a `gis_id`-keyed search could never reach it.
>
> All three "hazards" this item listed dissolve against that. The grouping key is not needed
> — the base row *is* the parent. "The main one" is unique — the partial index enforces it.
> A copy needs no marker — nothing is copied, because the row is read, not propagated.
>
> **What was actually missing was the read side.** `ParcelModel` did not declare
> `is_base_site` at all, so no ORM lookup could prefer it even in principle, and the resolver
> never selected it. A fully-built write side with nothing reading it. See
> [`base_site_rows_decision.md`](../briefings/base_site_rows_decision.md).

## Fixed

* **`d4989cd`** — the save writes the row the caller names (`parcel_id`, which the lookup
  already returns); an ambiguous match is refused with a 409 rather than guessed. Deployed,
  API rebuilt on the kiosk, `ParcelEntranceSchema` verified on the running instance.
* **`1ba6e09`** — a refused save renders a red **NOT SAVED** block naming the padlock, instead
  of a 10 px red line under the form. It was that, plus closing the card cancelling the
  placement, that made a misfiled write look like a lost one.
* **2026-09-10, by hand** — the operator's mall ruling moved from `2929 Barnet Hwy 1202`
  (id 181959) to `2929 Barnet Hwy 2112` (id 181939) on his
  instruction. Values copied verbatim including `entrance_set_at`: the filing was corrected,
  the decision was not remade. **Superseded by `ec34d27`**: suite 2112 was the row the *old*
  resolver read, and it is not the base row. The point belongs on id 201357.
* **`ec34d27`** — **the read side.** `ParcelModel` declares `is_base_site`; `parcels._address_row`
  becomes the one address → row rule and `lookup_parcel`, both Street View save paths and the
  Street View override all call it; `_entrance_target` treats a base_site row as the answer
  rather than an ambiguity to refuse; and `resolve_exact` selects `is_base_site` and orders by
  it first, so `scored[0][0]` takes the property's master row. Confirmed on the kiosk database:
  `2929 Barnet Hwy` resolves to **id 201357**, and **0 of 500** sampled single-parcel addresses
  change. Code is on the kiosk; **the API and the dispatch agent have not been restarted**, so
  it is not yet in force.

## Open

1. **Restart to take effect.** `backend/api` needs `docker compose up -d --build api`; the
   resolver change is in `services/gis`, which the dispatch agent loads. Left for the operator
   to pick the moment — a restart during a capture loses the call and its audio (#70).
2. **The 71-site frontage review.** Pointing everything at the master row makes that row's
   frontage the default destination. It is the *same* snapping algorithm — `backfill_parcel_frontage`
   treats a base row like any other — against the property union rather than one arbitrary lot.
   128 of 1,671 sites move, 71 by 25 m or more, worst 397 m; 1,543 do not move at all. Queue:
   [`briefings/base_site_frontage_review_queue.md`](../briefings/base_site_frontage_review_queue.md).
   Where the union point is wrong the fix is **an arrival point on the base row** — `front_lat`
   is recomputed every import, so a copied coordinate reverts silently; `entrance_lat` is
   protected by omission and survives.
3. **Four arrival points are still filed on City rows.** `2865 Glen Dr`, `3030 Lincoln Ave`,
   `602 Como Lake Ave 2606` and `2929 Barnet Hwy 2112` carry rulings the resolver no longer
   reads. `1800 Austin Ave` (id 201131) was already on its base row and is correct. The
   operator is re-setting them by hand in Explore with admin unlocked; with `lookup_parcel`
   now preferring the base row, entering the address targets the right row by construction.
   The stale values on the suite rows are unread rather than wrong, and can be cleared at
   leisure.

## Deliberately not done

**Suites.** Operator ruling, 2026-09-10: *"I don't want to deal with suites right now in 99%
of the bigger sites."* A dispatched unit number is not resolved to its own row, and no arrival
point cascades from base to suite. The suite rows stay in the table, unread.

Measured, should that change: the parser already extracts the unit — `extract_subaddress_info`
puts it on `DispatchData.subaddress` and formats a bare number as `Number 205` — but
`resolve_exact` has no unit parameter and the street normaliser *strips* trailing unit
designators before matching. Of 617 dispatches, 289 carry a subaddress; 138 are numeric
(135 of them `Number NNN`), and **116 of those match a real `parcels.unit`** at that address.
The other 151 are pure names (`Rain City Housing` ×52, `Coquitlam Center Mall` ×11 across three
spellings), 48 distinct places, and `public.custom_places` — which CLAUDE.md §1 names as their
home — **does not exist in the database**. Backlog, with business-licence data as the operator's
preferred source.

**Named tenants inside a site cannot be distinguished geometrically, and never will be from
this layer.** All 236 rows at 2929 Barnet Hwy carry the *identical* 218,322 m² footprint —
min area = max area — so every suite's "parcel" is the whole mall. `ST_ClosestPoint` has one
answer for all of them. A per-tenant arrival point can only ever be set by hand.

## Not a live routing error at the address that started this

All 236 rows at `2929 Barnet Hwy` share one `front_lat`/`front_lng`, and
`dest = entrance_lat or front_lat or centroid_lat`. So at *that* address, changing which row
wins moved nothing.

> [!WARNING]
> **Correction, 2026-09-10.** The earlier version of this section generalised that to
> *"Fixing the resolver's row choice will move no routes."* **That is false across the
> table.** Measured over all 1,671 base_site sites: 1,543 unchanged, 57 move 1–24 m, 71 move
> 25 m or more, worst **397 m**. The mall is unrepresentative precisely because its rows share
> a single footprint; the sites that move are mostly two- and three-lot split properties,
> where the union frontage is a different point from any one lot's.
>
> A first attempt at this measurement returned "1,448 sites move, max 12 km". That was wrong
> — the query compared rows by house number across *all* streets rather than the street the
> resolver scores. Recorded rather than quietly replaced, per CLAUDE.md §7.7.
