# CFR EVO: Parser Audit — Handoff

**Written 2026-08-23. Start here if you are auditing the dispatch parser as a whole system.**

This is a *scoped* handoff, not a replacement for
[`docs/review_status_handoff.md`](./review_status_handoff.md) — read that one for overall
system state, the punch list, and environment gotchas. This document covers only what a
parser audit needs, and exists so that audit starts from evidence rather than from the
geocoder context it grew out of.

Companion documents:
* [`docs/qa_harnesses.md`](./qa_harnesses.md) — **the QA toolset: how to measure any change against
  historical records, and the traps that make a rate wrong.** Read it before quoting a number.
* [`docs/review_status_handoff.md`](./review_status_handoff.md) — system state and the live work queue
* [`docs/standards/dependency-behaviour.md`](./standards/dependency-behaviour.md) — verified library semantics
* [`CLAUDE.md`](../CLAUDE.md) — §6 (no fabricated data) and §7 (start from the source of record)

---

## Why this audit is worth doing

The geocoder half of this work has now been *measured* rather than read, and the result
was not what reading predicted. Of 34 historically wrong addresses in the verified corpus,
**30 no longer resolve at all** under current code — already fixed by the 2026-08-21/22
work — and only 4 still resolve to a wrong place. Reading the code would not have told you
which 4.

The parser has never had that treatment. It has ground truth available and unused.

---

## 1. The corpus: paired ground truth that is not being used

`public.dispatches` holds **what the system concluded** next to **what a human confirmed
was actually true**, for every reviewed call:

| System's answer | Human ground truth |
|:--|:--|
| `raw_transcript` (STT output) | `verified_transcript` |
| `sanitized_transcript` (see §4 — *not* a transcript) | — |
| `incident_type` | `verified_incident` |
| `responding_units` | `verified_units` |
| `target->>'address'` | `verified_address` |
| `target->>'map_grid'` | `target->>'verified_map_grid'` |
| `target->>'radio_channel'` | `target->>'verified_talkgroup'` |
| `confidence_score` | — (see §5) |

**Size, as of 2026-08-23:** 433 dispatches, **202 fully verified** (all `verified_*`
fields populated together), **432 with audio**. Ratings: 77 PERFECT, 66 OPERATIONAL,
13 FAILED, 46 verified-but-still-PENDING.

Until now this corpus was consumed almost exclusively by the STT MLOps path
(`extract_training_data.py`, `backtest_regression.py`) to compute Word Error Rate. WER
scores *transcription*. Every serious defect found in this review lived **downstream** of
the transcript — in parsing, classification, and geocoding. The same corpus scores those
too, and it is the only CLAUDE.md §6.5-compliant source of test dispatches: real records
replayed, never synthesised.

---

## 2. Measured parser baselines (2026-08-23)

Across the 202 verified calls. These are counts from the database, not estimates:

| Field | Disagrees with ground truth | Rate |
|:--|--:|--:|
| `incident_type` | **39** | 19.3% |
| `map_grid` | **19** | 9.4% |
| `responding_units` | **15** | 7.4% |
| address (see §3) | 34 | 16.8% |

**Incident type breaks into three classes**, and they are not equally serious:

| Class | n | What it looks like |
|:--|--:|:--|
| **Qualifier dropped** | **22** | `Report of Smoke` for `Report of Smoke - High Risk` |
| System gave up | 15 | `Unknown Incident` for `Medical Aid - Collapse` |
| Genuinely different type | 2 | — |

The 22 dropped qualifiers are the operationally dangerous class, and the one a WER metric
would barely register. `- High Risk`, `- Breathing Problem`, `- Overdose`, `- Assault`,
`- Airway Obstruction` change what crews bring and how they stage. The base type is
right, so nothing looks wrong on the kiosk. **This is the single most promising lead in
this document.** `Unknown Incident`, by contrast, is honest failure — it is visible.

Start at [`backend/cfr_dispatch/parser/call_types.py:38`](../backend/cfr_dispatch/parser/call_types.py)
(`token_set_ratio(ct.lower(), transcript)`, punch-list #19) and check specifically whether
a short base type scores equal-or-better than the longer qualified one. Note the subset
trap in §6 below — `token_set_ratio` of a subset returns **100**, so `Report of Smoke`
scoring against a transcript containing `Report of Smoke - High Risk` is exactly the
shape that produces this.

---

## 3. What is already covered, and what is not

`backend/scripts/trace_geocode_corpus.py` (committed `8d00ea3`) replays verified
dispatches through the live geocoder, wraps all seven resolvers to record **which step
answered**, and buckets the result against `verified_address`.

```bash
# one call, full step ladder
python backend/scripts/trace_geocode_corpus.py --dispatch-id DISP-2026-156DCF

# geocode an arbitrary string (use the text the PARSER produced)
python backend/scripts/trace_geocode_corpus.py --probe "3000 avenue"

# whole corpus, summary + per-call CSV
python backend/scripts/trace_geocode_corpus.py --all --csv /tmp/geocode_corpus.csv
```

**It covers the geocoder only.** It probes `target->>'address'`, which is the geocoder's
*own output* — so it measures whether an address round-trips, never how the parser arrived
at it. The missing half, and the natural thing for this audit to build, is:

> `raw_transcript` → **parser** → parsed fields, diffed against `verified_transcript`,
> `verified_incident`, `verified_units`, `verified_talkgroup`, `verified_map_grid`.

Reuse the classifier discipline from the geocoder harness: bucket outcomes into
*cosmetic* vs *actually wrong*, because a raw string diff massively overstates the error
rate. On the address side, unbucketed diffing said 30.2% wrong; the true figure was 16.8%,
and the gap was entirely `Ave`/`Avenue`, trailing unit numbers, and intersection leg order.
**Expect the same inflation on incident type and units.**

Also reusable: `frontend/scripts/verify_dispatch_model.mjs` — freeze the old behaviour,
run both over the real corpus, diff. That pattern is what gave real confidence on the
dispatch-model unification (421 records, 0 mismatches).

---

## 4. Three traps that will cost you time

### 4.1 `sanitized_transcript` is not a transcript

It is a **reconstruction from parsed fields**
([`parser/announcement.py:428`](../backend/cfr_dispatch/parser/announcement.py) builds it
from `dispatch.map_grid` and friends). It shows what the parser *concluded*, formatted to
look like what was said. Diffing `sanitized_transcript` against `verified_transcript` is
therefore **not** an STT measurement — it silently scores the parser while appearing to
score transcription. Use `raw_transcript` for anything STT-related.

This is also why fabricated values are so hard to spot in the review panel: they appear
inside a field that reads as a record of the audio.

### 4.1a `verified_transcript` is ONE round, not the whole audio

**Operator confirmation 2026-08-23.** The reviewer verifies a **single round**. The stored
`verified_transcript` therefore covers roughly **half** the audio, because nearly every
dispatch is announced twice (§4.3).

Confirmed by query: `respond` appears **once** in 197 of 202 verified transcripts, while the
matching `raw_transcript` carries two or more rounds.

The duplication happens **downstream, at STT training extraction only** --
[`extract_training_data.py:182`](../backend/scripts/extract_training_data.py):

```python
if duration > 25.0 and normalized_text:
    rounds = split_rounds(normalized_text, UNITS_VOCABULARY)
    if len(rounds) < 2:
        normalized_text = f"{normalized_text} {normalized_text}"
```

That exists so the Whisper training label matches the two-round audio. It is **not** applied
to the database column.

Consequences, both easy to hit:

* **Never diff `verified_transcript` against `raw_transcript` directly.** One is a single
  round, the other is two. A naive WER or string comparison reports roughly 50% error on a
  perfect transcription. Compare round-for-round, or duplicate the verified text first the
  same way the extractor does.
* **It is human-idealised.** Reviewers write correct spelling and punctuation, so it is the
  right source for deriving the *announcement grammar* but the wrong source for judging what
  STT actually produces. Anchor-reliability figures must be measured on `raw_transcript` --
  they differ sharply (§4.3a).

Same defect class as §4.1: a field whose name promises a record of the audio, which is
something else.

### 4.2 The corpus is historical — a stored defect may already be fixed

Each record reflects the code as of its date, and the geocoder was substantially rewritten
after most of these calls were captured. **30 of 34 stored address defects are already
remediated.** An audit that reports stored-vs-verified without re-running current code
will produce a punch list of ghosts.

Always separate **"was broken"** (stored value vs ground truth) from **"still broken"**
(current code re-run vs ground truth). The geocoder harness does this by replaying; do the
same for the parser.

### 4.3 Round 2 is discarded, and nearly every call has one

**201 of the 202 verified calls have `audio_duration > 25s`** — i.e. they are double-round
dispatches. The redundancy is not an edge case, it is the norm, and at least one call
throws away a correct round-2 reading in favour of a garbled round 1 (§5). Whatever
`split_rounds()` / the multi-round reconciliation is doing, it is worth measuring across
all 201 rather than reasoning about.

---

### 4.3a Anchor reliability differs sharply between verified and raw text

The announcement is a **strictly ordered template**. Across 202 verified transcripts the
marker order **never varies** -- only optional slots are omitted:

```
coquitlam [UNITS] respond [MODE] [CALL TYPE] [ADDRESS] near [CROSS STREETS] use talk group [N] map grid [N]
```

But a parser sees `raw_transcript`, not the reviewer's clean text, and the anchors survive
STT very differently. Measured over the 202 calls holding both:

| Anchor | in verified | in raw | lost |
|:--|--:|--:|--:|
| `coquitlam` (wake) | 202 | **202** | 0 |
| `talk group` | 199 | 194 | 5 |
| `respond` (exact) | 202 | 193 | 9 |
| `routine` / `emergency` | 201 | 193 | 8 |
| **`map grid`** | 202 | **165** | **37** |
| `near` | 170 | 172 | **-2** |

* **`coquitlam` is the only perfect anchor**, and it is also the least useful alone -- it
  recurs inside the talk group name (`Talk Group 5 Coquitlam`,
  `Talk Group 10 Combined Response Coquitlam`), so it anchors the *start* only.
* **`near` appears MORE often in raw than in verified text.** STT invents it. It cannot be
  used as a structural anchor, only as a hint.
* **`map grid` is missing from 37 raw transcripts -- but the defect is ALREADY FIXED.**
  Pooled over the whole corpus this reads as 18%, which is wrong and was reported that way
  first. Split by date it is unambiguous:

  | Month | missing grid | double-round calls | rate |
  |:--|--:|--:|--:|
  | 2026-07 | 37 | 205 | **18%** |
  | 2026-08 | 1 | 218 | **0%** |

  All 37 fall between **2026-07-19 and 2026-07-29**. Call volume continued normally through
  the changeover (12/day on 07-30, 14 on 07-31), so the drop to zero is real, not a gap in
  the data. The operator's audio-listener work to capture both rounds is the cause; the exact
  commit is not pinned (the 75s recording increase, `b78dbe6`, lands 08-03 -- *after* the
  defect stops -- so an earlier kiosk-side change is the more likely trigger). Max audio
  duration does rise from 59s in July to 75s in August.

  The single 2026-08 case, `DISP-2026-9B4E70`, is **not** a grid failure: 75s of audio and an
  11-character transcript reading `"Ice Coffee."` -- a PA announcement, the leakage class of
  punch-list #14.

  > **Read this as a method warning.** The 18% figure was produced by pooling a historical
  > defect across all time and reporting it as live -- the exact trap §4.2 describes, walked
  > into while citing §4.2. Any rate computed over this corpus must be split by date before it
  > is believed. The operator caught this one from intuition about the fix history.

### 4.3b The two rounds are redundancy, and it is not being used

The dispatcher announces the call twice, and the rounds are meant to be **identical**. Where
`split_rounds` separates them cleanly they are near-identical (median `fuzz.ratio` 82; 86 of
186 score 90+).

That redundancy is error correction that nothing currently exploits. **Split by date**, per
the warning in §4.3a:

| Month | rounds split | no split | grid in BOTH | **grid in ONE only** | grid in neither |
|:--|--:|--:|--:|--:|--:|
| 2026-07 | 190 | 15 | 111 | **57** | 22 |
| 2026-08 | 217 | **1** | 204 | **13** | **0** |

The July column is the pre-fix audio capture (§4.3a) and should not be used to size the work.
**On current data the cross-round merge is worth 13 calls (6%), not 57 (30%)** -- still real,
much smaller than first reported.

`split_rounds` is likewise far healthier than the pooled figure suggested: **1** failure to
split in August versus 15 in July.

The one caution that is *not* a historical artifact: merging must take the **most specific**
answer per field, never the first. Taking the first reintroduces the round-1-wins bias of §5,
which is a live defect in [`pipeline/phase2.py:146`](../backend/cfr_dispatch/pipeline/phase2.py)
for addresses today.

## 5. The worked example: `DISP-2026-156DCF`

One call that shows the whole chain. Operator's review note: *"Wrong main address, wrong map."*

**Raw STT (both rounds, verbatim):**
> "Coquitlam medic 1 respond emergency medical aid, fall **3000 avenue** near pine tree
> way and ponderosa street use talk group combined response coquitlam **map grid** ⟨blank⟩
> **3007 Anson Avenue** near pine tree way and ponderosa street use talk"

**What the pipeline produced:** `3000 Walton Ave`, map grid `85`, confidence **100**.
**Ground truth:** `3007 Anson Ave`, map grid `82`.

What this single record demonstrates:

1. **Round 1 was garbled; round 2 was correct; the pipeline used round 1.** The right
   answer was in the audio and was discarded. This is the highest-value lead.
2. **`Walton` was fabricated** — the raw transcript contains no street name at all, only
   `3000 avenue`. A §6.1 violation: the unknown should have propagated as `null` and
   rendered as the Tier 1 amber card.
3. **Map grid 85 is a cascade, not a second invention.** It is derived from the (wrong)
   coordinates at [`pipeline/payload_builder.py:149`](../backend/cfr_dispatch/pipeline/payload_builder.py).
   Consequence worth internalising: **the grid always corroborates the address**, so
   cross-checking one against the other can never catch this class of error.
4. One inference in the chain *is* defensible: raw `talk group combined response` →
   `talk group 10 combined response` fills from a unique real vocabulary entry. Don't
   "fix" that one.

**Where `Walton` came from is still unresolved, and current code does not reproduce it.**
`--probe "3000 avenue"` returns `None` today — every resolver step misses, which is correct
behaviour. So the fabrication is either upstream in the parser or already fixed. Two
readings that were *stated and then disproved by measurement*, recorded here so they are
not repeated:

* "`resolve_exact` produced Walton" — **wrong.** It scores 60 and is correctly rejected;
  `parsed_street` is `"AVENUE AVE"`, not `"AVE"`.
* "the address error rate is 30.2%" — **wrong.** Unbucketed string diffing; true rate 16.8%.

---

## 6. Verified library behaviour you can rely on

Measured against installed `rapidfuzz 3.14.5` on 2026-08-23. Re-verify before extending;
see CLAUDE.md §7.3a.

```
token_set_ratio("AVE", "WALTON AVE")   = 100.0     # subset -> 100, always
token_set_ratio("AVE", "ANSON AVE")    = 100.0
ratio("AVE", "WALTON AVE")             =  46.2     # what the name implies
token_set_ratio("AVENUE AVE", "WALTON AVE") = 60.0
```

**`token_set_ratio` returns 100 whenever one token set is a subset of the other**, because
the intersection equals one side by construction. Any site comparing a fragment against a
longer canonical string is exposed. Five such sites are inventoried in punch-list #19;
`call_types.py:38` and `channels.py:42` are the two in parser territory.

Related, in [`services/gis/src/gis_service/address_resolver.py`](../services/gis/src/gis_service/address_resolver.py):
both fuzzy sites (`:44`, `:345`) query parcels with **no `ORDER BY`** and keep the first of
any tied maximum — so among equal scores the "winner" is whatever row order Postgres
happens to return. `:345` is `validate_address_exists`, meaning the validator meant to
catch a bad address shares the bug that produces one.

---

## 7. Confidence does not measure correctness

Across the 28 wrong-street calls, mean stored `confidence_score` is **55.5**, and **10
scored ≥90**. Some genuinely-unresolved calls correctly scored 0, which makes the
confident-and-wrong cases *more* misleading, not less.

In `DISP-2026-156DCF` the 100 is literally the subset artifact: `resolve_exact` returns
`"confidence": float(best_score)`, so the fuzzy score becomes the operator-facing
confidence. More generally, confidence appears to score **template completeness**, not
whether values came from the audio — which means **fabricating a field raises the score**.

Treat this as its own finding, not a symptom. It is arguably above punch-list #19 in
priority: it is not one wrong value, it is the signal crews use to decide whether to trust
a value at all.

---

## 8. Open, and not yet investigated

* **The 4 calls that still resolve wrongly under current code** — `DISP-2026-1388CD`
  (Harbour Dr for Harper Road, conf 55), `DISP-2026-74813F` (house number, conf 55),
  `DISP-2026-8E7B55` (returns a *junction* where truth was a civic address, conf **100**),
  `DISP-2026-156DCF` (conf **100**).
* **UI honesty:** the Call Review Panel's `SYSTEM PREFILLS` column displays the *verified*
  address, not what the system produced — hiding the disagreement an operator scans that
  list to find. Same defect class as punch-list #12. Confirmed from a kiosk screenshot.
* **PA page leakage (#14), rail crossings (#21), `TALK_GROUPS` (#20)** — see the punch list.

---

## 9. Working notes

* **The kiosk is the test machine.** Full environment setup, the `DATABASE_URL` /
  `XDG_RUNTIME_DIR` traps, and the SSH re-auth behaviour are in
  [`docs/review_status_handoff.md`](./review_status_handoff.md) — read that section before
  running anything; without `DATABASE_URL` tests *skip* rather than fail, which reads green.
* **Tailscale SSH lapses and hangs silently.** Each retry mints a *new* auth URL, so hand
  the user one link and wait rather than re-running and reissuing.
* **The user is available in-session** for kiosk screenshots and manual HITL steps, and has
  offered. The in-app browser sandbox blocks `ws://…:9001`, so MQTT-driven behaviour cannot
  be observed by an agent at all. Three defects in this review were found from screenshots;
  a fourth (§8, `SYSTEM PREFILLS`) was found from one today. Ask rather than infer.
* **Measure, don't infer.** Every wrong conclusion in this work — including three of mine,
  two recorded in §5 — came from reading, and every correction came from running something.
  A ten-second probe would have prevented each one.
