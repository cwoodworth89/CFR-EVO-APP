# Punch list #79 — A descriptor inside the spoken address placed a call 1.3 km away

| | |
|:--|:--|
| **Status** | **REPORTED, not fixed.** Measured 2026-09-12 on the kiosk database. One occurrence in the corpus; the parser path that produced it is unchanged. |
| **Severity** | 🔴 crew-visible |
| **Area** | 🗣️ Dispatch parser · 🗺️ GIS / address resolver |
| **Ruling** | Operator, 2026-09-12: *"the xstreet terms/vocab should NEVER show in a main address to my knowledge. Maybe an intersection call, I don't know."* |
| **Origin** | Found while wiring the XStreets descriptor vocabulary ([#78's sibling work](../../backend/cfr_dispatch/pipeline/near_roads.py)); the operator raised the rule and the corpus had a case of it. |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happened

`DISP-2026-282647`. Locution put the descriptor **inside the address**, in parentheses:

> *"Coquitlam Medic 1, respond emergency, medical aid - overdose, **lougheed highway (near
> turning lane) Superstore Town Center**, use talk group 10 combined response coquitlam,
> map grid 68"*

The parser carried the parenthetical through as part of the address:

| | |
|:--|:--|
| Stored address | `Lougheed Hwy (Near Turning Lane)` |
| Placed at | 49.263121, -122.798193 |
| Operator's `verified_address` | `3000 Lougheed Hwy` → 49.273763, -122.791367 |
| **Off by** | **1,284 m** |

There is no house number in the broadcast, so the resolver had a street name polluted with a
descriptor and nothing else to go on. `location_type` is null, `review_flags` is absent — the
record predates the flag list, so **nothing on the screen said the placement was doubtful**.
That is the §7.1 test: a plausible wrong answer a crew cannot see through.

## It landed outside the zone the broadcast named

Operator, 2026-09-12: *"It picked a spot outside it's emergency zone map???"* It did.

| | |
|:--|:--|
| Grid announced | **68** |
| Zone containing the placed point | **61** |
| Zone containing `3000 Lougheed Hwy` | **68** ✓ |

The broadcast carried the answer the whole time. The placement contradicted the dispatcher's
own grid and nothing compared the two, because this record predates `GRID_MISMATCH`.

**Today it would be caught.** `compute_review_flags` raises `GRID_MISMATCH` when the announced
`map_grid` differs from the `derived_map_grid` of the zone the address sits in (#72): 55
dispatches now carry a derived grid and 4 of them raised the flag. So the *silence* is fixed;
the 1.3 km placement is not. This item is about the placement — a flag is a person's cue to
look, not a correction.

## Why the descriptor vocabulary does not fix this

The [`xstreet_descriptor` vocabulary](../../backend/migrations/2026-08-23_xstreet_descriptor_vocabulary.sql)
and its read side (2026-09-12) work on the **XStreets field**. This call never reached that
field: the descriptor was inside the address string, and `x_street_1`/`x_street_2` are both
null on the record. The two are separate paths.

## Measured scope

One dispatch of 617 carries a descriptor term in its main address. Measured at the same time,
across every descriptor term in the vocabulary:

| Where | Hits |
|:--|:--|
| `target->>'address'` | **1** — this record |
| `verified_address` | 0 |
| `parcels.street` | 0 |
| `roads.fullname` | 0 |

The last two matter: **no Coquitlam street is named anything like a descriptor term**, so a
rule that refuses descriptor text in an address cannot collide with a real street name. That
is what makes the operator's rule safe to enforce rather than merely plausible.

## The rule, as far as the operator will commit to it

Operator, 2026-09-12: *"the xstreet terms/vocab should NEVER show in a main address to my
knowledge"*, then — asked whether an intersection could be the exception — *"I don't know if a
dispatch can come in as 'Lougheed Hwy and Turning Lane' … I feel like it could."*

Recorded as a **leaning, not a ruling**, because he hedged it and the corpus cannot settle it:
**0 of 617 dispatches** announce an intersection with a descriptor on one side. So a fix must
be written to *allow* that shape rather than forbid descriptors outright — the cheap direction
to be wrong in, since allowing it costs nothing today and forbidding it would silently mangle
the first real one.

What would settle it is the next such broadcast, or a look at Locution's own address grammar.
Until then a fix should target the case that is actually evidenced: a **parenthetical** inside
a single-street address, which is what this record is.

## Falsifier

Strip the parenthetical from this transcript and re-resolve: the address becomes
`Lougheed Hwy` with no house number, which should raise `LOCATION_UNRESOLVED` (Tier 1, the
amber standby card) rather than place a point. A visible unknown 1.3 km from nothing beats an
invisible wrong answer 1.3 km from the call (CLAUDE.md §6.1).
