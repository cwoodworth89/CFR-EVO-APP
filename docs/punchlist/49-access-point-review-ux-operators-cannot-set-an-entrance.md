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
* **How much property lies beyond the arrival point** is what ranks the review queue — a
  12-hectare trailer park matters more than a wide driveway. It was briefly a stored column,
  `access_far_corner_m`, and was **dropped 2026-08-31**: it is derived from the arrival point,
  so it was only true until that point moved, and nothing recomputed it. When **#58** cleared
  56 stale front points, those rows kept a distance measured from a position that no longer
  existed. Operator decision: do not store values with no perpetual use. It is a report, and
  the query is in `backend/migrations/2026-08-31_drop_access_far_corner.sql` — run it against
  `is_base_site` rows once **#48** is applied, so a property is measured once rather than once
  per legal lot.

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

---

## 49 (update). The review queue is 1,671 sites, not 65,401 parcels

> **Status**: 🟡 **Built 2026-09-06 — the operator sets an arrival point from the workstation's search view; the kiosk says when one is in play. Open until the operator has used it on a real site.**

This item has read as "operators must set entrances on 65,401 parcels", which is why it has
not moved. Under the `base_site` decision it is **1,671 multi-parcel sites**, ranked by
parcel count, and the top fifty cover the complexes crews actually struggle with:

| Site | Parcels |
|:--|--:|
| 523 Gatensbury St | 392 |
| 567 Clarke Rd | 374 |
| 1016 Howie Ave | 360 |
| 657 Whiting Way | 335 |
| 1188 Pinetree Way | 316 |

One entrance set on the `base_site` serves every unit at that address — the resolution rule
is that a unit row with no `entrance_lat` falls back to its `base_site` row.

**Worth reconciling** against the "~1,400-site review queue" figure in
[`arrival_point_handoff.md`](../arrival_point_handoff.md); they may be the same set.

The UI is still the whole of this item — all 65,401 `entrance_lat` are NULL and there is no
way to set one without direct SQL. See
[`briefings/base_site_rows_decision.md`](../briefings/base_site_rows_decision.md).

---

## 49 (built). Set the arrival point where the truck stops, from the search view

> **Status**: 🟡 **Built 2026-09-06 (`API POST /api/parcels/entrance`, workstation card,
> kiosk note). Live for search after the API rebuild; live for dispatches after the next
> agent restart. Closes when the operator has set one on a real site.**

The operator's ruling earlier the same day settled what the marker means: *"the truck is
going to stop at the marker, not the door … that marker point is where we transition from
city to private."* So the arrival point is an operational fact the operator owns, and the
UI is the smallest thing that lets them own it:

* **Workstation, Explore mode.** Search an address; the target card gains an *Arrival
  point* section showing what is in play — *computed frontage* or *OPERATOR-SET · name ·
  date · "note"*. *Set arrival point* enters placement mode: the next map click drops an
  amber dashed pin, a note in the officer's words and a name (remembered on the machine)
  are typed, *Save* writes `entrance_lat/lng`, `entrance_note`, `entrance_set_by`,
  `entrance_set_at` through `POST /api/parcels/entrance`. *Clear* returns the parcel to the
  computed frontage and keeps the note as the record. One parcel per save, no bulk, name
  required: the API refuses an unattributed override.
* **The map follows the ruling**: after a save the target moves to the new point, the route
  and the hydrant picks measure from it.
* **Kiosk.** The resolver now says which of the three points answered (`arrival_point`:
  entrance / front / centroid) and carries `entrance_note`; the dispatch payload passes both
  through, and the details box shows *ARRIVAL POINT SET BY OPERATOR — note* when an
  operator's point is the pin, so a crew reads it as a ruling rather than a wrong guess.
* **Constraints held**: `import_parcels.py` never writes `entrance_*`; nothing bulk; every
  override attributed; a unit row with no entrance still falls back to its base site.

Not built: the worst-first review queue as a screen. `docs/complex_sites_for_review.csv`
still ranks the sites; the operator works it by searching each address. The top hundred
covers 65 % of the addresses behind complex sites and is an afternoon.
