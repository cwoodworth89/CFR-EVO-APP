# CFR EVO: QA Harnesses — Measuring Changes Against Historical Records

**Written 2026-08-26.** Read this before quoting an accuracy figure for any stage of the
dispatch pipeline, and before changing code that decides an operational value.

A **harness** replays real historical dispatches through current code and scores the output
against what a human confirmed was true. It is not a unit test: a unit test asserts one
hand-written input produces one expected output, while a harness runs the whole verified
corpus and reports where the system and the ground truth disagree.

This project can do that because `public.dispatches` stores the system's answer beside the
human's for every reviewed call, and because CLAUDE.md §6.5 forbids synthesising test
dispatches — **the corpus is the test suite**, so it only ever needed something to run it.

---

## 1. The three stages, and what covers each

The pipeline has three places a value can go wrong, and each needs its own harness because
each has a different notion of "correct".

| Stage | Question it answers | Harness | Status |
|:--|:--|:--|:--|
| **STT** | Did we hear what was said? | — | ⚠️ **Does not exist** (§4) |
| **Parser** | Did we pull the right values out of what we heard? | [`backtest_parser_corpus.py`](../tools/backtest_parser_corpus.py) | ✅ Built 2026-08-26 |
| **Geocoder** | Does the address resolve to the right place? | [`trace_geocode_corpus.py`](../tools/trace_geocode_corpus.py) | ⚠️ **Needs review** (§3) |

The three are **not** interchangeable. Word Error Rate scores transcription and says nothing
about whether the parser then dropped the qualifier off a call type. Every serious defect in
the 2026-08-23 audit lived downstream of the transcript, in territory WER does not reach.

---

## 2. Parser harness — `backtest_parser_corpus.py` ✅

Replays `raw_transcript` through the current parser and scores `incident`, `units`,
`map_grid`, `talkgroup` and `address` against the matching `verified_*` columns.

```bash
# headline numbers, split by month (the default, and the honest reading)
python tools/backtest_parser_corpus.py

# one call in detail -- both rounds, every field, got vs truth
python tools/backtest_parser_corpus.py --dispatch-id DISP-2026-A19179

# before/after a change
python tools/backtest_parser_corpus.py --json /tmp/before.json
#   ... make the change ...
python tools/backtest_parser_corpus.py --baseline /tmp/before.json

# per-call rows for triage
python tools/backtest_parser_corpus.py --csv /tmp/parser.csv
```

Baseline as of 2026-08-26 (see §5 on why the split matters):

| Field | 2026-07 | 2026-08 |
|:--|--:|--:|
| incident | 95.1% | 93.0% |
| units | 98.5% | 98.0% |
| map_grid | 64.7% | **99.0%** |
| talkgroup | 89.0% | **100%** |
| address | 64.9% | 71.0% |

**Known limitation, stated plainly:** `parse_like_production()` **mirrors** the selection
logic in `pipeline/phase2.py` rather than calling it, because the real path needs a geocoder,
a validator and database writes. If phase2's selection changes and the mirror does not, the
harness scores something production no longer does. Change both in the same commit.

### The `address` column is the parser's string, NOT the geocoded result

This column is systematically pessimistic and must not be read as end-to-end accuracy. It
compares what the **parser** extracted from the transcript against `verified_address`, with no
geocoder in between. Two consequences:

* **STT damage lands here.** Roughly half of the 2026-08 misses are street names the parser
  faithfully carried through from a mis-transcription — `Loheed`/`Lowheed`/`Lockheed` for
  Lougheed, `Landsdown` for Lansdowne, `Kenny` for Kenney. The parser is not wrong; the audio
  never contained the right word. Snapping the parsed street to `public.road_names` is the
  open fix.
* **The geocoder often repairs it afterwards.** `DISP-2026-EC4501` scores `WRONG` here with
  `3305 Chartwell Grove`, yet the pipeline stored `3305 Chartwell Green` at the correct parcel
  — the right place. A handful of "failures" are ground-truth-versus-cadastre conflicts of
  this kind (#47), not defects at all.

The other four columns have no such gap: `incident`, `units`, `map_grid` and `talkgroup` are
parser output compared to ground truth directly, and can be read at face value.

---

## 3. Geocoder harness — `trace_geocode_corpus.py` ⚠️ needs review

Committed `8d00ea3`. Replays verified dispatches through the live geocoder, wraps all seven
resolvers to record **which step answered**, and buckets the result against
`verified_address`.

```bash
python tools/trace_geocode_corpus.py --dispatch-id DISP-2026-156DCF
python tools/trace_geocode_corpus.py --probe "3000 avenue"
python tools/trace_geocode_corpus.py --all --csv /tmp/geocode.csv
```

**Why it needs a review pass before its numbers are trusted again:**

1. **It predates the 2026-08-21/23 geocoder rewrite.** Nine commits landed on
   `services/gis/` in that window — tie-breaking by map grid, near-road ranking, civic
   substitution bounds, honest centroid labelling. Whether the seven-step ladder it wraps is
   still the seven steps that run has not been re-checked.
2. **It probes `target->>'address'`, the geocoder's own output** — so it measures whether an
   address round-trips, never how the parser arrived at it. That gap is what
   `backtest_parser_corpus.py` now fills; the two should be read together.
3. **It has no date split** (§5). Its headline "30 of 34 stored defects already remediated"
   is a *historical* statement, and the same pooling trap applies to any rate it reports.
4. **Its ground truth is contested.** Reviewers use `verified_address` for cosmetic edits —
   expanding suffixes, stripping unit numbers — which inflates a naive error rate by roughly
   3×. The parser harness buckets EXACT / COSMETIC / WRONG for exactly this reason; the
   geocoder harness should adopt the same buckets.

**Action:** re-run it against current `services/gis/`, confirm the resolver list matches,
add a `--by-month` split and cosmetic bucketing, and record a fresh baseline here.

---

## 4. STT harness — ⚠️ does not exist

`extract_training_data.py` and `backtest_regression.py` compute Word Error Rate for Whisper
training, but there is no harness that answers **"did this STT change make the system better
or worse against historical audio?"**

What one would need:

* Replay stored audio (`audio_url`, present on essentially every dispatch) through the
  current faster-whisper configuration.
* Score against `verified_transcript` — **but see the trap below**.
* Report by month, and report *both* WER and downstream field accuracy, because a WER
  improvement that loses the map grid is not an improvement.

### ⚠️ The trap that will corrupt any STT measurement

**`verified_transcript` holds ONE round; `raw_transcript` holds two.** The reviewer verifies
a single round, and the duplication that matches it to the two-round audio happens only at
training extraction ([`extract_training_data.py:182`](../tools/extract_training_data.py)),
never in the database column.

Confirmed by query: `respond` appears once in 197 of 202 verified transcripts.

**Diffing the two columns directly reports ~50% error on a perfect transcription.** Duplicate
the verified text first, the same way the extractor does, or compare round-for-round. This is
recorded at greater length in [`parser_audit_handoff.md`](parser_audit_handoff.md) §4.1a,
alongside the sibling trap that `sanitized_transcript` is not a transcript at all.

### What such a harness would already have caught

* **Tail truncation.** In 2026-07, 37 calls (18%) lost `map grid` from the transcript while
  having *longer* median audio (50.6s vs 47.5s) and *fewer* words (37 vs 51). Fixed by the
  operator's audio-listener work around 2026-07-29; zero occurrences since.
* **Consistent mis-recognitions.** faster-whisper writes `smoldering` 5/5 (never
  `smouldering`) and `Tassus` for Tahsis in 2 of 3 occurrences. These are stable, learnable
  patterns — the kind a harness surfaces and a spot check does not.

---

## 5. The rule that applies to all three: split by date

**Any rate computed over this corpus must be split by date before it is believed.**

The corpus spans a period of active fixes, so a pooled figure mixes already-fixed defects with
live ones and systematically overstates what is broken. This is CLAUDE.md §6.6 and
`parser_audit_handoff.md` §4.2 in a single operational rule.

It caught three separate wrong claims during the 2026-08-23 audit:

| Claim, pooled | Reality, split by date |
|:--|:--|
| "map grid missing from 18% of transcripts" | 18% in July, **0%** in August — the operator had already fixed it |
| "cross-round merge recovers 57 map grids" | 57 in July, **13** in August |
| "`split_rounds` fails on 15 calls" | 15 in July, **1** in August |

A fourth wrong claim came from a different mistake worth naming here too: a **46% talk-group
accuracy** figure was quoted as a live defect when it was measuring `destructive_parser.py`,
which nothing in production calls. Production stores the talk group correctly on 97/97 August
calls. **Always state which code path a number describes.**

---

## 6. Reading a harness result honestly

* **A harness bug and a code bug look identical in the output.** While building
  `backtest_parser_corpus.py`, a normalisation bug scored production units at 76% when the
  true figure was 99%. When a number moves sharply, check the harness against stored
  production output before believing it.
* **Denominators differ per field.** `verified_map_grid` exists on ~150 calls,
  `verified_incident` on ~305. Dividing every field by the same n understated the map-grid
  error rate as 9.4% when it was 12.7%.
* **Cosmetic diffs are not errors.** `Ave`/`Avenue`, trailing unit numbers and intersection
  leg order made the address error rate read 30.2% against a true 16.8%.
* **A missing vocabulary row is not a parser defect.** `match_incident_type` can only return a
  term that exists, so a `verified_*` value with no vocabulary row is evidence of a **missing
  term first** and a reviewer mistake second. This was got backwards twice in one session.
* **`Unknown Incident` is a correct answer** when the transcript does not contain the
  information (CLAUDE.md §6.1). Do not tune a harness toward eliminating it — a confident
  wrong answer scores the same as an honest unknown in a naive accuracy metric, and is far
  more dangerous.

---

## 7. When to run these

* **Before and after** any change to parsing, geocoding, vocabulary or STT configuration —
  using `--json` / `--baseline` so the diff is explicit rather than remembered.
* **Before believing a defect is live.** Re-run current code against the stored record; the
  corpus is historical and a stored defect may already be fixed.
* **Before sizing work.** Punch-list #44 (round-1-wins) is the current example: the obvious
  fix — prefer round 2 — trades 5 wins for 20 losses, which is only visible by measuring.

See also: [`parser_audit_handoff.md`](parser_audit_handoff.md) for the corpus description and
the traps in full, [`debug_and_qa_punchlist.md`](debug_and_qa_punchlist.md) for open items,
and [`standards/README.md`](standards/README.md) for what governs each domain value.
