# Punch list #79 — A venue talk group loses to channel 10 on list order, and no stored channel is a vocabulary term

| | |
|:--|:--|
| **Status** | FIXED in the tree, not yet deployed. Migration written, **not yet applied**. `cfr-agent` restart required for either to take effect — the operator picks the moment (§ never restart the agent unasked). |
| **Severity** | 🔴 crew-visible |
| **Area** | 🎙️ Parser / talk group · 🗄️ Vocabulary · 🖥️ HITL review |
| **Ruling** | Operator, 2026-09-11: the `Talk Group` prefix is not part of a channel's name. Canonical is `5 Coquitlam`, `10 Combined Response Coquitlam`, `Combined Venue Port Mann`. One truth list, used everywhere. *(List confirmed as the right **form**; the operator has flagged it as **incomplete** — additions outstanding.)* |
| **Origin** | Operator, 2026-09-11, on `DISP-2026-07CC85`: *"The talk group was wrong... It missed Combined Venue Port Mann, and defaulted to combined response coquitlam. STT problem or something else?"* |

[← punch list index](../debug_and_qa_punchlist.md)

---

## Why this is crew-visible

The talk group is printed on the kiosk HUD and is what a crew keys up on. A wrong one is not
a blank field — it is a plausible channel, correctly formatted, that puts the truck on the
wrong net. Nothing on the display distinguishes it from a right one.

**The parser has never once resolved `Combined Venue Port Mann`.** Two calls in the corpus
were announced on it and both were filed as channel 10:

| Call | Heard after "talk group" | Parser | Actual |
|:--|:--|:--|:--|
| `DISP-2026-B772D2` (2026-08-02) | `combined response venue port mann` | 10 Combined Response | Port Mann — **operator corrected by hand** |
| `DISP-2026-07CC85` (2026-09-09) | `combined response venue port man` | 10 Combined Response | Port Mann |

The single correct `Combined Venue Port Mann` row in the database is the operator's HITL
correction on the first of those, not a parse.

## The cause — three faults, only one of them STT

### 1. Whisper inserted a word (contributing, not sufficient)

Both rounds of `07CC85` transcribe `use talk group combined **response** venue port man`.
The word `response` is not in the broadcast. Whether it is a free hallucination or a pull
from the bias prompt is **not established** — `bias_prompt.py` injects `use talk group` as a
phrase and the channel vocabulary carries "Combined Response" — and attributing it needs a
re-run against the audio. Recorded as unknown rather than guessed (§7.7).

This is not the deciding fault. `B772D2` spelled `mann` correctly and still resolved to
channel 10.

### 2. `match_radio_channel` returned the first qualifying channel in list order

`backend/cfr_dispatch/parser/channels.py`. Stage 2 admitted any channel sharing a word no
other channel carries, then **returned the first one in the list**. The fragment named two:

| Channel | Named by | Words of the fragment it accounts for |
|:--|:--|--:|
| `10 Combined Response Coquitlam` | `response` | **1** |
| `Combined Venue Port Mann` | `port`, `mann` | **3** (`combined`, `venue`, `port`) |

Channel 10 was sixth in `sort_order`, Port Mann seventh. That decided it. Reproduced by
moving Port Mann to the front of the list, which flips the answer with the input unchanged.

This is the **same defect class the #19a fix was closing**: that fix removed a
`token_set_ratio` stage whose failure was order dependence, and left an order dependence one
stage earlier.

**Fix:** a qualifying channel is now scored by how much of what was heard it accounts for;
a tie is `None`. Shared words ("combined", "venue") break ties but still cannot nominate a
channel on their own. Two channel digits in one fragment is now `None` rather than the
earlier one.

**Measured before changing it (§7.6):** all 624 stored `raw_transcript`s replayed through the
parser on the kiosk, both rules diffed over the 1029 fragments that reached the function —
**1026 identical, 3 changed, all 3 this defect.** No fragment the old rule got right is
decided differently. Script: `tools/oneshot/2026-09-11_replay_channel_match.py`.

### 3. The stored channel was never a vocabulary term — this is the dropdown oddity

`clean_channel_name_for_output()` stripped `Talk Group` and `Coquitlam` from every match, so
the parser stored `10 Combined Response` while the vocabulary held
`Talk Group 10 Combined Response Coquitlam`. **575 of 576 stored values matched nothing in
the list the operator picks from.** `VerificationSidebar.jsx` appends any unrecognised saved
value as an extra `<option>` so it stays choosable — which is why a stray `10 Combined
Response` sat below the real list on nearly every call.

It also reached ground truth: **396 `verified_talkgroup` rows hold `10 Combined Response`**
(prefilled from the system value by the Sys ⤓ control) against **1** holding a real term. And
two spellings of one channel accumulated from successive versions of the cleaner —
`Combined Response` (38) and `10 Combined Response` (385).

**Fix:** the cleaner is deleted. The vocabulary term is the spoken form and is stored
verbatim. Migration `2026-09-11_canonical_radio_channel_names.sql` renames the six prefixed
terms and backfills both columns.

### Caught in passing — the WER reference transcript rewrote the channel

`reconstruct_template_transcript()` built the scoring reference with:

```python
if chan == "10" or "combined" in chan.lower():
    channel_part = "use talk group 10 combined response coquitlam"
```

`Combined Venue Port Mann` contains "combined", so a Port Mann call was scored against words
the dispatcher never said — punch-list #31 again, in the same function #31 is documented in.
With canonical terms the whole branch collapses to `use talk group {term}`.

## Not fixed here

* **The channel list is knowingly incomplete.** The operator ruled 2026-09-11 that it holds
  the channels that matter and is not the full set, and that completing it waits. An absent
  channel usually resolves to `None` as it should, but one sharing a listed channel's
  distinguishing word is captured by it — `combined venue port moody` returns **Combined
  Venue Port Mann**, because `port` belongs to no other listed channel. Not a regression:
  the pre-#79 rule returns the same, verified against `HEAD~1`. No code change can close
  this; only the list can → [`post_freeze_backlog.md`](../post_freeze_backlog.md).

* `DISP-2026-07CC85` also parsed its address as `4453 Port Man Bridge`, which is not a civic
  address. Separate defect → [`post_freeze_backlog.md`](../post_freeze_backlog.md).
* The fallback talk-group regex in `announcement.py` is bounded by `map grid` **or end of
  text**, so on a transcript with no map grid it hands the rest of the announcement to the
  matcher, map-grid digits included. The digit stage now returns `None` on two channel digits
  rather than guessing, so this is contained, not correct → backlog.
* `sanitized_transcript` is deliberately **not** rewritten by the migration. It records what
  the system produced and is read as evidence in review (§6.6).

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
