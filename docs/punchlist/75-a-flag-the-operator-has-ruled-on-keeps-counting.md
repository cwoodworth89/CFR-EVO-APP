# Punch list #75 — A flag the operator has ruled on keeps counting

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🧑‍⚖️ Review screen |
| **Blocks** | — |
| **Origin** | Operator, 2026-09-06: *"Can I make notes on calls that flag the address and the announced map grid differing. Can I rule one way or another and the system won't flag anymore?"* |

[← punch list index](../debug_and_qa_punchlist.md)

---

> **Status**: ✅ **Closed 2026-09-06 — a flag is ruled by the verified column that answers it;
> ruled flags show struck through with the ruling and no longer count.**

`GRID_MISMATCH` and the other review flags are what the system saw at capture, stored on the
record and never rewritten. Until today the review counted them forever: a call the operator
had already verified still sat in the *flagged* filter and the sidebar still said *verify or
refute*.

**The ruling is the verified value.** `frontend/src/utils/reviewFlags.js` now maps each flag
to the verified column that answers it (`GRID_MISMATCH` → `verified_map_grid`,
`XSTREET_UNRESOLVED` → `verified_x_street_1`, `RESPONSE_TYPE_UNKNOWN` →
`verified_response_type`, and so on). `getReviewFlags(call)` returns only the flags with no
ruling; `getRuledFlags(call)` returns the rest with the ruling beside them. The *flagged*
filter, the table badge and the kiosk banner count open flags only; the verification sidebar
shows ruled ones struck through, *ruled: 74*. The note goes in `review_notes` as before.

So, to answer the question: yes. Write the grid you decide on into the verified map-grid box
(the announced one or the one the address sits in), save, and the flag is ruled. Nothing on
the record is altered except your own columns, and the flag stays readable as what the
system saw.

Not done: teaching the system from the ruling. When the announced grid beats the parcel's
zone repeatedly on the same street, that is a zone-boundary question for the City data
register, and the rulings are now queryable (`verified_map_grid` set, `GRID_MISMATCH` in
`target->'review_flags'`) when someone wants to look.
