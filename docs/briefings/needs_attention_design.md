# Needs attention: the design

**Answers:** [`needs_attention_design_request.md`](needs_attention_design_request.md).
**Status:** direction agreed with the operator 2026-09-13, as a one-page sketch. **Not built.**
Most of it writes to the `cfr` schema, which is not built either
([`../standards/operator_data.md`](../standards/operator_data.md), ruling 1); what can be built
before it is listed at the end.

## Where it lives

On the console, behind the existing admin unlock. A **Needs attention** entry swaps the left
sidebar for the queue. Everything else is Explore as it is: the map in the middle, the aerial and
Street View tiles on the right, with a work panel under the tiles. No new screen.

```
┌ CONSOLE · ADMIN ──────────────────────────────────────────────────────────────────┐
│ NEEDS ATTENTION          │                                    │ AERIAL             │
│ ───────────────────────  │                                    │   [lot outline]    │
│ No City road         40  │                                    ├────────────────────┤
│ Not in City data     24  │               MAP                  │ STREET VIEW        │
│ After refresh         —  │                                    │                    │
│ ───────────────────────  │    ○  suggestion — not placed      ├────────────────────┤
│ 2973 GLEN DR    PENDING  │    ◆  your pin                     │ PLACE THIS ADDRESS │
│ PINECONE BURKE  PENDING  │    ┄┄ tied lot · 2963 Glen Dr ┄┄   │ Evidence (optional)│
│ …                        │                                    │  [ ] dispatches    │
│                          │                                    │  [ ] City label pt │
│                          │                                    │  [ ] Street View   │
│                          │                                    │ Note  [__________] │
│                          │                                    │ Initials [__] · now│
│                          │                                    │ [ Save as placed ] │
│                          │                                    │ Reject…   Skip     │
└───────────────────────────────────────────────────────────────────────────────────┘
```

Counts measured on the kiosk 2026-09-13. **No City road is 40 addresses**, not the 44 a first
reading of the request's table gave: Fremont St has nine lots but only five carry a number. The 1,660 base sites without an arrival
point are not a heading (operator answer 1).

## Working one item

* Picking a row moves the map to it.
* Anything the system can offer — the City's label point, where a past dispatch landed — shows as a
  **hollow marker labelled *suggestion***. It never pre-fills the pin; a person places it
  (request rulings 2 and 3).
* **Save needs the operator's initials** and nothing else. Evidence is optional and recorded when
  ticked (operator answer 4). The note carries what a crew needs, including gated access — *Harper
  Rd FSR, locked gate* — exactly as the arrival point's note already does.
* **A tie to a lot** is drawn dashed and labelled with the lot's own address, so its outline cannot
  be read as the added address's footprint. An added civic number stays its own row, never folded
  into the lot (`operator_data.md` rulings 5 and 6).

## Statuses

Plain text chips.

```
PENDING ──► PLACED ──► RETIRED                 (the City later holds the address)
   └──────► REJECTED · reason required
PLACED ───► ORPHANED ─► keep / move / retire   (after a City refresh)
```

The refresh's orphans and retirements join the same list under their own heading, not a second
screen (`operator_data.md` rulings 3 and 13).

## On the kiosk

Follows the `kiosk-responsive-ergonomics` skill.

| Placed data | What crews see |
|:--|:--|
| Arrival point and note | The existing emerald *Arrival point* notice with its note, unchanged — a locked gate stays there for now (operator answer 2) |
| Added address (#82) | The address shown normally in phase 1, with a quiet *Placed by the operator* line — not the amber approximate-location banner (request ruling 6) |
| Tie to a lot | The added point as the target, **and the tied lot's outline drawn dashed so it can be reviewed** (operator answer 3) |

## Operator answers, 2026-09-13

1. **The 1,660 base sites without an arrival point** will be reviewed slowly over time. Not part of
   this queue now.
2. **A locked gate** stays in the arrival-point note and its existing notice. No separate warning.
3. **The tied lot** is drawn on the dispatch display, so it can be reviewed.
4. **No hard evidence requirement.** Notes carry the operator's initials, as the arrival point's do.
   *This relaxes the request's first ruling, "at least one piece of evidence": evidence is optional,
   initials are required.*

## What can be built before the `cfr` schema

| Part | Needs | Buildable now |
|:--|:--|:--|
| The queue list, heading **No City road** (40 addresses) | A read-only query; nothing stored | Yes |
| Working those lots | The arrival point on `public.parcels` (`entrance_*`), already built and live | Yes — but it is today's storage; ruling 1 moves hand data to `cfr` |
| **Not in City data** (24 addresses, #82), ties to lots, PENDING / REJECTED with a reason, evidence | The `cfr` schema | No |
| **After refresh** | The semi-manual refresh (ruling 3) | No |
| Base sites (1,660) | — | Deferred (answer 1) |

## The No City road list, until there is a screen

Operator decision 2026-09-13: **the list now, the queue screen once `cfr` exists.** Arrival points
on these addresses are placed through Explore search and the existing placer, which already records
the initials (`entrance_set_by`). The list is this query, not a copy, so it cannot go stale — a
placed arrival point drops the row out:

```sql
SELECT street || ' ' || streettype AS street, house, address, gis_id
FROM public.parcels
WHERE NOT is_base_site
  AND front_lat IS NULL
  AND NULLIF(TRIM(house::text), '') IS NOT NULL
  AND entrance_lat IS NULL
ORDER BY street, NULLIF(regexp_replace(house::text, '\D', '', 'g'), '')::int NULLS LAST, house;
```

On 2026-09-13 it returned **40 rows, none with an arrival point**, matching the counts in
`operator_data.md` §5 (Pinecone Burke Mtn 28, Coronation Cres 7, Fremont St 5). **All 28 Pinecone
Burke Mtn addresses share one City lot, `!8180021`** — one parcel behind the Harper Rd FSR gate
carrying 28 civic numbers. The placer sets an arrival point per address, so as built that is 28
placements.
