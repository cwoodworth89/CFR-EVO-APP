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

## 6. MBTiles & the Slippy Map Standard (`cfr_tiles`, port 8081)

Every basemap and overlay is served offline from SQLite MBTiles archives by `cfr_tiles`
(`ghcr.io/consbio/mbtileserver`); no layer depends on an outside map CDN. What each archive
holds, how it is built and how to probe it: the **`mbtiles-tile-server`** skill.

```
backend/data/tiles/
├── street_vector.mbtiles     # Street basemap: OpenStreetMap vector tiles, z0-14, drawn at any zoom
├── ortho.mbtiles             # 2025 7.5 cm aerial imagery, z12-20
└── cadastral.mbtiles         # City parcel lines, address numbers and road labels, z14-20
```

### 6.1 OpenStreetMap Slippy Map Specification Compliance
* **Projection**: Standard Web Mercator (`EPSG:3857` / Spherical Mercator).
* **Coordinate Origin**: Top-left origin convention ($x=0, y=0$ at Northwest quadrant), matching the OpenStreetMap Slippy Map standard (`{z}/{x}/{y}`).
* **Row order**: MBTiles stores rows bottom-up ($y_{\text{TMS}} = 2^z - 1 - y_{\text{XYZ}}$). The build scripts write TMS rows and `mbtileserver` serves XYZ, so no client code flips rows.
* **Endpoints**: `${TILE_BASE_URL}/services/<service>/tiles/{z}/{x}/{y}.pbf|jpg|png`, with `TILE_BASE_URL` from `frontend/src/apiClient.js`; never a hardcoded host (CLAUDE.md §1).

### 6.2 Aerial Imagery (`ortho.mbtiles`)

> [!IMPORTANT]
> **The live archive is the Esri World Imagery crawl of the City's 2025 capture** (511,118
> tiles, z12–20), possibly with City gap tiles. The tree cannot rebuild it: the Esri crawl
> scripts were deleted in `d4a04fc8`, and `compile_mbtiles.py --layer ortho` crawls the City's own
> `Imagery_2025` cache instead. **Operator ruling 2026-09-15: City imagery is the goal**, and Esri
> stays live until a process gives City imagery at a quality he accepts (post-freeze backlog). Do
> not crawl or swap the archive without the operator. Record: punch-list #47b; serving and
> probes: `mbtiles-tile-server` skill §1 and §5.2.

* **Resolution**: the City's capture is 7.5 cm ground sampling distance (measured: `.sdw` pixel
  size 0.075 m).
* **Extent**: the Esri crawl reaches beyond the City at every zoom. z12–16 cover the region, and
  at least 45,594 z20 tiles lie outside the City's bounding box (Port Moody, Anmore, Belcarra,
  south of the Fraser); those are not known to be City photographs (#47b).
* **Native zoom**: z20, the honest limit for a 7.5 cm source: z20 is 9.74 cm/px here and z21
  would be 4.87 cm/px. The City's own cache also ends at z20 (z21 returns 404).
* **Endpoint**: `${TILE_BASE_URL}/services/ortho/tiles/{z}/{x}/{y}.jpg`
* **$0 Subscription-Free Guarantee**: Stored 100% locally on NVMe SSD storage with `fallbackUrl: null`, ensuring 100% disaster resilience with zero recurring API or tile-serving costs.
