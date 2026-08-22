/**
 * Apparatus profile seed data for the routing configuration surface.
 *
 * Extracted from RoutingConfigModal.jsx for `react-refresh/only-export-components`.
 */

// STAGED SEED DATA -- NOT APPLIED (CLAUDE.md §6.4).
//
// `speedRatio` is displayed by RoutingConfigModal and is read by nothing else: verified
// 2026-08-22, the only reference outside this file is the modal's own render. No routing
// calculation multiplies by it, and reported ETAs remain stock OSRM.
//
// The values carry NO provenance. 0.88 for an aerial and 0.82 for a tender are not
// sourced from apparatus specifications, department policy, or measurement on this
// system, and they must not be applied to routing until they are (§6.3). This is the
// third copy of the same idea -- see APPARATUS_TIERS in
// services/gis/src/gis_service/routing_engine.py and frontend/src/utils/EVORoutingEngine.js,
// both likewise documented as staged and not applied.
export const APPARATUS_PROFILES = [
  { id: 'ENGINE', name: 'Engine (E1/E2/E3/E4)', icon: '🚒', speedRatio: 1.0, weight: 'Heavy Pumper' },
  { id: 'LADDER', name: 'Aerial Ladder (L1)', icon: '🪜', speedRatio: 0.88, weight: '100ft Heavy Tower (Turn Restrictions)' },
  { id: 'RESCUE', name: 'Heavy Rescue (R1)', icon: '🛟', speedRatio: 0.95, weight: 'Tandem Axle Rescue' },
  { id: 'TENDER', name: 'Water Tender (WT1)', icon: '💧', speedRatio: 0.82, weight: 'Bulk Liquid Pumper' },
];
