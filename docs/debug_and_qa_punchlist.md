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

**29 open** (16 crew-visible) · **40 closed** → [`punchlist/_closed.md`](punchlist/_closed.md)

---

## Open — 31

| ID | Severity | Status | Item |
|:--|:--|:--|:--|
| **1** | 🔴 crew-visible | OPEN | [Erratic Routing Loops & Intra-Municipal Path Preference](punchlist/01-erratic-routing-loops-intra-municipal-path-preference.md) |
| **14** | 🔴 crew-visible | OPEN | [PA announcements are being captured as dispatches](punchlist/14-pa-announcements-are-being-captured-as-dispatches.md) |
| **17** | 🔴 crew-visible | OPEN | [Grade-separated interchanges have no junction to find](punchlist/17-grade-separated-interchanges-have-no-junction-to-find.md) |
| **19a** | 🔴 crew-visible | OPEN | [Remaining fuzzy-match sites have not been reviewed](punchlist/19a-remaining-fuzzy-match-sites-have-not-been-reviewed.md) |
| **20** | 🔴 crew-visible | OPEN | [`TALK_GROUPS` duplicates `public.vocabulary`](punchlist/20-talk-groups-duplicates-public-vocabulary.md) |
| **21** | 🔴 crew-visible | OPEN | [Rail crossing list is hand-entered and probably incomplete](punchlist/21-rail-crossing-list-is-hand-entered-and-probably-incompl.md) |
| **30** | 🔴 crew-visible | OPEN | ["Code 1 / Code 3" is not Coquitlam terminology, and the border has no warning or review state](punchlist/30-code-1-code-3-is-not-coquitlam-terminology-and-the-bord.md) |
| **34a** | 🔴 crew-visible | OPEN | [Apparatus names collide with call-type names, turning STT damage into a confident wrong answer](punchlist/34a-apparatus-names-collide-with-call-type-names-turning-st.md) |
| **34b** | 🔴 crew-visible | OPEN | [Live overdose call still showed the green ROUTINE (Code 1) badge](punchlist/34b-live-overdose-call-still-showed-the-green-routine-code.md) |
| **35b** | 🔴 crew-visible | OPEN | ["Near roads" stopped being recorded on 2026-08-21 — Phase 2 rebuilds `target` and drops `cross_streets`](punchlist/35b-near-roads-stopped-being-recorded-on-2026-08-21-phase-2.md) |

| **44a** | 🔴 crew-visible | OPEN | [Round 1 wins the address unconditionally — Phase 2 never compares the two rounds](punchlist/44a-round-1-wins-the-address-unconditionally-phase-2-never.md) |
| **47a** | 🔴 crew-visible | EXTERNAL | [`Chartwell Rd` does not exist in municipal data — three sources give three street names](punchlist/47a-chartwell-rd-does-not-exist-in-municipal-data-three-sou.md) |
| **51b** | 🔴 crew-visible | OPEN | [The kiosk shows the junction field labelled "cross streets", and never reads the real one](punchlist/51b-the-kiosk-shows-the-junction-field-labelled-cross-stree.md) |
| **54** | 🔴 crew-visible | SUPERSEDED | [Confidence 100 means "the two STT passes agreed", not "the location is right"](punchlist/54-confidence-100-means-the-two-stt-passes-agreed-not-the.md) |
| **56** | 🔴 crew-visible | OPEN | [Bring XStreets onto the same resolution path as main addresses](punchlist/56-bring-xstreets-onto-the-same-resolution-path-as-main-ad.md) |
| **57** | 🔴 crew-visible | OPEN | [Candidate-level parse bleed — latent, not live](punchlist/57-candidate-level-parse-bleed-latent-not-live.md) |
| **35a** | 🟠 operational | OPEN | [Google Street View panel still not working](punchlist/35a-google-street-view-panel-still-not-working.md) |
| **44b** | 🟠 operational | OPEN | [Kiosk crashed on a live dispatch — stale chunk after a frontend deploy](punchlist/44b-kiosk-crashed-on-a-live-dispatch-stale-chunk-after-a-fr.md) |
| **47b** | 🟠 operational | OPEN | [Basemap tile licensing has never been checked — Carto and Esri](punchlist/47b-basemap-tile-licensing-has-never-been-checked-carto-and.md) |
| **49** | 🟠 operational | OPEN | [Access-point review UX — operators cannot set an entrance without direct SQL](punchlist/49-access-point-review-ux-operators-cannot-set-an-entrance.md) |
| **51a** | 🟠 operational | OPEN | [Add cross_street_1 and cross_street_2 to the review panel for HITL verification](punchlist/51a-add-cross-street-1-and-cross-street-2-to-the-review-pan.md) |
| **53** | 🟠 operational | OPEN | [The dispatch agent makes a WAN call to huggingface.co on every start](punchlist/53-the-dispatch-agent-makes-a-wan-call-to-huggingface-co-o.md) |
| **55** | 🟠 operational | OPEN | [Audio Pipeline & Digital PA Architecture Alignment (Locution CAD, 15s Phase 1, 3s Silence)](punchlist/55-audio-pipeline-digital-pa-architecture-alignment-locuti.md) |
| **10** | ⚪ hygiene | OPEN | [Three test modules have never run in review](punchlist/10-three-test-modules-have-never-run-in-review.md) |
| **32** | ⚪ hygiene | DEFERRED | [QA review: re-derive the amber "needs attention" threshold once more calls are rated](punchlist/32-qa-review-re-derive-the-amber-needs-attention-threshold.md) |
| **37** | ⚪ hygiene | OPEN | [Close button and timer timeout should not dismiss to the same place](punchlist/37-close-button-and-timer-timeout-should-not-dismiss-to-th.md) |
| **45a** | ⚪ hygiene | OPEN | [Geocoder harness needs a review pass before its numbers are trusted again](punchlist/45a-geocoder-harness-needs-a-review-pass-before-its-numbers.md) |
| **46a** | ⚪ hygiene | OPEN | [No STT harness exists — WER is computed for training, never for regression](punchlist/46a-no-stt-harness-exists-wer-is-computed-for-training-neve.md) |
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
