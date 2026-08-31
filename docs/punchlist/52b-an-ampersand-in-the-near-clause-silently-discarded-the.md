# Punch list #52b — An ampersand in the "near" clause silently discarded the second cross street

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3884 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 52. An ampersand in the "near" clause silently discarded the second cross street
> **Status**: ✅ **Fixed 2026-08-30.** Found on the first live call after the #51 transcript fix
> deployed — `DISP-2026-AAFDB8`, which proved the fix worked *and* exposed this underneath it.

**Announced:** *"1123 Westwood St, **Near, Anson, Avenue & Lincoln Ave**, Use Talk Group 5
Coquitlam, Map Grid 8, 2"*

**Captured:** `cross_streets: ["Anson Ave"]` — Lincoln Ave gone.

> ⚠️ **First diagnosis was wrong, corrected the same hour.** I initially blamed
> `clean_location_text`'s negative lookahead in `location.py`, shipped that in `6d2d907`, and
> re-tested against the live call — **it still returned `cross_street_2: None`.** The cause is
> upstream: I had traced the stages using the *raw* transcript, when the parser sanitises first.
> Recorded rather than overwritten, because a fix that did not work is the more useful thing to
> know about.

**Cause.** `sanitize_transcript` strips every non-alphanumeric character to nothing
(`backend/cfr_dispatch/parser/sanitize.py`), and `&` is punctuation to that rule. The separator
is **deleted before any cross-street logic runs**:

```
announced : "Westwood St, Near, Anson, Avenue & Lincoln Ave, Use Talk Group, 5"
sanitized : "westwood st near anson avenue lincoln ave use talk group 5"
                                  ^ no separator left at all
```

`clean_location_text` then behaves **correctly**: it sees `anson avenue lincoln ave`, finds the
street type `avenue`, and strips `lincoln ave` as trailing junk — the same rule that turns
`Burlington Drive 105` into `Burlington Drive`. Everything downstream is correct too and never
gets the chance to matter: both `fuzzy_correct_cross_roads` (`location.py:211`) and the column
split (`announcement.py:158`) handle `&` properly, but there is no `&` left to handle.

**Why it survived this long.** Locution speaks the clause both ways and the announcement repeats
itself. This call's **second** round said *"Near, Anson Ave, and Lincoln Ave"*, which parses
correctly. Round 1 wins the address unconditionally (punch-list #44), so the broken form is the
one kept. Any call whose first round used "and" looked fine.

**Fix.** `sanitize_transcript` now rewrites `&` to `" and "` *before* the punctuation strip, so
the separator survives as the word it stands for. Verified end to end on the real announcement:
`cross_street_1='Anson Avenue'`, `cross_street_2='Lincoln Ave'`, transcript reads
*"...near anson avenue and lincoln avenue..."*. Backend suite 162 passed.

The `location.py` lookahead from `6d2d907` is **kept as defence in depth and relabelled as
such** — it is unreachable from the announcement path now, and its comment says so rather than
claiming credit for the fix.

**Not investigated:** `split_intersection_parts` also treats `/` and `@` as intersection
separators, and the same punctuation strip deletes both. No live example has been measured, so
they are left alone — but they are the identical defect if Locution ever speaks them. `at` is
likewise absent from the `location.py` lookahead and left alone deliberately: unlike `&` it
plausibly introduces a landmark rather than a street (*"Lougheed Highway at Superstore"*).

---
