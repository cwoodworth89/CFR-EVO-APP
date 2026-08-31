# Punch list #48 — One civic address, many parcels — the import keeps whichever the shapefile lists first

| | |
|:--|:--|
| **Status** | DESIGNED |
| **Severity** | crew-visible |
| **Area** | 🧾 Import Completeness Audit, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3259 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 48. One civic address, many parcels — the import keeps whichever the shapefile lists first
> **Status**: ⚠️ **Open — measured 2026-08-28. Ours, not a City data gap.**

Found while accounting for the 4,307-record difference between `Addresses.dbf` (69,708) and
`public.parcels` (65,401). **The accounting reconciles exactly** — there are 65,401 distinct
`ADDRESS` values in the source, so nothing is being lost at import:

| | |
|:--|--:|
| Records in `Addresses.dbf` | 69,708 |
| Distinct `ADDRESS` values | **65,401** |
| Rows in `public.parcels` | **65,401** |
| Duplicated addresses | 1,509 |
| Extra rows they account for | **4,307** ✅ |

`Addresses.dbf` also has its own `STATUS` column — worth checking after the roads import
filter (#42) — but its entire domain is `Active` (69,704) plus 4 blanks. Nothing is filtered.

#### The problem is *which* duplicate wins

`backend/scripts/import_parcels.py:336` deduplicates on the raw address string:

```python
if raw_addr in seen_addresses:
    continue
seen_addresses.add(raw_addr)
```

First-wins, **in shapefile row order, with no ordering rule** — the same shape as the
unordered-parcel-query defect in #19. That is only safe if the duplicates sit in the same
place, and measured against the shapefile geometry (UTM 10N, representative points) they
frequently do not:

| Duplicate groups | With a house number | Street-only |
|:--|--:|--:|
| Total | 1,452 | 56 |
| More than 5 m apart | 708 | 54 |
| More than 25 m apart | **631** | 53 |
| More than 100 m apart | **143** | 47 |
| More than 500 m apart | 14 | 26 |

The duplicates never differ in `HOUSE`, `STREET`, `STREETTYPE`, `UNIT` or `UNITTYPE` — only
in `LEGALDESC` (714 groups), `FOLIO` (712) and `GIS_ID` (676). So this is **one civic address
spanning several legal lots**, which is legitimate municipal data, not a City defect.

> **A first hypothesis was wrong and is recorded rather than overwritten.** The worst
> spreads looked like street-only right-of-way records (`Shaughnessy St` ×469,
> `Pitt River Rd` at 13.5 km), so the effect appeared to be confined to records with no
> house number. Splitting the two classes disproved it: **1,452 of the 1,508 duplicate
> groups DO carry a house number**, and 631 of those are more than 25 m apart.

#### Operational exposure so far

Seven dispatches in the corpus went to an address whose duplicates are >25 m apart. Five are
street-only (`Pipeline Rd`, `United Blvd` ×3, `Gatensbury St`) and already handled as
street-level. **Two are genuine numbered addresses:**

```
DISP-2026-C0F4AA   2865 Glen Dr    216.6 m spread   8 features, 7 sharing GIS_ID !4190583
DISP-2026-A977D4   210 Lebleu St    35.3 m spread   4 features, 2 distinct locations
```

Small in the observed corpus, but the mechanism affects 631 addresses that have not been
dispatched to yet.

**Second-order effect, easy to miss**: `parcels.rings` comes from the kept record too, so the
kiosk highlights **one lot of eight** for 2865 Glen Dr rather than the whole property.

#### What to do is a domain decision (§7.2), not a coding one

Do **not** pick a tiebreak by feel. Candidate rules, each with a different failure mode:

1. **Largest parcel by area** — favours the main site, but a large rear lot can beat the
   building that fronts the street.
2. **Closest to the road centreline for that street** — favours the frontage a crew arrives
   at, and `public.roads` is now complete enough to support it (#42).
3. **Union all duplicate geometries into one parcel** — most honest about what the address
   is, and would fix the rings; changes the meaning of a parcel row.
4. **Keep all rows and mark the address ambiguous** — surfaces it via the amber banner
   rather than choosing, consistent with §6.1.

Whichever is chosen, the selection must become **deterministic and stated**, and the change
measured against the corpus the way #42 was.

**Also worth asking the City** (see `docs/city_gis_data_register.md`): is one civic address
across 8 legal parcels expected, and is there an attribute marking the primary parcel?

---

---

## 48 (direction agreed). `base_site` rows — City rows are left alone

> **Status**: 📐 **Design agreed with the operator 2026-08-31, not implemented.**
> Full reasoning, measurements and open questions:
> [`briefings/base_site_rows_decision.md`](../briefings/base_site_rows_decision.md).

**The tiebreak question is withdrawn — nothing is chosen between any more.** All 69,708
City records are imported and kept, duplicates included, each keeping its own `folio`,
`legaldesc`, `gis_id` and geometry. A CFR-owned **`base_site`** row is added for each of the
**1,671 multi-parcel properties**, carries the operational context, and speaks for every City
row at that address.

`base_site` rather than `base_building`: the latter is fire-prevention vocabulary for a
highrise or commercial structure and stops meaning anything for a trailer park or townhome
complex, which is where this problem is worst.

**The City's `MASTER` record was checked before being adopted, and is not what its name
suggests.** Across 517 properties holding both a MASTER row and unit rows, MASTER averages
**10.3% of the summed unit area** while its bounding box spans ~100% of the site, and 99.6%
of unit parcels intersect it. 99% carry a strata `PLAN`, 1% a `LOT`, 12% a `FOLIO`. It is
**strata common property** — driveways, walkways, perimeter — not the building and not the
property envelope. Adopting it as "the property" would have had the kiosk outline a driveway
network. It is still valuable, as the access surface an arrival point should snap to.

**Blocked on**: the parcel-snapping workstream landing first (it is baselined against current
parcel geometry), and one open question — whether single-parcel addresses also get a
`base_site`, since otherwise their operator data sits on a City row the import can no longer
key on. Both in the briefing.
