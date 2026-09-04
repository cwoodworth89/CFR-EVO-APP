# Punch list #51a — Add cross_street_1 and cross_street_2 to the review panel for HITL verification

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3732 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 51. Add cross_street_1 and cross_street_2 to the review panel for HITL verification
> **Status**: ✅ **Closed 2026-08-31.** *(Opened as: Open — Feature request logged.)*
* **Requirement**: The parser extracts cross_street_1 and cross_street_2, but they need to be fully exposed, verifiable, and editable by dispatchers in the Human-In-The-Loop (HITL) review panel.
* **Context**: This will allow operators to correct or confirm cross streets during the review process, ensuring accuracy for routed crews.

---

## 51a (closed). The XStreet fields are in the review panel

> **Status**: ✅ **Closed 2026-08-31.** Verified in the working tree, not inferred.

`frontend/src/components/review/VerificationSidebar.jsx:623-650` renders **XStreet1 and
XStreet2 side by side as editable inputs**, each showing the system value with click-to-import
(📥) or `Ctrl+Space`, and `Ctrl+Enter` to submit. The requirement — *fully exposed, verifiable
and editable by dispatchers* — is met on all three counts.

The backend persists them: `verified_x_street_1` / `verified_x_street_2` exist as columns
(`api/models.py:50-51`), are returned by `routers/dispatches.py:58-59` and accepted in
`schemas.py:45-46`.

The component's own comment records the distinction that matters operationally, and it is
worth keeping: **XStreets are the "near \<road\> and \<road\>" block reference — they *can*
intersect the incident street but need not, and often run parallel. The Intersection field is
a different thing: the incident location itself, when the call is to a junction.** Conflating
the two is what **#51b** was about.

Closed as already-done. It is the sixth item found this way on 2026-08-31, which is why
CLAUDE.md §6.6 now says to query before working an item.
