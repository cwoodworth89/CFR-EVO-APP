# Decision: `base_site` rows, and what the City's MASTER record actually is

**Date:** 2026-08-31
**Operator decision.** Covers punch-list **#48** (one civic address, many parcels) and
**#49** (access-point review UX).
**Status:** direction agreed, **not implemented** — see *Sequencing* below.

---

## The decision

**City-owned rows are left alone.** Every record from `Addresses.shp` is imported and kept
as it is — all 69,708, duplicates included. `folio`, `legaldesc`, `gis_id` and geometry stay
on the lot they belong to. Nothing is collapsed and nothing is chosen between.

**A `base_site` row is added for each multi-parcel property.** It is CFR's row, not the
City's. It carries the operational context — entrance point, lockbox, hazard notes,
pre-plans — and **speaks for every City row at that address, the MASTER record included.**

### Why `base_site` and not `base_building`

`base_building` is fire-prevention vocabulary for a highrise or commercial structure —
the building exclusive of its units. It stops meaning anything for a trailer park or a
townhome complex, which is precisely where this problem is worst. `base_site` holds across
all of them.

---

## What the City's MASTER record actually is

**It is strata common property. It is not the building and it is not the property envelope.**
Measured before assuming, because the name invites the wrong assumption:

| Measurement | Result |
|:--|--:|
| Properties with both a MASTER row and unit rows | 517 |
| **MASTER area as a share of summed unit area** | **10.3%** (min 0.3%, max 83%) |
| Unit parcels intersecting the MASTER polygon | 99.6% |
| MASTER bounding box vs whole-site bounding box | ~100% (median) |

It **spans** the site while occupying a tenth of it — a thin network threading between the
units. The attributes agree: 99% carry a strata `PLAN`, 1% a `LOT`, and only 12% a `FOLIO`,
so they are not separately assessed. That is common property: driveways, walkways, perimeter.

`2865 Glen Dr` is the worked example — MASTER is 6,256 m² against roughly 26,000 m² of
units across 76 townhomes.

**Had this been adopted as "the property", the kiosk would have outlined a driveway network
and labelled it the site** — a plausible wrong answer of exactly the kind §6 exists to
prevent. Another instance of the §7.3a pattern: the name described the intent, the data
described something else.

### So use it for what it is

* **Property extent** = union of the MASTER row *and* its unit rows. Never MASTER alone.
* **Arrival-point snapping** = MASTER geometry is the strongest candidate surface available,
  because it is literally the land crews drive onto.
* **Identity** = the strata `PLAN` number is a clean handle.

### Two data cautions

* **24 MASTER records carry a `UNIT` number**, contradicting the concept. Do not trust the
  flag blindly.
* **4 of 948** have MASTER spanning under 50% of the site bounding box — `2979 Panorama Dr`
  at 27.9% across 159 parcels. Even "it spans the site" has exceptions.

---

## Scale

| | |
|:--|--:|
| Source records in `Addresses.shp` | 69,708 |
| Distinct main addresses (house + street) | 28,202 |
| Single-parcel — no `base_site` needed | 26,531 |
| **Multi-parcel — gets a `base_site` row** | **1,671** |
| — with unit numbers | 1,015 |
| — split lots, no units | 656 |
| Resulting table | **71,379 rows** (today: 65,401) |

Largest: `523 Gatensbury St` (392 parcels), `567 Clarke Rd` (374), `1016 Howie Ave` (360),
`657 Whiting Way` (335), `1188 Pinetree Way` (316).

**This is what makes #49 tractable.** The access-point review queue is not 65,401 parcels —
it is **1,671 sites**, and the top fifty cover the complexes crews actually struggle with.

---

## Mechanics

**How CFR data survives re-import — the existing mechanism, unchanged.** Operator columns
(`entrance_lat/lng`, `entrance_set_by/at/note`, `lock_box_notes`, `hazard_notes`,
`pre_plan_pdf_url`, `construction_type`, `floor_count`) appear in **neither** the INSERT
column list **nor** the `ON CONFLICT ... DO UPDATE` set in `import_parcels.py`. They are
protected by omission. Nothing else defends them, so any redesign must keep an upsert path
rather than truncate-and-reload.

**The unique index has to become partial.** `idx_parcels_address` is currently
`UNIQUE (address)`, which is what forces the collapse. It becomes unique **only for
`base_site` rows**, letting City rows repeat freely:

```sql
CREATE UNIQUE INDEX parcels_base_site_address_uniq
    ON public.parcels (address) WHERE is_base_site;
```

**Resolution rule.** Resolving `2865 Glen Dr 42`: if that row has no `entrance_lat`, fall
back to its `base_site` row. Query-time logic in `address_resolver.py` — no schema change.
`address_resolver` already handles multiple matching rows, so this is an addition rather
than a rewrite.

**Zones should be derived, not stored.** `parcels.zone_id` is precomputed at import;
`public.intersections` derives the grid at read time via `public.zone_for_point()`
deliberately, *"so there is exactly one definition of which zone a point is in"*
(`derive_intersections.py:148`). Parcels having their own stored copy is the second
definition, and it is what raises the "which zone does a multi-parcel site straddle?"
question at all. Deriving removes it: the zone is whatever the point you asked about
resolves to. Map grid itself is emphatically needed — 291 of 313 dispatches in the last 30
days carry one and 273 are operator-verified — and `address_resolver.py:110` uses it to
narrow candidates.

---

## Sequencing — do not start yet

**The parcel-snapping workstream must land first.** `verify_snapping_corpus.py` reads
`p.geom` and `p.front_lat/front_lng`, `import_parcels_PROPOSED.py` is mid-flight with an
unlanded decision, and `docs/dispatch_corpus_snapping_benchmark.json` is baselined against
current geometry. Changing what a parcel row means would pull the ground out from under
work in progress — the same failure the snapping rollback briefing apologises for.

**#49 gates the operator half regardless.** All 65,401 `entrance_lat` are NULL and there is
no UI to set one.

---

## Open, and needing a decision before implementation

1. **Single-parcel addresses keep CFR data on a City row.** With `base_site` only for the
   1,671 multi-parcel properties, the other 26,531 addresses hold operator context on a
   City-owned row — which cannot then be freely reloaded, and whose address is no longer
   globally unique, so the upsert has nothing to key on. Creating a `base_site` for every
   main address (28,202) removes the branch entirely at the cost of ~26k thin rows. **This
   is the one open question that blocks implementation.**
2. **Geometry for a `base_site` row** — union of its members is the obvious answer, but the
   42 street-only groups spread over kilometres (`Harper Rd` ×61 across 3.9 km) would union
   to a multipolygon whose centroid means nothing. Those carry no house number and resolve
   at street level; they likely should not get a `base_site` at all.
3. **The 147 unitted properties with no base row** (14.4% of 1,023) — mostly small duplexes
   and fourplexes such as `3411 Roxton Ave`. Their `base_site` is synthesised from the units.
4. **`streetview_heading/pitch/fov`** are in the INSERT but not the DO UPDATE, so they
   freeze against the geometry they were first computed from — the same defect already
   fixed for `front_lat`. Logged, not fixed.
