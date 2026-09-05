# Punch list #63 — The STT initial prompt is echoed into pauses as "map grid N", and the parser believed it

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🎙️ Dispatch Pipeline |
| **Blocks** | 1 |
| **Origin** | Found 2026-09-05 by the first full run of `tools/harness_chain.py` (32 wrong map grids on 129 scored calls) and the fresh transcripts behind them |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 63. The model in service writes the prompt's own phrase into the transcript

> **Status**: 🔴 **Open — parser mitigation shipped 2026-09-05 (`8b962b8`); operator ruling 2026-09-05:
> no prompt, applied on the kiosk at 08:28 PDT. Stays open until fresh calls are measured without it.** Crew-visible: the map grid drives the zone the
> kiosk shows, and the same insertion loses the cross streets.

### What happens

`backend/cfr_dispatch/stt/bias_prompt.py` ends its `initial_prompt` with *"Respond on talk group
Tac 1, map grid."* and lists `map grid` among the hotwords. Whisper is known to echo prompt
fragments into silences, and a model fine-tuned on transcripts that all end in *"coquitlam map
grid N"* echoes exactly that. On the 2026-09-05 baseline the model in service wrote
*"coquitlam map grid N"* into the pause mid-round on 19 of 129 scored calls, every time with a
wrong N. The base model's stored transcripts of the same audio do not contain it.

Two things then went wrong downstream. `split_rounds` cuts a round at the first *"map grid N"*,
so the cross streets after the insertion fell into a phantom second round. And the parser read
the first *"map grid"* it saw, so the inserted N became the call's map grid.

```
heard   : ... chest pain 2950 glen drive near coquitlam map grid 68 pacific street & the high
          street use talk group 10 combined response coquitlam map grid 82
verified: ... chest pain 2950 glen drive near pacific street and the high street use talk group
          10 combined response coquitlam map grid 82
```

### What was done

`sanitize_transcript` now drops a map-grid phrase that has no *"talk group"* in the 60
characters before it and another map-grid phrase after it. The template
(`docs/call_structure.md`) puts the grid last, immediately after the talk-group clause, 46
characters apart; the last phrase in a transcript is never dropped, so a call whose talk-group
clause was lost keeps its grid. Seven tests on the real transcripts,
`backend/tests/test_sanitize_orphan_map_grids.py`; six failed before, all pass after.

`STT_INITIAL_PROMPT` is a new environment switch in `bias_prompt.py`: set, it replaces the
template prompt; empty, no prompt is sent. A named tuning surface (CLAUDE.md §6.4) so the
prompt's effect is measured, not argued.

### Measured, 2026-09-05, the 42 hardest calls of the corpus (the map-grid misses and the worst WER; not a random sample)

| Run, model `whisper-base-cfr-ct2` | Unanchored "map grid N" | Map grid wrong | Address wrong | Wrong street | WER mean |
|:--|--:|--:|--:|--:|--:|
| Template prompt, parser before the fix | — | 32 | 18 | 15 | — |
| Template prompt, parser fixed | 25 in 17 calls | 25 | 18 | 14 | 16.6 % |
| **No prompt**, parser fixed | **7 in 6 calls** | **7** | **3** | **1** | **2.9 %** |

The parser fix recovers what it can; the prompt is the cause.

**The fair test**, the 44-clip round-1 holdout the model never saw, both runs recorded in
`evaluation_history` (the second also carries the parser fix and classify v2):

| Round-1 holdout, 44 clips | With the prompt (`ec6988a`) | Without (`8b962b8`) |
|:--|--:|--:|
| WER mean / median | 4.55 % / 0 % | 4.45 % / 0 % |
| Map grid wrong | 1 | 0 |
| Address wrong | 8 | 3 |
| Placed exactly | 32 | 34 |
| Wrong street | 4 | 3 |

Most clips are clean either way; the prompt's damage lands in pauses and hard audio, which
is why the tail shows it at fifteen times the size the holdout does.

### Applied 2026-09-05

The operator ruled: no prompt. `STT_INITIAL_PROMPT=` (empty) is in the kiosk's `backend/.env`
and `cfr-agent` restarted at 08:28 PDT with the loader reading `''`. The hotwords were then
measured without *map grid*, below. To close: run `tools/harness_chain.py --since 2026-09-05`
once a few dozen calls have arrived and compare the map-grid and address misses against the
baseline rows in `evaluation_history`.

### Hotwords without "map grid", measured 2026-09-05

`STT_HOTWORDS_EXCLUDE` (`bias_prompt.py`, `62d70d4`) removes named terms from the hotword list
before the budget is spent. A and B ran on the same code (`56a68a5`, #67 and #68 in), the same
44 clips, no initial prompt, within the same half hour; both are in `evaluation_history`.

| Round-1 holdout, 44 clips | A: default hotwords | B: without "map grid" |
|:--|--:|--:|
| WER mean / median | 4.38 % / 0 % | 4.02 % / 0 % |
| Map grid wrong | 0 | 0 |
| Address wrong | 3 | 3 |
| Placed exactly | 34 | 34 |
| Wrong street | 3 | 3 |

Round 1, the scored text, moved on 5 of 44 clips: four better (the Port Mann Bridge call
25.6 → 16.3 %, DISP-2026-F5C0FC 18.5 → 14.8 %, D239B1 2.9 → 0, 815224 6.3 → 3.1 %) and one
worse by an abbreviation (*Tahsis Ave* for *Tahsis Avenue*, 0 → 3.3 %). Round 2 differed on
34 of 44, which is where the model varies from run to run (the opening of round 2 kept or
dropped, "&" for "and", capitalisation); nothing downstream moved either way.

The first B run (`62d70d4`, 15:41) showed one wrong grid. That was the parser: the model
dropped round 2's opening and the digit join made "map grid 8210" (#68, fixed the same
afternoon). Two defaults of "default" are not byte-identical either: the list is built live
from HITL-verified streets and dispatch frequency, so only a same-code, same-hour pair counts.

**Applied 2026-09-05 09:04 PDT**, operator ruling: `STT_HOTWORDS_EXCLUDE=map grid` in the kiosk's
`backend/.env` beside the empty prompt, `cfr-agent` restarted, the loader read both back.

**Full corpus, same code, both ways**, 507 verified calls 2026-07-12 to 2026-09-01 (`[PA]` pages
out), code `715aa57` (`6ab5eb0` is docs only), both recorded in `evaluation_history`, run B at
10:16 and run A at 10:29 to 11:00 PDT. The morning baseline (`88ea5de`: template prompt, pre-#62
geocoder, default hotwords, 529 calls) is the third column for the day's trend; the gap to it is
the whole day's changes, not the hotword.

| Full corpus | A: default hotwords | B: without "map grid" (live) | Morning baseline |
|:--|--:|--:|--:|
| WER mean, non-training clips (n=119) | 4.59 % | 4.78 % | 9.62 % (n=129) |
| WER July / August | 4.04 % / 4.99 % | 5.07 % / 4.57 % | |
| Map grid wrong | 6 | 6 | 32 |
| Address wrong (parser field) | 33 | 27 | 85 |
| Placed exactly | 425 | 428 | 394 |
| Resolved by a cross-street section | 6 | 3 | |
| Place ok | 94.3 % | 94.7 % | 90.2 % |

Call by call, A against B: transcripts differ on 347 of 507 calls, almost all in round 2. WER
moved on 14 of the 119 scored clips, 10 better without "map grid" and 4 worse; the mean goes the
other way on one clip, DISP-2026-C41EFE (3.7 → 63 %), where run B swallowed the tail of round 1
and wrote *"coquitlam map grid 100"* in its place. The sanitiser removed the orphan correctly,
which left nothing for `split_rounds` to cut on, so the scored "round 1" was both rounds; the
parser still had the right address and grid. Run A inserted a *"map grid 71"* into that call's
round 2 instead. The insertion is the model's, in both conditions. Address verdicts changed on 8
calls, 7 toward B; two are crew-visible, both A's: *"routine 61300 pinetree way"* fell to a
cross-street section where B placed `1300 Pinetree Way`, and `Parkway Blvd (Near Eagle Mountain
Dr)` where B placed `1999 Parkway Blvd`. The other six are parser-field verdicts with the same
final address, since #44a picks the better round either way. Grids are identical: the six wrong
are the number-mangling class below.

**Reading.** On the full corpus the term is a wash on the intermediate figure and slightly
better on the crew-visible ones: three more parcels placed, three fewer sections, six fewer
parser-field misses, the same grids. The holdout gave −0.36 WER points, the corpus +0.19, and
each is a handful of clips. The setting stays as applied; revisit if the hotword list changes.

### What is not done, and why

The prompt was written for the base model, which needed template priming. Whether to drop it,
shorten it, or drop `map grid` from the hotwords as well is STT tuning, the operator's domain
(CLAUDE.md §7.6). To apply it on the kiosk: `STT_INITIAL_PROMPT=` (empty) in `backend/.env`,
then restart `cfr-agent`, which drops the live listener for a few seconds. The hotwords were
not tested in the same run: one variable at a time (§7.7).

The 7 grids still wrong without the prompt are the model mangling the number itself
(*"map grid 1010"* for 109, *"904"* for 94) or losing the clause. No parser rule should
guess those.
