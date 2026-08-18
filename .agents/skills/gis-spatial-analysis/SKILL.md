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

