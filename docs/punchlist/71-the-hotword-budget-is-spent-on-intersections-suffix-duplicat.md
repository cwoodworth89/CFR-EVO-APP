# Punch list #71 — The hotword budget is spent on intersections, suffix duplicates and template words; *Thor* never gets in

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🎙️ STT Vocabulary Biasing |
| **Blocks** | 0 |
| **Origin** | The #18 coverage look the operator asked for on 2026-09-05, after *Thor Crt* was heard as *four* twice (#69) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 71. 52 terms survive the 223-token cap, and a quarter of them are not street names

> **Status**: ✅ **Closed 2026-09-05 — the three leaks fixed and live from 19:16 PDT (steps 1 and 2,
> `ab4da95`, `7f254d0`); experiment 3 measured and not applied; experiment 4 not run.**
> *(Opened as: 🔴 Open — measured, experiments proposed, nothing changed.)* Crew-visible: the
> streets that get misheard are mostly the ones the list cannot reach.

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

### Step 1 built and measured, 2026-09-05 (`ab4da95`)

`street_terms()` in `bias_prompt.py`: an intersection gives its two streets, the house number
goes, the suffix is normalised, and the final list is de-duplicated on the normalised name.
The live list went from 27 streets reaching rank 15 to 34 streets reaching rank 27, with the
seven intersection strings and the suffix pairs gone. Kensal Pl is rank 28 and still just
misses; Thor Crt is rank 58.

| Same live settings otherwise; baseline = Friday's run B | Holdout (44) | Corpus (507) |
|:--|--:|--:|
| WER mean | 4.02 → 4.39 % | 4.78 → **3.22 %** |
| Scored clips moved, better / worse | 2 / 5 | 10 / 8 |
| Map grid wrong | 0 → 0 | 6 → 6 |
| Wrong street | 3 → 3 | 13 → **16** |
| Placed exactly | 34 → 34 | 428 → 426 |

The WER gain is four hard clips recovered outright (*"routine testing only 1300 pinetree way"*
84 → 0 %, the Chrome Cres call 63 → 0 %, 2525 Como Lake Ave 26 → 0 %). The three streets
lost are `3080 Lincoln Ave` heard as *Lnkin*, `3001 Gordon Ave` falling to a Christmas Way
section, and `Eagle Mountain Park` landing on the contact-dispatch placeholder; whether those
are the list or run-to-run variance, one run cannot say. Not live: the agent was restarted
before this landed and is still on the old list. The operator decides whether it goes live
with step 2 or alone.

### Step 2 built and measured, 2026-09-05 (`7f254d0`)

The misheard-street list now comes from the whole corpus (`get_hitl_verified_streets(engine)`):
34 streets, most-misheard first, Thor Crt, Kensal Pl and Port Mann Bridge among them. They fill
the street budget; the live list is 57 terms and only Glen Dr survives from the frequency
ranking beyond them. "Sugarpine Ct" folds onto the City's CRT since the suffix alias landed the
same day (`a788e8f`, migration applied).

| Baseline = the step-1 run | Holdout (44) | Corpus (507) |
|:--|--:|--:|
| WER mean | 4.39 → 4.26 % | 3.22 → 4.04 % |
| Scored clips better / worse | | 4 / 4 |
| Map grid wrong | 0 → 0 | 6 → 5 |
| Wrong street | 3 → 3 | 16 → 15 |
| Placed exactly | 34 → 34 | 426 → 429 |

The WER swing is one clip: *"routine testing only 1300 pinetree way"* (DISP-2026-D7F118),
84 % on Friday's list, 0 % with step 1, 84 % again with step 2, damaged audio that collapses or
recovers depending on the biasing and moves the mean by 0.7 points on its own. The three
streets step 1 lost came back (3080 Lincoln Ave, 3001 Gordon Ave, Eagle Mountain Park); two
others went (2561 Lougheed Hwy to a Thyme Dr section, Ozada and Tahsis heard as *Tosses*).

**What step 2 was for:** both Thor Crt calls now transcribe *Thor* and place exactly, and all
four Kensal Pl calls place (one exact, three cosmetic). Against Friday's live list, the two
steps together: WER 4.78 → 4.04 %, grid wrong 6 → 5, exact 428 → 429, wrong street 13 → 15.
Not live until the agent is restarted; the operator's call.

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

### Experiment 3 measured, 2026-09-05 (`7ca2c40`): names without suffixes, a wash

`STT_HOTWORDS_NAMES_ONLY=1` for the run only. Against the step-2 runs, same live settings:

| | Holdout (44) | Corpus (507) |
|:--|--:|--:|
| WER mean | 4.26 → 4.30 % | 4.04 → 4.03 % |
| Scored clips better / worse | | 5 / 5 |
| Map grid wrong | 0 → 0 | 5 → 5 |
| Wrong street | 3 → 3 | 15 → 13 |
| Placed exactly | 34 → 34 | 429 → 428 |

The list reaches further and nothing measurable follows on this model; the suffix words are
not where it goes wrong. Not applied; the switch stays for a later model. Experiment 4, the
template and unit words, is on the backlog and unmeasured.

### Closed 2026-09-05

Steps 1 and 2 are the fix: the hotword list is single streets in one suffix form, the
misheard-street list comes from the whole corpus, and Thor Crt and Kensal Pl transcribe and
place. Live since the 19:16 restart. Whole-corpus record against Friday's list: WER 4.78 →
4.04 %, grid wrong 6 → 5, exact 428 → 429, wrong street 13 → 15, each within the one-clip
swings the same corpus shows between runs.
