# Punch list #19a — Remaining fuzzy-match sites have not been reviewed

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🎙️ STT Vocabulary Biasing |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L850 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 19. Remaining fuzzy-match sites have not been reviewed
> **Status**: ✅ **Closed 2026-09-06 — all five sites reviewed; the last two measured on the whole corpus, one replaced, one kept on the numbers.** *(Opened as: Open — inventoried 2026-08-22, not yet reviewed.)*

#15 fixed `intersection_resolver.lookup`. Five other similarity-matching sites share the
same exposure and have **not** been examined against the Coquitlam street-collision
measurements (`HAMBER`/`AMBER` 96, `WESTWOOD`/`EASTWOOD` 93, `BURKE MOUNTAIN`/`BLUE
MOUNTAIN` 93):

| Site | Call | Risk |
|:--|:--|:--|
| `address_resolver.py:44` | `token_set_ratio(parsed_street, db_norm)` | **Highest** — same metric and same subset trap as #15, on the main address path rather than only intersections |
| `address_resolver.py:345` | `token_set_ratio(parsed_street, db_norm)` | As above, second call site |
| `parser/location.py:196` | `fuzz.ratio(clean_base, ks_lower)` | Feeds `fuzzy_correct_cross_roads`, invoked from `announcement.py:123` |
| `parser/call_types.py:38` | `token_set_ratio(ct.lower(), transcript)` | Different class (classification, not location) — a wrong call type is serious but not a wrong address |
| `parser/channels.py:42` | `token_set_ratio(raw_clean, chan_clean)` | Radio channel selection |

**2026-09-05:** three of the five are resolved. `address_resolver` scores with `fuzz.ratio`
(both sites, since #15's follow-up); `location.py`'s fuzzy correction is no longer called by
the parser, the near roads being resolved against the roads near the placed address instead
(#56); `call_types.py` searches only the incident slot of each round (#34a), though its fuzzy
stage still uses `token_set_ratio` on that slot. Remaining: `channels.py` (talk group) and
that fuzzy stage. Neither places a call.

Nothing is needed from the operator for this item: both remaining sites are code, and neither affects the map.

`token_set_ratio` scoring a short string against a longer one that contains it returns 100
(#15), so any site comparing a street fragment against a full street name is exposed.
`sanitize_transcript`'s phonetic corrections are hardcoded regex rather than fuzzy — they
are deterministic and auditable, but should be checked for the same collision property:
a correction that rewrites one real street into another real street would be worse than
any fuzzy match, because nothing scores it.

---

## 🧱 Duplicated & Unsourced Frontend Constants

### Closed 2026-09-06

**`channels.py` — replaced.** The talk group is now named by its digit, or by a word only one
channel carries (*response* for 10 Combined Response, *port* for the Port Mann venue); the
words the channels share (*talk group*, *coquitlam*, *combined venue*) name nothing on their
own, and a digit no channel has is a misread, not an invitation to match the rest. The
fuzzy stage that used to follow — `token_set_ratio` over those shared words, returning
whichever channel came first in the list at 75 — is gone. Measured first: every talk-group
fragment in the corpus with a digit, or *combined response*, resolved at the earlier stages
(355 × "10 combined response", 118 × "5", 25 × "combined response", 20 × "6", 12 × "10
combined respond"; 48 with nothing after "talk group"); the fuzzy stage decided nothing that
was right. Whole corpus through the chain harness after the change: **talk group wrong 20 →
20, zero calls changed verdict.** Seven tests, `backend/tests/test_channel_match.py`.

**`call_types.py` — kept, on measurement.** The fuzzy stage after the substring match was
removed and the corpus re-run: **incident wrong 15 → 18**. The three: DISP-2026-4C9D76 and
7270E4, *"order, unknown source"* for Odor - Unknown Source, and 969223, *"Medic, Aid,
overdose, arrest"* for Medical Aid - Overdose Arrest — STT misspellings only a fuzzy score
sees. Restored, with the measurement beside the threshold. An offline check against the
API's stored transcripts had said the stage decided nothing; the harness, which is the
record, said otherwise, and the harness wins (CLAUDE.md 6.6).

Score sheet for the five sites: `address_resolver` ×2 → `fuzz.ratio` (#15); `location.py`
→ no longer called, near roads resolved against the roads near the placed address (#56);
`channels.py` → replaced (above); `call_types.py` → kept, measured.
