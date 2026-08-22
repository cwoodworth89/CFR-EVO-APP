/**
 * Level crossings shown on the kiosk hazard layer.
 *
 * ⚠️ UNSOURCED (CLAUDE.md §6.3). These four crossings are hand-entered, carry
 * seven-decimal coordinates with no stated origin, and no `avoidable` determination is
 * attributable to anything. Coquitlam very likely has more than four level crossings, and
 * an incomplete hazard layer is worse than an absent one, because a crew reading a clear
 * map concludes there is no crossing.
 *
 * CLAUDE.md §6.2 already names the authoritative source for exactly this data:
 * "rail crossings are `railway=level_crossing` in OSM, not `lat < 49.26`". This list is
 * the same defect one level up -- four hand-placed points standing in for the OSM layer.
 *
 * Currently DISPLAY ONLY: the layer defaults to off and nothing routes around these
 * points, so no apparatus route depends on them today. Tracked as punch-list #21. Left in
 * place rather than changed as a side effect of a lint extraction.
 */

export const COQUITLAM_RAILROAD_CROSSINGS = [
  { id: 'RR-01', name: 'Westwood St Crossing', lat: 49.2692679, lng: -122.7912637, location: 'Westwood St & Kingsway Ave', avoidable: true },
  { id: 'RR-02', name: 'Kingsway Ave Crossing', lat: 49.2650819, lng: -122.7911077, location: 'Kingsway Ave (Riverbend Corridor)', avoidable: false, note: 'Difficult to avoid for Riverbend' },
  { id: 'RR-03', name: 'Pitt River Rd Crossing', lat: 49.2505499, lng: -122.8016317, location: 'Pitt River Rd at CP Rail mainline', avoidable: true },
  { id: 'RR-04', name: 'Colony Farm Rd Crossing', lat: 49.2397800, lng: -122.8142995, location: 'Colony Farm Rd (Sole Access)', avoidable: false, note: 'Sole access road - Cannot route around' }
];
