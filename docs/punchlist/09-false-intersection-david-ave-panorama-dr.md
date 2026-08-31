# Punch list #9 — False intersection: DAVID AVE & PANORAMA DR

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🧪 Test Suite Debt |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L430 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 9. False intersection: DAVID AVE & PANORAMA DR
> **Status**: ✅ **Closed 2026-08-22 — resolved structurally.** `public.intersections` is
> now DERIVED from `public.roads` centreline geometry
> ([`backend/scripts/derive_intersections.py`](../backend/scripts/derive_intersections.py)),
> so a pair of streets that never meet cannot be stored. 6,499 rows → **1,784**; the
> `DAVID AVE & PANORAMA DR` rows are gone, and
> `test_every_intersection_is_geometrically_real` now asserts the invariant over the whole
> table rather than that one pair.
>
> **The scope question is answered, and it was not a handful of bad rows.** The old table
> came from `extract_all_intersections_from_gis.py`, which never read a road centreline:
> it paired PARCEL address points within 40 m of each other on differently-named streets,
> took the midpoint of the shortest line between the two parcels, and clustered those with
> a 45 m epsilon. Its working definition of "intersection" was *two houses on different
> streets happen to be within 40 m*. Measured against road geometry:
>
> | Measure | Count |
> |:--|--:|
> | Rows whose two streets never meet | **3,086** (1,777 of those pairs >60 m apart) |
> | Rows where the streets do meet, median coordinate error | **63 m** (only 129 of 2,863 within 10 m) |
> | Stored points not within 20 m of *any* road | **3,413** |
> | Rows on a street literally named `NAN` | **113** |
>
> Verified against the 24 real intersection dispatches: **kept 20, gained 1, lost 0**, and
> against the five operator-verified coordinates the error fell from 879 m → 5 m,
> 471 m → 1 m, 107 m → 15 m, 41 m → 7 m, and 8 m → 9 m.
>
> The original finding is kept below.

**Original finding (2026-08-21):** the two rows were
> still present on the kiosk: `SELECT count(*) FROM public.intersections WHERE
> intersection_key = 'DAVID AVE & PANORAMA DR'` returns **2**, against a table of **6,499**.

`test_no_false_intersections` asserts these parallel streets never meet. `public.intersections`
holds **2 rows** for them, and PostGIS confirms the road geometries do **not** intersect:

```sql
SELECT EXISTS (SELECT 1 FROM public.roads a, public.roads b
  WHERE a.fullname ILIKE 'DAVID AVE%' AND b.fullname ILIKE 'PANORAMA DR%'
    AND ST_Intersects(a.geom, b.geom));   -- returns false
```

A dispatch to that intersection geocodes to a fabricated point with no warning.

**Scope is not established.** A bulk check comparing every stored intersection against
road geometry was attempted and is invalid: `intersections.street_a/street_b` use
abbreviated suffixes (`ABBEY LN`) while `roads.fullname` uses full words
(`Waterford Place`), so only 317 of 6,499 join at all. A real audit must normalise
suffixes first — reuse `normalize_street_suffix` from `parser/location.py` rather than
joining raw strings.

Also observed: duplicate rows (`ABBEY LN & GLENBROOK ST` twice). May be legitimate
multi-candidate entries distinguished by `candidate_index`, or may be duplicates —
not yet determined.
