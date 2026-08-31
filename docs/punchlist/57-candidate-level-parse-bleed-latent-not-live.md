# Punch list #57 — Candidate-level parse bleed — latent, not live

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🧾 Session batch, 2026-08-29/30 — XStreets, rounds, and the confidence ruling |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L4524 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 57. Candidate-level parse bleed — latent, not live
> **Status**: 🔵 **Open, low priority. Explicitly NOT a live defect** — recorded because it was
> observed and mis-described in conversation before being measured, and the correction belongs
> in writing (§6.6).

Re-deriving **every candidate from every round** yields cross-street values that have swallowed
the talk group, the call type, or the next round:

```
Private Driveway Use Easttalk Group 5 Coquitlam
Summit Middle School Access Broom 1415 Parkway Blvd
Westwood Cyclist Struck Westwood Street
School Rescue 2 Ladder 1
```

**None of this reaches the database.** Measured against stored `target.cross_streets`:

| | |
|:--|--:|
| Stored values | 110 |
| Distinct | 59 |
| Containing a talk-group / unit / call-type token | **0** |
| Longer than four words | **0** |

Those candidates never win. The cross-roads segment boundary
(`announcement.py:110-119`) is bounded by the talk-group anchor, so a round whose anchor is
missing or misheard runs the segment on to the end. It is worth a guard and a test — an
upper bound on plausible cross-street length would catch every example above — but it is
**not** evidence the parser is producing bad output today, and it should not be cited as one.
