# Punch list #42 — The roads import silently discards 242 road segments, including 45 streets that 1,918 parcels are addressed on

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🧾 Import Completeness Audit, 2026-08-23 |
| **Blocks** | 2 |
| **Origin** | `debug_and_qa_punchlist.md` L2679 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 42. The roads import silently discards 242 road segments, including 45 streets that 1,918 parcels are addressed on
> **Status**: ✅ **Closed 2026-08-30.** *(Opened as: ⚠️ Open — confirmed against source and database. This is the answer to the "missing `public.roads` entries" report.)*

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

---

## 42 (closed). Filter removed, re-imported, re-derived — verified against the live database

> **Status**: ✅ **Closed 2026-08-30.** Verified by querying the running kiosk database, not
> by reading the commit (§6.6).

Fixed in `302af14` — *"import roads of every status, and repair the import script itself."*
The filter is gone, `status` is preserved per row for consumers to act on, and the import now
logs a per-status breakdown so an unexpectedly absent class is visible on every run.

**The arithmetic reconciles exactly, which was this item's own standard:**

| | |
|:--|--:|
| `road_centre_lines.geojson` features | 3,456 |
| Dropped — no `FULLNAME` (all 5 are `PRIVATE`) | 5 |
| **Expected** | 3,451 |
| **Actual `public.roads` rows** | **3,451** ✅ |

`public.roads` now holds four statuses: `OPERATING` 3,214 · `PRIVATE` 165 · `MOT` 71 ·
`METRO` 1.

**The operational damage is undone:**

| | Before | After |
|:--|--:|--:|
| Streets in `public.parcels` with no matching road | 45 | **17** |
| Parcels addressed on them | 1,918 | **69** |

`public.intersections` was re-derived — 1,995 rows, with junctions now present on the
recovered streets (Princess, Silver Springs, Riverbend, Whisper) and 33 on `Highway #1` /
`Mary Hill By-Pass Road`, which previously had none because the roads did not exist.

**The 69 remaining parcels are not a defect, and this is why.** Ten of the 17 names are not
streets at all — `Power Line`, `N/O Quarry`, `S.E. Quarry`, `S.E./O Quarry`, `E/O Pipeline`,
`Fraser River`, `Railroad`, `Munro Creek`, `Deboville Slough`, `Coquitlam` — survey notations
and geographic features carried in an address field. The remainder (`Pinecone Burke` 28,
`Deer's Leap` 15, `Coronation` 7, `Fremont` 6, `Taft` 1, `Addington` 1, `Trans Canada` 1) were
each checked against every road sharing a name stem: **none exists in `public.roads` under any
spelling.** The City does not publish centrelines for them. That is a municipal data gap, not
an import defect — [`city_gis_data_register.md`](../city_gis_data_register.md) is where it
belongs if it is ever worth raising.

**Queries reproducible on the kiosk database**; the parcel/road cross-reference is
`upper(trim(roads.roadname)) = upper(trim(parcels.street))`.
