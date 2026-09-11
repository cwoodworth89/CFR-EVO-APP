# Punch list #77 — An arrival point is saved to one parcel row and read from another

| | |
|:--|:--|
| **Status** | OPEN — the save is fixed; the resolver is not |
| **Severity** | 🔴 crew-visible |
| **Area** | 🗺️ GIS / address resolver · 🖥️ Kiosk view |
| **Blocks** | The operator's propagation ruling (2026-09-11) |
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

**Three of the operator's five arrival points were stranded this way** (measured 2026-09-11):

| Address as saved | Rows at that site | What the resolver reads | Status |
|:--|--:|:--|:--|
| `3030 Lincoln Ave` | 59 | the same row | LIVE |
| `602 Como Lake Ave 2606` | 209 | the same row | LIVE |
| `1800 Austin Ave` | 53 | a *different* row with the same address | **STRANDED** |
| `2865 Glen Dr` | 85 | a *different* row with the same address | **STRANDED** |
| `2929 Barnet Hwy 1202` | 236 | `2929 Barnet Hwy 2112` | **moved 2026-09-11, now live** |

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

## Fixed

* **`d4989cd`** — the save writes the row the caller names (`parcel_id`, which the lookup
  already returns); an ambiguous match is refused with a 409 rather than guessed. Deployed,
  API rebuilt on the kiosk, `ParcelEntranceSchema` verified on the running instance.
* **`1ba6e09`** — a refused save renders a red **NOT SAVED** block naming the padlock, instead
  of a 10 px red line under the form. It was that, plus closing the card cancelling the
  placement, that made a misfiled write look like a lost one.
* **2026-09-11, by hand** — the operator's mall ruling moved from `2929 Barnet Hwy 1202`
  (id 181959) to `2929 Barnet Hwy 2112` (id 181939), the row the resolver reads, on his
  instruction. Values copied verbatim including `entrance_set_at`: the filing was corrected,
  the decision was not remade.

## Open

1. **The resolver still picks by lowest id.** Suite 2112 is the mall's arrival point today
   only because it sorts first. A re-import that renumbers rows moves it silently. Until the
   propagation below lands, the hand-moved row is a stopgap and nothing guards it.
2. **`1800 Austin Ave` and `2865 Glen Dr` are still stranded** — same address text, different
   row. Left for the operator to decide (they are his rulings; moving them is the same
   one-row operation).
3. **The operator's ruling, 2026-09-11**, is the design to build to:
   > *"the base building arrival point should be propagated to all the suites, and if the
   > suite has an arrival point different from default (set manually), leave it alone."*

   The brief's §4 records the three hazards the data puts in its way: `gis_id` cannot be the
   grouping key (the mall's base row has a **null** `gis_id` while its 235 suites carry one,
   and the null bucket is 1,671 unrelated addresses); "the main one" is not unique (two rows
   are addressed exactly `2929 Barnet Hwy`); and a propagated copy needs to be
   distinguishable from a hand-set one or the next propagation destroys it (CLAUDE.md §6.6).
4. **Named tenants are not covered by that ruling.** 151 of 289 sub-addresses in the corpus
   are names with no digits (`Rain City Housing`, `Coquitlam Center Mall`), and the operator's
   own example — London Drugs — is one. `public.custom_places`, which CLAUDE.md §1 names as
   the home for a named place, **does not exist in the database**.

## Not a live routing error

All 236 rows at 2929 Barnet Hwy share one `front_lat`/`front_lng`, and
`dest = entrance_lat or front_lat or centroid_lat`. With no arrival point set, every row gives
the same destination, so which row the resolver picks changed nothing before this feature
existed. **Fixing the resolver's row choice will move no routes** until an arrival point is in
play. Said here because it is the obvious thing to get wrong when reading §3 of the brief.
