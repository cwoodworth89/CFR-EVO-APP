# Site locations: where department knowledge about a parcel's buildings, gates and units should live

Design note, 2026-09-19, from a conversation between the operator and lead. **Nothing built** —
the project is in a feature freeze. This is the answer to the operator's question *"do we add
department rows to the city parcels schema, and make Riverview a base building with suites, or
do we inject a lookup table? … Does our data or schema point us in a direction?"*

## What the data says today (measured 2026-09-19)

| | City rows at the address | Base row | Department data | What the CAD announces |
|:--|--:|:--|:--|:--|
| A house | 1 | none (lone row) | entrance/streetview on the row | the address |
| **Coquitlam Centre**, 2929 Barnet Hwy | 236 (234 with a unit) | 1, entrance set | on the base row | address + suite |
| **Riverview**, 2601 Lougheed Hwy | **1** (98.7 ha, no units) | none | none (unset) | address + building: `subaddress` "Number 47 Station 47" |

Citywide: 1,671 base rows; 58 entrances set (17 on base rows, 41 on lone rows).

Two facts fix the direction:

1. **Every row in `public.parcels` is a City row.** `import_parcels.py` upserts on address and
   never writes the department's columns (`entrance_*`, `streetview_*`, notes, pre-plan) — so
   department *values* survive a City refresh, as the operator intends. But a department
   *row* would not be reconciled by anything: the City never issued it, so a refresh can
   neither update nor retire it. Inventing "suite" rows for Riverview's buildings puts
   department-made rows in the City's table and breaks the one rule that keeps the two apart.
2. **The sanitizer already isolates the key.** `target.subaddress` carries exactly what the CAD
   added ("Number 47 Station 47", a suite number, a unit). The thing to look up by exists on
   every call without new parsing.

## Recommendation: a child table, not more parcel columns and not fake suites

`public.site_locations` (name open), one row per place the department knows on a parcel:

| Column | Meaning |
|:--|:--|
| `parcel_id` | the City row it hangs off (the base row where one exists, else the lone row) |
| `label` | what the CAD says, verbatim-normalised: `47`, `Station 47`, `Unit 12`, `Food court entrance` |
| `kind` | `building` · `unit` · `entrance` · `gate` — for humans and the display, not for logic |
| `lat`, `lng` | the point itself |
| `arrival_lat`, `arrival_lng` | where the truck stops for it (may differ from the point) |
| `use_entrance` | which of the parcel's entrances/gates serves it — Riverview's entrances change with the destination |
| `streetview_*` | a saved view for this place |
| `notes` | hydrants, hazards, "road impassable past this point" |
| `set_by`, `set_at` | provenance, §6.3 tier 4: a named person, a date |

**Resolver cascade** (in front of today's entrance → frontage → centroid at `address_resolver.py:370`):

    announced subaddress → site_locations match on (parcel, label) → its arrival point
                        → no match → the parcel's own entrance → frontage → centroid

Nothing changes for a parcel with no rows in the table. The near-road search (`near_roads.py`,
400 m) runs from the matched point, so Thyme Dr resolves at ~100 m instead of failing at 1.17 km.

## Why this answers the terminology question without a new flag

The operator's proposed split — *base building* (one building, many suites) vs *complex* (one
parcel, many buildings) — describes real cases, but Coquitlam Centre is both (234 City suites
**and** several entrances to different parts of one building), and Riverview is neither in the
City's eyes. A type flag on the parcel would have to pick one and be wrong for the mall. With a
child table the question dissolves: **a parcel either has site locations or it does not.**
`is_base_site` keeps its present meaning (the one City row that speaks for a multi-row address);
"complex" becomes a word for a parcel with `building`/`gate` rows, not a column.

- Townhouse and trailer-park units (the cascade the operator was already considering): rows of
  kind `unit`, keyed by the unit number the CAD announces. Same table, same cascade.
- The mall: rows of kind `entrance` keyed by what appears in the notes ("Food court", a store
  name) — usable only if the dispatch notes reach us, which today they do not (the operator: "if
  we had the initial dispatch notes").
- Riverview: rows of kind `building` (Station 47 …) and `gate`, each building naming its gate.

## Provenance and what must not happen

Every row is department knowledge — a pre-plan, a site walk, a company officer — and says who
and when. No row is derived from City geometry or OSM footprints: a building point nobody stands
behind is the plausible wrong answer §6 forbids. Recorded as an open gap in
[`../standards/README.md`](../standards/README.md) ("Building locations on multi-building sites").

## Open, for the operator when he returns to it

- Whether the CAD's building labels are stable enough to key on ("Number 47" vs "Station 47" on
  the same call — the sanitizer keeps both words; the match rule needs a ruling).
- Whether the mall entrances are worth rows without the dispatch notes.
- Where the console edits this: the review-mode arrival-point editor is the obvious home (one
  more field: *which place on this parcel*).
