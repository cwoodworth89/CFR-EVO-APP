# Progress — Explorer 2 (Frontend & JS SDK Specialist)

Last visited: 2026-08-13T23:47:30Z

- [x] Initialized DISPATCH.md, BRIEFING.md, and progress.md
- [x] Search for all Street View and Map components across `frontend/src`
- [x] Answer Question 1: What component renders Street View? (`StreetViewPanel.jsx` in `KioskView.jsx`, `MapBoard.jsx`, and popout modal)
- [x] Answer Question 2: How is Google Maps JS SDK loaded and initialized? (Dynamic `<script>` tag, `StreetViewPanorama`, `StreetViewService`)
- [x] Answer Question 3: Are event listeners bound for `pov_changed`, `position_changed`, `pano_changed`? (`pov_changed` bound; `position_changed`, `pano_changed`, `zoom_changed` missing)
- [x] Answer Question 4: How is continuous vantage point captured and stored? (`currentPovRef` stores heading/pitch/zoom, missing `lat`/`lng`/`pano_id`/`fov`)
- [x] Answer Question 5: How does "Save Preferred View" work? Payload & localStorage details (`handleSaveView` POSTs to `/api/streetview-overrides` and writes `cfr_sv_override_${address}`)
- [x] Answer Question 6: Loading skeleton / dark HUD implementation & lifecycle issues (missing dark HUD skeleton causing gray canvas flashes, destructive `innerHTML = ''` wipes, WebGL context accumulation across expand/reopen)
- [x] Answer Question 7: Identify all frontend files that need modification for R1, R3, R4 (`StreetViewPanel.jsx`, `apiClient.js`, `KioskView.jsx`, `MapBoard.jsx`)
- [x] Write analysis.md
- [x] Write handoff.md
- [x] Notify parent orchestrator
