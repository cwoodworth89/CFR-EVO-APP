# Original User Request

## Initial Request — 2026-08-13T23:44:34Z

# Complete Google Street View Facade Engine Overhaul & Property Table Persistence

Overhaul the CFR EVO Google Street View Facade Inspection panel to provide deterministic touch/mouse 360° vantage point exploration, atomic persistence to the unified `parcels` property intelligence table in PostgreSQL, seamless cache synchronization, and flawless multi-launch rendering lifecycle across apparatus kiosks.

Working directory: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP`
Integrity mode: benchmark

## Requirements

### R1. Complete Vantage Point Capture (Position + Orientation + Zoom)
The Street View panel must continuously track both the active street panorama location (`lat`, `lng`, `pano_id`) and camera orientation (`heading`, `pitch`, `zoom`/`fov`) as the user moves down the road or pans around, enabling reviewers to capture the single clearest vantage point of the building facade.

### R2. Unified `parcels` Property Database Table & Migration
Ensure the primary **`parcels`** table is created and indexed in PostgreSQL 16 (`cfr_dispatch` database). Tapping "Save Preferred View" must write camera vectors (`streetview_heading`, `streetview_pitch`, `streetview_fov`, `front_lat`, `front_lng`) directly into the property's record in `parcels` (alongside future tactical fields like `lock_box_notes`, `hazard_notes`, and `pre_plan_pdf_url`), with normalized address matching (`3030 GORDON AVE`).

### R3. Standard Google Maps Platform SDK Conformance
Adhere strictly to official, standard Google Maps Platform JavaScript API patterns (`google.maps.StreetViewPanorama`, `google.maps.StreetViewService`, `pov_changed`, `position_changed`, `pano_changed`). Avoid esoteric, brittle hacks, or non-standard DOM manipulation.

### R4. Resilient Multi-Launch Rendering Lifecycle & HUD Skeleton
When opening, exiting, and reopening any dispatch call (in simulation mode or live dispatch HUD), the panel must display a sleek dark HUD loading skeleton ("Loading Street View Facade...") until the 360° tiles are ready, smoothly fading into the panorama without blank/gray canvas flashes, WebGL context disposal race conditions, or `innerHTML` container wipes.

### R5. Controlled Remote Full-Stack Verification
All changes must be validated locally via automated endpoint/build tests and deployed over Tailscale SSH to the physical station kiosk host (`tcfire@100.95.146.94`) for end-to-end multi-launch verification.

## Acceptance Criteria

### Interactive Facade Inspection & Property Persistence
- [ ] PostgreSQL `parcels` table is created and populated with address indexing.
- [ ] Dragging/swiping, tilting, stepping down the road, and zooming update camera orientation in real time.
- [ ] Clicking "Save Preferred View" atomically updates the property record in `parcels` with exact road coordinates, heading, pitch, and zoom.
- [ ] Database lookup endpoint (`GET /api/parcels/lookup?query={address}` and `/api/streetview-overrides/{address}`) returns the saved property vantage point.
- [ ] Exiting and reopening the call immediately loads the saved vantage point with the `[SAVED PREFERRED VIEW]` indicator.
- [ ] Initial panorama loading displays a dark HUD skeleton and transitions into the 360° view without blank/gray canvas screens.
- [ ] Verified across multiple consecutive dispatch simulations on the physical kiosk display (`100.95.146.94`).
