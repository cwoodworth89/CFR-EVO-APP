# Punch list #68 — The digit join glued the next clause's number onto the map grid when the STT lost round 2's opening

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🎙️ Dispatch Pipeline |
| **Blocks** | 0 |
| **Origin** | Found 2026-09-05: the one map-grid miss in the hotword holdout run, DISP-2026-CF0CC2 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 68. "map grid 82 10 combined response" became "map grid 8210"

> **Status**: ✅ **Closed 2026-09-05 — fixed in `56a68a5`, tested on the transcript that showed
> it.** Crew-visible: the grid drives the zone the kiosk shows, and this call lost it.

### What happened

`sanitize_transcript` compresses digit groups so that spoken digits and split numbers read as
one number: *"1, 3, 7, 8, Oxford"* → `1378 Oxford`, *"110 0"* → `1100`. The third rule joined
*any* two digit groups separated by whitespace.

Replaying DISP-2026-CF0CC2 with "map grid" left out of the STT hotwords, the model in service
dropped the opening of round 2 and produced:

```
... use talk group 10 combined response coquitlam map grid 82  10 combined response coquitlam map grid 82
```

The join made `map grid 8210`; the parser rejected `8210` as not a zone and the call had no
grid. The same transcript with the default hotwords had round 2 start normally and parsed
`82`. So the miss belonged to the parser, not to the hotword change it was measured under.

### Fix

A map grid is at most three digits: `MAP_GRIDS`, the City's response zones, run 1-134. The
join rule now refuses a join that would exceed three digits when the left group directly
follows "map grid", and otherwise behaves as before. `map grid 10 9` still becomes `109`;
house numbers are untouched. The grid that reaches the parser is `82`, and the parser takes
the first digit group after "map grid" as it always did.

Not touched: a grid the model itself mangles into one token (`map grid 1010` for 109, #63).
There is no digit group boundary to refuse there, and shortening it would be a guess.

### Test

`backend/tests/test_sanitize_map_grid_join.py`: the CF0CC2 transcript parses to grid `82`
through `split_rounds` and `parse_dispatch_announcement`; `10 9` still joins; the two house
number forms still join. 227 tests pass.
