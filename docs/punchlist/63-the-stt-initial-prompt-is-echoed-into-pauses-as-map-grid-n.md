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

> **Status**: 🔴 **Open — parser mitigation shipped 2026-09-05 (`8b962b8`); the prompt itself is the
> operator's call, with the measurement below.** Crew-visible: the map grid drives the zone the
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

### What is not done, and why

The prompt was written for the base model, which needed template priming. Whether to drop it,
shorten it, or drop `map grid` from the hotwords as well is STT tuning, the operator's domain
(CLAUDE.md §7.6). To apply it on the kiosk: `STT_INITIAL_PROMPT=` (empty) in `backend/.env`,
then restart `cfr-agent`, which drops the live listener for a few seconds. The hotwords were
not tested in the same run: one variable at a time (§7.7).

The 7 grids still wrong without the prompt are the model mangling the number itself
(*"map grid 1010"* for 109, *"904"* for 94) or losing the clause. No parser rule should
guess those.
