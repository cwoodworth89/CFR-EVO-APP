# Quality & Adversarial Review Report — Milestone 2 & 3 (Frontend Street View Facade Engine & HUD Lifecycle)

**Reviewer**: Reviewer M2  
**Date**: 2026-08-14T00:05:00Z  
**Target Files**:
- `frontend/src/apiClient.js`
- `frontend/src/components/kiosk/StreetViewPanel.jsx`

---

## Review Summary

**Verdict**: **APPROVE**

Worker M2 has implemented all frontend features for Milestone 2 & 3 in accordance with Google Maps Platform JS SDK guidelines, UI/UX requirements, and project architectural rules. Build verification passed cleanly with zero errors.

---

## Verified Claims & Requirements

| Requirement / Claim | Verification Method | Status | Notes |
|---|---|---|---|
| **1. Standard SDK Usage** (`StreetViewPanorama`, `StreetViewService`) | Code inspection of `StreetViewPanel.jsx` (Lines 168, 171, 178) | **PASS** | Correctly initializes standard `google.maps.StreetViewPanorama` and `google.maps.StreetViewService` without private API hacks or brittle DOM overrides. |
| **2. Continuous Vantage Point Capture** (`heading`, `pitch`, `zoom`, `lat`, `lng`, `pano_id`) | Code inspection of event listeners (Lines 197-267) | **PASS** | All 5 event listeners (`pov_changed`, `position_changed`, `pano_changed`, `zoom_changed`, `status_changed`) bound and update `currentPovRef.current` in real time. |
| **3. Dark HUD Loading Skeleton** ("Loading Street View Facade...") | Code inspection of skeleton loader UI (Lines 409-417) | **PASS** | Sleek `bg-slate-950` overlay with animated spinner and pulsing text "Loading Street View Facade..." renders while `isLoading` is active. |
| **4. `[SAVED PREFERRED VIEW]` Indicator Badge** | Code inspection of header and overlay badges (Lines 455-459, 496-500, 535-539) | **PASS** | Prominently displays pulsing emerald `[SAVED PREFERRED VIEW]` badge in card header, overlay, and popout modal whenever a saved parcel override exists. |
| **5. Build Verification** (`cmd /c npm run build` in `frontend/`) | Terminal execution | **PASS** | Build completed in 3.48s with exit code 0, transforming 416 modules with zero errors. |

---

## Integrity Audit

- **Hardcoded test results / facade implementations**: Checked. No fake test results or bypass logic found. Fallback coordinate map (`STREETVIEW_OVERRIDES`) is standard offline fallback for local station dev, while live pathing connects dynamically to `apiClient.parcels.lookup` and `apiClient.parcels.saveStreetView`.
- **Shortcut / Delegation bypasses**: Checked. Full event handling and SDK integration implemented natively.
- **Fabricated verification outputs**: Verified build output independently via `npm run build`.

---

## Adversarial Stress-Testing & Edge Cases

### 1. Rapid Address Switch & Unmount Safety
- **Scenario**: User switches dispatch calls rapidly or toggles full-screen popout modal while panorama tiles are loading.
- **Assessment**: The cleanup function in `useEffect` (line 298) clears `targetContainer.innerHTML = ''` and resets `panoramaRef.current = null`. `isMounted` flags in async lookup chains prevent state updates on unmounted components.

### 2. Network Instability / API Failure Fallback
- **Scenario**: Parcel API request fails or station is temporarily offline when user clicks "Save Preferred View".
- **Assessment**: `handleSaveView` saves camera vectors to `localStorage` key `cfr_sv_override_${cleanAddrKey}` first before making network calls. Even if network post fails, local state and `localStorage` preserve the saved view for immediate UI consistency.

### 3. API Key Missing / SDK Error Fallback
- **Scenario**: `VITE_GOOGLE_MAPS_API_KEY` is not provided or Google Maps SDK fails to load / auth fails (`gm_authFailure`).
- **Assessment**: Global `window.gm_authFailure` handler sets `sdkError = true`. The component gracefully falls back to an `iframe` embed or offline footprint canvas without crashing the UI.

---

## Recommendations & Minor Enhancements (Non-Blocking)

- None required for approval. The implementation is clean, robust, and meets all criteria.
