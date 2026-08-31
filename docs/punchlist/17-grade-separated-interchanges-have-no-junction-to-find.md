# Punch list #17 — Grade-separated interchanges have no junction to find

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🔎 Geocoder Substitution |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L756 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 17. Grade-separated interchanges have no junction to find
> **Status**: ⚠️ **Open — one manual row added, needs operational confirmation.**

Lougheed Hwy and Mariner Way never meet: closest approach **221.6 m**. The derived table
correctly holds `HIGHWAY RAMP & LOUGHEED HWY` (3 candidates) and `MARINER WAY & UNITED
BLVD` there instead. Crews nevertheless call the place "Lougheed and Mariner", so it exists
as a `source='manual'` row that `derive_intersections.py` will never overwrite.

**The coordinate is not operationally confirmed.** It is the midpoint of the shortest line
between the two centrelines (`49.240487, -122.816114`, map grid 49) — a defensible
derivation, but nobody has decided whether the centre of the gap is where apparatus should
be sent rather than a specific ramp head or the Mariner Way overpass. The row's `notes`
column says so. Needs review by whoever owns response geography.

---

## 🎙️ STT Vocabulary Biasing
