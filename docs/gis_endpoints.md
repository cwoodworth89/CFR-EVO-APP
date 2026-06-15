# Coquitlam GIS Data Sources & API Endpoints

This document serves as the authoritative map of all external GIS APIs, datasets, and local caching/fallback mechanisms used by the CFR-EVO-APP.

---

## 1. Overview of the GIS Architecture

To maintain high reliability during dispatch operations, the system is designed to **rely as little as possible on external network queries**:
* **Backend Geocoding**: Done 100% offline using high-performance local Shapefiles indexed in memory at startup.
* **Frontend Overlays**: Large visual layers (like hydrants and zone polygons) are served locally as static JSON files.
* **Live GIS Overlays**: Dense overlays (like parcel property lines) are loaded dynamically via ESRI Leaflet image streams from the city's servers, with automatic fallback structures if they go offline.

---

## 2. Live MapServer Endpoints (Frontend Leaflet UI)

These live ArcGIS map services are consumed by Leaflet inside the React frontend:

| Component Name | Service Type | ArcGIS Server REST URL | Layers/Sublayers Used |
| :--- | :--- | :--- | :--- |
| `CoquitlamOverlays` | MapServer | `https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Cadastral/MapServer` | `0` (Roads), `1` (Addresses), `16` (Parcels) |
| `FireZonesLayer` | MapServer | `https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Planning/MapServer` | `6` (Emergency Response Zones boundary lines & labels) |

---

## 3. Offline Shapefile Downloads (Backend Geocoder)

These raw shapefiles are used by the backend geocoding and zone containment systems. They are downloaded, wind-order-corrected, and stored locally.

### Address Points Dataset
* **ArcGIS Hub ID**: `e38a2f7cdc9b47e38d87873ea6fee275_0`
* **Direct Download (SHP ZIP)**: `https://opendata.arcgis.com/api/v3/datasets/e38a2f7cdc9b47e38d87873ea6fee275_0/downloads/data?format=shp&spatialRefId=4326`
* **Local Path**: `backend/data/Property_Information/Addresses.*` (`.shp`, `.dbf`, `.prj`, `.shx`)

### Emergency Response Zones Dataset
* **ArcGIS Hub ID**: `f7e227f598e94696ac8e43538e80c35f_6`
* **Direct Download (SHP ZIP)**: `https://opendata.arcgis.com/api/v3/datasets/f7e227f598e94696ac8e43538e80c35f_6/downloads/data?format=shp&spatialRefId=4326`
* **Local Path**: `backend/data/Emergency_Response_Zones/Emergency_Response_Zones.*` (`.shp`, `.dbf`, `.prj`, `.shx`)

---

## 4. Local Cached Datasets (Frontend Static JSONs)

These datasets are pre-processed and saved inside the frontend's static directory for client-side rendering performance.

### Water Hydrants
* **Live Query URL**: `https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Water/MapServer/2/query`
* **Local Path**: `frontend/public/data/hydrants.json`
* **Fields Fetched**: `OBJECTID,gis_id,status,flow_class`
* **Query Parameters**: `where=1=1&outSR=4326&f=json` (fetched sequentially in pages of 1000 using `resultOffset` pagination to bypass server query limitations).

### Emergency Response Zones (Geometry)
* **Local Path**: `frontend/public/data/zones.json`
* **Purpose**: Allows 100% offline rendering of Fire Zones boundaries and Hall/Unit details.

---

## 5. Maintenance & Cron Automation

GIS databases are updated automatically on a scheduled maintenance cycle via Windows Task Scheduler.
* **Scheduled Task Name**: `CFR_GIS_Maintenance`
* **Trigger**: Monthly (1st of every month at 3:00 AM)
* **Script Location**: `backend/scripts/update_gis_data.py`
* **Registration Script**: `backend/schedule_maintenance.bat` (Run as Administrator)

---

## 6. Offline Fallback Logic

If Coquitlam's ArcGIS servers go offline, the system self-heals in the following sequence:
1. **Network Error Interception**: `CoquitlamOverlays` monitors the MapServer using a Leaflet `requesterror` event.
2. **Blinking Indicator Status**: Once an error is detected, the frontend header displays a pulsing **`COQUITLAM GIS OFFLINE`** warning badge next to the application logo.
3. **MapServer Muting**: All ongoing image-generation requests to `CoquitlamOverlays` and `FireZonesLayer` are disabled to avoid flooding the browser console with repeated network timeouts as the map is panned.
4. **Basemap Labels Restoration**: The `BaseMap` component replaces the default no-labels basemap tile URL (CartoDB Light/Dark `nolabels` tiles) with the standard labeled version (`light_all` or `dark_all`) as an emergency labels backup.
5. **Local GeoJSON Zone Render**: The map falls back to rendering fire zone boundaries and responding hall units using local coordinates from the cached `zones.json` with dynamic hover tooltips.
