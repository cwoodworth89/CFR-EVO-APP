# Punch list #21 — Rail crossing list is hand-entered and probably incomplete

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🧱 Duplicated & Unsourced Frontend Constants |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L898 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 21. Rail crossing list is hand-entered and probably incomplete
> **Status**: ⚠️ **Open — found 2026-08-22.**

`frontend/src/components/map/railroadCrossings.js` holds **four** level crossings with
seven-decimal coordinates and `avoidable` flags, none of which carry provenance (§6.3).

CLAUDE.md §6.2 already names the authoritative source for exactly this data — *"rail
crossings are `railway=level_crossing` in OSM, not `lat < 49.26`"*. This list is the same
defect one level up: four hand-placed points standing in for the OSM layer. Coquitlam
almost certainly has more than four level crossings, and **an incomplete hazard layer is
worse than an absent one**, because a crew reading a clear map concludes there is no
crossing.

**Mitigating for now**: display only. The layer defaults to off and no route avoids these
points, so no apparatus routing depends on them today.

**Fix**: derive from OSM `railway=level_crossing` into a table, the way intersections are
now derived from `public.roads`, and drop the `avoidable` judgement unless it can be
attributed to someone.
