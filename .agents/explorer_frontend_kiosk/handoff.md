# Handoff Report — Frontend & Kiosk Ergonomics Architecture

**Agent**: Frontend & Kiosk Ergonomics Architecture Explorer  
**Date**: 2026-08-14  
**Working Directory**: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\explorer_frontend_kiosk\`  
**Milestone**: CFR EVO v1.0.0 Architecture Review & Component Decomposition

---

## 1. Observation

1. **Monolithic Component Size**:
   - `frontend/src/components/DispatchReview.jsx` is **1,602 lines** long, housing authentication state (lines 72-76, 511-607), database/RF listener status polling (lines 63-70, 139-167), table rendering with complex filters (lines 469-502, 735-982), HTML5 audio player management with -5s skip (lines 187-301, 1033-1073), 3-stage pipeline execution flow timeline (lines 1075-1250), ground-truth review form (lines 1252-1575), and auto-advance index computation (lines 424-443).

2. **Violation of `GEMINI.md` Rule 1 (Raw Relative `fetch()` Calls)**:
   - `frontend/src/components/MapBoard.jsx:678`:
     ```javascript
     const fetchFromGateway = fetch("/api/road-closures")
     ```
   - `frontend/src/components/admin/SystemMetricsPanel.jsx:22`:
     ```javascript
     const res = await fetch("/api/metrics/summary");
     ```
   - When accessed on remote kiosk displays over Tailscale (`http://100.95.146.94:5173`), relative `/api/...` requests route to the Vite dev/preview server on port 5173 instead of the FastAPI backend on port 8000, causing 404 HTTP errors.

3. **External CDN Asset Leaks (Online Dependencies in Kiosk View)**:
   - `frontend/src/components/kiosk/RouteOverviewPanel.jsx:63-64`
   - `frontend/src/components/kiosk/BlockParcelPanel.jsx:32-33`
   - `frontend/src/components/kiosk/PropertySatellitePanel.jsx:50-51`
     ```javascript
     const targetIcon = new L.Icon({
       iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-gold.png',
       shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
       iconSize: [25, 41],
       iconAnchor: [12, 41],
       popupAnchor: [1, -34],
       shadowSize: [41, 41]
     });
     ```
   - When station internet is offline, these marker icons fail to load or block map initialization.

4. **Offline Local Tile Server Architecture**:
   - `frontend/src/apiClient.js:16-24` defines dynamic tile server base URL:
     ```javascript
     const getTileBaseUrl = () => {
       if (import.meta.env.VITE_TILE_BASE_URL) {
         return import.meta.env.VITE_TILE_BASE_URL.replace(/\/$/, '');
       }
       const hostname = window.location.hostname || 'localhost';
       return `http://${hostname}:8081`;
     };
     export const TILE_BASE_URL = getTileBaseUrl();
     ```
   - `frontend/src/components/MapLayers.jsx:74-116` implements `FallbackTileLayer` which loads tiles from port 8081 and falls back to online Carto/OSM unless `VITE_DISABLE_WAN_FALLBACK=true`.

5. **Station Bay 10-Foot HUD Ergonomics**:
   - `frontend/src/components/kiosk/KioskView.jsx` splits viewport into top 15% alert HUD (with high-contrast emergency banners, unit ETAs, hydrant callouts, and large address) and bottom 85% multi-panel map view (2/3 Route Overview + 1/3 3-panel stack: BlockParcel, PropertySatellite, StreetView).
   - `frontend/src/hooks/useKioskQueue.js` manages hands-free auto-activation, touch reset of 5-minute dismiss timer, and dual-tone chime playback on incoming queued calls.

---

## 2. Logic Chain

1. **From Observation 1**: `DispatchReview.jsx` combines multiple unrelated state machines (auth, table, audio, form, pipeline timeline) in one file. This results in heavy re-render storms on every keystroke, poor maintainability, and high token consumption during automated code reviews. **Therefore**, modular decomposition into dedicated sub-folders (`ReviewTable/`, `AudioPlayer/`, `VerificationSidebar/`, `Auth/`) backed by a shared `ReviewContext` is necessary.
2. **From Observation 2**: In production, remote station displays access the frontend at `http://100.95.146.94:5173`. Any `fetch('/api/...')` call is resolved relative to the origin port 5173 (Vite), not port 8000 (FastAPI). **Therefore**, all `fetch()` calls in `MapBoard.jsx` and `SystemMetricsPanel.jsx` must be updated to use `${API_BASE_URL}/api/...` as mandated by `GEMINI.md` Rule 1.
3. **From Observation 3**: The requirement specifies 100% offline survival for station bay kiosks. Referencing external CDN URLs (`raw.githubusercontent.com`, `cdnjs.cloudflare.com`) creates a point of failure during internet outages. **Therefore**, marker icons and shadows must be bundled locally into `frontend/public/icons/`.
4. **From Observation 4 & 5**: The local tile server on port 8081 and the 10-foot HUD responsive layout provide robust offline display capabilities, but require complete removal of WAN asset leaks and modularized code to ensure long-term stability and clean execution during v1.0.0 implementation.

---

## 3. Caveats

- **Street View Panorama Offline Limitation**: Google Street View (`StreetViewPanel.jsx`) requires an active internet connection to stream 360° panoramas from Google Maps JS SDK. In offline mode, the panel gracefully displays a local building footprint fallback canvas (`Local Building Footprint Canvas`).
- **Satellite Aerial Tiles**: High-resolution satellite tiles (`PropertySatellitePanel.jsx`) require internet access to Esri ArcGIS servers. When offline, it displays an offline standby indicator while the primary vector route and parcel block maps remain 100% operational locally.
- **Audio Autoplay Policies**: Chromium browsers may restrict audio playback without prior user interaction. The system includes safe `.catch()` handlers, but touch/click initialization is recommended when starting the kiosk display.

---

## 4. Conclusion

The CFR EVO frontend architecture is fundamentally sound, with excellent 10-foot HUD layout ergonomics, dynamic local tile server integration on port 8081, and rapid review workflows. However, immediate remediation is required for:
1. **Rule 1 Violations**: Fixing relative `fetch('/api/...')` paths in `MapBoard.jsx` and `SystemMetricsPanel.jsx`.
2. **Offline Icon Bundling**: Replacing external GitHub/CDN marker assets with local SVGs/PNGs in `dist/icons/`.
3. **Component Decomposition**: Refactoring `DispatchReview.jsx` (1,602 lines) into modular sub-components under `frontend/src/components/review/`.

A model tier allocation matrix assigns these tasks cleanly across **Flash-Lite** (bug fixes, icon bundling) and **Flash** (component decomposition, state context extraction).

---

## 5. Verification Method

To independently verify all findings and validate fixes:

1. **Verify Forbidden Raw Relative `fetch()` Calls**:
   ```bash
   # Must return ZERO matches in frontend/src/components/
   grep -rn 'fetch("/api' frontend/src/
   grep -rn "fetch('/api" frontend/src/
   ```

2. **Verify External CDN Marker URLs**:
   ```bash
   # Must return ZERO matches in frontend/src/components/
   grep -rn 'https://raw.githubusercontent.com' frontend/src/
   grep -rn 'https://cdnjs.cloudflare.com' frontend/src/
   ```

3. **Frontend Production Build Verification**:
   ```bash
   cd frontend
   npm run build
   ```

4. **Full-Stack Remote Kiosk Verification**:
   ```bash
   ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/frontend && npm run build"
   ```
