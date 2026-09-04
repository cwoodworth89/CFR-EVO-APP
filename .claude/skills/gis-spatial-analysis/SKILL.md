---
name: gis-spatial-analysis
description: Procedures and tools for managing ESRI shapefiles, performing spatial queries, calculating parcel boundary rings, querying NFPA 291 fire hydrants, and transforming coordinate reference systems (CRS) in CFR EVO.
---

# GIS Spatial Analysis & Data Engineering Runbook

This skill provides comprehensive instructions for working with geospatial datasets, spatial indexing, coordinate transformations, parcel boundaries, and fire hydrant flow classifications in **CFR EVO**.

---

## 1. Primary GIS Datasets (`backend/data/shapes/`)

```
backend/data/shapes/
├── Property_Information/
│   ├── Addresses.shp             # Primary street addresses & house numbers (EPSG:26910 / EPSG:4326)
│   └── Parcels.shp               # Cadastral parcel polygons & boundary rings
├── Emergency_Response_Zones/
│   └── Emergency_Response_Zones.shp # 1..134 spatial map grid boundaries
└── Infrastructure/
    └── Fire_Hydrants.shp         # NFPA 291 flow rate, pressure, and static head attributes
```

---

## 2. Coordinate Reference Systems (CRS) & Transformations

All internal GIS computations and shapefile queries must handle coordinate projections cleanly:
* **Native Storage**: Often stored in **EPSG:26910** (NAD83 / UTM Zone 10N) for metric area/distance calculations.
* **Frontend & MapLibre/Leaflet**: Requires **EPSG:4326** (WGS84 lat/lng in degrees).

### Reprojection Pattern (Python / GeoPandas):
```python
import geopandas as gpd

def load_and_reproject(shapefile_path: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(shapefile_path)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    return gdf
```

---

## 3. Option 2 Parcel Boundary Ring Extraction

When `local_geocode()` resolves an address, it extracts the multi-point polygon rings conforming to the Option 2 database contract:

```python
def extract_parcel_rings(geometry) -> list[list[list[float]]]:
    """Extracts GeoJSON-compatible coordinate rings [[ [lng, lat], [lng, lat], ... ]]"""
    rings = []
    if geometry.geom_type == 'Polygon':
        # [lng, lat] format for MapLibre/GeoJSON standard
        rings.append([[round(coord[0], 6), round(coord[1], 6)] for coord in geometry.exterior.coords])
    elif geometry.geom_type == 'MultiPolygon':
        for poly in geometry.geoms:
            rings.append([[round(coord[0], 6), round(coord[1], 6)] for coord in poly.exterior.coords])
    return rings
```

---

## 4. Point-in-Polygon Emergency Zone Grid Lookup

Given geocoded coordinates $(lat, lng)$, the validator determines the 1..134 emergency zone grid:

```python
from shapely.geometry import Point

def get_map_grid_for_coordinates(validator, lat: float, lng: float) -> str | None:
    """Returns matching 1..134 map grid number for given WGS84 point."""
    if lat is None or lng is None or validator.zones_gdf is None:
        return None
    point = Point(lng, lat)
    matches = validator.zones_gdf[validator.zones_gdf.geometry.contains(point)]
    if not matches.empty:
        col = validator.zone_map_name_col or 'MAP_NAME'
        return str(matches.iloc[0][col]).strip()
    return None
```

---

## 5. NFPA 291 Fire Hydrant Classification & Queries

Hydrants within a 500-meter radius of the incident are retrieved and color-coded according to NFPA 291 rated capacity:

| NFPA Class | Rated Flow (GPM at 20 PSI) | Barrel / Bonnet Color | Frontend Hex Code |
| :--- | :--- | :--- | :--- |
| **Class AA** | $\ge 1500$ GPM | 🔵 Light Blue | `#00a8ff` |
| **Class A** | $1000 - 1499$ GPM | 🟢 Green | `#4cd137` |
| **Class B** | $500 - 999$ GPM | 🟠 Orange | `#e1b12c` |
| **Class C** | $< 500$ GPM | 🔴 Red | `#e84118` |

### Nearest Hydrant Query:
```powershell
.\.venv\Scripts\python.exe -c "from gis_service import CoquitlamDataValidator; from cfr_dispatch.worker import get_shared_validator; v = get_shared_validator(); hydrants = v.find_nearest_hydrants(49.2781, -122.8123, max_results=3); print(hydrants)"
```

---

## 6. LiDAR 3D Spatial Intelligence & Topography Engine

> [!CAUTION]
> **None of §6 is implemented, and the data it needs is not held.** Verified 2026-08-30:
> there is **no elevation, DEM, HGT or point-cloud data anywhere in the system**, `public.roads`
> has no grade, incline or elevation column, and no point-cloud classification, canopy model or
> floodplain analysis exists in the codebase. `FLAG_OVERHEAD_OBSTRUCTION` appears nowhere.
>
> Two statements below are not merely unbuilt but **false as written**: §6.2 says *"the routing
> engine biases against routes with >15% downhill gradients"* — OSRM runs the **stock `driving`
> profile** with no elevation input and no custom Lua profile exists in the repository, so no
> such bias is applied to anything.
>
> Read §6 as a wish list. Do not cite any figure in it as provenance (CLAUDE.md §6.3), and do
> not build on it without first obtaining the elevation data it assumes. The same content, with
> the same problem, appears in `docs/emergency_routing_gis_parcels_standard.md` §3.5, which is
> annotated there for the same reason.

CFR EVO integrates point-cloud LiDAR data, Digital Surface Models (DSM), and Digital Elevation Models (DEM/DTM) to provide tactical 3D spatial awareness for apparatus dispatch, tactical positioning, and route computation.

```
backend/data/lidar/
├── dtm/                          # Bare-earth Digital Terrain Model (1m raster, EPSG:26910)
├── dsm/                          # Digital Surface Model including canopy & structures (1m raster)
└── nDSM/                         # Normalized DSM (nDSM = DSM - DTM) representing height above ground
```

### 6.1 Building Height Extraction & Aerial Apparatus Reach Validation
* **Formula**: $\text{Structure Height } (H_{\text{bldg}}) = \text{DSM}_{\text{roof}} - \text{DTM}_{\text{ground}}$
* **Aerial Apparatus Dispatch Validation**:
  * **Ladder 1 & Ladder 3** (105-foot / 32m aerial reach, maximum operational scrub height: ~28m / 92ft considering setback angle and outrigger deployment).
  * Structures with $H_{\text{bldg}} \ge 12.0\text{m}$ ($\sim 4$ storeys, e.g., high-density developments in City Centre, Burquitlam, and Lougheed Corridor) automatically trigger mandatory Ladder company dispatch assignments and outrigger placement clearance alerts in the CAD payload.
* **Setback & Scrub Envelope Calculation**:
  ```python
  def validate_aerial_reach(building_height_m: float, setback_distance_m: float, max_reach_m: float = 32.0) -> dict:
      """Calculates aerial reach vector and operating angle for Ladder 1/3."""
      diagonal_reach = (building_height_m**2 + setback_distance_m**2) ** 0.5
      reach_ratio = diagonal_reach / max_reach_m
      return {
          "required_reach_m": round(diagonal_reach, 2),
          "reach_ratio": round(reach_ratio, 2),
          "ladder_feasible": reach_ratio <= 0.85,  # 85% safety threshold under operational NFPA envelope
          "setback_m": setback_distance_m,
          "height_m": building_height_m
      }
  ```

### 6.2 Topographic Slope Calculations & Apparatus Route Biasing
* **Westwood Plateau & Burke Mountain Grade Hazards**:
  * Topographic slopes across Burke Mountain (Coast Meridian Rd, David Ave, Harper Rd) and Westwood Plateau (Plateau Blvd, Parkway Blvd) feature grades ranging from **15% to 25%** ($\sim 8.5^\circ - 14.0^\circ$).
  * Heavy apparatus (Tenders, 40,000+ lb Engine 1/2/3/4, Aerial Ladders) face severe brake thermal fade, transmission retarder limits, and uphill acceleration penalties on sustained $\ge 12\%$ grades.
* **OSRM / Emergency Route Grade Penalties**:
  * Slope $(\%) = \frac{\Delta \text{Elevation}}{\text{Run}} \times 100$
  * The routing engine biases against routes with $>15\%$ downhill gradients for heavy units, favoring gentler arterial switchbacks unless primary access is physically impossible.

### 6.3 Overhead Wire & Tree Canopy Clearance in Residential Cul-de-Sacs
* **Vertical Clearance Envelope**:
  * Full NFPA vertical clearance requires $\ge 4.15\text{m}$ (13.6 ft) for front-line Engines and Ladders.
  * Point cloud classification filters return returns between $3.5\text{m}$ and $6.0\text{m}$ within the street right-of-way (ROW) buffer ($8\text{m}$ corridor).
* **Cul-de-Sac Chokepoint Detection**:
  * In heavily wooded cul-de-sacs (e.g., Chineside, Harbour Chines, Ranch Park, Westwood Plateau), mature Western Redcedar and Douglas Fir branch overgrowth combined with low-hanging telecommunications/power service drops are flagged as apparatus clearance warnings (`FLAG_OVERHEAD_OBSTRUCTION`).

### 6.4 Wildland-Urban Interface (WUI) Fuel Canopy Density Modeling
* **Northern Interface Boundary**:
  * The northern municipal boundary adjoins Pinecone Burke Provincial Park, Eagle Mountain, and Coquitlam Watershed forests.
* **Canopy Fuel Bulk Density (CBD) & Crown Base Height (CBH)**:
  * LiDAR returns above $2.0\text{m}$ calculate Canopy Cover Percentage ($\text{CC}\%$) and Crown Volume within $30\text{m}$ and $100\text{m}$ defensible space buffers around residential property parcel lines.
  * Structures with $\text{CC} > 60\%$ within $30\text{m}$ of natural forest interface are assigned elevated FireSmart wildfire hazard ratings on CAD dispatch.

### 6.5 Floodplain Ground Bare-Earth Elevation Mapping
* **Hydrological Inundation Zones**:
  * Lowland areas along the Fraser River (Maillardville / Colony Farm / Fraser Mills), Coquitlam River corridor, and Pitt River floodplain lie at bare-earth elevations below $4.0\text{m}$ Geodetic Datum (CGVD28/CGVD2013).
* **Freshet & Extreme High Tide Routing**:
  * DTM bare-earth raster queries determine parcel immersion risk during spring freshet and king tides.
  * Access roads with bare-earth elevations $\le 2.2\text{m}$ GVD are dynamically flagged when hydrological freshet warnings are broadcast.

---

## 7. Centralized MBTiles Architecture & Slippy Map Standard (`cfr_tiles` Port 8081)

CFR EVO eliminates external map CDN dependencies (Mapbox, Carto, Google Maps, ArcGIS Online) by serving all raster and vector basemaps directly from containerized SQLite MBTiles archives on port `8081` (`ghcr.io/consbio/mbtileserver:latest`).

```
backend/data/tiles/
├── ortho.mbtiles             # City of Coquitlam 2025 7.5cm orthophotos (z12-20, OGL)
├── street.mbtiles            # Full street & reference basemap with road labels
└── street_nolabels.mbtiles   # Clean tactical basemap for high-contrast HUD overlays
```

### 7.1 OpenStreetMap Slippy Map Specification Compliance
* **Projection**: Standard Web Mercator (`EPSG:3857` / Spherical Mercator).
* **Coordinate Origin**: Top-left origin convention ($x=0, y=0$ at Northwest quadrant), matching the OpenStreetMap Slippy Map standard (`{z}/{x}/{y}`).
* **TMS Inversion Elimination**: MBTiles archives are generated and served directly in standard Slippy format, removing runtime TMS $y$-coordinate flipping ($y_{\text{TMS}} = 2^z - 1 - y_{\text{XYZ}}$).
* **Base Layer Endpoints**:
  - `http://${window.location.hostname}:8081/services/ortho/tiles/{z}/{x}/{y}.jpg`
  - `http://${window.location.hostname}:8081/services/street/tiles/{z}/{x}/{y}.png`
  - `http://${window.location.hostname}:8081/services/street_nolabels/tiles/{z}/{x}/{y}.png`

### 7.2 City of Coquitlam 7.5cm Aerial Orthophoto Pyramid (`ortho.mbtiles`)

> [!IMPORTANT]
> **There is one imagery layer now.** `ortho.mbtiles` holds City of Coquitlam 7.5cm
> orthophotography under the Open Government Licence, crawled from the City's own
> `Imagery_2025` cache. The Esri `satellite.mbtiles` layer was **retired 2026-08-31** — it
> was never City data and its terms were never read (#47). A verifier script
> (`backend/scripts/verify_ortho_provenance.py`) was written and deleted the same day
> (9017e6a) because it could not do its job; there is no script for this.

<!-- audit-ok: backend/scripts/verify_ortho_provenance.py -- records that the verifier was deleted 2026-08-31 -->

* **Resolution**: 7.5 cm ground sampling distance (measured: `.sdw` pixel size 0.075 m).
* **Extent**: −122.8995, 49.2165 → −122.6110, 49.3628 (covers `public.city_boundary`).
  **Blank outside that footprint is correct** — there is no fallback beneath it by design
  (CLAUDE.md §6.1), so the edge of municipal imagery is visible rather than disguised.
* **Native zoom**: z20 — where the City's cache ends (z21 returns 404) and the honest limit
  for a 7.5 cm source, since z20 is 9.74 cm/px here and z21 would be 4.87 cm/px. Every zoom
  is crawled from the City directly; no level is derived from another.
* **Endpoint**: `http://${window.location.hostname}:8081/services/ortho/tiles/{z}/{x}/{y}.jpg`
* **Crawl**: `gis-pipeline-sync` skill §4.1 —
  `python backend/scripts/compile_mbtiles.py --layer ortho`. No GDAL, no MrSID.
* **$0 Subscription-Free Guarantee**: Stored 100% locally on NVMe SSD storage with `fallbackUrl: null`, ensuring 100% disaster resilience with zero recurring API or tile-serving costs.


