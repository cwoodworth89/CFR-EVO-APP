# Punch list #15 — Fuzzy matching silently substituted a different intersection

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🔎 Geocoder Substitution |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L701 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 15. Fuzzy matching silently substituted a different intersection
> **Status**: ✅ **Closed 2026-08-22.** Found while verifying the #9 rebuild.

`intersection_resolver.lookup` resolved an unmatched intersection by fuzzy-matching the
whole normalized key against every other key and returning the best hit above 80.

Observed live:

| Requested | Returned | Reported as |
|:--|:--|:--|
| `Lougheed Hwy & Mariner Way` | `Lougheed Hwy & Pinetree Way` — **4,301 m away** | conf 86, `is_ambiguous: false`, no note |
| `Lougheed Hwy & Lougheed Hwy` | `Alderson Ave & Lougheed Hwy` | **conf 100** |

Two independent causes:

1. **The `token_set_ratio` subset trap.** It returns 100 when one token set is a subset of
   the other, so `token_set_ratio('LOUGHEED HWY', 'ALDERSON AVE & LOUGHEED HWY')` = 100.
   Any key containing the requested street scored a perfect match.
2. **No safe threshold exists.** Measured across all 1,079 road names, genuinely different
   streets score `HAMBER CRT`/`AMBER CRT` **96**, `WESTWOOD ST`/`EASTWOOD ST` **93**,
   `BURKE MOUNTAIN ST`/`BLUE MOUNTAIN ST` **93** — while the transcription errors worth
   recovering score `TASIS→TAHSIS` **95** and `JOHNSON→JOHNSTON` **98**. The correct
   corrections sit *below* the dangerous collisions. No cutoff separates them, and
   confusing Westwood with Eastwood sends apparatus across the city.

**Fix.** Fuzzy matching is now a *candidate generator only*, never a resolution. Each
street is scored independently (whole-key scoring let the shared half inflate the result —
that is how `MARINER WAY`→`PINETREE WAY` reached 86), only combinations that correspond to
a real existing junction are offered, and any non-exact match comes back
`is_ambiguous: true` with `requested_address` and `resolution_note` so the operator sees
and confirms it. The street-type alias swap (`RD↔AVE`, `ST↔WAY`, `BLVD↔DR`, returning
confidence 95) was deleted outright — renaming a street is not a match.

The real fix for transcription noise is upstream: Whisper already receives
`COQUITLAM_STREETS` from `public.road_names`, and biasing transcription toward the real
vocabulary stops "Lowheed" reaching the geocoder at all.
