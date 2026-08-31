# Design Proposal (UNADOPTED): Emergency Vehicle Routing to Cadastral GIS Parcels

> [!CAUTION]
> **This is not a standard, and it was never ratified.** It was retitled and re-classified on
> 2026-08-29 because its previous framing — *"Authoritative Engineering Standard, Release
> 1.0.0"* — caused it to be read as a description of the system CFR EVO actually runs. It is
> not. Large parts of it describe software that does not exist, data the City of Coquitlam does
> not publish to us, and compliance with standards this project does not hold.
>
> **Read §0 below before acting on any part of it.**

**Document Identifier**: `CFR-EVO-PROPOSAL-GIS-ROUTING-2026`
**Classification**: Unadopted design proposal / research write-up. **Not an operational
authority.** Nothing in it may be cited as provenance for a constant (CLAUDE.md §6.3, §7.4).
**Target Platform**: Coquitlam Fire Rescue Emergency Vehicle Operations (CFR EVO)
**Subsystems it assumes**: `cfr_api` (FastAPI Gateway), `cfr_postgres` (PostgreSQL 16 +
PostGIS 3.4), `cfr_kiosk`, and **`cfr_valhalla` — which is not deployed and was never
adopted.** The system routes on OSRM (`cfr_osrm`, stock `driving` profile, MLD algorithm).
**CRS it assumes**: `EPSG:26910` (NAD83 / UTM Zone 10N) as the primary metric CRS.
**The database as built does not use 26910 in any column** — all geometry is `EPSG:4326`.
**Originally dated**: August 2026
**Status**: ⚠️ **UNADOPTED — annotated for known errors 2026-08-29.** Superseded in part by
what was actually built; see §0.


---

## §0 What in this document is true — read before anything else

Added 2026-08-29 by the QA/GIS workstream. Everything below §0 is the document as originally
written, annotated in place. **Original claims are left visible and corrections recorded beside
them rather than overwriting them**, so a reader can see both what was asserted and what was
found.

Every finding here was **measured against the running kiosk system or the working tree**, not
inferred from reading. The queries are reproducible on request.

### The part that is genuinely good, and was adopted

**§2.1–§2.4 — boundary-edge decomposition and multi-criteria frontage scoring — is sound work,
and its central insight is now in production.** Snapping a parcel by its polygon boundary rather
than its centroid is what fixed large sites: `2865 Glen Dr`'s centroid is 135.6 m from Glen
Drive, and on 177 parcels citywide the centroid falls outside the parcel entirely.

What was **not** adopted is its treatment of the street name as a scoring weight. The proposal's
`(1.0 + 2.0 * I_name)` prior gives the addressed street a 3× advantage and then lets
parallelism, edge length and road class outvote it. That is a weight overruling a municipal
fact, and it put **1,813 of 65,399 parcels on a street their address does not name**. In
production the street name is a **filter**, not a prior — see
[`briefings/addressed_street_snapping_decision.md`](./briefings/addressed_street_snapping_decision.md).

### Claims that are measurably false

| § | The document says | Measured |
|:--|:--|:--|
| §3.1.3 | Response zones *"form a seamless planar partition with **zero slivers, zero gaps, and zero overlapping polygons**"* | **0.2937 km²** of the city lies in no zone; **33 overlapping zone pairs**; those overlaps total 0.0001 km² — they *are* slivers. Two junctions already fall in the gap and resolve to no map grid. |
| §3.1.2 | Road centrelines carry `Z_Level` for bridge / surface / tunnel separation | **There is no `Z_LEVEL`, level or elevation attribute** in the City's `Roads.shp` or in `public.roads`. A safety guarantee was built on a field that does not exist; it could never have fired. |
| §3.1.2 | Segments carry left/right **parity** (`O` / `E`) | `public.roads` has `left_begin`, `left_end`, `right_begin`, `right_end` — the ranges exist. **There is no parity field.** |
| §3.1.1 | *"Every geocoded address in CFR EVO records its placement method"* (`PlacementMethod`) | **No such column exists** on `public.parcels`. Nothing records placement method. |
| §1.4 | `ST_Buffer(geom, 50)` to build a 50 m exclusion ring | The geometry is 4326, so `ST_Buffer` buffers in **degrees**. As written this yields a **57,232,823 km²** polygon — roughly 11% of the Earth. The correct form is `ST_Buffer(geom::geography, 50)::geometry` (0.019 km²). |

### Software this document describes that does not exist

| § | Described | Reality |
|:--|:--|:--|
| §1.5, §1.4, §4.3 | Valhalla as the primary routing engine, `exclude_polygons`, request-time dynamic costing | **Valhalla is not deployed.** There is no `cfr_valhalla` container. Routing is OSRM on the **stock `driving` profile**. The Valhalla migration was reviewed and **paused**. |
| §3.4 | An OSRM Lua profile `evo.lua` carrying emergency tagging rules | **No `.lua` file exists anywhere in the repository.** No custom profile has ever been written. |
| §2.5 | `parcel_access_overrides` + `parcel_access_overrides_history`, audit triggers, Knox / FDC / staging coordinates | **Neither table exists.** What was built instead is `public.parcels.entrance_lat/lng` with `entrance_set_by`, `entrance_set_at`, `entrance_note`. All 65,401 entrance points are currently NULL and there is no UI to set one — punch-list #49. |
| §2.6 | Three PL/pgSQL functions | Only `fn_calculate_parcel_road_snap` is registered in the database, and **it is called by nothing**. `fn_determine_arrival_side_and_heading` and `fn_resolve_incident_routing_destination` do not exist. |
| §2.7 Tier 2 | A municipal curb-cut / ingress layer, `access_points.shp` | **The City does not publish this to us and we do not hold it.** The tier is unreachable. |
| §3.5 | Grade-aware routing, DEM ingestion, downhill speed caps by slope | **There is no elevation or DEM data anywhere in the system.** `public.roads` has no grade, incline or elevation column, and no HGT / GeoTIFF raster is held. Every equation in §3.5 has no input. |
| §2.7 | A 5-tier resolution hierarchy | What is built is **three** tiers: `entrance → front → centroid`. Tiers 2 and 3 as described have no data source. |

### Numbers presented as authority that have no source

CLAUDE.md §6.3 requires every operational constant to name where it came from, and §7.4 requires
the clause rather than the document. Neither is satisfied anywhere below.

* **§1.1 Table 1.1** — the engine benchmark was **not measured on this system**. Our OSRM
  measures **44.6 MiB** container RSS against the table's "~80 MB", **232 MB** on disk against
  "~110 MB", and a **median 1.4 ms** route against a stated floor of 1.5 ms. The table's figures
  should not be quoted for this deployment — and the comparison that actually matters is on
  **Raspberry Pi**, which neither the table nor our measurement covers.
* **§1.2 Table 1.2** — apparatus weights, heights, turning radii and speed factors are presented
  as CFR fleet specification. **They are not sourced from CFR's fleet.** No apparatus
  specification document is held. They must be confirmed against the actual apparatus by the
  department before any of them influences a route. `APPARATUS_TIERS` in
  `services/gis/src/gis_service/routing_engine.py` is **deliberately staged and not applied**
  (CLAUDE.md §6.4) for exactly this reason.
* **§1.3** — gate and preemption delays (`+10 s`, `+15 s`, `+30 s`, `+45 s`, and `+1.5 s` vs
  `+12.0 s`) carry **no cited source of any kind**. Whether Coquitlam runs Opticom / EMTRAC
  preemption at all is unconfirmed. §1.3.4's proposal to treat `no_left_turn` and `no_u_turn` as
  permitted is an **operational and legal policy decision the department has not made.**
* **§2.7 Table 2.1** — the per-tier confidence figures (100% / 95% / 85% / 75% / 50%) and the
  latency figures are invented. Confidence in this system is **not calibrated**: score 100 was
  wrong on 8% of reviewed calls, while the 81–89 band was flawless (punch-list #32).
* **§3.2** — NFPA clause numbers are cited precisely (`1225 §18.2`, `1710 §4.1.2.1`, `1900 §5.7`,
  `1141 §5.2`). **This project holds none of those documents** — see
  [`standards/README.md`](./standards/README.md), where every row reads `NOT HELD`. The figures
  may well be correct; they are **unverified**, and a precise-looking clause number on an
  unverified figure is worse than no citation, because it stops the next reader checking.
* **§3.5 Table 3.2** — the thermal brake simulation is an unvalidated model with invented inputs
  (250 kg of brake steel, a 350 kW retarder, 150 °C ambient) and, as above, no elevation data to
  run on.
* **§4.3 Table 4.1** — the polygon-vertex benchmark was not measured on this system, and it
  benchmarks a Valhalla feature that is not deployed.
* **§3.6 Table 3.3** — the academic citations are **unverified**. They have not been checked
  against the publications and several could not be located. Treat none of them as support for a
  value until the paper is in hand (CLAUDE.md §7.3 — recollection is not provenance).

### How to use this document

1. **Never cite it as provenance.** It is not a source. If you need a governing authority, start
   at [`standards/README.md`](./standards/README.md); if nothing there covers your decision,
   stop and raise it with the operator (CLAUDE.md §7.2).
2. **§2.1–§2.4 is worth reading** for the frontage-scoring approach, with the street-name
   correction noted above.
3. **Treat the rest as a wish list** — and note that several of the wishes need data the City
   does not publish. Those belong in
   [`city_gis_data_register.md`](./city_gis_data_register.md) as requests, not in code as
   assumptions.
4. **Anything adopted from here needs its own provenance**, gathered independently.

Full review correspondence, with the queries behind every figure above:
[`briefings/valhalla_standard_review_response.md`](./briefings/valhalla_standard_review_response.md).
The snapping half of that correspondence was deleted on 2026-08-31 with the proposal it
reviewed; git history holds it.

---

## §0a What was removed, 2026-08-30

**Sections 1, 3 and 4 and the executive summary were deleted.** Operator direction: prune
rather than annotate. §0 above had already measured them and found, variously, a routing
engine that is not deployed, a Lua profile that was never written, elevation physics with no
elevation data, NFPA and NENA clauses from documents this project does not hold, and academic
citations that could not be located. A document does not become safe by admitting it is wrong;
it stays in the search path, and the next reader still has to litigate it.

**§0's findings about those sections are deliberately kept**, because the record of *how* a
plausible document turned out to be fiction is worth more than the fiction. Section references
in §0 pointing at §1, §3 and §4 therefore name content that is no longer in this file — that is
intended, and git history holds it.

Section 2 was kept at that point because live code cited it by section number. **It has since
been removed too — see §0b below.** Nothing in this file is a specification any more; what is
left is the audit.

---

## §0b Section 2 removed, 2026-08-31

**The proposal this document specifies was not adopted, and its code is deleted.**
`import_parcels_PROPOSED.py` and `test_boundary_snapping_PROPOSED.py` were removed on
2026-08-31 along with the review correspondence around them. Section 2 was their
specification, so it is removed too — a spec for code that does not exist is the purest form
of the problem §0 describes.

**What shipped instead is one rule, and it is not in this document.** The addressed street is
a **filter**, not a weighted term: constrain the road search to `roads.roadname =
parcels.street`, then take `ST_ClosestPoint(road.geom, parcel.geom)` — measured to the
polygon, not the centroid. Department decision 2026-08-29, live in
`import_parcels.py::backfill_parcel_frontage`.

Section 2's multi-criteria scoring made the street name a 3× prior instead, which geometry
could outvote, and that put **1,813 parcels on a street their address does not name** —
`2865 Glen Dr` onto Guildford Way, 254 m from where a crew should stop. Measured against the
live database on 2026-08-31, the shipped rule leaves **zero** misplacements wherever a road
of the right name exists.

**The four reference cases survive as executable tests**, which is a better home for them
than prose: `backend/tests/test_boundary_snapping.py`.

Current direction: [`briefings/addressed_street_snapping_decision.md`](briefings/addressed_street_snapping_decision.md)
and [`briefings/base_site_rows_decision.md`](briefings/base_site_rows_decision.md).

---

*§0 above is retained in full. It is the measured audit of how a fluent, precisely formatted
document turned out to be fiction, and that record is the only part of this file still worth
reading.*
