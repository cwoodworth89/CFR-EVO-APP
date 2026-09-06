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

**9 open** (3 crew-visible) · **74 closed** → [`punchlist/_closed.md`](punchlist/_closed.md)

---

## Open — 9

| ID | Severity | Status | Item |
|:--|:--|:--|:--|
| **1** | 🔴 crew-visible | OPEN | [Erratic Routing Loops & Intra-Municipal Path Preference](punchlist/01-erratic-routing-loops-intra-municipal-path-preference.md) |
| **19a** | 🔴 crew-visible | OPEN | [Remaining fuzzy-match sites have not been reviewed](punchlist/19a-remaining-fuzzy-match-sites-have-not-been-reviewed.md) |
| **64** | 🔴 crew-visible | OPEN | [Sixteen dispatched civic numbers are absent from the City's address layer](punchlist/64-sixteen-dispatched-civic-numbers-are-absent-from-the-citys-a.md) |
| **60** | ⚪ hygiene | DEFERRED | [`DriverStationSetup` is a placeholder, not in operational use](punchlist/60-driverstationsetup-is-a-placeholder-not-in-operational.md) |
| **35a** | 🟠 operational | OPEN | [Google Street View panel still not working](punchlist/35a-google-street-view-panel-still-not-working.md) |
| **49** | 🟠 operational | OPEN | [Access-point review UX — operators cannot set an entrance without direct SQL](punchlist/49-access-point-review-ux-operators-cannot-set-an-entrance.md) |
| **32** | ⚪ hygiene | DEFERRED | [QA review: re-derive the amber "needs attention" threshold once more calls are rated](punchlist/32-qa-review-re-derive-the-amber-needs-attention-threshold.md) |
| **37** | ⚪ hygiene | OPEN | [Close button and timer timeout should not dismiss to the same place](punchlist/37-close-button-and-timer-timeout-should-not-dismiss-to-th.md) |
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
