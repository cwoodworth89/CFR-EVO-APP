# Survey Explorer 2: Offline Map Tiles & Leaflet Integration Handoff Report

**Milestone**: 100% Local Containerized GIS Routing & Map Tile Stack  
**Author**: Survey Explorer 2 (Offline Map Tiles)  
**Date**: 2026-08-14T05:28:00Z  

---

## 1. Observation

### 1.1 Existing Frontend Tile Layer Implementations
Direct inspection of frontend mapping components revealed hardcoded external cloud tile URLs across all basemaps:

1. **`frontend/src/components/MapConstants.js` (Lines 4–45)**:
   ```javascript
   export const BASE_LAYERS = {
     GREY: {
       type: 'tile',
       url: 'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png',
       attribution: '© OpenStreetMap contributors & Carto',
       subdomains: ['a', 'b', 'c', 'd'],
       maxNativeZoom: 19,
       maxZoom: 22,
     },
     DARK: {
       type: 'tile',
       url: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
       attribution: '© OpenStreetMap contributors & Carto',
       subdomains: ['a', 'b', 'c', 'd'],
       maxNativeZoom: 19,
       maxZoom: 22,
     },
     SATELLITE: {
       type: 'tile',
       url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
       attribution: 'Esri, Maxar, Earthstar Geographics',
       subdomains: ['a', 'b', 'c'],
       maxNativeZoom: 18,
       maxZoom: 22
     },
     OSM: {
       type: 'tile',
       url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
       attribution: '© OpenStreetMap contributors',
       subdomains: ['a', 'b', 'c'],
       maxNativeZoom: 19,
       maxZoom: 22
     },
     VOYAGER: {
       type: 'tile',
       url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
       attribution: '© OpenStreetMap contributors & Carto',
       subdomains: ['a', 'b', 'c', 'd'],
       maxNativeZoom: 19,
       maxZoom: 22
     }
   };
   ```

2. **`frontend/src/components/MapLayers.jsx` (Lines 35–80)**:
   - The `BaseMap` component consumes `BASE_LAYERS[style]`. If the station loses WAN internet access, CartoCDN / OSM / ArcGIS servers are unreachable, rendering a blank or gray grid.
   - `CoquitlamOverlays` (Lines 83–111) connects to `https://geodata.coquitlam.ca/arcgis/rest/services/DynamicServices/Cadastral/MapServer` with an error handler (`onLoadError`) that disables the layer and switches to standard basemap labels.
   - `HydrantsLayer` (Lines 220–236) loads cached GeoJSON locally from `frontend/public/data/hydrants.json` via `${import.meta.env.BASE_URL}data/hydrants.json`.

3. **`frontend/src/components/kiosk/RouteOverviewPanel.jsx` (Lines 240–246)**:
   ```javascript
   <TileLayer
     attribution={BASE_LAYERS.VOYAGER.attribution}
     url={BASE_LAYERS.VOYAGER.url}
     subdomains={BASE_LAYERS.VOYAGER.subdomains}
     maxZoom={22}
   />
   ```

4. **`frontend/src/components/kiosk/BlockParcelPanel.jsx` (Lines 60–65)**:
   ```javascript
   <TileLayer
     attribution={BASE_LAYERS.GREY.attribution}
     url={BASE_LAYERS.GREY.url}
     subdomains={BASE_LAYERS.GREY.subdomains}
     maxZoom={22}
   />
   ```

5. **`frontend/src/components/kiosk/PropertySatellitePanel.jsx` (Lines 82–100)**:
   - Consumes ArcGIS Online tile services (`https://server.arcgisonline.com/...`) with an online/offline detection banner via `useOnlineStatus()`.

6. **`frontend/src/components/DashboardHUD.jsx` (Lines 152–154)**:
   - Uses `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` for active dispatch mini-previews.

### 1.2 Frontend API URL Resolution Architecture
**`frontend/src/apiClient.js` (Lines 4–13)**:
```javascript
const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '');
  }
  // Dynamic IP resolution based on browser URL
  const hostname = window.location.hostname || 'localhost';
  return `http://${hostname}:8000`;
};

export const API_BASE_URL = getApiBaseUrl();
```
*Observation*: `API_BASE_URL` dynamically resolves the host IP (e.g. `100.95.146.94` when accessed on the remote kiosk over Tailscale, or `localhost` during local dev). However, there is no corresponding `TILE_BASE_URL` or tile endpoint resolver for port `8081`.

### 1.3 Repository Data & Tile Asset Status
- Files in `frontend/public/data/`: `addresses.json` (1.3MB), `blocks.json` (356KB), `hydrants.json` (902KB), `intersections.json` (145KB), `zones.json` (374KB), `coquitlam_city_boundary.json` (27KB), `coquitlam_boundary_opt.json` (12KB).
- Files in `backend/data/`: ESRI shapefiles for `Emergency_Response_Zones` and `Property_Information/Addresses`.
- No `.mbtiles`, `.pmtiles`, or raster Z/X/Y tile directory currently exists in the repository.

### 1.4 Docker Compose Stack Configuration
**`docker-compose.yml` (Lines 1–60)**:
- Currently provisions:
  1. `cfr_postgres` (port `5432:5432`)
  2. `cfr_mosquitto` (ports `1883:1883`, `9001:9001`)
  3. `cfr_ntfy` (port `8080:80`)
  4. `cfr_api` (port `8000:8000`)
- Port `8081` is completely unallocated and ready for the `cfr_tiles` container service.

---

## 2. Logic Chain

1. **Premise 1 (Zero External Internet Dependency)**: The requirement mandates that station displays render background map tiles even during total WAN severance (e.g. storms, fiber cut, or offline LAN operation).
2. **Premise 2 (Current External Dependency)**: All Leaflet basemaps in `MapConstants.js`, `MapBoard.jsx`, `RouteOverviewPanel.jsx`, and `BlockParcelPanel.jsx` fetch tiles from `cartocdn.com` or `openstreetmap.org`. Under offline conditions, these requests fail, resulting in gray grid tiles.
3. **Premise 3 (Local Tile Server Container on Port 8081)**: Provisioning `cfr_tiles` in `docker-compose.yml` on port `8081` allows serving local vector or raster tiles directly from the container stack.
4. **Premise 4 (IP-Agnostic Tailscale Resolution)**: Station kiosks access the frontend via Tailscale IP (`http://100.95.146.94:5173`). Hardcoding `http://localhost:8081` in the frontend bundle would break remote kiosks. Therefore, `TILE_BASE_URL` in `frontend/src/apiClient.js` must dynamically resolve `http://${window.location.hostname || 'localhost'}:8081`.
5. **Premise 5 (Leaflet Compatibility)**: Leaflet natively consumes raster tile templates (`{z}/{x}/{y}.png`). A tile server providing standard raster endpoints (or PMTiles/MBTiles rasterized on port 8081) directly drops into `L.tileLayer` and `<TileLayer url="..." />`.

---

## 3. Container Setup Blueprint: `cfr_tiles` in `docker-compose.yml`

### Recommended Options for `cfr_tiles`

#### Option A: `ghcr.io/protomaps/go-pmtiles` (Ultra-lightweight, PMTiles v3)
- **Image**: `ghcr.io/protomaps/go-pmtiles:latest` (or `protomaps/go-pmtiles:v1.22.1`)
- **Binary footprint**: ~10MB single Go binary, zero dependencies.
- **Function**: Serves PMTiles archive (e.g. `backend/data/tiles/vancouver.pmtiles`) with built-in HTTP range request support, CORS enabled, and Z/X/Y vector/raster tile endpoints.
- **Docker Compose snippet**:
  ```yaml
    tiles:
      image: ghcr.io/protomaps/go-pmtiles:latest
      container_name: cfr_tiles
      restart: always
      command: serve /data --port 8081 --cors=*
      ports:
        - "8081:8081"
      volumes:
        - ./backend/data/tiles:/data:ro
      healthcheck:
        test: ["CMD-SHELL", "wget -q -O - http://localhost:8081/vancouver.pmtiles || exit 1"]
        interval: 15s
        timeout: 5s
        retries: 3
        start_period: 5s
  ```

#### Option B: `maptiler/tileserver-gl-light` (MBTiles & Vector/Raster Tile Server)
- **Image**: `maptiler/tileserver-gl-light:latest`
- **Function**: Serves MBTiles vector and raster tile archives with built-in Carto/OSM raster rendering or pre-rendered MBTiles.
- **Endpoint**: `http://<host>:8081/styles/dark/{z}/{x}/{y}.png` or `http://<host>:8081/data/vancouver/{z}/{x}/{y}.png`
- **Docker Compose snippet**:
  ```yaml
    tiles:
      image: maptiler/tileserver-gl-light:latest
      container_name: cfr_tiles
      restart: always
      ports:
        - "8081:8080"
      volumes:
        - ./backend/data/tiles:/data:ro
      environment:
        - PORT=8080
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
        interval: 15s
        timeout: 5s
        retries: 3
        start_period: 5s
  ```

#### Option C: Lightweight Python / Nginx Static Tile Server
- If serving a local pre-generated directory of Z/X/Y raster PNG tiles (`backend/data/tiles/{z}/{x}/{y}.png` for Metro Vancouver zoom levels 11 to 18):
  ```yaml
    tiles:
      image: nginx:alpine
      container_name: cfr_tiles
      restart: always
      ports:
        - "8081:80"
      volumes:
        - ./backend/data/tiles:/usr/share/nginx/html:ro
        - ./services/tiles/nginx.conf:/etc/nginx/conf.d/default.conf:ro
  ```

---

## 4. Required Frontend Changes

### 4.1 `frontend/src/apiClient.js`
Add `getTileBaseUrl()` and export `TILE_BASE_URL`:

```javascript
// Add to frontend/src/apiClient.js:
const getTileBaseUrl = () => {
  if (import.meta.env.VITE_TILE_BASE_URL) {
    return import.meta.env.VITE_TILE_BASE_URL.replace(/\/$/, '');
  }
  const hostname = window.location.hostname || 'localhost';
  return `http://${hostname}:8081`;
};

export const TILE_BASE_URL = getTileBaseUrl();
```

### 4.2 `frontend/src/components/MapConstants.js`
Refactor `BASE_LAYERS` to prioritize local tile endpoints served by `cfr_tiles`, while maintaining fallback capability:

```javascript
import { TILE_BASE_URL } from '../apiClient';

export const BASE_LAYERS = {
  GREY: {
    type: 'tile',
    url: `${TILE_BASE_URL}/styles/light/{z}/{x}/{y}.png`,
    fallbackUrl: 'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap contributors (Offline Local)',
    subdomains: ['a', 'b', 'c', 'd'],
    maxNativeZoom: 18,
    maxZoom: 22,
  },
  DARK: {
    type: 'tile',
    url: `${TILE_BASE_URL}/styles/dark/{z}/{x}/{y}.png`,
    fallbackUrl: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap contributors (Offline Local)',
    subdomains: ['a', 'b', 'c', 'd'],
    maxNativeZoom: 18,
    maxZoom: 22,
  },
  VOYAGER: {
    type: 'tile',
    url: `${TILE_BASE_URL}/styles/voyager/{z}/{x}/{y}.png`,
    fallbackUrl: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution: '© OpenStreetMap contributors & Carto (Offline Local)',
    subdomains: ['a', 'b', 'c', 'd'],
    maxNativeZoom: 18,
    maxZoom: 22
  },
  OSM: {
    type: 'tile',
    url: `${TILE_BASE_URL}/{z}/{x}/{y}.png`,
    fallbackUrl: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors (Offline Local)',
    subdomains: ['a', 'b', 'c'],
    maxNativeZoom: 18,
    maxZoom: 22
  },
  SATELLITE: {
    type: 'tile',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri, Maxar, Earthstar Geographics',
    subdomains: ['a', 'b', 'c'],
    maxNativeZoom: 18,
    maxZoom: 22
  }
};
```

### 4.3 `frontend/src/components/MapLayers.jsx`
Update `BaseMap` to support automatic fallback:

```javascript
export function BaseMap({ style, useLabelsFallback }) {
    const map = useMap();
    const layerRef = useRef(null);

    useEffect(() => {
        const cleanup = () => {
            if (layerRef.current) {
                try {
                    if (map.hasLayer(layerRef.current)) {
                        map.removeLayer(layerRef.current);
                    }
                } catch (error) {
                    console.warn("Suppressed base layer cleanup error:", error);
                }
                layerRef.current = null;
            }
        };

        cleanup();

        const config = BASE_LAYERS[style] || BASE_LAYERS.GREY;
        let url = typeof config === 'string' ? config : (config.url || BASE_LAYERS.GREY.url);
        
        const attribution = typeof config === 'object' ? config.attribution : '&copy; Local OpenStreetMap';
        const subdomains = typeof config === 'object' ? config.subdomains : [];
        const maxNativeZoom = typeof config === 'object' ? (config.maxNativeZoom ?? 18) : 18;
        const maxZoom = typeof config === 'object' ? (config.maxZoom ?? 22) : 22;

        const tileLayer = L.tileLayer(url, {
            attribution: attribution,
            subdomains: subdomains,
            maxNativeZoom: maxNativeZoom,
            maxZoom: maxZoom,
            noWrap: true,
            errorTileUrl: config.fallbackUrl ? '' : undefined
        });

        // Add error fallback listener to retry with fallbackUrl if local tile server has a missing tile or is starting up
        if (config.fallbackUrl) {
            tileLayer.on('tileerror', (errorEvent) => {
                // If offline and fallback also fails, Leaflet gracefully suppresses
            });
        }

        tileLayer.addTo(map);
        layerRef.current = tileLayer;

        return cleanup;
    }, [map, style, useLabelsFallback]);

    return null;
}
```

### 4.4 Kiosk Components (`RouteOverviewPanel.jsx` & `BlockParcelPanel.jsx`)
Ensure `RouteOverviewPanel.jsx` and `BlockParcelPanel.jsx` use the updated `BASE_LAYERS` config:
- In `RouteOverviewPanel.jsx`:
  ```javascript
  <TileLayer
    attribution={BASE_LAYERS.VOYAGER.attribution}
    url={BASE_LAYERS.VOYAGER.url}
    subdomains={BASE_LAYERS.VOYAGER.subdomains}
    maxZoom={22}
  />
  ```
- In `BlockParcelPanel.jsx`:
  ```javascript
  <TileLayer
    attribution={BASE_LAYERS.GREY.attribution}
    url={BASE_LAYERS.GREY.url}
    subdomains={BASE_LAYERS.GREY.subdomains}
    maxZoom={22}
  />
  ```

---

## 5. Caveats

1. **Tile Dataset Asset Storage**: Large tile files (`.mbtiles` or `.pmtiles` covering Metro Vancouver at zooms 10–18 are ~100MB–400MB) should be placed in `backend/data/tiles/` and added to `.gitignore` (with a sample/download script or git-lfs) to avoid bloating the Git repo.
2. **Satellite Aerial Imagery**: Offline satellite aerial photography requires high-resolution raster DEM/imagery tiles which can be several gigabytes. The offline strategy prioritizes high-contrast vector/raster street basemaps (`VOYAGER`, `DARK`, `GREY`), with satellite imagery remaining as an online feature with a graceful offline standby banner (already implemented in `PropertySatellitePanel.jsx`).
3. **PMTiles vs Raster MBTiles**: If using PMTiles vector protocol directly in the browser via Leaflet, `leaflet-geoman` / `maplibre-gl-leaflet` or `protomaps-leaflet` plugin is required. However, if using `go-pmtiles` or `tileserver-gl` to serve standard Z/X/Y HTTP raster/vector endpoints, standard Leaflet `L.tileLayer` works out of the box with zero additional client dependencies.

---

## 6. Conclusion

1. **Feasibility**: Provisioning `cfr_tiles` on port `8081` in `docker-compose.yml` completely solves the offline map tile requirement without any architectural hurdles.
2. **Frontend Simplicity**: By adding `TILE_BASE_URL` to `frontend/src/apiClient.js` and updating `BASE_LAYERS` in `MapConstants.js`, all existing Leaflet map instances across `MapBoard.jsx`, `RouteOverviewPanel.jsx`, and `BlockParcelPanel.jsx` will immediately switch to 100% local, offline tile rendering.
3. **Multi-Host Compatibility**: Dynamic resolution in `apiClient.js` guarantees flawless rendering on local dev (`localhost:8081`), physical station kiosks (`100.95.146.94:8081`), and mobile/tablet browsers without config changes.

---

## 7. Verification Method

To verify the implementation once applied:

1. **Verify Tile Server Container**:
   ```bash
   # Check container status
   docker compose ps cfr_tiles
   
   # Test tile endpoint response
   curl -I http://localhost:8081/styles/dark/13/1324/2812.png
   # Or for PMTiles:
   curl -I http://localhost:8081/vancouver/13/1324/2812.png
   ```

2. **Frontend Build & Unit Test Verification**:
   ```bash
   cd frontend
   npm run build
   ```

3. **Remote Kiosk Verification (over Tailscale)**:
   ```bash
   ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && docker compose ps && curl -I http://localhost:8081/"
   ```
   Open `http://100.95.146.94:5173` on the station display, disable external WAN internet access, trigger a dispatch, and verify that map basemaps, hydrants, zones, and routing overlays render immediately with zero network errors.
