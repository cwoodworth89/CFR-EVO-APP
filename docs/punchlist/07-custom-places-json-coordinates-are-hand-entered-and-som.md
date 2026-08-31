# Punch list #7 — `custom_places.json` coordinates are hand-entered and some are badly wrong

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 📍 Custom Places Data Quality |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L268 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 7. `custom_places.json` coordinates are hand-entered and some are badly wrong
> **Status**: ✅ **Closed 2026-08-21 — obsolete, resolved by removal.** The problem was not
> fixed by correcting the coordinates; **the entire cascade step was deleted** (commit
> `2ef12b7`), which moots the item. Verified on all four surfaces:
>
> * `backend/data/vocabulary/custom_places.json` — deleted.
> * `public.custom_places` — dropped (`to_regclass` returns `NULL` on the kiosk).
> * The geocoder cascade no longer has a custom-places step; `geocoder.py` documents the
>   removal in place, citing the ≤1.8 km error and the fact that Locution always speaks
>   the civic address first, so the step was effectively unreachable anyway.
> * The competing hardcoded school list in `MapLayers.jsx` is gone — the "two
>   hand-maintained lists disagreeing" defect no longer has two lists.
>
> No references to `custom_places` remain anywhere in the tree.
>
> **What this does not resolve**: the underlying need. A dispatch that names a place rather
> than an address now returns `None` and surfaces the §5 Tier 1 card instead of resolving
> ~1.8 km off. That is the correct failure under §6.1 — visibly unknown beats confidently
> wrong — but it is a *capability gap*, not a capability. If place-name dispatches turn out
> to matter operationally, the fix is authoritative records in `public.parcels`, per §6.2 —
> never a re-imported hand-keyed list.
>
> The original analysis is kept below as the rationale for the removal.

**Original finding (2026-08-21, measured against `public.parcels`):**

* **What it was**: `backend/data/vocabulary/custom_places.json` held 152 named places (deleted — see the status above)
  (parks, schools, civic buildings) keyed by lowercase name. It seeds
  `public.custom_places`, which is **Step 7 of the 8-step geocoder cascade** — the
  fallback used when a dispatch names a place rather than an address.
* **The problem**: coordinates appear hand-entered and are not validated against any
  authoritative source. Three secondary schools, cross-checked against `public.parcels`
  (municipal `Addresses.shp`):

  | Place | `custom_places.json` error | `MapLayers.jsx` error |
  |:--|--:|--:|
  | Centennial Secondary | **1,774 m** | 92 m |
  | Gleneagle Secondary | 537 m | 14 m |
  | Pinetree Secondary | 309 m | 28 m |

* **Operational impact**: a dispatch naming "Centennial Secondary" that falls through to
  Step 7 resolves ~1.8 km from the actual school. Apparatus routes to the wrong place,
  and nothing flags it — the coordinates are inside Coquitlam, so the §5 bounds check
  passes and tiles render normally.
* **Scope of the sample**: 140 of 152 entries carry a civic address in parentheses.
  Only **14** matched a parcel on exact address string (formats differ), so the
  distribution below is indicative, not a full audit: 8 within 50 m, 1 at 50–200 m,
  2 at 200–500 m, 3 over 500 m.
* **Second source of truth**: `MapLayers.jsx` carries its own hardcoded school list with
  *different* coordinates for the same schools. It is consistently closer to the parcel
  data (14–92 m). Two hand-maintained lists disagreeing is itself the defect.

* **Do NOT blind-snap to parcels.** For a school or civic building the parcel centroid is
  right. For a park, a lake, or a trailhead the useful dispatch point may deliberately be
  an entrance or muster point rather than the parcel centroid — some hand-placed values
  may be intentional. This needs a per-category decision:
  - **Buildings** (schools, hospitals, civic): resolve through the geocoder cascade
    against `public.parcels` and replace.
  - **Open spaces** (parks, lakes, trails): confirm with operations whether the stored
    point is a deliberate access point; if so, record that in `public.custom_places` as
    provenance rather than leaving it looking like an unverified guess.
  - Reconcile `MapLayers.jsx`'s school list against `public.custom_places` so there is
    one source.
* **Suggested check** — run the 140 addresses through the geocoder rather than exact
  string match, which will resolve far more than 14 and give a real error distribution.

---

## 🧪 Test Suite Debt

<!-- audit-ok: backend/data/vocabulary/custom_places.json -- closed item; its subject is the deletion of this file -->
