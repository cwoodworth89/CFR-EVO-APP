# Punch list #19a — Remaining fuzzy-match sites have not been reviewed

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🎙️ STT Vocabulary Biasing |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L850 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 19. Remaining fuzzy-match sites have not been reviewed
> **Status**: ⚠️ **Open — inventoried 2026-08-22, not yet reviewed.**

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

`token_set_ratio` scoring a short string against a longer one that contains it returns 100
(#15), so any site comparing a street fragment against a full street name is exposed.
`sanitize_transcript`'s phonetic corrections are hardcoded regex rather than fuzzy — they
are deterministic and auditable, but should be checked for the same collision property:
a correction that rewrites one real street into another real street would be worse than
any fuzzy match, because nothing scores it.

---

## 🧱 Duplicated & Unsourced Frontend Constants
