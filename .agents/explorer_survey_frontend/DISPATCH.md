## 2026-08-13T23:45:02Z
<USER_REQUEST>
You are Explorer 2 (Frontend & JS SDK Specialist).

Your assigned working directory is: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\explorer_survey_frontend\`

Read the verbatim user request from: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`
Also review `GEMINI.md` for workspace rules.

Your mission:
Investigate the frontend Google Street View facade inspection components, Google Maps JS SDK integration, state management, HUD skeleton, and rendering lifecycle.

Investigate and document:
1. What component renders Street View? (Check `frontend/src/components/kiosk/StreetViewPanel.jsx` and any related components/modals).
2. How is Google Maps JS SDK loaded and initialized (`window.google.maps.StreetViewPanorama`, `StreetViewService`)?
3. Are event listeners bound for `pov_changed`, `position_changed`, `pano_changed`?
4. How is continuous vantage point (heading, pitch, zoom/fov, lat, lng, pano_id) captured and stored in state/refs?
5. How does "Save Preferred View" work? What payload is sent to the backend API and saved to `localStorage`?
6. How is the loading skeleton / dark HUD currently implemented? Are there gray/blank canvas flashes, `innerHTML` container wipes, or WebGL context leaks across open/close/reopen?
7. Identify all frontend files that need modification for R1, R3, R4.

Write your findings in:
`c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\explorer_survey_frontend\analysis.md`
Write your handoff report in:
`c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\explorer_survey_frontend\handoff.md`

Update `progress.md` in your working directory as you work. When done, send a summary message back to orchestrator.
</USER_REQUEST>
