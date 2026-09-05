# Punch list #71 — The hotword budget is spent on intersections, suffix duplicates and template words; *Thor* never gets in

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🎙️ STT Vocabulary Biasing |
| **Blocks** | 0 |
| **Origin** | The #18 coverage look the operator asked for on 2026-09-05, after *Thor Crt* was heard as *four* twice (#69) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 71. 52 terms survive the 223-token cap, and a quarter of them are not street names

> **Status**: 🔴 **Open — measured, experiments proposed, nothing changed.** Each proposal
> alters what the model is primed for, so each is one harness A/B (CLAUDE.md §7.6), and the
> live list is the operator's to change. Crew-visible: the streets that get misheard are
> mostly the ones the list cannot reach.

### The live list, reproduced on the kiosk 2026-09-05 with the model's tokenizer

52 of 1,205 terms kept, 222 of 223 tokens. In priority order: 13 core template words,
14 unit words, 12 "HITL-corrected streets", then the frequency ranking, which reaches
**rank 15** (`Pacific St`) before the budget is gone.

| Where the tokens go | Terms | What they are |
|:--|--:|:--|
| Core template words | 13 | *respond, routine, emergency, medical aid, structure fire …* |
| Unit words | 14 | *Engine, Ladder, Car, Chief, Rescue, Light Attack Vehicle …* |
| "HITL streets" | 12 | **7 are whole intersection strings** (*"Westwood St & Lougheed Hwy"*, *"Ozada Avenue And Tahsis Ave"*), ~8 tokens each |
| Frequency-ranked streets | 13 | ranks 1-15 less the two already listed |

### Four leaks

1. **Intersections as "streets".** `get_hitl_verified_streets` strips a leading house
   number and keeps the rest; a verified intersection has no house number, so the whole
   string becomes one term. Seven of twelve HITL entries, roughly 55 tokens, a quarter of
   the budget, for strings the model will never need as a unit. The frequency ranking has
   the same leak: 3 intersections in its top 60.
2. **Suffix duplicates.** The verified column is typed by hand, so `LOUGHEED HWY` and
   `LOUGHEED HIGHWAY` rank as two streets; 5 such pairs in the top 60. `Lougheed Hwy` is
   in the list and `Lougheed Highway` competes for a second slot.
3. **The HITL window is the API's last 200 rows**, PA pages included, which on 2026-09-05
   reached back to 2026-08-17. Both *Thor Crt* calls (08-08, 08-14) are outside it, so the
   one list built for misheard streets does not contain the street misheard twice. The
   whole corpus is in the same database the frequency ranking already reads.
4. **Template and unit words.** 27 terms for words in every training transcript: the model
   in service was fine-tuned on them, which is why the initial prompt measured as
   unnecessary (#63). Whether hotwords on *Engine* or *emergency* still help is unmeasured;
   they cost about 45 tokens.

### What the corpus says the list should reach

483 verified civic-address calls on 161 streets (suffixes normalised):

| Streets by dispatch count | Share of calls covered |
|:--|--:|
| top 15 (today's reach) | 56 % |
| top 27 | 67 % |
| top 60 | 79 % |
| top 100 | 87 % |

36 verified streets or intersections were transcribed wrongly at least once. 21 of them
rank inside the top 60, 30 inside the top 100; *Thor Crt* is rank 44 (two calls, both
wrong), *Kensal Pl* rank 24 (three wrong of four), *Port Mann Bridge* rank 48.

### The cost lever

With the model's tokenizer: `Thor Crt` is 3 tokens, `Thor` 1; `Lougheed Hwy` 5,
`Lougheed` 3; `Gatensbury St` 5, `Gatensbury` 4. The first 60 ranked streets cost 216
tokens as full names and 134 as names alone. Suffix words are the ones the model never
mishears. (#18 flagged this as untested; still untested.)

### Experiments, one variable each, on the round-1 holdout then the full corpus

`tools/harness_chain.py` with `--record`, against the 2026-09-05 A/B rows in
`evaluation_history` (4.59 % / 4.02 % WER, 6 wrong grids, 27-33 wrong addresses):

1. **Split intersections into their streets** in both rankings and de-duplicate suffixes
   through `normalize_street_name`. Frees ~60 tokens; no change to what a term is.
2. **HITL from the corpus, not the API window**: tally verified street ≠ system street
   over `public.dispatches` directly (the engine is already in hand). Puts *Thor*, *Kensal*
   and *Port Mann* in front of the frequency ranking.
3. **Names without suffixes** for the street terms. Roughly doubles reach; changes priming.
4. **Drop the template and unit words**, or keep only the ones the corpus shows misheard.
   Frees ~45 tokens; changes priming.

Each is an env switch or a small change in `bias_prompt.py`, measured before it is applied,
and applied only by the operator. Expected end state if all four hold up: the list reaches
rank 80-100, which covers 83-87 % of calls and 30 of the 36 misheard streets.
