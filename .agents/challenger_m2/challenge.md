# Adversarial Challenge Report — Milestone 2 & 3 (Frontend Street View Facade Engine)

**Target Component**: `frontend/src/components/kiosk/StreetViewPanel.jsx` & `frontend/src/apiClient.js`
**Target Worker**: Worker M2
**Challenger**: Challenger M2 (Empirical Challenger)
**Date**: 2026-08-13

---

## Challenge Summary

**Overall risk assessment**: MEDIUM

Worker M2 has implemented the core Google Maps JS SDK integration, continuous vector tracking via `currentPovRef`, dark HUD loading skeleton, `apiClient.parcels.lookup`, `apiClient.parcels.saveStreetView`, and `localStorage` fallback. The production frontend build (`npm run build`) compiles cleanly without errors.

However, empirical stress testing revealed a critical memory leak flaw: `google.maps.event.clearInstanceListeners` is **completely missing** from the `StreetViewPanel.jsx` cleanup routine when the component unmounts or re-renders.

---

## Stress Test Results

| Test Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| **1. REST API Endpoint & Payload Formatting** | `apiClient.parcels.saveStreetView` posts `{ clean_address, front_lat, front_lng, heading, pitch, fov, pano_id }` to `/api/parcels/streetview`. `lookup` calls `/api/parcels/lookup?query=...` | Requests formatted correctly with full schema fields and URL encoding | **PASS** |
| **2. Continuous Camera Vector State Updates** | Rapid pan, tilt, zoom, and street stepping events (10,000 continuous events) update `currentPovRef.current` in real time | 10,000 continuous updates processed in 7ms without state corruption or race conditions | **PASS** |
| **3. LocalStorage Vector Persistence & Fallback** | Instant local override retrieval (`cfr_sv_override_${cleanAddrKey}`) and fallback ordering (DB > LocalStorage > hardcoded > frontage angle) | `localStorage` getItem/setItem operational; fallback chain works seamlessly | **PASS** |
| **4. Build Execution** | `cmd /c npm run build` in `frontend/` succeeds | 0 errors, 416 modules transformed, dist artifacts generated | **PASS** |
| **5. Memory & Event Listener Cleanup** | Unmounting or re-rendering `StreetViewPanel` calls `google.maps.event.clearInstanceListeners(pano)` to prevent listener leaks in Google Maps SDK | `google.maps.event.clearInstanceListeners` is **missing** from `StreetViewPanel.jsx` cleanup | **FAIL** |

---

## Challenges

### [Medium] Challenge 1: Unbound Google Maps Event Listeners Cause Memory Leak on Re-renders & Unmounts

- **Assumption challenged**: Worker M2 assumed setting `panoramaRef.current = null` and clearing `targetContainer.innerHTML` was sufficient DOM and memory cleanup for `StreetViewPanorama`.
- **Attack scenario**: On apparatus kiosk displays, dispatches are launched, popped out into full-screen modals, closed, and reopened repeatedly. Each mount binds 5 SDK listeners (`pov_changed`, `position_changed`, `pano_changed`, `zoom_changed`, `status_changed`) to a new `StreetViewPanorama` instance.
- **Blast radius**: Without calling `google.maps.event.clearInstanceListeners(panoramaRef.current)` on unmount, Google Maps JS SDK retains references to old panorama instances and event handlers in internal listener tables, leading to progressive memory accumulation and degraded kiosk performance over long runtime shifts.
- **Mitigation**: Add explicit listener cleanup in the primary `useEffect` return block of `StreetViewPanel.jsx`:
  ```javascript
  return () => {
    if (panoramaRef.current && window.google?.maps?.event?.clearInstanceListeners) {
      window.google.maps.event.clearInstanceListeners(panoramaRef.current);
    }
    if (targetContainer) targetContainer.innerHTML = '';
    panoramaRef.current = null;
  };
  ```

---

## Unchallenged Areas

- **Dark HUD Loading Skeleton**: Loading indicator accurately renders when `isLoading` is true and transitions smoothly when `status_changed` fires `OK`.
- **Fallback Embed Rendering**: Embed iframe correctly activates when `!apiKey` or `sdkError` occurs.
