---
name: emergency-routing-engine
description: Architectural specifications, apparatus-aware pathfinding, station origin lookups, and dual-mode (online Google / offline OSRM) emergency vehicle routing in CFR EVO.
---

# Emergency Apparatus Routing Engine Runbook

This skill outlines the pathfinding algorithms, station origin mapping, vehicle clearance profiles, and dual-mode (offline OSRM / online Google Directions) routing workflows for **CFR EVO**.

---

## 1. Station Origin Directory & Apparatus Mapping

When a dispatch specifies responding units, the routing engine resolves the departure fire hall:

```mermaid
flowchart TD
    A[Dispatch Responding Units: E1, L1, Q5] --> B{Resolve Origin Hall}
    B -->|E1, L1, R1, C10, C1| H1[Hall 1 - Town Centre: 1300 Pinetree Way]
    B -->|E2, L2, R2| H2[Hall 2 - Mariner: 775 Mariner Way]
    B -->|E3, Q5, H3, HT3, S3| H3[Hall 3 - Austin Heights: 438 Nelson St]
    B -->|E4, T4, LAV4| H4[Hall 4 - Burke Mountain: 3501 David Ave]
    
    H1 --> C[Apparatus Pathfinding Engine]
    H2 --> C
    H3 --> C
    H4 --> C
    
    C --> D[Incident Target Coordinates]
```

### Station Coordinates Master Table:
| Station | Address | Latitude | Longitude | Primary Units |
| :--- | :--- | :--- | :--- | :--- |
| **Hall 1 (Town Centre)** | 1300 Pinetree Way | `49.29109654571679` | `-122.79072561861948` | `E1`, `L1`, `R1`, `C1`, `C10`, `S1`, `M1`, `SQ1` |
| **Hall 2 (Mariner)** | 775 Mariner Way | `49.2622197420057` | `-122.81747986099539` | `E2`, `L2`, `R2`, `SQ2`, `T2`, `WT2` |
| **Hall 3 (Austin Heights)** | 438 Nelson Street | `49.24803974681661` | `-122.86546062387211` | `E3`, `Q5`, `H3`, `HT3`, `S3`, `SQ3` |
| **Hall 4 (Burke Mountain)** | 3501 David Ave | `49.29510006403205` | `-122.74247651791484` | `E4`, `T4`, `WT4`, `LAV4`, `SQ4` |

> Coordinates are verified front-apron driveway GPS points and are the single source of
> truth for routing origins. They mirror `FIRE_HALLS` in
> [`routing_engine.py`](../../../services/gis/src/gis_service/routing_engine.py) and
> `STATIONS` in [`MapConstants.js`](../../../frontend/src/components/MapConstants.js);
> update all three together.
>
> Departure is always the hall apron regardless of incident bearing. OSRM decides the
> direction of travel from the real road network — do not add destination-conditional
> departure coordinates.

---

## 2. Dual-Mode Routing Architecture

```mermaid
flowchart LR
    Target[Target Coordinates lat, lng] --> RouteSelector{WAN Internet Active?}
    RouteSelector -->|Online| GoogleDir[Google Maps Directions API]
    RouteSelector -->|Offline / Local| LocalOSRM[Local OSRM Container :5000]
    
    GoogleDir --> Avoidance[Apply Active Road Closure Penalties]
    LocalOSRM --> Avoidance
    
    Avoidance --> Output[GeoJSON Route Polyline + ETA + Turn Cue Cards]
```

### A. Online: Google Maps Directions API

> [!CAUTION]
> **Not present in the system, and contrary to the architecture.** Verified 2026-08-30:
> `departure_time`, `traffic_model` and the Directions endpoint appear nowhere in the codebase.
> CLAUDE.md §1 requires turn-by-turn routing to work with **no WAN connectivity and no
> per-request API fees**, so an online routing mode is not a fallback this system is allowed to
> depend on.
>
> **All routing goes through §B, the local OSRM container**, which runs the stock `driving`
> profile (punch-list #1 — the profile has never been tuned). Leave this subsection only as a
> record of a path that was considered and not taken.
* **Endpoint**: `https://maps.googleapis.com/maps/api/directions/json`
* **Parameters**:
  - `origin`: Hall apron coordinates (e.g. Hall 1 `49.29109654571679,-122.79072561861948`)
  - `destination`: Target incident coordinates
  - `departure_time`: `now`
  - `traffic_model`: `pessimistic` / `best_guess`
* **Output**: Detailed step-by-step instructions, polyline decoded into GeoJSON coordinates, distance in kilometers, duration in traffic.

### B. Offline: Local Containerized OSRM Engine
* **Endpoint**: `http://localhost:5000/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}?overview=full&geometries=geojson&steps=true`
* **Performance**: Sub-10ms response time with zero internet dependency.

---

## 3. Apparatus Physical Profiles & Road Restrictions

Different vehicle classes require specific path weighting:

| Apparatus Class | Units | Weight / Size | Routing Constraints |
| :--- | :--- | :--- | :--- |
| **Heavy Aerial / Quint** | `L1`, `L2`, `Q5` (Quint 5) | 35–38 Tons, 12'8" Height | • Avoids residential laneways and tight traffic circles<br>• Avoids weight-restricted bridges<br>• Prefers multi-lane arterial roads |
| **Pumper / Engine** | `E1`, `E2`, `E3`, `E4` | 18 Tons, 10'2" Height | • Standard commercial vehicle clearance<br>• Prefers secondary arterials over local alleys |
| **Command / Rescue** | `R1`, `R2`, `C10`, `C1`, `C9` | 3–12 Tons (SUV/Heavy Rescue) | • Standard emergency vehicle clearance<br>• Quickest possible path |

---

## 4. Response Mode & ETAs

> [!IMPORTANT]
> **ETAs come from OSRM. No local physics model is applied.**
>
> `distance_km` and `eta_minutes` are OSRM's own `distance` and `duration`, computed
> from per-segment speeds and real turn costs on the graph. The engine does not
> recompute travel time, estimate turn counts, or apply speed/road-factor multipliers.
>
> If OSRM is unreachable the result is `status: "degraded"` with `eta_minutes: None`
> and a great-circle placeholder distance. An unknown ETA is reported as unknown
> (`-- min`), never estimated (CLAUDE.md §6.1).
>
> `response_type` currently selects only the display label
> (`Emergency (Code 3)` / `Routine (Code 1)`); it does not alter the ETA.

Apparatus-class and response-mode adjustment is planned as the **CFR customized route
configuration** feature, layering on top of the OSRM baseline. Seed values live in
`APPARATUS_TIERS` (both engines), explicitly marked as not applied and as requiring
cited provenance before use (CLAUDE.md §6.3, §6.4).

Historical note: a previous implementation estimated ETAs from `distance / avg_speed`
plus an assumed `1.2 turns per km`, along with an EMTRAC rush-hour model and a blanket
"downhill" speed cap. None carried a cited source and all disagreed with the router's
own answer; they were removed in commit `c332b81`.

---

## 5. Road Closure & Obstruction Avoidance

When active closures exist (from `road_closures` table):
1. Closed road segments are converted into exclusion coordinate polygons or forbidden bounding boxes.
2. In Google Directions, waypoints are injected to steer around the obstruction.
3. In local OSRM, road segments are excluded or penalized in the speed profile matrix.

---

## 6. Tactical EVO Routing Biases & Corridor Weighting

When crafting prompt instructions or configuring custom routing rules, use standard **Tactical Emergency Vehicle Operator (EVO)** weighting principles:

### A. Core Tactical Principles:
1. **EmTrac / Opticom Preemption Corridors**:
   - Always prefer multi-lane arterial corridors equipped with EmTrac green-light preemption (e.g. `Pinetree Way`, `Lougheed Hwy`) over shorter residential cut-throughs.
2. **Barrier-Free Lane maneuverability (No Median Islands)**:
   - **Mariner Way Corridor (Station 1 Departure)**: When responding toward Mariner Way / Ranch Park, **always take Guildford Way $\rightarrow$ Johnson St $\rightarrow$ Mariner Way**.
   - *Reason*: Guildford/Johnson has **no center-line median islands or physical concrete barriers**, allowing heavy apparatus to cross center-lines and maneuver around stopped traffic cleanly. (Never take Pinetree $\rightarrow$ Right on Lougheed $\rightarrow$ Left on Mariner, which has dangerous traffic barriers and awkward turns).
3. **Town Centre / Gordon Ave Corridor (Station 1 Departure)**:
   - When responding to the Gordon Ave / Coquitlam Centre sector: **Pinetree Way South $\rightarrow$ Left onto Lougheed Hwy $\rightarrow$ Right onto Christmas Way $\rightarrow$ Right onto Gordon Ave**.
   - *Reason*: Leverages Pinetree's synchronized rolling-green EmTrac wave down to Lougheed.

### B. Implementation via Intermediate Waypoints:
To force an explicit tactical corridor for a target neighborhood:
```json
{
  "hall_1_mariner_corridor": {
    "origin": "1300 Pinetree Way (Hall 1)",
    "target_sector": "Mariner Way / Ranch Park",
    "waypoints": ["Pinetree Way & Guildford Way", "Guildford Way & Johnson St", "Johnson St & Mariner Way"],
    "reason": "Barrier-free lanes; avoids Lougheed/Mariner traffic islands"
  },
  "hall_1_gordon_corridor": {
    "origin": "1300 Pinetree Way (Hall 1)",
    "target_sector": "Gordon Ave / Town Centre",
    "waypoints": ["Pinetree Way & Lougheed Hwy", "Lougheed Hwy & Christmas Way"],
    "reason": "Pinetree rolling-green EmTrac wave; natural right-turn approach"
  }
}
```

---

## 7. Driver Station HUD & Mobile QR Integration

The route output generates three synchronized formats:
1. **Interactive Leaflet/MapLibre Polyline**: Bold glowing emerald line (`#00e676`) with directional arrows.
2. **Turn-by-Turn Cue Cards**: High-contrast, large-format instructions on the bay kiosk display (e.g., `➔ RIGHT onto David Ave in 400m`).
3. **MDT / Mobile Tablet QR Code**: Generates a dynamic QR code on the kiosk screen. Drivers scanning with a rugged tablet or phone instantly open the live route in native Google Maps or Apple Maps.

---

## 8. Iterative Call-Review Calibration Protocol

The emergency routing engine is designed to be tuned and calibrated continuously based on call reviews and firefighter driver feedback:

1. **Review Loop**: As dispatches are reviewed in the UI or audited by analysts, flag routes that take suboptimal residential shortcuts, steep hill climbs, or awkward multi-point apparatus turns.
2. **Profile Calibration**: Adjust OSRM Lua emergency profiles, arterial road speed weights, turn-penalty matrices, and tactical corridor waypoints based on empirical driver behavior.
3. **Regression Testing**: Re-run historical dispatch routing benchmarks after profile adjustments to verify that fixes in one response district do not cause regressions in others.

---

## 9. LiDAR-Based Topographic Slope & Apparatus Hill-Grade Routing Penalties (Future Roadmap)

Coquitlam features extreme topography across Westwood Plateau, Burke Mountain, Chineside, and Austin Heights with roadway grades exceeding $15\% - 25\%$. Future iterations of the routing engine will leverage municipal LiDAR elevation models (DEM) to dynamically calculate slope penalties:

### A. Mathematical Incline/Decline Calculation
For each street edge $(u, v)$ in the routing graph:
$$\text{Grade } (\%) = \left( \frac{z_v - z_u}{\text{Distance}_{u,v}} \right) \times 100$$

### B. Heavy Apparatus Slope Penalty Matrix:
| Road Grade $(\%)$ | Direction | OSRM Speed Adjustment | Operational EVO Rationale |
| :--- | :--- | :---: | :--- |
| **$0\% - 6\%$** | Flat / Mild | `1.0x` (Unrestricted) | Normal Code 3 emergency response speed profile |
| **$7\% - 12\%$** | Downhill | `0.80x` (-20% speed) | Early engine braking; transmission retarder engagement |
| **$7\% - 12\%$** | Uphill | `0.75x` (-25% speed) | Torque-limited heavy apparatus climb rate |
| **$13\% - 18\%$** | Downhill | `0.55x` (-45% speed) | **Severe Brake Fade Prevention**: Caps 50,000 lb engines at $\le 35\text{ km/h}$ |
| **$13\% - 18\%$** | Uphill | `0.50x` (-50% speed) | Low-gear torque crawl (realistic turnout ETA calculation) |
| **$> 18\%$** | Any | `0.30x` (+ Severe Route Weight Penalty) | **Avoided by Pathfinding**: Disincentivizes steep residential chutes unless target address is directly on that segment |

### C. Low-Gradient Arterial Biasing
The OSRM routing profile will actively favor engineered switchback arterials (e.g. *Johnson St*, *Pinetree Way*, *David Ave*) over sheer vertical residential hillside climbs, protecting vehicle brakes and powertrain longevity.
