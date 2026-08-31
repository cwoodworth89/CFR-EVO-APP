# Punch list #13 — `public.intersections` needs the same data-integrity pass

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🧭 Geocoder Honesty Gaps |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L593 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 13. `public.intersections` needs the same data-integrity pass
> **Status**: ✅ **Closed 2026-08-22.** This item proposed deriving intersections from
> `public.roads` via `ST_Intersects` "so false entries become structurally impossible".
> That is what was done — see #9 for the measured before/after.
>
> Three further defects were found and fixed in the same pass:
>
> * **Suffix vocabulary was hardcoded in two places that disagreed.** The extractor wrote
>   `SUNSET SQ` while the geocoder normalized a dispatch to `SUNSET SQUARE`, so those
>   intersections were unreachable; `normalization.py` was also missing 10 suffix types
>   present in `public.roads.roadtype`, covering 26 real streets. Suffixes now live in
>   `public.vocabulary` (category `street_suffix`) and are read by both, with a migration
>   guard that fails loudly if the municipal data gains a suffix nothing maps.
> * **Five inconsistent zone-containment queries.** `ST_Contains` tests the strict
>   interior, and zone polygons are bounded by roads, so junctions sit exactly on a
>   boundary and were rejected: 155 of 1,784 intersections got no map grid for that reason
>   alone. There is now one `public.zone_for_point()`, and `intersections.zone_id` — a
>   denormalized copy of it — was dropped.
> * **Fuzzy intersection matching substituted silently.** See #15.

The nearest-civic work fixed the *address* side of unresolvable locations. The
intersection side has had no equivalent review:

* At least one confirmed false intersection (`DAVID AVE & PANORAMA DR`, item #9), where
  PostGIS confirms the road geometries never meet.
* 6,499 rows against 3,947 documented in `docs/development_freeze_summary.md`.
* Apparent duplicates (`ABBEY LN & GLENBROOK ST` twice) that may or may not be legitimate
  `candidate_index` entries.
* No validation that a stored intersection point actually lies on both named roads.

A proper audit must normalise street suffixes first — `intersections.street_a` uses
abbreviations (`ABBEY LN`) while `roads.fullname` uses full words (`Waterford Place`),
so a raw string join matches only 317 of 6,499. Reuse `normalize_street_suffix` from
`parser/location.py`.

Worth considering whether intersections should be *derived* from `public.roads` geometry
via `ST_Intersects` rather than imported as a separate list — that would make false
intersections structurally impossible.

---

## 📢 PA Page Leakage
