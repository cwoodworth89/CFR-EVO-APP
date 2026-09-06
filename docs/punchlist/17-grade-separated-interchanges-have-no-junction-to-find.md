# Punch list #17 — Grade-separated interchanges have no junction to find

| | |
|:--|:--|
| **Status** | WITHDRAWN |
| **Severity** | crew-visible |
| **Area** | 🔎 Geocoder Substitution |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L756 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 17. Grade-separated interchanges have no junction to find
> **Status**: ⚪ **Withdrawn 2026-09-05, operator ruling: this came from the Gemini-era "NG911 standards" that were invented, and it is not data a crew arrives with.** *(Opened as: ⚠️ Open — one manual row added, needs operational confirmation.)*

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

---

## 17 (update). Materially changed by the #42 roads re-import

> **Status**: ⚠️ **Open — but the ground moved 2026-08-30. Needs re-measurement, not the
> original manual fix.**

This item predates **#42**. At the time, 41 of 44 `Highway Ramp` segments were missing from
`public.roads` because the import dropped everything that was not `STATUS = OPERATING`, so a
grade-separated interchange genuinely had no junction to find.

Now that every status is imported, the database holds **4 `Ramp` roads and 67 ramp
junctions** in `public.intersections`. The original problem statement no longer describes the
data. Re-measure against the actual interchanges before doing any manual work here — the
manually added row referenced in the original entry may now be redundant or conflicting.

### Withdrawn 2026-09-05

Operator: *"Not sure where #17 came from, and that is not data we can arrive with. It was a
routing issue when Gemini made up a bunch of NG911 standards."* The one manual row it added
stays; a junction pair the resolver cannot narrow goes to the candidate selector (#72's rule
A shows both), which is the real behaviour for the interchanges the dispatcher does name.
