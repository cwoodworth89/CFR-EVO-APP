# CFR EVO: Debug & QA Punch List

Index only. **Each item's full history lives in its own file** under [`docs/punchlist/`](punchlist/) — open just the one you are working on.

> [!IMPORTANT]
> **One item per session.** Read this index, open a single item file, fix it, commit, verify on the kiosk.
> Anything new you discover goes to [`post_freeze_backlog.md`](post_freeze_backlog.md)
> as one line and is **not investigated** during the freeze.

**Severity** applies the CLAUDE.md §7.1 gate — *if this is wrong, can crews tell?*

| | Meaning |
|:--|:--|
| 🔴 crew-visible | Produces plausible wrong operational output. Crews cannot tell it is wrong. **Freeze scope.** |
| 🟠 operational | Degrades or interrupts operation, but the failure is visible. |
| ⚪ hygiene | Internal quality, tooling, test debt. Safe to defer past the freeze. |

**7 open** (4 crew-visible) · **81 closed** → [`punchlist/_closed.md`](punchlist/_closed.md)

---

## Open — 7

| ID | Severity | Status | Item |
|:--|:--|:--|:--|
| **77** | 🔴 crew-visible | OPEN — save fixed, resolver not | [An arrival point is saved to one parcel row and read from another](punchlist/77-an-arrival-point-is-saved-to-one-parcel-row-and-read-from-another.md) |
| **76** | 🔴 crew-visible | OPEN | [A dispatched block lands on one civic number at the block's end, and the route U-turns past it](punchlist/76-a-dispatched-block-lands-on-one-civic-number-the-route-u-turns.md) |
| **64** | 🔴 crew-visible | OPEN | [Sixteen dispatched civic numbers are absent from the City's address layer](punchlist/64-sixteen-dispatched-civic-numbers-are-absent-from-the-citys-a.md) |
| **74** | 🔴 crew-visible | BUILT, unconfirmed (3A, 2026-09-09) | [Kiosk map: no hydrants, RE-CENTER always on, details box over the pin, Street View tile buried](punchlist/74-kiosk-map-no-hydrants-recentre-always-on-details-box-over-the-pin.md) |
| **60** | ⚪ hygiene | DEFERRED | [`DriverStationSetup` is a placeholder, not in operational use](punchlist/60-driverstationsetup-is-a-placeholder-not-in-operational.md) |
| **32** | ⚪ hygiene | DEFERRED | [QA review: re-derive the amber "needs attention" threshold once more calls are rated](punchlist/32-qa-review-re-derive-the-amber-needs-attention-threshold.md) |
| **52a** | ⚪ hygiene | OPEN | [Kiosk review button formatting and review rating functionality](punchlist/52a-kiosk-review-button-formatting-and-review-rating-functi.md) |

---

## Reused numbers

Each of these numbers named more than one **unrelated** defect. Suffixes were added so every existing reference still resolves — a bare `#45` in an older commit or doc is genuinely ambiguous, and both candidates are listed rather than guessed between.

| Was | Now |
|:--|:--|
| `#19` | **19a**, **19b** |
| `#34` | **34a**, **34b**, **34c** |
| `#35` | **35a**, **35b** |
| `#43` | **43a**, **43b** |
| `#44` | **44a**, **44b** |
| `#45` | **45a**, **45b** |
| `#46` | **46a**, **46b** |
| `#47` | **47a**, **47b** |
| `#51` | **51a**, **51b** |
| `#52` | **52a**, **52b** |

Progressions that were *one* defect tracked over time were merged into a single file: **#14**, **#39**, **#40** (six blocks), **#41**, **#35a**, **#45b**.

Reconciliation history and session batch notes: [`punchlist/_session_notes.md`](punchlist/_session_notes.md).
