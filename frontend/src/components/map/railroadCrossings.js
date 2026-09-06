/**
 * Level crossings shown on the kiosk hazard layer. DISPLAY ONLY: the layer defaults to off
 * and no route avoids these points.
 *
 * Source: the operator, a 15-year member of the department, from the roads crews take; the
 * `avoidable` flags and notes are the operator's judgement of the alternatives (CLAUDE.md 6.3,
 * provenance 4, department operational knowledge). Confirmed 2026-09-05 against the
 * `railway=level_crossing` nodes of the OSM extract the kiosk routes on
 * (`tools/osm_level_crossings.py`): each point lies within 53 m of its crossing's nodes, one
 * node per track, named in `osmNodes`; all four hand points sit about 45 m west of the rails.
 * RR-01 and RR-02 are on the Port Coquitlam side of the City boundary, kept because crews
 * cross them.
 *
 * Not on this list, inside the City, from the same run: a disused CPKC spur across United
 * Boulevard (49.229873, -122.864847) and two CPKC spurs across unnamed service roads in the
 * industrial park north of it (49.231283, -122.863669 and 49.231724, -122.862323). The
 * operator has not ruled on them. Punch-list #21.
 */

export const COQUITLAM_RAILROAD_CROSSINGS = [
  { id: 'RR-01', osmNodes: [2339907118, 2339907122], name: 'Westwood St Crossing', lat: 49.2692679, lng: -122.7912637, location: 'Westwood St & Kingsway Ave', avoidable: true },
  { id: 'RR-02', osmNodes: [9034674729, 9034674727, 9034674728], name: 'Kingsway Ave Crossing', lat: 49.2650819, lng: -122.7911077, location: 'Kingsway Ave (Riverbend Corridor)', avoidable: false, note: 'Difficult to avoid for Riverbend' },
  { id: 'RR-03', osmNodes: [4353486403, 4353486401, 7280277992], name: 'Pitt River Rd Crossing', lat: 49.2505499, lng: -122.8016317, location: 'Pitt River Rd at CP Rail mainline', avoidable: true },
  { id: 'RR-04', osmNodes: [3685886502], name: 'Colony Farm Rd Crossing', lat: 49.2397800, lng: -122.8142995, location: 'Colony Farm Rd (Sole Access)', avoidable: false, note: 'Sole access road - Cannot route around' }
];
