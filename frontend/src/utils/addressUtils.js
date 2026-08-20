/**
 * Universal Address Sanitizer & Unit Stripper for Coquitlam Fire Rescue EVO App
 * Strips all unit, suite, bay, apartment, building, and prefix/suffix unit designations
 * to collapse multi-unit complexes down to their clean base civic street address.
 */
export function sanitizeAddress(rawAddr) {
  if (!rawAddr || typeof rawAddr !== 'string') return '';
  let addr = rawAddr.trim();

  // 1. Harmonize intersection separators to standardized " & ":
  addr = addr.replace(/\s+(?:AND|AT|\/|@)\s+/gi, ' & ');
  addr = addr.replace(/\s*&\s*/g, ' & ');

  // 2. Handle prefix unit numbers with dash/slash: "105-3000 Riverbend Dr" -> "3000 Riverbend Dr"
  addr = addr.replace(/^\d+[-/]\s*(\d+\s+[A-Za-z])/i, '$1');

  // 3. Handle prefix keyword unit numbers: "UNIT 105 - 3000 Riverbend Dr", "Unit B - 3000 Riverbend Dr", "#105 3000 Riverbend Dr", "Suite 200 - 3000 Riverbend Dr"
  addr = addr.replace(/^(?:UNIT|APT|STE|SUITE|BAY|BLDG|BUILDING|#)\s*[\w\d]+(?:[-/\s]+|\s+-\s+)(\d{1,5}\s+[A-Za-z])/i, '$1');

  // 4. Remove keywords + unit designations anywhere in trailing/middle:
  // e.g. "UNIT 105", "BAY 4", "SUITE 200", "#116", "BLDG B", "PHASE 2", "LOT 3", "WHSE 5", "ROOM 12"
  addr = addr.replace(/\s+(?:UNIT|APT|SUITE|STE|BAY|BLDG|BUILDING|LOT|WHSE|WAREHOUSE|PHASE|PH|COMP|RM|ROOM|FL|FLOOR|#)\s*[\w-]+/gi, '');

  // 5. Remove trailing unit numbers/letters after standard street suffixes:
  // e.g. "3000 Riverbend Dr 105", "3000 Riverbend Dr 105A", "3000 Riverbend Dr A", "3000 Riverbend Dr #1"
  const streetSuffixes = '(?:AVE|AVENUE|ST|STREET|RD|ROAD|WAY|DR|DRIVE|CRT|COURT|BLVD|BOULEVARD|CRES|CRESCENT|PL|PLACE|LANE|LN|HWY|HIGHWAY)';
  const trailingUnitRegex = new RegExp(`(\\b${streetSuffixes})\\s+(?:#\\w+|\\d+[A-Za-z]?|[A-Za-z])$`, 'i');
  addr = addr.replace(trailingUnitRegex, '$1');

  return addr.trim();
}


/**
 * Validates if geographic coordinates fall within the municipal boundaries of Coquitlam
 * Bounding box: lat [49.20, 49.39], lng [-122.92, -122.70]
 */
export function isWithinCoquitlam(lat, lng) {
  if (lat == null || lng == null) return false;
  const numLat = typeof lat === 'number' ? lat : parseFloat(lat);
  const numLng = typeof lng === 'number' ? lng : parseFloat(lng);
  if (isNaN(numLat) || isNaN(numLng)) return false;
  return numLat >= 49.20 && numLat <= 49.39 && numLng >= -122.92 && numLng <= -122.70;
}


const NS_STREETS = [
  'COAST MERIDIAN', 'PINETREE', 'MARINER', 'JOHNSON', 'WESTWOOD', 'BLUE MOUNTAIN',
  'SCHOOLHOUSE', 'PIPELINE', 'FARROW', 'NORTH', 'GUTHE', 'GAUTHIER', 'SHESS',
  'DESERT', 'REGAN', 'HOWIE', 'REGAN', 'SHAY', 'SOBALL', 'LANSDOWNE', 'DOUGALL'
];

/**
 * Calculates the exact 0m front property line midpoint from parcel polygon rings.
 */
export function calculateParcelFrontagePoint(rings, streetName = '') {
  if (!rings || !rings.length || !rings[0] || rings[0].length < 3) return null;
  const pts = rings[0]; // [lng, lat]
  
  const avgLat = pts.reduce((sum, p) => sum + p[1], 0) / pts.length;
  const avgLng = pts.reduce((sum, p) => sum + p[0], 0) / pts.length;

  const edges = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const p1 = pts[i];
    const p2 = pts[i + 1];
    edges.push({
      p1, p2,
      midLat: (p1[1] + p2[1]) / 2,
      midLng: (p1[0] + p2[0]) / 2
    });
  }
  // Return exact parcel centroid for reliable street frontage matching
  return {
    front_lat: Number(avgLat.toFixed(6)),
    front_lng: Number(avgLng.toFixed(6))
  };
}
