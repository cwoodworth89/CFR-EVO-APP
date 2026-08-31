# Punch list #44a — Round 1 wins the address unconditionally — Phase 2 never compares the two rounds

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🔁 Batch follow-up, 2026-08-23 (operator screenshots + kiosk probes) |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2575 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 44. Round 1 wins the address unconditionally — Phase 2 never compares the two rounds
> **Status**: ⚠️ **Open — measured 2026-08-23.** **Confirmed live**, not historical: split by
> month, it still costs ~5% of double-round calls in 2026-08. Characterised only; no fix
> applied. Related to `parser_audit_handoff.md` §5, which flagged this as a lead but never
> sized it.

**The dispatcher announces every call twice, and the system reads only the first answer.**

#### Mechanism

`all_candidates` is built by iterating rounds in order
([`phase2.py:113`](../backend/cfr_dispatch/pipeline/phase2.py)):

```python
announcements = split_rounds(transcript, units_vocab)
for text in announcements:
    all_candidates.extend(parse_dispatch_announcement(text, units_vocab))
```

then the address is selected at [`phase2.py:146`](../backend/cfr_dispatch/pipeline/phase2.py):

```python
p2_candidate = next((d for d in all_candidates if d.address or d.intersection), None)
```

The **first round that yields any address wins.** There is no scoring, no comparison, no
fallback. Round 2 is never consulted once round 1 produced something — even when what it
produced is `29883 Robson Dr`.

Note `p2_grid` and `p2_channel` (`:164`, `:167`) use the same `next(...)` idiom, but for those
it is benign: they skip nulls, so any round holding the value supplies it. The address is
different because a *corrupted* address is still an address, and it short-circuits the search.

#### Measured against ground truth, by month

Double-round verified calls, parsing each round separately and asking which agrees with
`verified_address`:

| Month | rounds agree | R1 right | **R2 right (bias hurts)** | neither | single round |
|:--|--:|--:|--:|--:|--:|
| 2026-07 | 93 | 51 | **8** | 38 | 15 |
| 2026-08 | 63 | 20 | **5** | 11 | 0 |

**~5% of double-round calls in 2026-08.** Unlike the map-grid figure corrected in
`parser_audit_handoff.md` §4.3a, this one survives the date split.

#### The failure mode is consistent: round 1 has digit or street corruption

```
29883 Robson Dr                   ->  2983 Robson Dr        extra digit
303030 Gordon Ave                 ->  3030 Gordon Ave       repeated digits
3025 Loheed Hwy                   ->  3025 Lougheed Hwy     street mis-heard
2991 Lockheed Hwy                 ->  2991 Lougheed Hwy     street mis-heard
47 Lougheed Hwy                   ->  2747 Lougheed Hwy     house number truncated
2615 Harrier Drive Nearcastoral…   ->  2615 Harrier Dr       "near" swallowed into the street
```

Affected: `DISP-2026-E5D4EC`, `DISP-2026-9B16EB`, `DISP-2026-4C4BAF`, `DISP-2026-070BC2`,
`DISP-2026-D239B1` (2026-08); `DISP-2026-4F427E`, `DISP-2026-76A4BF`, `DISP-2026-1D8368` and
others (2026-07).

#### ⚠️ Do NOT "fix" this by preferring round 2

Round 1 is right and round 2 wrong in **20** of the 2026-08 cases, against 5 the other way.
Preferring round 2 trades 5 wins for 20 losses. Preferring *either* round positionally is the
same class of mistake as the original.

#### Suggested fix: let the parcel data decide, not the round order

The geocoder already knows which candidate is real. `29883 Robson Dr` is absent from
`public.parcels`; `2983 Robson Dr` is present. `3025 Loheed Hwy` is not a Coquitlam street;
`3025 Lougheed Hwy` is. So the selection rule should be **"prefer the candidate that resolves
to a real parcel"**, using the authority that already exists rather than a positional
heuristic (CLAUDE.md §6.2 — prefer the authoritative source over a local model).

This should also recover part of the **11** "neither" cases, where round 1 won with a corrupted
address and neither round matched the verified string exactly.

`validate_address_exists` in
[`address_resolver.py`](../services/gis/src/gis_service/address_resolver.py) is the obvious
hook — noting it currently shares the no-`ORDER BY` tie-break bug inventoried in
`parser_audit_handoff.md` §6, which should be settled first.

#### Before implementing

This is a more invasive change than the vocabulary and payload fixes. Build the replay
harness as a regression gate first — `trace_geocode_corpus.py` already replays the geocoder;
the missing half is the parser-side equivalent (`parser_audit_handoff.md` §3). Any candidate
rule must be scored over the full corpus **split by month**, because a pooled figure here
would be dominated by 2026-07 STT damage that no longer occurs.

---

## 🧾 Import Completeness Audit, 2026-08-23

Run because the operator was worried that **imports are silently dropping data** — #41
(a missing address) and a parallel report of missing `public.roads` entries.

**Headline: both importers are faithful to their sources. The losses are real, but they are
deliberate filters and stale source data, not import bugs.** One filter is a genuine
operational problem and is the largest finding in this batch.

---
