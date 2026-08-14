# Changes Summary — Worker M2 (Frontend Street View Facade Engine & SDK Conformance)

## Files Modified

### 1. `frontend/src/apiClient.js`
- Added `apiClient.parcels` namespace with:
  - `lookup: async (query)` -> performs HTTP GET to `${API_BASE_URL}/api/parcels/lookup?query=${encodeURIComponent(query)}`
  - `saveStreetView: async (payload)` -> performs HTTP POST to `${API_BASE_URL}/api/parcels/streetview`
- Added `apiClient.streetviewOverrides` namespace with `get(address)` helper for backwards compatibility and seamless override fetching.

### 2. `frontend/src/components/kiosk/StreetViewPanel.jsx`
- Strictly aligned with Google Maps JS SDK (`window.google.maps.StreetViewPanorama`, `StreetViewService`).
- Implemented continuous vantage point vector tracking in `currentPovRef.current` with fields: `heading`, `pitch`, `zoom`/`fov`, `lat`, `lng`, `pano_id`.
- Bound all 5 required JS SDK event listeners:
  1. `pov_changed`: continuous heading & pitch updates
  2. `position_changed`: continuous lat/lng updates
  3. `pano_changed`: continuous pano_id & position updates
  4. `zoom_changed`: continuous zoom updates
  5. `status_changed`: monitor panorama readiness and control dark HUD loading skeleton
- On load: Resolves saved parcel camera override from `localStorage` (`cfr_sv_override_${cleanAddrKey}`), `apiClient.parcels.lookup`, and `apiClient.streetviewOverrides.get`.
- High-visibility `[SAVED PREFERRED VIEW]` indicator badge rendered in the HUD header title bar when a saved view exists.
- "Save Preferred View" handler:
  - Reads active camera vector directly from `currentPovRef.current` (and `panoramaRef.current` fallback getters).
  - Posts payload `{ clean_address, front_lat, front_lng, heading, pitch, fov, pano_id }` to `/api/parcels/streetview`.
  - Saves to `localStorage` under `cfr_sv_override_${cleanAddrKey}`.
  - Updates React state (`setDbOverride`) causing immediate appearance of the `[SAVED PREFERRED VIEW]` badge in HUD header.
- Added dark HUD loading skeleton ("Loading Street View Facade...") with smooth fade transition to satisfy R4 lifecycle requirements.

## Build Verification
- Executed `cmd /c npm run build` inside `frontend/` directory.
- Result: 0 JSX or syntax errors. 416 modules transformed successfully.
