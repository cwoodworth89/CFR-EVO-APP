# Punch list #49 — Access-point review UX — operators cannot set an entrance without direct SQL

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | operational |
| **Area** | 🧾 Import Completeness Audit, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3501 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 49. Access-point review UX — operators cannot set an entrance without direct SQL
> **Status**: 🔴 **Open — HIGH PRIORITY. Schema and data are ready; only the UI is missing.**
> Operator decision 2026-08-29: build the geometry now, defer the UX as the next feature.

The arrival-point pipeline is complete and correct for ordinary properties. What has no
interface is the exception path.

#### What is already done

* `backend/scripts/import_parcels.py` computes every front point as the closest point on the
  road **the address names** to the parcel **polygon**, recomputing all 65,401 rows on each
  run. Verified: **0 parcels sit off their addressed street** where such a street exists; the
  54 that do are municipal data gaps in `docs/city_gis_data_register.md`.
* `public.parcels.entrance_lat` / `entrance_lng` are now the **operator-verified** access
  point, cleared of the copied centroids they used to hold, with `entrance_set_by`,
  `entrance_set_at` and `entrance_note` for attribution.
* Resolution precedence is **entrance → front → centroid**
  (`services/gis/src/gis_service/address_resolver.py`). A recorded human answer outranks the
  calculation.
* `public.parcels.access_far_corner_m` records how much property lies beyond the arrival
  point, so the review queue is a query rather than a stale list.

**All 65,401 entrance points are NULL.** There is no way to set one except by hand-writing SQL
against production, which is exactly the practice this workstream spent two days arguing
against.

#### The queue is smaller than it looks

`docs/complex_sites_for_review.csv` — 1,395 sites, 25,475 addresses behind them:

| Sites reviewed | Addresses covered | |
|--:|--:|--:|
| 25 | 7,750 | 30% |
| 50 | 11,612 | 46% |
| **100** | **16,635** | **65%** |
| 252 | 23,417 | 92% |

Highrises dominate by address count, trailer parks by distance: `1158 The High St` is 645
addresses at 120 m; `201 Cayer St` is 266 addresses at 366 m across a 122,923 m² site. Both
need one decision each.

#### What the UX needs to do

One screen per site, worked worst-first:

1. Orthophoto at the site, parcel outline drawn, current computed front point pinned.
2. Click to place the verified access point.
3. A note in the officer's words — *"gated, keypad at Glen Dr west end"* — stored in
   `entrance_note` and shown to crews.
4. Save writes `entrance_lat/lng`, `entrance_set_by`, `entrance_set_at`.

Roughly 30 seconds per site. The top 100 is an afternoon.

#### Constraints that must hold

* **An import must never overwrite `entrance_*`.** `import_parcels.py` already carries that
  comment; a UI that writes through the same path would break it.
* **Every override is attributable.** An unattributed override is just another unexplained
  number (§6.3).
* **Do not offer a "clear all" or bulk-apply.** These are per-site human judgements.
* The kiosk should show `entrance_note` when an override is in play, so crews know why the pin
  is where it is rather than wondering if it is wrong.

---
