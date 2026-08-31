# Punch list #43a — Call-type vocabulary carries locale variants as duplicate rows; HITL captures incident as free text

| | |
|:--|:--|
| **Status** | IN PROGRESS |
| **Severity** | crew-visible |
| **Area** | 🏷️ Response Terminology & Status Colour |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L1692 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 43. Call-type vocabulary carries locale variants as duplicate rows; HITL captures incident as free text
> **Status**: 🔧 **In progress — found 2026-08-23 during the parser audit.** All counts below
> are **confirmed** by query against the kiosk database (`100.95.146.94:5432`), not read from
> code. Two records are **flagged for operator re-review** (see the last section) and are not
> being guessed at.

**Root cause is the input, not the data.**
[`VerificationSidebar.jsx:429`](../frontend/src/components/review/VerificationSidebar.jsx)
captures `verified_incident` as a bare `<input type="text">` — no datalist, no select, no
validation against `public.vocabulary`. Reviewers hand-type the incident type, so ground truth
drifts from the vocabulary the parser is matching against. Every item below is downstream of
that one control.

#### The vocabulary is doing two jobs at once

`public.vocabulary` (`category='call_type'`, 66 rows, all `source='cfr_curated'`) is
simultaneously **what the parser listens for** and **what the kiosk displays**. Where those
two disagree, the table has grown a second row instead of a second field.

Measured, `raw_transcript` vs vocabulary:

| Pair | STT writes | Reviewers confirm | Verdict |
|:--|:--|:--|:--|
| `Wildland Fire - Smoldering` / `- Smouldering` | `smoldering` **5/5**, `smouldering` **0/5** | `Smouldering` **2/2** | **not a duplicate — a recognition alias** |
| `Medical Aid - Breathing Problem` / `- Problems` | `breathing problem` **24/24** singular | split 5 / 4 | plural row is dead weight |

Whisper writes American English consistently; the department writes Canadian. The
`- Smoldering` row is the only reason those five calls classify at all — **retiring it as a
duplicate would introduce the qualifier-drop defect this audit set out to measure.**

Genuinely dead rows (zero usage on either side, safe to retire):
`Alarms Activated`, `Alarms Activated - High Risk`, `Medical Aid - Cardiac Problems`.

#### Ground truth contains terms the parser structurally cannot emit

Seven `verified_incident` values have no matching vocabulary row. `match_incident_type` returns
a vocabulary term or `Unknown Incident`, so these can never be produced no matter how good the
parse. They are vocabulary gaps, **not** parser defects:

`Structure Fire - Detached Structure`, `Tent Fire - High Risk`,
`Medical Aid - Airway Obstruction`, `Odor - Unknown Source` — legitimate, being added.

#### Correction to an earlier claim in this audit

An earlier pass in this session reported `Tent Fire - High Risk` and
`Structure Fire - Detached Structure` as **2 live parser defects**. That was wrong — both are
missing vocabulary rows. Recorded here so the claim is not repeated (CLAUDE.md §6.6).

Also corrected: the qualifier-drop class is **not** 22 live defects.
Re-running current code over the class gives **16 already correct, 6 remaining**, of which 4
were these locale variants. The stored-vs-verified figure was measuring history, exactly the
ghost-defect trap `docs/parser_audit_handoff.md` §4.2 warns about.

#### ⚠️ Flagged for operator re-review — do not guess

Two records have `verified_incident` values that are data-entry errors. The correct incident
type cannot be recovered from the vocabulary and **must not be inferred** (CLAUDE.md §6.1):

**Both records have since been cleared. Neither was an operator error.**

| Dispatch | `verified_incident` | Outcome |
|:--|:--|:--|
| ~~`DISP-2026-E05DBD`~~ | ~~`''`~~ | **CLEARED** — not a dispatch. See below. |
| ~~`DISP-2026-266B57`~~ | ~~`Assist`~~ | **CLEARED** — `Assist` was a missing vocabulary term, since added. |

`DISP-2026-E05DBD` is a **station PA page**, not a call:

```
raw_transcript      : 'Lunch, lunch is up, lunch is up.'
verified_transcript : ''      verified_units: []      verified_incident: ''
audio_duration      : 10.24s  confidence_score: 0.00  address: 'Unknown Location'
```

The reviewer emptied *every* verified field — a deliberate, internally consistent way of
marking "this is not a dispatch". Reading the empty string as a data-entry slip was wrong;
it is the correct answer to a record that should never have been created.

**This is punch-list #14 (PA page leakage) with concrete IDs.** The corpus holds at least
four non-dispatches captured as calls:

| Dispatch | Duration | Transcript |
|:--|--:|:--|
| `DISP-2026-E05DBD` | 10.2s | `Lunch, lunch is up, lunch is up.` |
| `DISP-2026-415E9F` | 8.2s | `Lunch is ready. Lunch is ready.` |
| `DISP-2026-E82B53` | 9.9s | `Medic 1, Medic 1, we're heading out.` |
| `DISP-2026-FEB541` | 10.0s | `Wilson, Wilson, you're good to go.` |

All are well under the ~25s double-round dispatch length. They contaminate any
incident-type or WER metric computed over the corpus unless excluded, and the only current
signal that they are not calls is that a human emptied their verified fields.

#### The domain model, recorded (CLAUDE.md §7.2)

No external standard governs the call-type vocabulary (`source='cfr_curated'`). The operator
supplied the model on 2026-08-23, and it is now a row in
[`docs/standards/README.md`](standards/README.md) and a comment block above `CALL_TYPES` in
[`config/vocab.py`](../backend/cfr_dispatch/config/vocab.py):

> A call type is a **main type** optionally followed by a **sub type**, joined by ` - `.
> A main type can stand on its own — 25 of 27 currently do — but most calls arrive with the
> expanded form, and the sub type is the operationally significant half.

**The two levels are deliberately not modelled separately.** One flat running list of complete
terms; ` - ` is the only structure. Do not split into main/sub categories, columns, or tables,
and do not offer or store a sub type alone — `Overdose` is not a call type,
`Medical Aid - Overdose` is.

Canonical spellings are operator decisions (`Breathing Problem` singular, `Smouldering`
Canadian). If E-Comm / Coquitlam Fire dispatch publishes an official list, it supersedes this.

#### The assist family: three distinct call types, one missing row — RESOLVED

**Correction to an earlier claim in this item.** `Public Assist`, `Lift Assist`,
`Medical Aid - Assist` and `Assist` were written up here as a naming inconsistency to be
rationalised. That was wrong. Operator ruling 2026-08-23: **they are separate call types,
not variants of one**, and the model does not require `Lift Assist` to be re-spelled
`Assist - Lift`. Nothing needed rationalising.

The actual defect was narrower and measurable: **bare `Assist` had no vocabulary row.**
`match_incident_type` can only return a vocabulary term, so dispatch saying
*"respond routine, assist, 1331 Green Bank Court"* fell through to `Unknown Incident`.

Added 2026-08-23. **Six calls recovered** from `Unknown Incident` to `Assist`:
`DISP-2026-587456`, `DISP-2026-266B57`, `DISP-2026-F1F328`, `DISP-2026-6547A7`,
`DISP-2026-511E01`, `DISP-2026-BF90E3`.

**This also clears one of the two records flagged above.** `DISP-2026-266B57` carried
`verified_incident = 'Assist'` and was flagged as an ambiguous data-entry error needing
operator disambiguation. It was neither — it was a **correct human answer to a vocabulary
gap**, and it now matches the parser exactly. Only the empty-string record remains flagged.

Worth generalising: a `verified_incident` with no vocabulary row is evidence of a **missing
term** first, and a reviewer mistake only second. The reviewer heard the call; the
vocabulary is the thing that was incomplete.

#### Two non-spoken terms retired — RESOLVED

Operator ruling 2026-08-23, after the corpus showed both had never been used:

* **`Vehicle Rollover` — retired.** `Motor Vehicle Incident - Rollover` **is** a spoken call
  type and stays; the bare form is not. Neither had ever been used and no transcript in the
  corpus contains "roll" at all, so the duplicate is gone before it could ever win a match.
* **`Public Assist` — retired.** Zero occurrences in any `raw_transcript`, `incident_type` or
  `verified_incident`. `Assist` and `Lift Assist` are the spoken forms and remain.

Both were retired via `is_active = FALSE`, not deleted, so the rows survive if either turns
out to be a real spoken form later. The script guards on live usage before retiring any term,
so re-running it is safe.

**64 active call types.** No regression: incident-type disagreement stayed at 4.5% (9/202).

#### A note for whoever extends this vocabulary next

Every change in this item was settled by **measuring the corpus, then asking the operator** —
never by reasoning from the term names. Three of this session's own conclusions were wrong and
were corrected the same way:

| Claim | Reality |
|:--|:--|
| `Smoldering` is a duplicate spelling to retire | It is the **only** form STT produces; retiring it would have broken 5 calls |
| `Assist` is an ambiguous data-entry error | A **correct** human answer to a missing vocabulary row; 6 calls recovered by adding it |
| Sub types are rare ("25 of 27 mains stand alone") | **77%** of calls carry one; 93% of `Medical Aid` |

A term's name tells you nothing about whether dispatch says it. The corpus does. Query
`raw_transcript` before adding, retiring, or merging anything here.

---
