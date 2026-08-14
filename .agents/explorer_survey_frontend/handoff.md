# Explorer 2 (Frontend & JS SDK Specialist) — Handoff Report

**Assigned Directory**: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\explorer_survey_frontend\`  
**Date**: 2026-08-13  
**Handoff Type**: Hard Handoff (Investigation Complete)

---

## 1. Observation

1. **Primary Component Location**:
   * File: `frontend/src/components/kiosk/StreetViewPanel.jsx` (405 lines).
   * Rendered in `KioskView.jsx` (line 455) and `MapBoard.jsx` (line 1382).
   * Static preview in `DashboardHUD.jsx` (lines 177-178, 297) uses Static Street View API `<img>` tag.

2. **SDK Loading & Initialization**:
   * Lines 174–190: Injects `<script id="google-maps-js-sdk" src="https://maps.googleapis.com/maps/api/js?key=${apiKey}">`.
   * Lines 125–136: Instantiates `new window.google.maps.StreetViewPanorama(targetContainer, options)`.
   * Lines 139–153 & 203–216: Resolves nearest outdoor panorama using `new window.google.maps.StreetViewService().getPanorama(...)`.

3. **Event Listener Bindings**:
   * Line 157: Binds `pano.addListener('pov_changed', ...)` capturing `heading`, `pitch`, `zoom`.
   * **Not bound**: `position_changed`, `pano_changed`, `zoom_changed`, `status_changed`, `visible_changed`.
   * Line 193: Cleanup returns `() => { if (targetContainer) targetContainer.innerHTML = ''; panoramaRef.current = null; };`. No `google.maps.event.clearInstanceListeners` call.

4. **Vantage Point State Storage**:
   * Line 32: `const currentPovRef = useRef({ heading: 0, pitch: 5, zoom: 1 });`.
   * Missing `lat`, `lng`, `pano_id`, and `fov` degrees in ref structure.
   * Lines 99–101: Overwrites ref with initial heading/pitch whenever `initialHeading`/`initialPitch` recalculates.

5. **"Save Preferred View" Handler**:
   * Lines 221–268 (`handleSaveView`):
     ```javascript
     const payload = {
       clean_address: cleanAddrKey,
       front_lat: saveLat,
       front_lng: saveLng,
       heading: currentHeading,
       pitch: currentPitch,
       fov: initialFov
     };
     ```
   * Saves to `localStorage` key `cfr_sv_override_${cleanAddrKey}`.
   * Sends POST request to `apiClient.streetView.saveOverride(payload)` (`/api/streetview-overrides`).

6. **HUD Skeleton & Lifecycle Artifacts**:
   * No dark HUD loading skeleton overlay currently exists in `StreetViewPanel.jsx`.
   * Container wipe `targetContainer.innerHTML = ''` occurs on lines 122 and 193.
   * Toggling `isExpanded` (lines 196 dependencies) destroys container DOM and creates a new `StreetViewPanorama` instance every time, accumulating WebGL contexts.

---

## 2. Logic Chain

1. **Observation 1 & 3 → Deficient Vantage Point Tracking (R1)**:
   Because only `pov_changed` is bound and `position_changed` / `pano_changed` / `zoom_changed` are missing, navigating down the road or zooming does not update the continuous vantage point. When the user clicks "Save Preferred View", the payload retains default/stale position and static initial FOV.
   *Ref: Observation 3, 4, 5.*

2. **Observation 2 & 5 → Non-Unified Database Persistence (R2 / R1)**:
   Because `handleSaveView` calls `/api/streetview-overrides` with a payload lacking `pano_id` and updated `streetview_fov`, saving a preferred view bypasses the unified `parcels` PostgreSQL table schema (`streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, `front_lng`).
   *Ref: Observation 5.*

3. **Observation 3 & 6 → WebGL Context Leaks & Flash Artifacts (R3, R4)**:
   Because `targetContainer.innerHTML = ''` is used for DOM cleanup without unbinding SDK event listeners or reusing panorama instances, toggling modal popout or switching dispatch calls creates redundant `StreetViewPanorama` instances. This exhausts browser WebGL contexts and displays default gray background flashes before 360° tiles load.
   *Ref: Observation 2, 3, 6.*

4. **Synthesis → Required Target Scope**:
   To satisfy R1, R3, and R4, `StreetViewPanel.jsx` must be overhauled to:
   - Bind `pov_changed`, `position_changed`, `pano_changed`, `zoom_changed`.
   - Store full camera vector (`lat`, `lng`, `heading`, `pitch`, `fov`, `pano_id`) continuously in refs.
   - Render a dark HUD skeleton overlay ("Loading Street View Facade...") with smooth fade transitions.
   - Clean up event listeners with `google.maps.event.clearInstanceListeners(pano)`.
   - Prevent WebGL context leaks across modal expand/collapse and call transitions.
   *Ref: Logic Chain steps 1–3.*

---

## 3. Caveats

- **Network Dependency**: Interactive 360° Street View requires an active internet connection and valid Google Maps JS API key (`VITE_GOOGLE_MAPS_API_KEY`). Offline mode correctly falls back to local building footprint canvas.
- **Backend Schema Sync**: Frontend payload structure must align with the PostgreSQL `parcels` table schema established by Explorer 1 (`streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, `front_lng`).

---

## 4. Conclusion

`frontend/src/components/kiosk/StreetViewPanel.jsx` is the core interactive Google Street View component requiring overhaul. Implementing R1, R3, and R4 requires adding standard JS SDK event listeners (`pov_changed`, `position_changed`, `pano_changed`, `zoom_changed`), tracking full camera vectors, displaying a dark HUD skeleton during tile load, performing clean event listener teardown, and preserving WebGL contexts across modal and call lifecycle transitions.

---

## 5. Verification Method

1. **Inspect Component File**:
   `view_file` on `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\frontend\src\components\kiosk\StreetViewPanel.jsx`.
2. **Inspect Analysis Report**:
   `view_file` on `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\explorer_survey_frontend\analysis.md`.
3. **Frontend Build Check**:
   Run `cd frontend && npm run build` to verify clean compilation without syntax or import errors.
