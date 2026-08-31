# Punch list #42 — The roads import silently discards 242 road segments, including 45 streets that 1,918 parcels are addressed on

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🧾 Import Completeness Audit, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2679 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 42. The roads import silently discards 242 road segments, including 45 streets that 1,918 parcels are addressed on
> **Status**: ⚠️ **Open — confirmed against source and database. This is the answer to the
> "missing `public.roads` entries" report.**

`backend/scripts/import_gis_data.py`, `step2_import_roads` (~`:228`):

```python
status = props.get("STATUS")
if status and str(status).strip().upper() != "OPERATING":
    continue
```

**The arithmetic reconciles exactly, so nothing is lost accidentally:**

| | |
|:--|--:|
| `road_centre_lines.geojson` features | 3,456 |
| Dropped — `STATUS != 'OPERATING'` | **242** |
| Dropped — missing `FULLNAME` | 0 |
| Expected in `public.roads` | 3,214 |
| **Actual `public.roads` rows** | **3,214** ✅ |

The 242 break down as **170 PRIVATE, 71 MOT, 1 METRO**, and `public.roads` contains exactly
one distinct status: `OPERATING`.

#### Why this matters operationally

**68 named roads exist *only* as non-OPERATING segments and are therefore entirely absent
from `public.roads`** — not thinned, absent. Among them:

* **`Highway #1`** (Trans-Canada) — 7 MOT segments, 0 OPERATING. Confirmed: `SELECT count(*)
  FROM public.roads WHERE fullname ILIKE '%Highway #1%'` returns **0**.
* **`Mary Hill By-Pass Road`** — 4 MOT segments, 0 OPERATING. Also **0** rows.
* ~60 strata/private residential streets.

Partial losses too, where a road survives but loses segments: `Lougheed Highway` 8 of 45,
`United Boulevard` 6 of 22, and **`Highway Ramp` 41 of 44**.

**The residential side is the serious part.** Cross-referencing `public.parcels.street`
against `public.roads.roadname`:

| | |
|:--|--:|
| Distinct streets in `public.parcels` | 997 |
| **Streets with no matching road** | **45** |
| **Parcels addressed on those streets** | **1,918** |

Largest affected streets:

| Street | Parcels |
|:--|--:|
| Princess | **568** |
| Silver Springs | **359** |
| Riverbend | 227 |
| Whisper | 193 |
| Bluff | 63 |
| River | 60 |
| Bow | 55 |
| Flynn | 50 |

Verified in the source: `Princess Crescent (PRIV)`, `Silver Springs Boulevard`,
`Riverbend Drive`, `Whisper Way`, `Oxbow Way (PRIV)`, `Parkland Drive (Private)` are all
present in `road_centre_lines.geojson` and all carry `STATUS = PRIVATE`. They are strata
roads — **but people live on them and crews respond to them.** A dispatch to
`2980 Princess Cres` is in the corpus already.

**What still works**: direct address geocoding, because `public.parcels` holds these
addresses with coordinates. **What does not**: anything road-derived — `public.intersections`
(derived from `public.roads`, so no junction on these streets can exist), "near \<road\> and
\<road\>" matching, cross-street validation, and street-name vocabulary.

#### Recommendation

Do not simply delete the filter — `STATUS` is meaningful municipal data and MOT/PRIVATE
segments may need different routing treatment. Instead **import all statuses and keep the
`status` column populated**, letting consumers decide. `public.roads.status` already exists
and currently holds one value for every row, which is the tell that a distinction was
flattened at import rather than preserved.

Requires a re-import and an `public.intersections` re-derivation. **Confirm with the operator
before running** — it changes the geocoder's street vocabulary.

---
