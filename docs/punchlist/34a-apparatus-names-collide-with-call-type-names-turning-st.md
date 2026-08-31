# Punch list #34a — Apparatus names collide with call-type names, turning STT damage into a confident wrong answer

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🏷️ Response Terminology & Status Colour |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L1925 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 34. Apparatus names collide with call-type names, turning STT damage into a confident wrong answer
> **Status**: ⚠️ **Open — found 2026-08-23 investigating `DISP-2026-A19179`.** **Confirmed**
> by re-running current code against the kiosk database. Characterised only; no fix applied.

**`Rescue` is both an apparatus type and a call type.** When STT garbles the incident
phrase, the apparatus name supplies a false call type — and does so at maximum score.

#### The worked case

`DISP-2026-A19179` (2026-07-29, 54.9s, rated FAILED). Ground truth
`Alarm Activated - High Risk`.

```
verified_transcript : ...respond emergency alarm activated high risk 1188 pinetree way near...
raw_transcript      : ...respondents way near glen drive and atlantic avenue...
```

STT collapsed *"respond emergency alarm activated high risk 1188 pinetree"* into
*"respondents"* — **the incident phrase is simply not in the transcript.** What remains is
the unit list, `engine 1 engine 2 rescue 2`, and `Rescue` is an active call type:

```
step-1 exact substring hits : ['Rescue']          <- "rescue 2" contains "rescue"
token_set_ratio('rescue', transcript) = 100       <- subset trap, would also fire
ratio('rescue', transcript)           =   7       <- what the name implies
```

Both matching stages independently produce `Rescue`. There is no path to `Unknown Incident`.

#### This is not a regression, and not the alias work

* Verified by re-running with `aliases={}`: still `Rescue`. The 2026-08-23 alias change is
  not the cause.
* The **stored** value is `Unknown Incident` (confidence 0.00) — correct at the time. The
  `Rescue` call-type row was created **2026-08-21**, three weeks *after* this call ran. The
  2026-08-21 vocabulary seeding introduced a term that collides with an apparatus name.

This is the §4.2 ghost-defect check run in the opposite direction, and worth noting as a
pattern: *older calls usually show already-fixed defects, but a vocabulary addition can make
a historical call newly wrong.* Re-running current code is what distinguishes the two.

#### Why it matters more than one call

Collisions between `UNITS_VOCABULARY` and `call_type`: **`Rescue`, `Hazmat 1`, `Hazmat 2`,
`Hazmat 3`.**

| Measure | n |
|:--|--:|
| Calls mentioning rescue apparatus (`rescue` + digit) | 64 |
| …verified as an incident **other** than `Rescue` (latent exposure) | 24 |
| …currently misclassified because of the collision | **1** |
| Calls whose true incident genuinely **is** `Rescue` | 7 |

Exposure is 1 of 24 because longest-first ordering saves it: when the real incident phrase
survives STT, the longer term (`Alarm Activated - High Risk`, 27 chars) is tested before
`Rescue` (6 chars) and wins. **The collision only bites when STT has already damaged the
incident phrase** — precisely when the system should be reporting `Unknown Incident`.

So the defect does not create wrong answers on its own. It **converts honest failures into
confident ones**, which is the more dangerous direction (CLAUDE.md §6.1). `Rescue` is a
legitimate call type on 7 verified calls, so it cannot simply be removed.

#### Fix, validated against the corpus but NOT applied

**Operator ruling 2026-08-23 supplied the rule**: the apparatus is always `Rescue 1`,
`Rescue 2` — never bare — and the call type is announced **after** the units. The
announcement template is:

```
[units] respond [routine|emergency] [CALL TYPE] [address] near [cross streets] ...
```

So the call type occupies the slot *after* `respond [mode]`, and everything before it is the
unit list.

**A first attempt keyed on "followed by a digit" and was wrong** — worth recording so it is
not retried. The call type is *also* followed by digits, because the address number comes
next: `"respond routine, rescue, 2968 glen drive"` reaches STT as `"Rescue 2, 968 Glen
Drive"`. Six of the seven true-`Rescue` calls have no bare `rescue` at all.

The rule that does work, tested over all 202 verified calls:

1. Match the call type only in the text **after** the `respond [mode]` marker.
2. A round with **no** `respond` marker is a **unit tail, not an announcement** — it has no
   call-type slot and is skipped entirely.
3. Across rounds, the **most specific** match wins (see below).

| | correct | wrong |
|:--|--:|--:|
| current (whole transcript) | 193/202 | 4.5% |
| proposed | 193/202 | 4.5% |

**One call changes**: `DISP-2026-A19179` goes from `Rescue` — confident and wrong — to
`Unknown Incident`, which is the honest answer for a transcript that never contained the
incident phrase. No regressions. Same accuracy, strictly better on the axis that matters
(CLAUDE.md §6.1: an unknown reported as unknown is a correct answer).

`split_rounds` already isolates the problem cleanly:

```
round 1: 'coquitlam engine 1 engine 2 rescue 2 respond way near glen drive ... map grid 82'
         -> has respond, nothing in the call-type slot -> Unknown  (correct)
round 2: 'coquitlam engine 1 engine 2 rescue 2'
         -> no respond marker: a unit tail -> skipped  (currently the source of 'Rescue')
```

#### Step 3 is not optional — it is punch-list #44's round-1 bias in miniature

Selecting the **first** non-Unknown round instead of the most specific one **breaks**
`DISP-2026-E792B0`:

```
round 1: 'medical aid epidominal pain'   <- STT garbled -> matches only 'Medical Aid'
round 2: 'medical aid abdominal pain'    <- correct     -> 'Medical Aid - Abdominal Pain'
```

Current code gets this right **by accident**: it matches against both rounds concatenated, so
round 2's correct wording is in the string and longest-first finds the qualified type. Any
move to per-round parsing must therefore choose the most specific answer across rounds, or it
reintroduces the round-1-wins defect described in
[`parser_audit_handoff.md`](parser_audit_handoff.md) §5 — which
[`pipeline/phase2.py:146`](../backend/cfr_dispatch/pipeline/phase2.py) still has for
addresses (`next(...)`, first candidate wins, unconditionally, across 201 double-round calls).

Related: the subset trap inventory in #19, and `Rescue`'s `token_set_ratio` of 100 above is
a fifth instance of it.

#### Numbering note — resolved

Two items were briefly numbered 33, written concurrently by two sessions. Operator ruling
2026-08-23: the **call-type vocabulary** item was renumbered to **#43**; "Legacy worked-example
placeholders…" keeps **#33**. Code comments citing "punch-list #33" in `config/vocab.py`,
`parser/call_types.py`, `api/routers/vocabulary.py`, the two vocabulary scripts and
`docs/standards/README.md` were updated to #43 in the same commit. The `#33` citation in
`review/VerificationSidebar.jsx` for the placeholder defect is correct and was left alone.

---

## 🖥️ Live Operation Batch, 2026-08-23

Eight items reported by the operator from one review session. Each was characterized
read-only against the working tree and the running kiosk; what was measured is stated.
