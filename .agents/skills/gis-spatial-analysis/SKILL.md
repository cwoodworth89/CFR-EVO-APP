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
