# BRIEFING — 2026-08-14T17:07:12Z

## Mission
Investigate frontend architecture, dual-mode responsive layout (10-foot apparatus bay kiosk vs desktop console), component decomposition (e.g., DispatchReview.jsx), rapid reviewer ergonomics, offline Leaflet map rendering, UI/UX bottlenecks, and create refactoring roadmaps for CFR EVO v1.0.0.

## 🔒 My Identity
- Archetype: explorer
- Roles: Frontend & Kiosk Ergonomics Architecture Explorer
- Working directory: c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\explorer_frontend_kiosk\
- Original parent: 9e71722a-6cc5-41ba-84ca-e9bb05e668e2
- Milestone: v1.0.0 Frontend & Kiosk Ergonomics Architecture Investigation

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Local edits in our folder only (.agents/explorer_frontend_kiosk/)
- Adhere to GEMINI.md rules (API_BASE_URL resolution, no raw fetch, no external cloud dependencies, offline-first)

## Current Parent
- Conversation ID: 9e71722a-6cc5-41ba-84ca-e9bb05e668e2
- Updated: 2026-08-14T17:08:50Z

## Investigation State
- **Explored paths**:
  - `frontend/src/App.jsx`, `frontend/src/apiClient.js`, `frontend/src/components/MapBoard.jsx`
  - `frontend/src/components/DispatchReview.jsx` (1,602-line monolith analyzed)
  - `frontend/src/components/kiosk/` (`KioskView.jsx`, `RouteOverviewPanel.jsx`, `BlockParcelPanel.jsx`, `PropertySatellitePanel.jsx`, `StreetViewPanel.jsx`, `PrePlanModal.jsx`)
  - `frontend/src/components/MapLayers.jsx`, `frontend/src/components/MapConstants.js`, `frontend/src/components/DashboardHUD.jsx`, `frontend/src/components/RoutingOverlay.jsx`
  - `frontend/src/components/admin/` (`SimulationControl.jsx`, `SystemMetricsPanel.jsx`)
  - `frontend/src/hooks/` (`useKioskQueue.js`, `useDispatchListener.js`, `useMqttListener.js`, `useOnlineStatus.js`)
  - `frontend/src/utils/` (`EVORoutingEngine.js`, `addressUtils.js`)
- **Key findings**:
  - Dual-mode responsive ergonomics: Station bay 10-foot HUD (high contrast, ultra-bold text, 80px touch targets, hands-free auto-wake, 5-min timeout, queue chime) vs Workstation split-pane console.
  - Component decomposition roadmap for `DispatchReview.jsx` into `ReviewTable/`, `AudioPlayer/`, `VerificationSidebar/`, `Auth/`, and `ReviewContext`.
  - Rapid reviewer ergonomics: `Ctrl+Space` prefill, `Ctrl+Enter` submit, double-click import, `-5s` jump back, auto-advance, and `<35s` training cutoff protection.
  - Offline Leaflet rendering: dynamic `TILE_BASE_URL` on port 8081, `FallbackTileLayer` design, 100% offline local static GIS datasets (`hydrants.json`, `zones.json`, etc.).
  - Critical bugs identified: Rule 1 relative `fetch()` violations in `MapBoard.jsx` and `SystemMetricsPanel.jsx`, and external CDN marker icon URLs in kiosk panels.
- **Unexplored areas**: Backend OSRM Lua profile weighting and LoRA fine-tuning scripts (allocated to DSP/MLOps peers).

## Key Decisions Made
- Authored comprehensive architectural report in `report.md`.
- Formulated 5-component self-contained `handoff.md`.
- Assigned model tier cost allocations (Flash-Lite for bug fixes/icons, Flash for component decomposition, Pro for offline vector fallback).

## Artifact Index
- DISPATCH.md — Initial dispatch log
- BRIEFING.md — Working memory and status
- report.md — Comprehensive Frontend & Kiosk Ergonomics Architecture Report
- handoff.md — 5-component handoff report
