# Punch list #66 — The kiosk address sanitizer removed 18 City street names that begin with a unit keyword

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🖥️ Kiosk |
| **Blocks** | 0 |
| **Origin** | Found 2026-09-05 by a parity check of `sanitizeAddress` against the dispatch corpus, while writing the JS/Python normalisation test |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 66. "1550 United Blvd" became "1550 Blvd" before the kiosk looked it up

> **Status**: ✅ **Closed 2026-09-05 — fixed in the same commit, measured against every City road
> name, test added.** Crew-visible: the sanitized string is the key the kiosk uses for the
> Street View panel and the map's target address, so every call on an affected street lost
> them.

### What happened

`frontend/src/utils/addressUtils.js` (`sanitizeAddress`) strips unit designators ("UNIT 105",
"Suite 200", "#5", "Bay 4") so the kiosk works from the base civic address. Its keyword
alternation had no word boundary, so `UNIT` matched the first four letters of *United* and `STE`
the first three of *Steeple*, and the rule that removes "keyword plus the token after it"
removed the street name.

Three call sites use the result: `StreetViewPanel.jsx` (the Street View override key),
`MapBoard.jsx` (`updateTargetAddress`, the address the map holds for the target), and
`LeftSidebar.jsx` (search de-duplication). `1550 United Blvd` (DISP-2026-DD939E, a real
dispatch, also in #64) reached them as `1550 Blvd`.

### Measured

| Input | Before | After |
|:--|:--|:--|
| 406 distinct address strings in the corpus since 2026-07-01 (parser output and the verified column, `[PA]` pages excluded) | 5 lost their street: `1050`, `1550` and `39 United Blvd`, `1332 Steeple Dr`, `2575 Steeple Crt` | 0 |
| `public.road_names`, all 1,079 City road names as `1234 <name>` | 19 damaged: United, Steeple ×2, Stewart, Stephens, Stellar, Fleet, Fleming, Florence, Floyd, Flynn, Lotus, Pheasant, Compass, Compton, Baycrest, Bayswater, Bayview, and `Highway #1` | 1: `Highway #1`, which reads as a unit and is not a civic-address street |

The other 32 changes in the corpus set are the function doing its job: trailing units removed
(`1131 Dufferin St 204D`), *And* harmonised to ` & `.

### Fix

A negative lookahead after each keyword, `(?![A-Za-z])`, in the prefix rule and the in-line
unit rule: the keyword must end the word. `UNIT 105`, `#5` and `UNIT105` still strip; *United*,
*Steeple*, *Fleet*, *Lotus* no longer do. The comment in the file carries the measurement
(CLAUDE.md §6.3).

### Test

`backend/tests/test_address_sanitizer_roads.py` runs the real JavaScript with node: the corpus
strings above, and every road name in `public.road_names`, asserting the damaged set is exactly
`{"Highway #1"}`. It skips without node; the road-name test also needs `DATABASE_URL`.

### What it says about §5

CLAUDE.md §5 calls address normalisation "one implementation, both sides". There are two,
written separately: this one and `extract_subaddress_info` in `parser/location.py`. The Python
one was not checked the same way today; that is one line in the post-freeze backlog.
