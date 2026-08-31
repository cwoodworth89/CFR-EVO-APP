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
[`briefings/valhalla_standard_review_response.md`](./briefings/valhalla_standard_review_response.md)
and
[`briefings/snapping_proposal_review_response.md`](./briefings/snapping_proposal_review_response.md).

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

**What remains is Section 2 only**, kept because live code cites it by section number:
`import_parcels_PROPOSED.py` (§2.2, §2.6), `verify_snapping_corpus.py` (§2 reference cases),
`test_boundary_snapping.py` and `test_boundary_snapping_PROPOSED.py` (§2.2), and
`city_gis_data_register.md` (§2.7). Numbering is unchanged so those citations still resolve.

Read §0 before trusting any of it — in particular, §2.5, §2.6 and §2.7 describe tables,
functions and a municipal layer that do not exist, and the five-tier hierarchy is three tiers
in production (`entrance → front → centroid`).

---

# Section 2: Street-to-Parcel Routing Architecture & Geometric Edge Matching

## 2.1 Failure Modes of Naive Centroid Snapping

> [!NOTE]
> **§2.1–§2.4 is the sound part of this document, and its central insight was adopted.**
> Measuring to the parcel **polygon** rather than the centroid is what fixed large sites. One
> thing was not adopted: the street name is a **filter** in production, never a scoring weight —
> the `(1.0 + 2.0 * I_name)` prior in §2.2 put 1,813 parcels on a street their address does not
> name. See
> [`briefings/addressed_street_snapping_decision.md`](./briefings/addressed_street_snapping_decision.md).


Naive centroid snapping calculates the geometric center of a parcel polygon ($C = \text{ST\_Centroid}(P)$ or $C = \text{ST\_PointOnSurface}(P)$) and projects an orthogonal vector to the closest road centerline segment in the spatial index:

$$P_{\text{snap\_naive}} = \arg\min_{R_k \in \mathcal{R}} \text{dist}(C, R_k)$$

In real-world municipal emergency vehicle operations, this naive approach fails across five primary failure modes:

```
                      FAILURE MODES OF NAIVE CENTROID SNAPPING
                      
[ Mode A: Back Alley Trap ]      [ Mode B: Divided Highway Trap ]     [ Mode C: Adjacent Parallel Street ]
      Main Civic Frontage             Divided Lougheed Hwy (West)           Parallel Street B (Back Yard)
  ═════════════════════════       ══════════════════════════════       ══════════════════════════════════
       ▲ (True Frontage)               ▲ (Wrong Side / Barrier)             ▲ (False Snap Across Fence)
  ┌────┴──────────────────┐       ┌────┴─────────────────────────┐     ┌────┴─────────────────────────────┐
  │   Civic Address 102   │       │   Commercial Supercenter     │     │      Deep Mountain Lot           │
  │   Parcel Centroid (C) │       │   Median Barrier [====]      │     │      Parcel Centroid (C)         │
  │        ▼              │       │                              │     │             ▼                    │
  └────────┬──────────────┘       └──────────────────────────────┘     └─────────────┬────────────────────┘
  ═════════▼═══════════════       ══════════════════════════════       ══════════════▼════════════════════
    Narrow Rear Laneway              Divided Lougheed Hwy (East)          Civic Frontage Street A
    (Blocked by Garages)             (Correct Response Side)              (True Driveway Access)
```

### Mode A: The "Back Alley / Service Laneway" Trap
* **Mechanism**: In dense urban and heritage residential neighborhoods (e.g., Maillardville, Austin Heights), lots are long and narrow, backing onto unpaved or narrow ($<4\text{m}$) rear service laneways. When homes or accessory dwelling units (laneway houses) sit near the rear boundary, the parcel centroid or address point lies geographically closer to the rear laneway centerline than the designated front street centerline.
* **Operational Hazard**: An Engine or Aerial Ladder is routed into a tight, dead-end alley obstructed by parked cars, overhead utility wires, and trash bins. The apparatus cannot deploy outriggers or advance master hose lines to the front entrance, losing 3–6 critical minutes executing a reverse multi-point turnaround.

### Mode B: The "Divided Carriageway / Dual Highway" Trap
* **Mechanism**: Major arterials such as Lougheed Highway (Highway 7), Barnet Highway (Highway 7A), and the Mary Hill Bypass feature multi-lane dual carriageways separated by concrete New Jersey barriers or raised curbed medians. A parcel located on the eastbound side may have a centroid that lies 18 meters from the westbound carriageway centerline and 22 meters from the eastbound carriageway centerline due to setback geometry.
* **Operational Hazard**: The routing engine directs the apparatus along the westbound lanes. Upon arrival, the crew observes the fire across four lanes of opposing traffic and an insurmountable concrete median barrier, necessitating an immediate 2.5 km detour to the nearest grade-separated interchange.

### Mode C: The "Adjacent Parallel Street / Back Fence" Dilemma
* **Mechanism**: On steep terrain (e.g., Westwood Plateau, Chineside, Ranch Park), large residential lots ($>800\text{m}^2$) back directly onto an uphill or downhill parallel street. Because of natural topography or retaining walls, the rear boundary is situated within 15 meters of the upper street centerline, while the front driveway is 25 meters from the lower street.
* **Operational Hazard**: The vehicle is routed to the upper street. Firefighters arrive at a 30-foot cliff or retaining wall overlooking the target roof, unable to access the structure with ground ladders or establish a continuous water supply.

### Mode D: The "Natural & Topographic Barrier" Trap
* **Mechanism**: Parcels abutting natural ravines, municipal greenbelts, rivers (Fraser River, Coquitlam River), or railway corridors (CP Rail mainline) have centroids positioned closer to a recreational trail, forest service road, or parallel track centerline than their actual civic access street.
* **Operational Hazard**: Apparatus are dispatched onto non-traversable gravel dyke roads or pedestrian trailheads.

### Mode E: Large Campus Centroid Snapping
* **Mechanism**: Large institutional, commercial, or healthcare parcels (e.g., Coquitlam Centre Mall, Eagle Ridge Hospital, Riverview Hospital Grounds) span hundreds of thousands of square meters. The geometric centroid falls inside an enclosed pedestrian atrium, courtyard, or rooftop zone hundreds of meters from any drivable perimeter ring road.
* **Operational Hazard**: The router snaps to an arbitrary exterior street rather than the dedicated emergency department ambulance bay, main lobby FDC, or fire lane ingress.

---

## 2.2 Boundary Edge Decomposition & Multi-Criteria Frontage Scoring

To eliminate these failure modes, CFR EVO implements a mathematical boundary edge matching algorithm. Rather than treating the parcel as a dimensionless point, the algorithm operates on the parcel's **cadastral boundary polygon** $\mathcal{P}$, decomposing the exterior ring into individual linear edge segments $E_i = (v_i, v_{i+1})$, and evaluating candidate road network centerlines $R_j \in \mathcal{R}$.

```
               BOUNDARY EDGE DECOMPOSITION & FRONTAGE MATCHING
               
                     Matching Road Centerline (R_j)
  ═════════════════════════════════════════════════════════════════════════
          ▲                                 ▲                     ▲
          │ d(E_front, R_j)                 │                     │
          ▼                                 │                     ▼
  ┌─────────────────────────────────────────┴────────────────────────────┐
  │                 Front Boundary Edge (E_front)                        │
  │                 Parallelism: |theta_E - theta_R| ≈ 0 deg             │
  │                                                                      │
  │  Side Edge (E_side1)                             Side Edge (E_side2) │
  │  Perpendicular to Road                           Perpendicular to    │
  │  |theta_E - theta_R| ≈ 90 deg                    Road                │
  │                                                                      │
  │                  Rear Boundary Edge (E_rear)                         │
  │                  Parallel to Rear Alley (Rejected via Name Match)    │
  └──────────────────────────────────────────────────────────────────────┘
```

### Mathematical Formulation

Let the parcel polygon boundary be $\partial \mathcal{P}$, decomposed into $N$ linear segments:
$$\partial \mathcal{P} = \bigcup_{i=1}^N E_i, \quad E_i = [v_i, v_{i+1}]$$

Let candidate road segments within search radius $D_{\text{max}} = 50\text{m}$ be $\mathcal{R}_{\text{cand}} = \{R_1, R_2, \dots, R_M\}$.

For each edge $E_i$ and candidate road segment $R_j$, the following criteria are evaluated:

1. **Minimum Euclidean Metric Distance**:
   $$d(E_i, R_j) = \min_{p \in E_i, q \in R_j} \|p - q\|_2$$

2. **Angular Alignment & Parallelism**:
   Let $\theta(E_i) \in [0, \pi)$ and $\theta(R_j) \in [0, \pi)$ represent the directional orientation angles in metric projection (`EPSG:26910`):
   $$\Delta \theta(E_i, R_j) = |\theta(E_i) - \theta(R_j)| \pmod \pi$$
   $$\text{Parallelism Score } \Phi(E_i, R_j) = \cos^2(\Delta \theta(E_i, R_j))$$

3. **Edge Frontage Length Weighting**:
   $$L(E_i) = \|v_{i+1} - v_i\|_2$$

4. **Lexical Street Name Match Indicator**:
   $$\mathbb{I}_{\text{name}}(R_j, \text{Address}) = \begin{cases} 1.0 & \text{if } \text{RoadName}(R_j) \equiv \text{CivicStreet}(\text{Address}) \\ 0.0 & \text{otherwise} \end{cases}$$

5. **Road Classification Hierarchy Weight ($W_{\text{class}}$)**:
   $$W_{\text{class}}(R_j) = \begin{cases} 
   1.2 & \text{Arterial / Primary Road (`ART`, `HWY`, `COL`)} \\
   1.0 & \text{Local Residential (`LOC`)} \\
   0.2 & \text{Service Lane / Rear Alley (`LANE`)} \\
   0.0 & \text{Private Driveway / Pedestrian Trail}
   \end{cases}$$

### Composite Frontage Objective Function $\Psi(E_i, R_j)$

The optimal frontage edge $E^*$ and target road snap segment $R^*$ are selected by maximizing the composite objective function $\Psi(E_i, R_j)$:

$$\Psi(E_i, R_j) = \left[ \alpha \cdot \Phi(E_i, R_j) + \beta \cdot \ln(1 + \min(L(E_i), L_{\text{max}})) \right] \times W_{\text{class}}(R_j) \times \exp\left(-\frac{d(E_i, R_j)}{\sigma_d}\right) \times \left( 1.0 + \kappa \cdot \mathbb{I}_{\text{name}}(R_j, \text{Address}) \right)$$

Where:
- $\alpha = 0.60$ (Weight for geometric angular parallelism $\Phi$).
- $\beta = 0.40$ (Weight for boundary frontage length).
- $L_{\text{max}} = 30.0\text{ m}$ (Upper bound on frontage length to prevent deep 100m+ lot lines from distorting the logarithmic term).
- $\kappa = 2.0$ (Multiplicative street name prior: yields a $3.0\times$ multiplier for candidate roads matching the authoritative CAD civic street name, versus $1.0\times$ for unmatched cross-streets or rear alleys).
- $\sigma_d = 25.0\text{ m}$ (Distance exponential decay scale parameter).
- $W_{\text{class}}(R_j)$ (Roadway classification weight: $1.2$ Arterial, $1.0$ Local, $0.2$ Lane).

*Empirical Rationale*: Employing a multiplicative name prior $(1.0 + 2.0 \cdot \mathbb{I}_{\text{name}})$ rather than an additive bonus (+0.50) mathematically eliminates false snaps on elongated corner lots (e.g. a $10\text{m}$ civic frontage with $18\text{m}$ setback achieving $\Psi = 2.28$ vs a $45\text{m}$ side flank on an unmatched cross-street achieving $\Psi = 0.91$, yielding a decisive $2.51\times$ preference for the true civic entrance).

### Orthogonal Projection & Linear Referencing

Once optimal edge $E^*$ and road segment $R^*$ are identified:
1. Construct the geometric midpoint or address-weighted point along $E^*$: $P_{\text{front}} = \text{ST\_PointOnSurface}(E^*)$.
2. Project $P_{\text{front}}$ orthogonally onto the centerline of $R^*$ using PostGIS linear referencing:
   $$t_{\text{proj}} = \text{ST\_LineLocatePoint}(R^*, P_{\text{front}}), \quad t_{\text{proj}} \in [0.0, 1.0]$$
   $$P_{\text{snap}} = \text{ST\_LineInterpolatePoint}(R^*, t_{\text{proj}})$$
3. **Boundary Clamping & Curvature Safety**: If $t_{\text{proj}} \in \{0.0, 1.0\}$ (the projection falls beyond the segment endpoint), clamp $P_{\text{snap}}$ to the endpoint and verify connectivity against adjacent road segments in the topology graph.

---

## 2.3 Complex Parcel Topologies & Edge Cases

```
                            COMPLEX PARCEL TOPOLOGIES
                            
  [ 1. Corner Lot (Dual Frontage) ]          [ 2. Through-Lot (Double Frontage) ]
         Side Cross Street                             Rear Parallel Street
    ════════════════════════════              ════════════════════════════════════
    ║  ┌───────────────────────┐              │  ┌─────────────────────────────┐ │
    ║  │ Secondary Flank       │              │  │ Back Fence / Rear Yard      │ │
    ║  │ (No Ingress)          │              │  │                             │ │
    ║  │                       │              │  │                             │ │
    ║  │ Primary Front Driveway│              │  │ Primary Front Entrance      │ │
    ║  └───────────┬───────────┘              │  └──────────────┬──────────────┘ │
    ║              ▼                          │                 ▼                │
    ════════════════════════════              ════════════════════════════════════
         Primary Civic Street                       Primary Civic Street
         
  [ 3. Flag Lot (Panhandle Easement) ]        [ 4. Cul-de-Sac Bulb & Head ]
         Main Residential Street                    Residential Access Road
    ════════════════════════════              ═══════════════════╗
          ▲ (Easement Neck Snap)                                 ║
    ┌─────┴─┐  ┌───────────────┐                                 ╚═════╗
    │ Pole  │  │ Front Lot A   │                                  ╔════╝  (Bulb Turnaround)
    │ (15m) │  └───────────────┘                                 ╱       ╲
    │       │                                                   │    ★    │ (Centroid: Center Island)
    │   ┌───┴──────────────────┐                                 ╲       ╱  Snaps to perimeter ring
    │   │  Flag Body           │                                  ╚═════╝
    │   │  (True Structure)    │
    │   └──────────────────────┘
```

1. **Corner Lots (Dual Frontage)**: The algorithm extracts the parsed street name from the CAD civic address (e.g., `1204 Lansdowne Dr` $\to$ `Lansdowne Dr`) and filters candidate boundary edges to those matching the primary street name, preventing false side-street snapping.
2. **Through-Lots (Double Frontage)**: Strict street name matching combined with house number parity validation (`left_begin`/`left_end` address ranges) eliminates the rear parallel street from consideration.
3. **Flag Lots (Panhandle Easements)**: The algorithm detects narrow access stems ($L \le 6.0\text{m}$) connecting landlocked rear parcels to the public right-of-way, snapping the destination to the **panhandle driveway ingress junction** rather than snapping through neighboring backyards.
4. **Cul-de-Sacs & Turnaround Bulbs**: The arrival coordinate is snapped to the **tangent entry point of the cul-de-sac neck**, directing apparatus to enter clockwise around the bulb to preserve vehicle momentum and nose-out egress position.
5. **Gated Communities & Multi-Family Strata**: For private townhouse and gated subdivisions (`STATUS = 'PRIVATE'`), the routing destination snaps to the **Main Security Gate Access Coordinate**, embedding the gate code directly into the CAD response cue card.
6. **Commercial / Institutional Campuses**: Multi-hectare facilities (e.g., Coquitlam Centre, Eagle Ridge Hospital) bypass algorithmic edge matching and route directly to **Tier 1 / Tier 2 Overrides** (Emergency Department bays, main lobby FDCs, or designated fire lanes).

---

## 2.4 Tactical Arrival Side & Heading Alignment

### Operational Fire Ground Tactical Context
Determining whether an incident structure lies on the **LEFT** or **RIGHT** side of the responding apparatus upon arrival is critical for vehicle positioning:
1. **Engine Pump Operator Safety & Supply Lines**:
   - The primary pump panel on North American fire apparatus (e.g., CFR Engine 1–4) is situated on the **driver/left side** of the vehicle.
   - If the target structure is on the right side of the street, positioning the apparatus curbside places the pump operator within the physical safety envelope of the vehicle, protected from passing traffic.
   - If the fire is on the left side of the street, the apparatus must be offset or a traffic block lane established to protect the operator.
   - 5-inch Storz Large Diameter Hose (LDH) supply lays from hydrants must avoid crossing active oncoming traffic lanes whenever possible.
2. **Aerial Ladder / Turntable Placement (Ladder 1 / Ladder 2)**:
   - The turntable of a 105-foot aerial ladder must be aligned to maximize scrub area across the building face. Arriving with the turntable positioned toward the structure eliminates cab obstruction and avoids outrigger interference with street curbs.

```
                      SIDE-OF-STREET ARRIVAL VECTOR MATH
                      
                               Direction of Travel (V_road)
                        P1 ──────────────────────────────► P2
                                         │ (P_snap)
                                         │
                                         │  Perpendicular Displacement
                                         │  Vector (V_disp)
                                         ▼
                                  ┌─────────────┐
                                  │ Target Bldg │ (P_parcel)
                                  └─────────────┘
                                  
  2D Cross Product: Z = (V_road_x * V_disp_y) - (V_road_y * V_disp_x)
  • Z < 0 ──► Incident is on the RIGHT side of travel
  • Z > 0 ──► Incident is on the LEFT side of travel
  • Z = 0 ──► Incident is directly AHEAD (roadway terminus)
```

### Mathematical 2D Cross Product Formulation

Let the road centerline vector in the direction of vehicle travel in metric coordinates (`EPSG:26910`) be:
$$\vec{V}_{\text{road}} = (x_2 - x_1, \, y_2 - y_1)$$

Let the displacement vector from the snapped road coordinate $P_{\text{snap}}$ to the target parcel entrance/centroid $P_{\text{parcel}}$ be:
$$\vec{V}_{\text{disp}} = (x_{\text{parcel}} - x_{\text{snap}}, \, y_{\text{parcel}} - y_{\text{snap}})$$

The 2D scalar cross product $Z$ is defined as:
$$Z = \vec{V}_{\text{road}} \times \vec{V}_{\text{disp}} = (x_2 - x_1)(y_{\text{parcel}} - y_{\text{snap}}) - (y_2 - y_1)(x_{\text{parcel}} - x_{\text{snap}})$$

- **If $Z < 0$**: The target structure lies on the **RIGHT** side of vehicle travel.
- **If $Z > 0$**: The target structure lies on the **LEFT** side of vehicle travel.
- **If $Z = 0$**: The target is directly collinear with the road vector (**AHEAD**).

---

## 2.5 Production PostgreSQL / PostGIS DDL Schema

> [!CAUTION]
> **Neither table below exists, and this DDL was never applied.** What was built instead is
> `public.parcels.entrance_lat` / `entrance_lng` with `entrance_set_by`, `entrance_set_at` and
> `entrance_note` for attribution. All 65,401 entrance points are currently NULL and there is no
> interface to set one — punch-list #49. The Knox box, FDC, staging and ingress coordinates
> below have **no data source**; nothing publishes them to us.


The following production-ready DDL defines the `public.parcel_access_overrides` and `public.parcel_access_overrides_history` tables, including spatial GiST indexes, check constraints, generated geometry columns, and automated audit triggers.

```sql
-- ============================================================================
-- CFR EVO Database Migration: Parcel Access Overrides & Audit System
-- Schema: public
-- Extensions Required: postgis, pgcrypto
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Master Table: parcel_access_overrides
CREATE TABLE IF NOT EXISTS public.parcel_access_overrides (
    id BIGSERIAL PRIMARY KEY,
    override_uuid UUID DEFAULT gen_random_uuid() NOT NULL UNIQUE,
    
    -- Relational Linkages
    parcel_id BIGINT REFERENCES public.parcels(id) ON DELETE CASCADE,
    gis_id VARCHAR(255) NOT NULL,
    civic_address VARCHAR(255) NOT NULL,
    
    -- Primary Tactical Arrival Coordinates (WGS84 EPSG:4326)
    front_lat DOUBLE PRECISION NOT NULL,
    front_lng DOUBLE PRECISION NOT NULL,
    front_geom GEOMETRY(Point, 4326) GENERATED ALWAYS AS (
        ST_SetSRID(ST_MakePoint(front_lng, front_lat), 4326)
    ) STORED,
    
    -- Secondary Tactical Sub-Locations
    ingress_lat DOUBLE PRECISION,
    ingress_lng DOUBLE PRECISION,
    ingress_geom GEOMETRY(Point, 4326) GENERATED ALWAYS AS (
        CASE WHEN ingress_lat IS NOT NULL AND ingress_lng IS NOT NULL 
             THEN ST_SetSRID(ST_MakePoint(ingress_lng, ingress_lat), 4326) 
             ELSE NULL END
    ) STORED,
    
    knox_box_lat DOUBLE PRECISION,
    knox_box_lng DOUBLE PRECISION,
    knox_box_geom GEOMETRY(Point, 4326) GENERATED ALWAYS AS (
        CASE WHEN knox_box_lat IS NOT NULL AND knox_box_lng IS NOT NULL 
             THEN ST_SetSRID(ST_MakePoint(knox_box_lng, knox_box_lat), 4326) 
             ELSE NULL END
    ) STORED,
    
    staging_lat DOUBLE PRECISION,
    staging_lng DOUBLE PRECISION,
    staging_geom GEOMETRY(Point, 4326) GENERATED ALWAYS AS (
        CASE WHEN staging_lat IS NOT NULL AND staging_lng IS NOT NULL 
             THEN ST_SetSRID(ST_MakePoint(staging_lng, staging_lat), 4326) 
             ELSE NULL END
    ) STORED,
    
    fdc_lat DOUBLE PRECISION,
    fdc_lng DOUBLE PRECISION,
    fdc_geom GEOMETRY(Point, 4326) GENERATED ALWAYS AS (
        CASE WHEN fdc_lat IS NOT NULL AND fdc_lng IS NOT NULL 
             THEN ST_SetSRID(ST_MakePoint(fdc_lng, fdc_lat), 4326) 
             ELSE NULL END
    ) STORED,
    
    -- Tactical Access Metadata
    access_type VARCHAR(50) NOT NULL DEFAULT 'DRIVEWAY_INGRESS' 
        CHECK (access_type IN ('CURB_PARKING', 'DRIVEWAY_INGRESS', 'GATED_KEYPAD', 'REAR_ALLEY_COMMERCIAL', 'FIRE_LANE', 'PRIVATE_EASEMENT')),
    
    gate_code VARCHAR(50),
    gate_key_box_type VARCHAR(50) DEFAULT 'KNOX_3200' 
        CHECK (gate_key_box_type IN ('NONE', 'KNOX_3200', 'KNOX_PADLOCK', 'OPTICOM_STROBE', 'SOS_SIREN_SENSOR', 'KEYPAD_CODE')),
    
    -- Apparatus Physical Clearance Constraints
    compatible_apparatus_tiers TEXT[] NOT NULL DEFAULT '{"LIGHT", "GENERAL", "HEAVY"}'::text[],
    max_apparatus_weight_tons NUMERIC(5,2) DEFAULT 40.0,
    vertical_clearance_m NUMERIC(4,2) DEFAULT 4.50, -- Standard NFPA 13.6ft / 4.15m clearance minimum
    turning_radius_m NUMERIC(4,2) DEFAULT 14.0,     -- Standard 45ft radius envelope
    
    -- Operational Flags & Provenance
    seasonal_access_restrictions TEXT,               -- E.g. "Steep unplowed winter grade >18%; dispatch Tender 4 via secondary route"
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    confidence_tier VARCHAR(20) NOT NULL DEFAULT 'TIER_1_VERIFIED'
        CHECK (confidence_tier IN ('TIER_1_VERIFIED', 'TIER_2_INGRESS', 'TIER_3_PROJECTED', 'TIER_4_EDGE_MATCH', 'TIER_5_CENTROID')),
    
    verification_status VARCHAR(30) NOT NULL DEFAULT 'VERIFIED_OFFICER'
        CHECK (verification_status IN ('PENDING_REVIEW', 'VERIFIED_OFFICER', 'VERIFIED_CHIEF', 'REJECTED_AUDIT')),
    
    created_by_badge VARCHAR(50) NOT NULL,
    verified_by_officer VARCHAR(100),
    verification_method VARCHAR(50) NOT NULL DEFAULT 'FIELD_SURVEY'
        CHECK (verification_method IN ('FIELD_SURVEY', 'INCIDENT_AFTER_ACTION', 'AERIAL_LIDAR_AUDIT', 'MUNICIPAL_GIS_IMPORT', 'DISPATCH_HITL')),
    
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Geographic Bounding Constraints (Coquitlam Operational Region)
    CONSTRAINT chk_front_lat_bounds CHECK (front_lat >= 49.15 AND front_lat <= 49.45),
    CONSTRAINT chk_front_lng_bounds CHECK (front_lng >= -122.95 AND front_lng <= -122.65),
    
    -- Secondary Coordinate Bounds & Pair Integrity Constraints
    CONSTRAINT chk_ingress_lat_bounds CHECK (ingress_lat IS NULL OR (ingress_lat >= 49.15 AND ingress_lat <= 49.45)),
    CONSTRAINT chk_ingress_lng_bounds CHECK (ingress_lng IS NULL OR (ingress_lng >= -122.95 AND ingress_lng <= -122.65)),
    CONSTRAINT chk_ingress_pair CHECK ((ingress_lat IS NULL) = (ingress_lng IS NULL)),
    
    CONSTRAINT chk_knox_lat_bounds CHECK (knox_box_lat IS NULL OR (knox_box_lat >= 49.15 AND knox_box_lat <= 49.45)),
    CONSTRAINT chk_knox_lng_bounds CHECK (knox_box_lng IS NULL OR (knox_box_lng >= -122.95 AND knox_box_lng <= -122.65)),
    CONSTRAINT chk_knox_pair CHECK ((knox_box_lat IS NULL) = (knox_box_lng IS NULL)),
    
    CONSTRAINT chk_staging_lat_bounds CHECK (staging_lat IS NULL OR (staging_lat >= 49.15 AND staging_lat <= 49.45)),
    CONSTRAINT chk_staging_lng_bounds CHECK (staging_lng IS NULL OR (staging_lng >= -122.95 AND staging_lng <= -122.65)),
    CONSTRAINT chk_staging_pair CHECK ((staging_lat IS NULL) = (staging_lng IS NULL)),
    
    CONSTRAINT chk_fdc_lat_bounds CHECK (fdc_lat IS NULL OR (fdc_lat >= 49.15 AND fdc_lat <= 49.45)),
    CONSTRAINT chk_fdc_lng_bounds CHECK (fdc_lng IS NULL OR (fdc_lng >= -122.95 AND fdc_lng <= -122.65)),
    CONSTRAINT chk_fdc_pair CHECK ((fdc_lat IS NULL) = (fdc_lng IS NULL))
);

-- Spatial GiST Indexes for Sub-Millisecond Lookups
CREATE INDEX IF NOT EXISTS idx_pao_front_geom ON public.parcel_access_overrides USING GIST (front_geom);
CREATE INDEX IF NOT EXISTS idx_pao_ingress_geom ON public.parcel_access_overrides USING GIST (ingress_geom);
CREATE INDEX IF NOT EXISTS idx_pao_knox_geom ON public.parcel_access_overrides USING GIST (knox_box_geom);
CREATE INDEX IF NOT EXISTS idx_pao_fdc_geom ON public.parcel_access_overrides USING GIST (fdc_geom);

-- B-Tree Indexes for Fast Relational Lookups
CREATE INDEX IF NOT EXISTS idx_pao_parcel_id ON public.parcel_access_overrides (parcel_id);
CREATE INDEX IF NOT EXISTS idx_pao_gis_id ON public.parcel_access_overrides (gis_id);
CREATE INDEX IF NOT EXISTS idx_pao_civic_address ON public.parcel_access_overrides (civic_address);
CREATE INDEX IF NOT EXISTS idx_pao_active_verified ON public.parcel_access_overrides (is_active, verification_status);

-- 2. Audit History Table
CREATE TABLE IF NOT EXISTS public.parcel_access_overrides_history (
    history_id BIGSERIAL PRIMARY KEY,
    override_id BIGINT NOT NULL,
    action_type VARCHAR(10) NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE'
    changed_by_badge VARCHAR(50),
    old_data JSONB,
    new_data JSONB,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Trigger Function: Maintain Updated At Timestamp
CREATE OR REPLACE FUNCTION public.fn_update_parcel_access_overrides_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_update_parcel_access_overrides_timestamp ON public.parcel_access_overrides;
CREATE TRIGGER trg_update_parcel_access_overrides_timestamp
BEFORE UPDATE ON public.parcel_access_overrides
FOR EACH ROW EXECUTE FUNCTION public.fn_update_parcel_access_overrides_timestamp();

-- 4. Trigger Function: Audit Trail Generation (Guaranteed non-null NEW.id on AFTER trigger)
CREATE OR REPLACE FUNCTION public.fn_audit_parcel_access_overrides()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        INSERT INTO public.parcel_access_overrides_history (
            override_id, action_type, changed_by_badge, old_data, new_data, changed_at
        ) VALUES (
            OLD.id, 'UPDATE', NEW.created_by_badge, to_jsonb(OLD), to_jsonb(NEW), CURRENT_TIMESTAMP
        );
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO public.parcel_access_overrides_history (
            override_id, action_type, changed_by_badge, old_data, new_data, changed_at
        ) VALUES (
            OLD.id, 'DELETE', OLD.created_by_badge, to_jsonb(OLD), NULL, CURRENT_TIMESTAMP
        );
        RETURN OLD;
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO public.parcel_access_overrides_history (
            override_id, action_type, changed_by_badge, old_data, new_data, changed_at
        ) VALUES (
            NEW.id, 'INSERT', NEW.created_by_badge, NULL, to_jsonb(NEW), CURRENT_TIMESTAMP
        );
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_parcel_access_overrides ON public.parcel_access_overrides;
CREATE TRIGGER trg_audit_parcel_access_overrides
AFTER INSERT OR UPDATE OR DELETE ON public.parcel_access_overrides
FOR EACH ROW EXECUTE FUNCTION public.fn_audit_parcel_access_overrides();
```

---

## 2.6 Production PostGIS PL/pgSQL Functions

> [!CAUTION]
> **Of the three functions below, only `fn_calculate_parcel_road_snap` is registered in the
> database — and it is called by nothing.** `fn_determine_arrival_side_and_heading` and
> `fn_resolve_incident_routing_destination` do not exist. Front points are computed by
> `backend/scripts/import_parcels.py`, not by any of this. Whether to wire the one registered
> function in or drop it is still open.


### Function 1: `fn_calculate_parcel_road_snap`
Computes the optimal road snapping point along a parcel's primary frontage using boundary edge decomposition and multi-criteria scoring.

```sql
CREATE OR REPLACE FUNCTION public.fn_calculate_parcel_road_snap(
    p_parcel_id BIGINT,
    p_target_street VARCHAR(255) DEFAULT NULL
)
RETURNS TABLE (
    snap_lat DOUBLE PRECISION,
    snap_lng DOUBLE PRECISION,
    snapped_road_id BIGINT,
    snapped_road_name VARCHAR(255),
    snap_distance_m DOUBLE PRECISION,
    frontage_edge_geom GEOMETRY(LineString, 4326),
    snap_point_geom GEOMETRY(Point, 4326)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_parcel_geom GEOMETRY(Geometry, 26910);
    v_target_street VARCHAR(255);
BEGIN
    -- 1. Fetch parcel geometry in metric UTM Zone 10N (EPSG:26910)
    SELECT ST_Transform(geom, 26910), COALESCE(p_target_street, street)
    INTO v_parcel_geom, v_target_street
    FROM public.parcels
    WHERE id = p_parcel_id;

    IF v_parcel_geom IS NULL THEN
        RETURN;
    END IF;

    -- If geometry is a Point (from Addresses.shp fallback), execute buffer search
    IF ST_GeometryType(v_parcel_geom) = 'ST_Point' THEN
        RETURN QUERY
        WITH candidate_roads AS (
            SELECT 
                r.id AS r_id,
                r.fullname AS r_fullname,
                (ST_Dump(ST_Transform(r.geom, 26910))).geom AS r_geom_utm
            FROM public.roads r
            WHERE ST_DWithin(ST_Transform(r.geom, 26910), v_parcel_geom, 100.0)
        ),
        ranked_points AS (
            SELECT 
                c.r_id,
                c.r_fullname,
                ST_ClosestPoint(c.r_geom_utm, v_parcel_geom) AS pt_utm,
                ST_Distance(c.r_geom_utm, v_parcel_geom) AS dist_m,
                CASE 
                    WHEN v_target_street IS NOT NULL AND UPPER(c.r_fullname) ILIKE '%' || UPPER(v_target_street) || '%' THEN 100.0
                    ELSE 0.0
                END AS name_bonus
            FROM candidate_roads c
            ORDER BY (dist_m - name_bonus) ASC
            LIMIT 1
        )
        SELECT 
            ST_Y(ST_Transform(rp.pt_utm, 4326)) AS snap_lat,
            ST_X(ST_Transform(rp.pt_utm, 4326)) AS snap_lng,
            rp.r_id AS snapped_road_id,
            rp.r_fullname AS snapped_road_name,
            rp.dist_m AS snap_distance_m,
            NULL::GEOMETRY(LineString, 4326) AS frontage_edge_geom,
            ST_Transform(rp.pt_utm, 4326) AS snap_point_geom
        FROM ranked_points rp;
        RETURN;
    END IF;

    -- 2. Decompose Polygon Boundary into Individual 2-Point Linear Edges (Exterior Ring Only)
    RETURN QUERY
    WITH boundary_edges AS (
        -- Extract exterior ring only, avoiding interior courtyard/atrium rings (CH-05)
        SELECT 
            (ST_DumpSegments(ST_ExteriorRing((ST_Dump(v_parcel_geom)).geom))).geom AS edge_geom_utm
    ),
    candidate_roads AS (
        -- Explode multipart road geometries to guarantee single LineStrings for linear referencing (CH-03)
        SELECT 
            r.id AS r_id,
            r.fullname AS r_fullname,
            r.road_class,
            (ST_Dump(ST_Transform(r.geom, 26910))).geom AS r_geom_utm
        FROM public.roads r
        WHERE ST_DWithin(ST_Transform(r.geom, 26910), v_parcel_geom, 60.0)
    ),
    edge_road_pairs AS (
        SELECT 
            e.edge_geom_utm,
            r.r_id,
            r.r_fullname,
            ST_Length(e.edge_geom_utm) AS edge_len_m,
            ST_Distance(e.edge_geom_utm, r.r_geom_utm) AS dist_m,
            -- Parallelism: angular difference guarded against coincident projection points (CH-01, F-02)
            CASE 
                WHEN ST_Equals(
                    ST_ClosestPoint(r.r_geom_utm, ST_StartPoint(e.edge_geom_utm)),
                    ST_ClosestPoint(r.r_geom_utm, ST_EndPoint(e.edge_geom_utm))
                ) THEN 90.0 -- Coincident projection yields zero parallelism
                ELSE ABS(
                    degrees(ST_Azimuth(ST_StartPoint(e.edge_geom_utm), ST_EndPoint(e.edge_geom_utm))) -
                    degrees(ST_Azimuth(
                        ST_ClosestPoint(r.r_geom_utm, ST_StartPoint(e.edge_geom_utm)),
                        ST_ClosestPoint(r.r_geom_utm, ST_EndPoint(e.edge_geom_utm))
                    ))
                )
            END AS angle_diff_deg,
            CASE 
                WHEN v_target_street IS NOT NULL AND UPPER(r.r_fullname) ILIKE '%' || UPPER(v_target_street) || '%' THEN 1.0
                ELSE 0.0
            END AS name_match_factor,
            CASE 
                WHEN r.road_class IN ('ART', 'HWY', 'COL') THEN 1.2
                WHEN r.road_class = 'LOC' THEN 1.0
                WHEN r.road_class = 'LANE' THEN 0.2
                ELSE 0.5
            END AS class_weight,
            r.r_geom_utm
        FROM boundary_edges e
        CROSS JOIN candidate_roads r
        WHERE ST_Distance(e.edge_geom_utm, r.r_geom_utm) < 50.0
          AND ST_Length(e.edge_geom_utm) > 0.5 -- Preserves cul-de-sac turnaround bulb chords (CH-06)
    ),
    scored_edges AS (
        SELECT 
            erp.*,
            -- Composite Frontage Objective Function Psi(E_i, R_j) with Multiplicative Name Prior (CH-07, F-02)
            (
                (0.60 * COALESCE(POWER(COS(radians(erp.angle_diff_deg)), 2), 0.0)) +
                (0.40 * LN(1.0 + LEAST(erp.edge_len_m, 30.0)))
            ) * erp.class_weight * EXP(-erp.dist_m / 25.0) * (1.0 + 2.0 * erp.name_match_factor) AS score,
            -- Orthogonal Projection via Linear Referencing on exploded single LineString (CH-03)
            ST_LineInterpolatePoint(
                erp.r_geom_utm,
                ST_LineLocatePoint(erp.r_geom_utm, ST_PointOnSurface(erp.edge_geom_utm))
            ) AS snap_pt_utm
        FROM edge_road_pairs erp
        ORDER BY score DESC NULLS LAST -- Explicit NULLS LAST guard (CH-01)
        LIMIT 1
    )
    SELECT 
        ST_Y(ST_Transform(se.snap_pt_utm, 4326)) AS snap_lat,
        ST_X(ST_Transform(se.snap_pt_utm, 4326)) AS snap_lng,
        se.r_id AS snapped_road_id,
        se.r_fullname AS snapped_road_name,
        se.dist_m AS snap_distance_m,
        ST_Transform(se.edge_geom_utm, 4326) AS frontage_edge_geom,
        ST_Transform(se.snap_pt_utm, 4326) AS snap_point_geom
    FROM scored_edges se;
END;
$$;
```

---

### Function 2: `fn_determine_arrival_side_and_heading`
Calculates approach azimuth, arrival bearing, and tactical arrival side (LEFT vs RIGHT vs AHEAD vs BEHIND) via 2D cross products with angular deadbands.

```sql
CREATE OR REPLACE FUNCTION public.fn_determine_arrival_side_and_heading(
    p_approach_lat DOUBLE PRECISION, -- Coordinates of vehicle ~50m prior to arrival
    p_approach_lng DOUBLE PRECISION,
    p_snap_lat DOUBLE PRECISION,     -- Snapped road endpoint
    p_snap_lng DOUBLE PRECISION,
    p_target_lat DOUBLE PRECISION,   -- Target building / parcel centroid
    p_target_lng DOUBLE PRECISION
)
RETURNS TABLE (
    arrival_heading_deg DOUBLE PRECISION,
    target_bearing_deg DOUBLE PRECISION,
    relative_angle_deg DOUBLE PRECISION,
    arrival_side VARCHAR(10),
    tactical_positioning_notes TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_pt_approach GEOMETRY(Point, 26910);
    v_pt_snap GEOMETRY(Point, 26910);
    v_pt_target GEOMETRY(Point, 26910);
    
    v_dx_road DOUBLE PRECISION;
    v_dy_road DOUBLE PRECISION;
    v_dx_target DOUBLE PRECISION;
    v_dy_target DOUBLE PRECISION;
    
    v_cross_product DOUBLE PRECISION;
    v_heading DOUBLE PRECISION;
    v_target_bearing DOUBLE PRECISION;
    v_rel_angle DOUBLE PRECISION;
    v_side VARCHAR(10);
    v_notes TEXT;
BEGIN
    -- Transform all points to metric UTM Zone 10N
    v_pt_approach := ST_Transform(ST_SetSRID(ST_MakePoint(p_approach_lng, p_approach_lat), 4326), 26910);
    v_pt_snap     := ST_Transform(ST_SetSRID(ST_MakePoint(p_snap_lng, p_snap_lat), 4326), 26910);
    v_pt_target   := ST_Transform(ST_SetSRID(ST_MakePoint(p_target_lng, p_target_lat), 4326), 26910);

    -- Vector components
    v_dx_road := ST_X(v_pt_snap) - ST_X(v_pt_approach);
    v_dy_road := ST_Y(v_pt_snap) - ST_Y(v_pt_approach);
    
    v_dx_target := ST_X(v_pt_target) - ST_X(v_pt_snap);
    v_dy_target := ST_Y(v_pt_target) - ST_Y(v_pt_snap);

    -- 2D Cross Product: Z = (dx_road * dy_target) - (dy_road * dx_target)
    v_cross_product := (v_dx_road * v_dy_target) - (v_dy_road * v_dx_target);

    -- Compute absolute compass azimuths guarded against null on coincident points (F-04)
    v_heading := COALESCE(degrees(ST_Azimuth(v_pt_approach, v_pt_snap)), 0.0);
    v_target_bearing := COALESCE(degrees(ST_Azimuth(v_pt_snap, v_pt_target)), 0.0);

    v_rel_angle := v_target_bearing - v_heading;
    IF v_rel_angle > 180.0 THEN v_rel_angle := v_rel_angle - 360.0; END IF;
    IF v_rel_angle < -180.0 THEN v_rel_angle := v_rel_angle + 360.0; END IF;

    -- Angular Deadband & Cross-Product Classification (CH-08)
    IF ABS(v_rel_angle) <= 15.0 THEN
        v_side := 'AHEAD';
        v_notes := 'Target directly AHEAD at terminus of roadway.';
    ELSIF ABS(v_rel_angle) >= 165.0 THEN
        v_side := 'BEHIND';
        v_notes := 'Target BEHIND vehicle heading (overshot/past target). Prepare to stop or reverse.';
    ELSIF v_cross_product < 0 THEN
        v_side := 'RIGHT';
        v_notes := 'Target on RIGHT. Position Engine curbside; driver pump panel protected from traffic envelope.';
    ELSE
        v_side := 'LEFT';
        v_notes := 'Target on LEFT. Position Engine offset; establish traffic block lane to protect pump operator.';
    END IF;

    RETURN QUERY SELECT 
        ROUND(v_heading::numeric, 1)::DOUBLE PRECISION,
        ROUND(v_target_bearing::numeric, 1)::DOUBLE PRECISION,
        ROUND(v_rel_angle::numeric, 1)::DOUBLE PRECISION,
        v_side,
        v_notes;
END;
$$;
```

---

### Function 3: `fn_resolve_incident_routing_destination`
Implements the full 5-Tier Fallback Hierarchy with spatial point-in-polygon resolution for coordinate-only dispatches and optimized GiST spatial index search.

```sql
CREATE OR REPLACE FUNCTION public.fn_resolve_incident_routing_destination(
    p_civic_address VARCHAR(255) DEFAULT NULL,
    p_gis_id VARCHAR(255) DEFAULT NULL,
    p_lat DOUBLE PRECISION DEFAULT NULL,
    p_lng DOUBLE PRECISION DEFAULT NULL
)
RETURNS TABLE (
    dest_lat DOUBLE PRECISION,
    dest_lng DOUBLE PRECISION,
    resolution_tier VARCHAR(30),
    confidence_score NUMERIC(5,2),
    snapped_road_name VARCHAR(255),
    gate_code VARCHAR(50),
    knox_box_location VARCHAR(255),
    is_degraded BOOLEAN,
    status_message TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_parcel_id BIGINT;
    v_gis_id VARCHAR(255);
    v_street VARCHAR(255);
    v_override RECORD;
    v_snap RECORD;
    v_centroid_geom GEOMETRY(Point, 4326);
    v_nearest_road RECORD;
BEGIN
    -- Step 0a: Resolve internal parcel ID via GIS ID or Civic Address
    SELECT id, gis_id, street
    INTO v_parcel_id, v_gis_id, v_street
    FROM public.parcels
    WHERE (p_gis_id IS NOT NULL AND gis_id = p_gis_id)
       OR (p_civic_address IS NOT NULL AND (address_normalized = LOWER(TRIM(p_civic_address)) OR address ILIKE TRIM(p_civic_address)))
    LIMIT 1;

    -- Step 0b: Point-in-Polygon spatial resolution for coordinate-only dispatches (CH-04, Reviewer 2)
    IF v_parcel_id IS NULL AND p_lat IS NOT NULL AND p_lng IS NOT NULL THEN
        SELECT id, gis_id, street
        INTO v_parcel_id, v_gis_id, v_street
        FROM public.parcels
        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(p_lng, p_lat), 4326))
        LIMIT 1;
    END IF;

    -- ========================================================================
    -- TIER 1: Check Database Override
    -- ========================================================================
    IF v_parcel_id IS NOT NULL OR p_gis_id IS NOT NULL THEN
        SELECT * INTO v_override
        FROM public.parcel_access_overrides
        WHERE (parcel_id = v_parcel_id OR gis_id = COALESCE(v_gis_id, p_gis_id))
          AND is_active = TRUE
          AND verification_status IN ('VERIFIED_OFFICER', 'VERIFIED_CHIEF')
        ORDER BY updated_at DESC
        LIMIT 1;

        IF v_override.id IS NOT NULL THEN
            RETURN QUERY SELECT 
                v_override.front_lat,
                v_override.front_lng,
                'TIER_1_OVERRIDE'::VARCHAR(30),
                100.00::NUMERIC(5,2),
                'VERIFIED_FRONTAGE'::VARCHAR(255),
                v_override.gate_code,
                CASE WHEN v_override.knox_box_lat IS NOT NULL 
                     THEN ('Lat: ' || v_override.knox_box_lat || ', Lng: ' || v_override.knox_box_lng)::VARCHAR(255)
                     ELSE 'See Pre-Plan'::VARCHAR(255) END,
                FALSE,
                ('Tier 1 Field-Verified Override Applied by Officer ' || v_override.created_by_badge)::TEXT;
            RETURN;
        END IF;
    END IF;

    -- ========================================================================
    -- TIER 2 & TIER 4: Boundary Edge Selection & Address Snapping
    -- ========================================================================
    IF v_parcel_id IS NOT NULL THEN
        SELECT * INTO v_snap
        FROM public.fn_calculate_parcel_road_snap(v_parcel_id, v_street);

        IF v_snap.snap_lat IS NOT NULL THEN
            RETURN QUERY SELECT 
                v_snap.snap_lat,
                v_snap.snap_lng,
                'TIER_4_EDGE_MATCH'::VARCHAR(30),
                85.00::NUMERIC(5,2),
                v_snap.snapped_road_name,
                NULL::VARCHAR(50),
                NULL::VARCHAR(255),
                FALSE,
                ('Tier 4 Boundary Edge Snapped to ' || v_snap.snapped_road_name || ' (' || ROUND(v_snap.snap_distance_m::numeric, 1) || 'm offset)')::TEXT;
            RETURN;
        END IF;
    END IF;

    -- ========================================================================
    -- TIER 5: Centroid Snapping with Strict Safety Threshold (45 meters) & Spatial Index k-NN
    -- ========================================================================
    IF p_lat IS NOT NULL AND p_lng IS NOT NULL THEN
        v_centroid_geom := ST_SetSRID(ST_MakePoint(p_lng, p_lat), 4326);
    ELSIF v_parcel_id IS NOT NULL THEN
        SELECT geom INTO v_centroid_geom FROM public.parcels WHERE id = v_parcel_id;
    END IF;

    IF v_centroid_geom IS NOT NULL THEN
        -- Optimized GiST spatial index search using native EPSG:4326 index and metric calculation (CH-04)
        SELECT 
            r.id,
            r.fullname,
            ST_Y(ST_Transform(ST_ClosestPoint(ST_Transform(r.geom, 26910), ST_Transform(v_centroid_geom, 26910)), 4326)) AS snap_lat,
            ST_X(ST_Transform(ST_ClosestPoint(ST_Transform(r.geom, 26910), ST_Transform(v_centroid_geom, 26910)), 4326)) AS snap_lng,
            ST_Distance(ST_Transform(r.geom, 26910), ST_Transform(v_centroid_geom, 26910)) AS dist_m
        INTO v_nearest_road
        FROM public.roads r
        WHERE ST_DWithin(r.geom, v_centroid_geom, 0.005) -- ~500m bounding window utilizing native GiST spatial index
        ORDER BY r.geom <-> v_centroid_geom
        LIMIT 1;

        IF v_nearest_road.id IS NOT NULL THEN
            IF v_nearest_road.dist_m <= 45.0 THEN
                RETURN QUERY SELECT 
                    v_nearest_road.snap_lat,
                    v_nearest_road.snap_lng,
                    'TIER_5_CENTROID'::VARCHAR(30),
                    65.00::NUMERIC(5,2),
                    v_nearest_road.fullname,
                    NULL::VARCHAR(50),
                    NULL::VARCHAR(255),
                    FALSE,
                    ('Tier 5 Centroid Snapped to ' || v_nearest_road.fullname || ' (' || ROUND(v_nearest_road.dist_m::numeric, 1) || 'm distance)')::TEXT;
                RETURN;
            ELSE
                -- Distance exceeds 45m safety threshold: Degraded State Flagged
                RETURN QUERY SELECT 
                    v_nearest_road.snap_lat,
                    v_nearest_road.snap_lng,
                    'TIER_5_DEGRADED'::VARCHAR(30),
                    40.00::NUMERIC(5,2),
                    v_nearest_road.fullname,
                    NULL::VARCHAR(50),
                    NULL::VARCHAR(255),
                    TRUE,
                    ('WARNING: Road offset is ' || ROUND(v_nearest_road.dist_m::numeric, 1) || 'm (>45m threshold). Verify access path manually.')::TEXT;
                RETURN;
            END IF;
        END IF;
    END IF;

    -- Complete Failure Fallback
    RETURN QUERY SELECT 
        p_lat, p_lng,
        'FAILED_NO_ROAD'::VARCHAR(30),
        0.00::NUMERIC(5,2),
        'UNKNOWN'::VARCHAR(255),
        NULL::VARCHAR(50),
        NULL::VARCHAR(255),
        TRUE,
        'ERROR: Unable to snap coordinate to any municipal road centerline.'::TEXT;
END;
$$;
```

---

## 2.7 5-Tier Fallback Resolution Hierarchy

> [!CAUTION]
> **What is built is three tiers, not five: `entrance → front → centroid`**
> (`services/gis/src/gis_service/address_resolver.py`). Tier 1's `parcel_access_overrides`
> table does not exist; Tier 2's municipal curb-cut layer `access_points.shp` **is not published
> to us and is not held**, making that tier unreachable. The confidence figures (100% / 95% /
> 85% / 75% / 50%) and latency figures are invented — confidence in this system is **not
> calibrated**, and score 100 was wrong on 8% of reviewed calls while the 81–89 band was
> flawless (punch-list #32).


To guarantee deterministic, sub-millisecond route endpoint calculation under all operational conditions, the routing pipeline adheres to a strict 5-Tier Fallback Hierarchy:

### Table 2.1: 5-Tier Fallback Resolution Hierarchy

| Tier | Resolution Tier Name | Primary Data Source | Snapping Logic | Confidence | Latency | Operational HUD Indicator |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- |
| **Tier 1** | **Verified DB Incident Front Override** | `parcel_access_overrides` table | Exact `front_lat` / `front_lng` or `ingress_lat` / `ingress_lng` field-verified by CFR company officers. | **100%** | $<1.0\text{ ms}$ | 🟢 `[VERIFIED FRONTAGE]` |
| **Tier 2** | **Site/Driveway Ingress Point Layer** | Municipal Curb-Cut & Ingress Layer (`access_points.shp`) | Point-in-polygon lookup matching designated property driveway apron cut into street curb. | **95%** | $<2.5\text{ ms}$ | 🟢 `[CURB INGRESS]` |
| **Tier 3** | **Address Point Orthogonal Projection** | `public.parcels` (`geom` point from `Addresses.shp`) | Orthogonal linear projection of civic address point onto matching named street centerline in `roads`. | **85%** | $<3.0\text{ ms}$ | 🔵 `[PROJECTED CIVIC]` |
| **Tier 4** | **Parcel Boundary Geometric Nearest Edge** | Cadastral Polygon Boundary (`Parcels.shp`) | Decompose polygon exterior boundary into linear segments; execute multi-criteria frontage scoring $\Psi(E_i, R_j)$. | **75%** | $<5.0\text{ ms}$ | 🔵 `[CADASTRE FRONTAGE]` |
| **Tier 5** | **Parcel Centroid Projection with Safety Filter** | `ST_PointOnSurface(geom)` with $D_{\text{thresh}} = 45\text{m}$ | Nearest road centerline projection with strict distance check. If $>45\text{m}$ or road name mismatch, flag degraded state. | **50%** | $<2.0\text{ ms}$ | 🟠 `[ESTIMATED CENTROID — VERIFY ACCESS]` |

---

---

*Sections 3 and 4 (public-safety standards research, topographic physics, implementation
blueprint) were removed 2026-08-30 — see §0a. Section 1 (routing engine evaluation) was
removed with them; the Valhalla migration it recommended was reviewed and paused, and the
routing engine has since been reset to a basic level for a future rebuild.*
