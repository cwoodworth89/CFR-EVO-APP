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

**18 open** (14 crew-visible) · **83 closed** → [`punchlist/_closed.md`](punchlist/_closed.md)

---

## Open — 18

| ID | Severity | Status | Item |
|:--|:--|:--|:--|
| **91** | 🔴 crew-visible | OPEN — severity and id ruled 2026-09-16, backend with gis-spatial-engineer; text placeholders not yet ruled | [Road closure fields the feed did not send are filled with invented values, including the access level](punchlist/91-road-closure-fields-the-feed-did-not-send-are-filled-with-invented-values.md) |
| **90** | 🔴 crew-visible | BUILT `e3009d6a` + `2978da7e`, **not deployed**; card placement ruled 2026-09-16, small follow-up with frontend-kiosk-architect; latent, 177 rows, 0 null on the kiosk | [A road closure with no coordinates is drawn at a hardcoded point near Coquitlam Centre](punchlist/90-a-road-closure-with-no-coordinates-is-drawn-at-a-hardcoded-point.md) |
| **89** | 🔴 crew-visible | DEPLOYED 2026-09-16 (operator reports; not confirmed by lead against the kiosk); **falsifier not yet run**. Any-feed-failed ruled "any for now" — as built | [A failed road closure sync leaves the last list on screen, with no warning](punchlist/89-a-failed-road-closure-sync-leaves-the-last-list-on-screen-with-no-warning.md) |
| **88** | 🔴 crew-visible | BUILT `bdcea8bc`, live 2026-09-15 (`cfr-agent` 16:52, `cfr_api` restarted); no live call has raised it yet | [A destination far from any road reaches the crew as an ordinary ETA: the snap distance is never read](punchlist/88-a-destination-far-from-any-road-reaches-the-crew-as-an-ordinary-eta.md) |
| **85** | 🔴 crew-visible | OPEN — found 2026-09-13, not built; no call has hit it | [A lot with no road of its street's name pins at the lot's centre, with no notice](punchlist/85-a-lot-with-no-road-of-its-streets-name-pins-at-the-lot-centre-with-no-notice.md) |
| **84** | 🔴 crew-visible | OPEN — ruled 2026-09-13: remove; not built | [`KNOWN_BUILDINGS`: eight hand-coded buildings override console pins, three of them wrong](punchlist/84-known-buildings-hand-coded-coordinates-override-console-pins.md) |
| **83** | ⚪ hygiene | OPEN — not built | [Phase 1's transcript is deleted, so the first screen crews see cannot be measured](punchlist/83-phase-1s-transcript-is-deleted-so-the-first-screen-cannot-be-measured.md) |
| **82** | 🔴 crew-visible | OPEN — design agreed 2026-09-13, not built | [A dispatched address that no City source holds is only ever estimated](punchlist/82-a-dispatched-address-no-city-source-holds-is-only-ever-estimated.md) |
| **81** | 🔴 crew-visible | FIXED in the tree 2026-09-13; needs a `cfr-agent` restart, not seen on screen | [A split street name raised a false warning, and a fuzzy junction passed the phase 1 gate](punchlist/81-a-split-street-name-and-a-fuzzy-junction-reached-the-crew-as-a-warning-and-a-place.md) |
| **80** | 🔴 crew-visible | FIXED `310f77a3`, built; chip not yet seen on screen | [An unresolved talk group looks exactly like a dispatch with no talk group](punchlist/80-an-unresolved-talk-group-looks-like-a-dispatch-with-no-talk-group.md) |
| **79** | 🔴 crew-visible | FIXED `c59a376`, deployed and running 2026-09-11 | [A venue talk group loses to channel 10, and the venue's name in the vocabulary was wrong](punchlist/79-a-venue-talk-group-loses-to-channel-10-on-list-order.md) |
| **77** | 🔴 crew-visible | FIXED `ec34d27`, awaiting kiosk restart | [An arrival point is saved to one parcel row and read from another](punchlist/77-an-arrival-point-is-saved-to-one-parcel-row-and-read-from-another.md) |
| **78** | 🔴 crew-visible | CLOSED — confirmed on the running system | [Saving a Street View overwrites the parcel's computed frontage](punchlist/78-saving-a-street-view-overwrites-the-parcels-computed-frontage.md) |
| **79** | 🔴 crew-visible | REPORTED, not fixed | [A descriptor inside the spoken address placed a call 1.3 km away](punchlist/79-a-descriptor-inside-the-spoken-address-placed-a-call-1-3-km-away.md) |
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
