# Handoff Report — Challenger M2 (Empirical Challenger)

## 1. Observation

- **Implementation Code Inspection**:
  - `frontend/src/components/kiosk/StreetViewPanel.jsx` lines 197-267 bind 5 SDK listeners:
    - `pano.addListener('pov_changed', ...)`
    - `pano.addListener('position_changed', ...)`
    - `pano.addListener('pano_changed', ...)`
    - `pano.addListener('zoom_changed', ...)`
    - `pano.addListener('status_changed', ...)`
  - `frontend/src/components/kiosk/StreetViewPanel.jsx` lines 297-300 cleanup block:
    ```javascript
    return () => {
      if (targetContainer) targetContainer.innerHTML = '';
      panoramaRef.current = null;
    };
    ```
    *Observation*: `google.maps.event.clearInstanceListeners(pano)` or `window.google.maps.event.clearInstanceListeners(panoramaRef.current)` is missing from the cleanup block.

- **Empirical Stress Test Suite Execution**:
  - Command: `cmd /c node run_empirical_tests.mjs` (cwd: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\challenger_m2`)
  - Output summary:
    - `apiClient.parcels.lookup` and `apiClient.parcels.saveStreetView` REST calls & payload schema: **PASS**
    - 10,000 rapid continuous pan, tilt, zoom, and street stepping events state updates in `currentPovRef`: **PASS** (completed in 7ms)
    - `localStorage` vector fallback persistence (`cfr_sv_override_${cleanAddrKey}`): **PASS**
    - Listener cleanup verification (`google.maps.event.clearInstanceListeners` in `StreetViewPanel.jsx`): **FAIL**

- **Frontend Build Execution**:
  - Command: `cmd /c npm run build` (cwd: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\frontend`)
  - Result: 0 errors, Exit code 0, 416 modules transformed.

## 2. Logic Chain

1. *Continuous Camera Vector Tracking*: `currentPovRef.current` correctly captures heading, pitch, zoom/fov, lat, lng, and pano_id across rapid event streams. `handleSaveView` constructs the correct payload (`{ clean_address, front_lat, front_lng, heading, pitch, fov, pano_id }`).
2. *REST API & LocalStorage Fallback*: `apiClient.parcels.lookup` and `apiClient.parcels.saveStreetView` correctly interface with FastAPI. Local storage fallback read/write correctly uses `cfr_sv_override_${cleanAddrKey}`.
3. *Build Execution*: The frontend application compiles cleanly using Vite (`npm run build`).
4. *Memory Leak Defect*: Because `google.maps.event.clearInstanceListeners` is not invoked during component unmount/re-render, attached event listeners accumulate in Google Maps JS SDK's internal event table on repeated modal toggles or call switches, violating the required memory cleanup standard.

## 3. Caveats

- Empirical tests used a mock Google Maps JS API environment in Node.js to simulate 10,000 continuous event firings and verify listener registration/deregistration.
- Physical kiosk multi-launch verification over Tailscale SSH requires active deployment after Worker M2 applies the cleanup fix.

## 4. Conclusion

The Street View facade panel implementation passes functional vector state tracking, REST payload formatting, fallback ordering, and build verification. However, due to the missing `google.maps.event.clearInstanceListeners` cleanup call in `StreetViewPanel.jsx`, the implementation fails memory leak requirements.

Worker M2 must add:
```javascript
if (panoramaRef.current && window.google?.maps?.event?.clearInstanceListeners) {
  window.google.maps.event.clearInstanceListeners(panoramaRef.current);
}
```
to the `useEffect` cleanup return function in `StreetViewPanel.jsx`.

**VERDICT: REQUEST_CHANGES**

## 5. Verification Method

1. Run the empirical stress harness:
   ```bash
   cd c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\challenger_m2
   cmd /c node run_empirical_tests.mjs
   ```
2. Verify frontend build:
   ```bash
   cd c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\frontend
   cmd /c npm run build
   ```
3. Inspect `frontend/src/components/kiosk/StreetViewPanel.jsx` cleanup block to confirm `clearInstanceListeners` is present.
