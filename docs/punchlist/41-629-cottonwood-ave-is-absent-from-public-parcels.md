# Punch list #41 — `629 Cottonwood Ave` is absent from `public.parcels`

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🖥️ Live Operation Batch, 2026-08-23 |
| **Blocks** | 3 |
| **Origin** | `debug_and_qa_punchlist.md` L2296–2808 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 41. `629 Cottonwood Ave` is absent from `public.parcels`
> **Status**: ✅ **Closed 2026-08-23.** *(Opened as: ⚠️ Open — confirmed. A data gap, not a search bug.)*

The operator could not find `629 Cottonwood Ave` in the search bar. It is not there to find:
723 parcels match `%Cottonwood%`, and **zero** match `629 Cottonwood%`.

The neighbours exist, and the gap is a run of consecutive odd numbers:

```
... 620, 622, 625, 628, [627, 629, 631 MISSING], 633, 635, 637, 639 ...
```

So the search bar is reporting the database honestly. Either the addresses are genuinely
absent from the City of Coquitlam `Addresses.shp` import, or they were dropped during
`backend/scripts/import_parcels.py`. A run of three consecutive missing odd numbers on one
side of the street suggests a real-world cause (a consolidated lot, a redevelopment, a
renumbering) at least as strongly as an import defect — **do not assume the importer is
broken without checking the source shapefile.**

Per §6.2 this belongs in the data, not in application code: if the addresses are real, the fix
is a parcel import correction, never a string-match special case in the geocoder.

**Next step**: check whether 627/629/631 Cottonwood Ave exist in the source `Addresses.shp`,
and whether the operator can confirm from local knowledge that 629 is a real, currently
addressable property.

---

## 🔁 Batch follow-up, 2026-08-23 (operator screenshots + kiosk probes)

---

## 41 (revised). `629 Cottonwood Ave` exists on the map but not in `public.parcels`
> **Status**: ⚠️ **Open — confirmed as an import gap, not a real-world absence.**

The operator points out that 629 **is** labelled as a parcel on the cadastral layer, and the
screenshot confirms it: one parcel carries **two** labels, `625` and `629`.

That resolves the question left open above. The parcel is an **address range, 625–629**, and:

* the **cadastral MBTiles** (built from the City data) renders both numbers;
* **`public.parcels` holds only `625 Cottonwood Ave`** (49.2595007, −122.8843437). There is no
  `629` row, so the search bar cannot find it.

So the earlier suggestion that a consolidated lot or renumbering explained it was **wrong** —
the address is real and the City data has it. Two derivations of the same municipal source
disagree, and the one the search reads is the lossy one.

**This is very likely not a single missing address.** Any parcel carrying an address *range*
would lose every number except the one imported. `public.roads` already stores
`left_begin/left_end/right_begin/right_end`, so range semantics exist elsewhere in the schema
— worth checking whether `Addresses.shp` carries a range per parcel that
`backend/scripts/import_parcels.py` collapses to a single value.

**Next step**: inspect the source `Addresses.shp` attributes for 625 Cottonwood Ave, determine
whether ranges are represented, and count how many parcels are affected before deciding on a
fix. Per §6.2 the correction belongs in the import, never as a geocoder special case.

---

---

## 41 (closed). `629 Cottonwood Ave` — the parcel import is correct; the shapefile does not have it
> **Status**: ✅ **Closed 2026-08-23 as "not an import defect."** The underlying discrepancy is
> real and is recorded below, but nothing in this project is losing it.

**The parcel import reconciles exactly**, read straight from `Addresses.dbf` (no GDAL locally,
so via a minimal DBF reader):

| | |
|:--|--:|
| Records in `Addresses.shp` | 69,708 |
| Blank `ADDRESS` | 167 |
| Exact duplicate `ADDRESS` strings | 4,141 |
| **Unique = expected import** | **65,400** |
| **Actual `public.parcels` rows** | **65,401** |

That is a clean reconciliation. (The extra row is 1 above the source; worth a glance but it is
a single record, not a pattern.)

**`629 Cottonwood Ave` is not in `Addresses.shp` at all.** Searching the source for
Cottonwood house numbers 625–633 returns exactly two records: `625 Cottonwood Ave` and
`633 Cottonwood Ave`, both `STATUS = Active`. So the earlier suggestion that the importer
collapses address *ranges* was **wrong** — there is no range to collapse.

**Where the map label comes from.** The cadastral layer is not rendered from a shapefile —
`backend/scripts/crawl_cadastral_tiles.py` pre-caches tiles from the **City of Coquitlam
ArcGIS Cadastral MapServer**, layers `[0: Road Labels, 1: Address Labels, 16: Parcels]`. So
`629` is drawn by the City's own live map service.

**The two municipal sources disagree**, and this project faithfully reflects both:

| Source | Has 629? |
|:--|:--|
| `Addresses.shp`, extract dated **2025-06-22** | **No** |
| ArcGIS Cadastral MapServer address labels (crawled later) | **Yes** |

The most likely explanation is simply that the shapefile extract is **over a year old** and
the address was created after it. That is worth acting on independently of 629: the whole
parcel layer is running on a 2025-06-22 snapshot.

**Next step**: re-pull `Addresses.shp` from the Open Data portal and re-run the import — it is
a non-destructive `ON CONFLICT (address) DO UPDATE` upsert that preserves operational data
(pre-plans, lockbox notes, Street View headings), so it is low risk. See the
`gis-pipeline-sync` skill. Then confirm 629 appears.

---
