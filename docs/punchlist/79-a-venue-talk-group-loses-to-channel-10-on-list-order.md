# Punch list #79 — A venue talk group loses to channel 10, and the venue's name in the vocabulary was wrong

| | |
|:--|:--|
| **Status** | FIXED, **deployed and running**. Both migrations applied; `cfr-agent` restarted 2026-09-11 22:50:49 behind `tools/kiosk_capture_state.sh` (SAFE, nothing lost) and verified resolving both Port Mann fragments against the live vocabulary. **Behaviour on a live call is confirmed at the next Port Mann dispatch** — not fabricated to close this out (§6.5). |
| **Severity** | 🔴 crew-visible |
| **Area** | 🎙️ Parser / talk group · 🗄️ Vocabulary · 🖥️ HITL review |
| **Ruling** | Operator, 2026-09-11: (a) `Talk Group` is not part of a channel's name — canonical is `5 Coquitlam`, `10 Combined Response Coquitlam`; (b) from the audio, the venue channels are **`Combined Response Venue Port Mann`** and `Combined Response Venue Transit System`; (c) the matcher is a cascade, not a score — *"looking for a number first and foremost with a following coquitlam... Then if no number, or unsure, check if it says venue"*; (d) a fragment degraded to bare `combined response` resolves to channel 10. *Unresolved* is not *no talk group*, which is a valid dispatch (→ #80). The list holds the channels that matter and is knowingly not the full roster. |
| **Origin** | Operator, 2026-09-11, on `DISP-2026-07CC85`: *"The talk group was wrong... It missed Combined Venue Port Mann, and defaulted to combined response coquitlam. STT problem or something else?"* — then, decisively: *"I just listened to the audio again, and this is the exact wording."* |

[← punch list index](../debug_and_qa_punchlist.md)

---

## Why this is crew-visible

The talk group is printed on the kiosk HUD and is what a crew keys up on. A wrong one is not
a blank field — it is a plausible channel, correctly formatted, that puts the truck on the
wrong net. Nothing on the display distinguishes it from a right one.

**The parser had never once resolved the Port Mann channel.** Both calls ever announced on it
were filed as channel 10; the single correct row in the database is the operator's own HITL
correction, not a parse.

| Call | Spoken (raw STT) | Parser | Actual |
|:--|:--|:--|:--|
| `DISP-2026-B772D2` (2026-08-02) | `combined response venue port mann` | 10 Combined Response | Port Mann — **operator corrected by hand** |
| `DISP-2026-07CC85` (2026-09-09) | `combined response venue port man` | 10 Combined Response | Port Mann |

## Correction to this entry, 2026-09-11

**An earlier version of this file said Whisper inserted the word `response` into "combined
venue port mann". That was wrong, and it was never checked against the audio.** It was
inferred from the word's absence in the vocabulary — the §7.3 failure exactly, and the §7.7
one: an explanation supplied for a result rather than measured.

The operator listened to the recording. The dispatcher says **"use talk group combined
response venue port mann"**. His own verified transcript of `B772D2`, corrected by hand six
weeks earlier, already said so:

> `use talk group combined response venue port mann, map grid 52`

The spoken template across 584 calls is invariably `use talk group <name> map grid <n>`, so
what sits in that slot *is* the channel name. **The STT was right; the vocabulary was missing
a word.** The venue channels are renamed by `2026-09-11b_correct_venue_channel_names.sql`.

Whisper's real failure on these calls is the opposite one — see fault 2.

## The cause — three faults

### 1. The vocabulary was missing a word

`Combined Venue Port Mann` should have been `Combined Response Venue Port Mann`. With the
wrong name, the two Port Mann calls could only ever match on `venue`/`port`/`mann` against a
channel 10 that owned `response` outright — see fault 3.

The transit channel is renamed on the same ruling, by pattern. **No call in the corpus has
ever used it**, so that rename rests on the operator's knowledge of the roster, not on a
measurement. Recorded as such rather than presented as verified.

### 2. Whisper drops the "10" from channel 10 on 8.5 % of calls

Measured 2026-09-11, and the reason the fix in fault 3 has the shape it does:

* **39 of 434** channel-10 calls transcribe `talk group combined response coquitlam` with no
  digit, in every round.
* **11 of those** have an operator-verified transcript, and every one reads
  `use talk group 10 combined response coquitlam`. The digit is spoken.
* **2 further calls** (`DISP-2026-E365BF`, `DISP-2026-78C19A`) keep the digit in one round and
  lose it in the other — the same broadcast, so only the STT can account for it.
* `parser/sanitize.py` was checked and does not touch digits after "talk group"; it only
  normalises the phrase itself. Not our code.

**Why Whisper drops it is not established** and is not guessed at here → backlog.

### 3. `match_radio_channel` returned the first qualifying channel in list order

Stage 2 admitted any channel sharing a word no other channel carried, then **returned the
first one in the list**. With the old (wrong) names the fragment named two:

| Channel | Named by | Words of the fragment it accounted for |
|:--|:--|--:|
| `10 Combined Response Coquitlam` | `response` | **1** |
| `Combined Venue Port Mann` | `port`, `mann` | **3** |

Channel 10 was sixth in `sort_order`, Port Mann seventh. That decided it — reproduced by
moving Port Mann to the front, which flips the answer with the input unchanged. It is the
**same defect class #19a was closing**: that fix removed a `token_set_ratio` stage whose
failure was order dependence and left an order dependence one stage earlier.

**Fix, in three attempts.** `1616c01` scored only the channels named by a word of their own.
The corrected names then broke that gate — `Combined Response Venue Port Mann` and `10 Combined
Response Coquitlam` share `combined` and `response`, so channel 10 has no distinguishing word
left but its digit, and fault 2 says that digit is missing 8.5 % of the time. Plain word
overlap across the whole roster replaced it, and got the right answers by arithmetic while
dropping 10 correct channels to unresolved.

**The operator replaced it with a cascade**, which is both better and checkable:

> *"If I were looking to differentiate the two, I would be looking for a number first and
> foremost with a following coquitlam... Then if no number, or unsure, check if it says venue.
> If it says venue look for Port Mann, or Transit System."*

| Step | Why it holds |
|:--|:--|
| **1. The number** | Every Coquitlam channel is announced with one, and across **148 calls on channels 5, 6 and 7 the digit survived the STT every single time**. A digit no channel carries falls through to the words rather than abandoning the fragment; two channels' digits at once is a contradiction and returns `None`. |
| **2. `venue`** | It appears in the venue channels **and nowhere else in the domain** — verified (§7.3a) as 0 of `road_names`, 0 of `parcels.street`, 0 of every other vocabulary category, and 2 of 624 raw transcripts, both of them the Port Mann calls. "Avenue" is a single token and does not collide. Heard, it restricts the answer to the venue channels; absent, it rules them out. **This is the step that was missing** — a venue channel used to have to outscore channel 10 across the whole roster, and lost. |
| **3. What is left** | Within whichever half step 2 chose: `port mann` against `transit system`, or `combined response coquitlam` against the bare numbered channels. A tie is `None`. |

**Bare `combined response` resolves to channel 10** — operator ruling, and it falls out of the
cascade rather than being special-cased: no `venue` excludes the venue channels, and no
numbered channel carries those words. Taken on the measurement that it happens on **17 of 436
channel-10 calls (3.9 %)**, that all 17 verify to channel 10, and that `venue` survived in both
Port Mann calls on record. **The residual risk is recorded, not hidden:** two calls is thin
evidence, and if a Port Mann call ever loses all three of `venue port mann` a crew goes to a
bridge incident on the wrong net and cannot tell. The ruling was made knowing that.

**Measured against the operator's verified transcripts (§7.6)** — 587 calls replayed through
the parser on the kiosk:

| | with ground truth | correct | wrong | unresolved |
|:--|--:|--:|--:|--:|
| **cascade (shipped)** | 537 | **536** | **0** | 1 |

All **14** calls that differ from the stored value are improvements: 11 had no channel and now
get the right one, **2 were on the wrong channel** (`DISP-2026-90674A` filed as 5 Coquitlam,
`DISP-2026-F24935` as 6 Coquitlam), and `DISP-2026-07CC85` moves to Port Mann. Nothing
regressed. The one unresolved call is `DISP-2026-747823`, where the STT lost the talk-group
clause entirely — there is nothing in the fragment to match.

Adding a channel needs no code: a new venue is found by step 2 and named by step 3 from
`public.vocabulary` alone. **Skytrain**, which the operator flagged as a name still to verify,
is covered by a test and deliberately not added to the list.

Script: [`tools/oneshot/2026-09-11_replay_channel_match.py`](../../tools/oneshot/2026-09-11_replay_channel_match.py).

### 4. The stored channel was never a vocabulary term — the dropdown oddity

`clean_channel_name_for_output()` stripped `Talk Group` and `Coquitlam` from every match, so
the parser stored `10 Combined Response` while the vocabulary held the full name. **575 of 576
stored values matched nothing in the list the operator picks from**, and
`VerificationSidebar.jsx` appends any unrecognised saved value as an extra `<option>` to keep
it choosable — the stray row at the bottom of the talk group dropdown, on nearly every call.

It reached ground truth too: **396 `verified_talkgroup` rows held `10 Combined Response`**
(prefilled from the system value) against **1** holding a real term; and two spellings of one
channel had accumulated from successive versions of the cleaner — `Combined Response` (38) and
`10 Combined Response` (385).

**Fix:** the cleaner is deleted, the vocabulary term is the spoken form and is stored
verbatim. `2026-09-11_canonical_radio_channel_names.sql` renamed the six prefixed terms and
backfilled both columns (applied: 575 + 537 rows).

### Caught in passing — the WER reference transcript rewrote the channel

`reconstruct_template_transcript()` built the scoring reference with:

```python
if chan == "10" or "combined" in chan.lower():
    channel_part = "use talk group 10 combined response coquitlam"
```

Any venue channel contains "combined", so a Port Mann call was scored against words the
dispatcher never said — punch-list #31 again, in the same function #31 is documented in. With
canonical terms the branch collapses to `use talk group {term}`.

## Not fixed here

* **The channel list is knowingly incomplete** (operator, 2026-09-11). An absent channel
  usually resolves to `None`, but one sharing a listed channel's words can be captured by it
  — `combined venue port moody` returns Combined Response Venue Port Mann. Not a regression:
  the pre-#79 rule does the same. Only the list can close it → backlog.
* **Why Whisper drops the "10"** — measured, unexplained, not guessed → backlog.
* **Stored channels are not re-decided.** 14 historical calls would parse differently under
  the cascade, 2 of them off a wrong channel. Those rows record what the system produced at
  the time; rewriting them is a re-parse, not a canonicalisation (§6.6). The operator can
  correct any of them in review.
* `DISP-2026-07CC85` also parsed its address as `4453 Port Man Bridge`, which is not a civic
  address → backlog.
* The fallback talk-group regex is bounded by `map grid` **or end of text**, so a transcript
  with no map grid hands the rest of the announcement to the matcher → backlog.

## Verify after deploy

```sql
SELECT d.target->>'radio_channel' AS stored, count(*),
       bool_or(v.term IS NOT NULL) AS in_vocabulary
FROM public.dispatches d
LEFT JOIN public.vocabulary v
  ON v.category = 'radio_channel' AND v.term = d.target->>'radio_channel'
WHERE d.target->>'radio_channel' IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC;
```

Every row must read `in_vocabulary = true`. The next Port Mann dispatch confirms the parse
itself — **not** to be closed out before one arrives (§6.5).
