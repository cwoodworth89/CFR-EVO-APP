# Technical Analysis: Google Street View Facade Engine & JS SDK Integration

**Author**: Explorer 2 (Frontend & JS SDK Specialist)  
**Target Component**: `frontend/src/components/kiosk/StreetViewPanel.jsx` & Related Frontend Integration  
**Date**: 2026-08-13  
**Status**: Complete Analysis (Read-Only Investigation)

---

## Executive Summary

This report presents a thorough investigation of the Google Street View facade inspection panel in the CFR EVO frontend (`frontend/src/components/kiosk/StreetViewPanel.jsx`), analyzing the Google Maps JS SDK initialization, event listener bindings, camera vantage point state management, property persistence payload, loading skeleton implementation, and rendering lifecycle challenges (gray canvas flashes, `innerHTML` DOM wipes, WebGL context leaks).

---

## 1. Street View Component Architecture & Rendering Locations

### 1.1 Core Component
* **Primary File**: `frontend/src/components/kiosk/StreetViewPanel.jsx`
* **Export Signature**: `export default function StreetViewPanel({ activeCall })`
* **Props**: `activeCall` object containing address, `front_lat`, `front_lng`, `lat`, `lng`, and optional `target` parcel metadata.

### 1.2 Layout & Viewport Embeddings
1. **Kiosk HUD View** (`frontend/src/components/kiosk/KioskView.jsx`, line 455):
   * Rendered in the right ~1/3 equal-height sidebar stack alongside `BlockParcelPanel` and `PropertySatellitePanel`.
2. **Explore Map Board** (`frontend/src/components/MapBoard.jsx`, line 1382):
   * Rendered in the right sidebar lower 1/3 panel when inspecting an active dispatch target address.
3. **Popout Full-Screen Modal** (`StreetViewPanel.jsx`, lines 378–401):
   * Toggleable via the `isExpanded` React state hook.
   * Renders a fixed inset modal (`fixed inset-0 z-[9999] bg-slate-950/95 backdrop-blur-md...`) with a dedicated DOM container (`modalContainerRef`).

### 1.3 Static vs Interactive Street View Distinction
* `DashboardHUD.jsx` (lines 177–178, 297) renders a static image preview using Google Static Street View API (`https://maps.googleapis.com/maps/api/streetview?size=400x250&location=...`).
* `StreetViewPanel.jsx` is the sole component rendering interactive 360° panoramas via Google Maps JavaScript SDK.

---

## 2. Google Maps JS SDK Loading & Initialization Lifecycle

### 2.1 SDK Script Loader
* **Location**: `StreetViewPanel.jsx` (lines 174–190).
* **Mechanism**: Checks for `window.google.maps`. If absent, checks for existing script with ID `#google-maps-js-sdk`. If missing, injects `<script id="google-maps-js-sdk" src="https://maps.googleapis.com/maps/api/js?key=${apiKey}">` into `document.head`.
* **Auth Error Guard**: Attaches `window.gm_authFailure` listener to intercept Google API key authorization errors and fall back to iframe embeds.

### 2.2 Panorama Instance Instantiation
* **Location**: `StreetViewPanel.jsx` (lines 118–173).
* **Target Container Selection**: Dynamically switches between `containerRef.current` (inline sidebar) and `modalContainerRef.current` (full-screen modal) based on `isExpanded`.
* **DOM Preparation**: Invokes `targetContainer.innerHTML = ''` prior to constructing `new window.google.maps.StreetViewPanorama(targetContainer, options)`.
* **Panorama Configuration**:
  ```javascript
  {
    pov: { heading: initialHeading, pitch: initialPitch },
    zoom: 1,
    fullscreenControl: false,
    addressControl: false,
    panControl: false,
    linksControl: true,
    motionTracking: false,
    motionTrackingControl: false,
    showRoadLabels: true,
    visible: true
  }
  ```

### 2.3 Outdoor Street View Resolution (`StreetViewService`)
* **Location**: `StreetViewPanel.jsx` (lines 138–154 & 198–219).
* **Service**: Instantiates `new window.google.maps.StreetViewService()`.
* **Query Parameters**:
  ```javascript
  {
    location: { lat: frontLat, lng: frontLng },
    radius: 300,
    source: window.google.maps.StreetViewSource.OUTDOOR,
    preference: window.google.maps.StreetViewPreference.NEAREST
  }
  ```
* **Fallback Behavior**: On `OK`, calls `pano.setPano(data.location.pano)` and `pano.setPov(...)`. On status failure, calls `pano.setPosition({ lat: frontLat, lng: frontLng })`.

---

## 3. SDK Event Listener Audit

| Event Name | Bound Currently? | Current Callback Implementation | Issue / Missing Functionality |
|---|---|---|---|
| `pov_changed` | **YES** | Updates `currentPovRef.current` with rounded `heading`, `pitch`, and `zoom`. | Reads `pano.getZoom()`, but does not listen to zoom-specific changes. |
| `position_changed` | **NO** | Not bound. | When user clicks road arrows to step down the street, position (`lat`, `lng`) is not tracked continuously. |
| `pano_changed` | **NO** | Not bound. | Active `pano_id` is not captured when switching panoramas. |
| `zoom_changed` | **NO** | Not bound. | Mouse wheel zoom / pinch zoom changes are not independently captured. |
| `status_changed` / `visible_changed` | **NO** | Not bound. | Cannot detect when tiles finished loading to smoothly hide loading skeleton. |

---

## 4. Vantage Point State & Ref Management Analysis

### 4.1 Current Ref Storage Structure
```javascript
const currentPovRef = useRef({ heading: 0, pitch: 5, zoom: 1 });
```

### 4.2 Deficiencies in Vantage Point Capture
1. **Missing Location Coordinates**: `currentPovRef` does not record `lat` or `lng`. Position coordinates are only retrieved lazily on save via `panoramaRef.current.getLocation()`. If the user steps down the street and `panoramaRef` is unmounted/remounted during modal toggle, the moved position is lost.
2. **Missing `pano_id`**: Google Street View unique panorama identifier (`pano_id`) is not captured or persisted.
3. **FOV Conversion Gap**: `currentPovRef` stores SDK `zoom` (typically integer 0–3), whereas API payloads and embeds use `fov` (Field of View in degrees, e.g. 80°, 90°). There is no active mapping between `zoom` and `fov`.
4. **Ref Overwrite Race Condition**: Line 99–101 has an effect that resets `currentPovRef.current` to `{ heading: initialHeading, pitch: initialPitch, zoom: 1 }` whenever `initialHeading` or `initialPitch` changes, overwriting user pan/tilt adjustments if parent props re-render.

---

## 5. "Save Preferred View" Flow & Persistence Payload

### 5.1 Save Handler Workflow (`handleSaveView`, lines 221–268)
1. Sanitizes address key (`cleanAddrKey`, e.g. `"3030 GORDON AVE"`).
2. Reads `currentPovRef.current` and queries `panoramaRef.current.getPov()` & `panoramaRef.current.getLocation()`.
3. Constructs payload:
   ```json
   {
     "clean_address": "3030 GORDON AVE",
     "front_lat": 49.26995,
     "front_lng": -122.7919,
     "heading": 35,
     "pitch": 10,
     "fov": 80
   }
   ```
4. Writes to `localStorage` under key `cfr_sv_override_${cleanAddrKey}`.
5. Invokes `apiClient.streetView.saveOverride(payload)` (`POST /api/streetview-overrides`).
6. Updates React state `dbOverride` and displays UI indicator `SAVED PREFERRED VIEW (${heading}°)`.

### 5.2 Required Changes for Requirement R2 & R1
* The backend API endpoint must write into the unified `parcels` PostgreSQL table.
* The payload should include `pano_id` and dynamically computed `fov` from camera zoom level.

---

## 6. Rendering Lifecycle, HUD Skeleton & WebGL Resource Issues

### 6.1 Missing Dark HUD Skeleton
* Currently, `StreetViewPanel.jsx` relies on default Google Maps container rendering while tiles load over the network.
* As a result, the user sees a bright default gray background (`#e5e3df`) while the 360° tiles compile, causing noticeable **gray/blank canvas flashes**.

### 6.2 Destructive `innerHTML = ''` Container Wipes
* In `StreetViewPanel.jsx` (line 122 and line 193):
  ```javascript
  targetContainer.innerHTML = '';
  ```
  and in effect cleanup:
  ```javascript
  return () => {
    if (targetContainer) targetContainer.innerHTML = '';
    panoramaRef.current = null;
  };
  ```
* Direct `innerHTML` wipes forcibly tear down DOM nodes created by Google Maps JS SDK without unbinding event listeners or invoking SDK teardown routines.

### 6.3 WebGL Context Leaks Across Expansion & Reopen
* Toggling `isExpanded` (modal open/close) switches the target container between `containerRef` and `modalContainerRef`.
* Because `isExpanded` is in the `useEffect` dependency array (line 196), toggling modal state destroys the inline `StreetViewPanorama` instance via `innerHTML = ''` and creates a brand-new `StreetViewPanorama` instance in the modal container.
* Browsers enforce a strict limit on active WebGL contexts (typically 8–16). Repeatedly opening/closing dispatch calls or expanding/collapsing the modal leads to accumulated WebGL contexts, eventual context loss errors (`WARNING: Too many active WebGL contexts`), and canvas rendering failures.

---

## 7. Frontend Target Files & Required Modifications (R1, R3, R4)

### Primary File to Modify
1. `frontend/src/components/kiosk/StreetViewPanel.jsx`:
   * **R1 (Vantage Point Capture)**: Bind `pov_changed`, `position_changed`, `pano_changed`, `zoom_changed` listeners. Update continuous ref with `{ heading, pitch, zoom, fov, lat, lng, pano_id }`. Map `zoom` level to `fov` (e.g. `fov = 180 / Math.pow(2, zoom)` or standard linear mapping). Include camera vectors in save payload.
   * **R3 (SDK Conformance)**: Implement clean Google Maps event listener cleanup using `google.maps.event.clearInstanceListeners(pano)`. Remove destructive `innerHTML = ''` wipes. Implement single-instance panorama re-parenting or clean destruction/re-instantiation patterns.
   * **R4 (HUD Skeleton & Lifecycle)**: Add a dark HUD skeleton overlay ("Loading Street View Facade...") with smooth CSS opacity transition. Keep skeleton overlay active until `status_changed` / `pano_changed` / tile ready event fires. Preserve WebGL contexts across expand/close and call transitions.

### Secondary Supporting Files
2. `frontend/src/apiClient.js`:
   * Ensure `streetView.saveOverride` and `streetView.fetchOverride` route to/from the unified PostgreSQL `parcels` backend endpoints (`/api/parcels/lookup` and `/api/parcels/override` or `/api/streetview-overrides`).
3. `frontend/src/components/kiosk/KioskView.jsx`:
   * Ensure stable key and prop passing to `StreetViewPanel`.
4. `frontend/src/components/MapBoard.jsx`:
   * Ensure stable key and prop passing when active call is inspected in Explore mode.

---

## 8. Verification Strategy
* **Local Build Check**: Run `npm run build` inside `frontend/` to confirm zero JSX/ESLint/TypeScript warnings or build errors.
* **SDK Listener Check**: Verify continuous console logging of `pov_changed`, `position_changed`, `pano_changed`, `zoom_changed` events.
* **WebGL Preservation Check**: Inspect browser DevTools WebGL context count when repeatedly expanding/closing modal and switching dispatch calls.
* **Remote Kiosk Verification**: Deploy build to station kiosk (`100.95.146.94`) and verify smooth dark HUD skeleton transitions, zero gray flashes, and accurate property persistence.
