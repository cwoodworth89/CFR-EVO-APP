# Punch list #39 — Review table: restore the verified value in the row, drop the pencil-and-legend

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🖥️ Live Operation Batch, 2026-08-23 |
| **Blocks** | 2 |
| **Origin** | `debug_and_qa_punchlist.md` L2216–2439 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 39. Review table: restore the verified value in the row, drop the pencil-and-legend
> **Status**: ✅ **Closed 2026-08-23.** *(Opened as: ⚠️ Open — operator wants the earlier behaviour back, with a caveat below.)*

The operator ask: *"I just want to see the accurate information in the row if it has been
verified, and if something was updated by a reviewer, make that obvious."*

**What it is now**: `SystemVsVerified` in `frontend/src/components/review/ReviewTable.jsx:17`
renders the **system** value plus a `✎` marker, with the verified value only in a `title`
tooltip, and a `✎ = corrected` legend in the column header (`:169-170`).

**What it was**: the column showed the **verified** value once `feedback_submitted` was set,
replacing the system value outright.

**Why it was changed — this matters, and it is documented at `ReviewTable.jsx:4-16`.** The
column is headed *"System Output"*, and swapping in the human answer meant a call whose
system address was **wrong** looked identical to one that was **right** — hiding the exact
disagreement the list is scanned to find. The stated reason for the tooltip rather than an
inline pair was column width: two values on one line clipped the address.

**So neither design is what the operator actually asked for.** The ask is *both*: show the
accurate (verified) value **and** make the correction obvious. That is achievable and is a
third design, not a revert:

* Render the **verified** value as the primary text when one exists.
* Style it distinctly — colour or weight — so a corrected row is obvious at a glance without
  a legend to decode.
* Keep the **system** value reachable (tooltip, or the review panel, which already shows both
  side by side when a row is selected).
* Consider renaming the column, since it would no longer be "System Output".

**Recommendation**: do not simply revert. Reverting reintroduces the defect the comment
describes — a wrong system answer becoming invisible — which is a §6.6-style honesty problem
in the one view used to audit accuracy. **Confirm the design with the operator before
building it**, in particular whether the column should remain system-first or become
verified-first with the system value on hover.

---

---

## 39 (revised). Review table now shows verified data, marked
> **Status**: ✅ **Closed 2026-08-23** to the operator's specification. Not yet deployed.

Operator direction: *"If verified data is different from system data, I want it marked (by
bolding, or a slight color change), and have a hover over show system original hypothesis."*

`SystemVsVerified` in `frontend/src/components/review/ReviewTable.jsx` now:

* renders the **verified** value when it differs from the system value, in **amber and bold**,
  with `title` = *"Corrected by reviewer. System originally produced: …"*;
* renders the system value plainly when there is no correction, or the correction is only
  whitespace/case.

The column header changed from **"System Output — ✎ = corrected"** to **"Call Data — amber =
reviewer corrected"**, since it no longer shows system output unconditionally.

This is the third design, not a revert, and the full history is preserved in the code comment:
the original showed verified values *unmarked* (hiding disagreement), the second showed system
values with a pencil (burying the accurate address behind a hover and needing a legend). The
current one makes the row read true at a glance while keeping the correction visible and the
system hypothesis one hover away. `lint:crash` and `npm run build` pass.

---
