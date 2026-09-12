# Punch list #80 — An unresolved talk group looked exactly like a dispatch with no talk group

| | |
|:--|:--|
| **Status** | FIXED in the tree and built on the kiosk (`310f77a3`). **Not visually confirmed** — the chip renders only on a call with no talk group, so it waits on the operator's eye or the next such dispatch (§6.6). |
| **Severity** | 🔴 crew-visible |
| **Area** | 🖥️ Kiosk HUD · 🏷️ Review flags |
| **Ruling** | Operator, 2026-09-11: *"I actually think we can just [go] with unknown. It'll flag the driver to check the run sheet. It's so rare that a TG is not assigned, it's more likely an error. So just throw the warning and display Unknown talk group."* |
| **Origin** | Operator, 2026-09-11, on the wording in #79: *"Well, not NO talk group. Unknown talk group. No talk group is a valid form of dispatch."* |

[← punch list index](../debug_and_qa_punchlist.md)

---

## The problem

[`ActiveAlertBanner.jsx`](../../frontend/src/components/hud/ActiveAlertBanner.jsx) rendered
the talk group as `{talkGroup && (…)}`, so when there was no channel **the field vanished
entirely**. A call whose channel was announced and lost looked identical to a call with none:
both an empty row, and a crew has no way to tell one from the other.

This is §6.1 in its less obvious direction. The rule is usually read as *don't print a number
you don't have*; it equally says **don't let a gap wear the appearance of a valid state**. An
unknown rendered as a legitimate blank is a plausible wrong answer a crew can't see through.

**48 of 629 calls** carry no talk group.

## The ruling collapsed the two states rather than separating them

An earlier version of this entry proposed splitting `NO_TALK_GROUP` into "none announced"
(valid) and `UNKNOWN_TALK_GROUP` (a gap), and carrying a new boolean from the parser to do it.
The operator ruled that unnecessary: a dispatch genuinely without a talk group is so rare that
**a blank is more likely an error than a fact**, so both cases get the same treatment — warn,
and say unknown. One state, no new parser field, no migration.

That is a smaller change than the one proposed, and a better one: the distinction would have
cost a `DispatchData` field, a second flag and a frontend branch to tell a crew something that
does not change what they do. Either way they check the run sheet.

## What changed

* The HUD shows an amber **`Unknown talk group`** chip in place of the empty row — the same
  chip `Response unknown` already uses two elements along. A flagged condition, not a third
  tone of the same thing (#31), and amber is the established warning colour
  (`kiosk-responsive-ergonomics`). Nothing new was invented for it.
* The `NO_TALK_GROUP` label read *"No talk group announced or transcribed"*, which stated the
  conflation in its own wording. Now *"Talk group unknown — none announced, or not
  transcribed"*, in both copies (`review_flags.py` and `reviewFlags.js`).

The **identifier** `NO_TALK_GROUP` is deliberately unchanged: the HITL confirm/refute record
keys off it, and `review_flags.py` says to rename only with a migration. The label is prose;
the name is a contract.

## Verified so far

| | |
|:--|:--|
| `npm run lint:crash` | clean (the pre-commit crash-class gate) |
| `npm run build` on the kiosk | built, and `Unknown talk group` is present in `dist/assets/index-*.js` |
| `test_review_flags.py` | 26 passed, including the every-flag-has-wording check |
| **The chip on screen** | **not confirmed** — needs a call with no talk group |

## The map grid, on the same ruling

Operator, 2026-09-11: *"Yes, do the map grid the same way."* `{gridValue && …}` hid the grid
by exactly the same pattern on **31 of 629 calls**, and `NO_MAP_GRID` is a flag for the same
reason `NO_TALK_GROUP` is. It now shows an amber **`Unknown map grid`** chip, and its label
becomes *"Map grid unknown — none announced, or not transcribed"*.

**26 of those 31 are also missing the talk group**, so a badly-transcribed call shows both
chips at once. That is two unknowns stated twice, which is what has happened; the row is
`flex-wrap` and takes it.
