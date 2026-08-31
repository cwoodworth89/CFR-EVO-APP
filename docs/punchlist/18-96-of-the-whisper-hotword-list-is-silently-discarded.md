# Punch list #18 — 96% of the Whisper hotword list is silently discarded

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🎙️ STT Vocabulary Biasing |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L774 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 18. 96% of the Whisper hotword list is silently discarded
> **Status**: ✅ **Closed 2026-08-22 — budget restored and measured.** Terms are now
> ranked by value and trimmed against the model's real token cap: **58 terms, 221 of 223
> tokens**, and `Lougheed`, `Westwood`, `Pinetree`, `Barnet`, `Como Lake` and `Guildford`
> are biased where previously **no** arterial was. The trim is logged every build, and a
> warning fires if no HITL-corrected street survives.
>
> Ranking, in priority order: core terms → units → HITL-corrected streets → streets by
> dispatch count (`public.dispatches`) → streets by parcel count (`public.parcels`) → call
> types. The parcel-count ranking is the one commit `79808cc` used before it was removed.
> `transcriber.py` supplies the loaded model's real `max_length` and tokenizer so the
> budget is measured rather than guessed from a term count — the earlier fix capped at 120
> terms, which is still roughly double the real cap.
>
> **Known remaining limit**: 58 terms is tight, so `Mariner` and `Austin` still miss the
> cut. An untested idea worth measuring — bias on the distinctive name alone
> (`Lougheed` rather than `Lougheed Highway`), since "Highway"/"Avenue" are common words
> the model already handles. That should roughly halve the per-street cost and about
> double coverage, but it changes what the model is primed for and needs a WER backtest
> before adoption, not a guess.
>
> The original finding follows.
>
> ⚠️ **Open — measured 2026-08-22 on the kiosk model.** This is the upstream
> cause of the transcription errors that #15 was trying to repair downstream.

`build_stt_bias_words` assembles every road name, unit, core term and call type into one
`hotwords` string — 1,173 entries, 5,172 tokens — with the comment *"Build complete
hotword list — NO artificial truncation"*, having replaced an earlier top-25 limit.

**faster-whisper truncates it anyway**, and keeps the *head*
(`faster_whisper/transcribe.py:1546-1547`, version installed on the kiosk):

```python
if len(hotwords_tokens) >= self.max_length // 2:
    hotwords_tokens = hotwords_tokens[: self.max_length // 2 - 1]
```

Measured against the loaded model (`max_length` 448, so the cap is 223 tokens):

| | |
|:--|--:|
| Hotword entries supplied | 1,173 |
| Tokens supplied | 5,172 |
| Tokens kept | **223** |
| Tokens discarded | **4,949 (95.7%)** |
| Entries actually surviving | **61 of 1,173** |

Because `all_streets` arrives alphabetically, the surviving set ends at **"Archworth
Avenue"** and everything from **"Argyle Street"** onward is dropped. Street biasing
therefore covers part of the letter A and nothing else. **Westwood, Lougheed, Pinetree,
Barnet, Mariner — every arterial in the city — receives no biasing at all.** Call types
sit last in the list and never survive.

Removing the top-25 limit made this *worse* than it was: a curated 25 was at least chosen;
an alphabetical prefix of 61 is arbitrary.

**This is why "Lowheed" and "Tasis" reached the geocoder.** #15 removed the dangerous
downstream guessing, which was right, but the errors themselves are produced here.

**Fix direction** — spend the 223-token budget on the highest-value terms, and measure the
spend rather than assuming it:
1. Core dispatch terms and unit names (small, always needed).
2. HITL-corrected streets — empirically demonstrated to be misheard, so the highest value
   per token. `get_hitl_verified_streets()` already tallies them and they are already
   ordered ahead of `all_streets`.
3. Remaining streets ranked by **dispatch frequency** from `public.dispatches`, not
   alphabetically.
4. Assert the encoded token count against the model's real cap at build time, so a future
   change that overflows the budget fails loudly instead of silently dropping arterials.

**Also unverified**: no Whisper or faster-whisper documentation is referenced anywhere in
the project, and the figures above were taken from the installed source and the loaded
model rather than from docs. Worth confirming against the faster-whisper release notes for
the pinned version before treating the 223-token cap as stable across upgrades.
