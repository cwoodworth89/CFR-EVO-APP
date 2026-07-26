/**
 * Universal Address Sanitizer & Unit Stripper for Coquitlam Fire Rescue EVO App
 * Strips all unit, suite, bay, apartment, building, and prefix/suffix unit designations
 * to collapse multi-unit complexes down to their clean base civic street address.
 */
export function sanitizeAddress(rawAddr) {
  if (!rawAddr || typeof rawAddr !== 'string') return '';
  let addr = rawAddr.trim();

  // 1. Handle prefix unit numbers: "105-3000 Riverbend Dr" -> "3000 Riverbend Dr"
  addr = addr.replace(/^\d+[-/]\s*(\d+\s+[A-Za-z])/i, '$1');

  // 2. Handle prefix keyword unit numbers: "UNIT 105 - 3000 Riverbend Dr" -> "3000 Riverbend Dr"
  addr = addr.replace(/^(?:UNIT|APT|STE|SUITE|BAY|#)\s*\w+[-/\s]+(\d{1,5}\s+[A-Za-z])/i, '$1');

  // 3. Remove keywords + unit designations anywhere in trailing/middle:
  // e.g. "UNIT 105", "BAY 4", "SUITE 200", "#116", "BLDG B", "PHASE 2", "LOT 3", "WHSE 5", "ROOM 12"
  addr = addr.replace(/\s+(?:UNIT|APT|SUITE|STE|BAY|BLDG|BUILDING|LOT|WHSE|WAREHOUSE|PHASE|PH|COMP|RM|ROOM|FL|FLOOR|#)\s*[\w-]+/gi, '');

  // 4. Remove trailing unit numbers/letters after street suffixes:
  // e.g. "3000 Riverbend Dr 105", "3000 Riverbend Dr 105A", "3000 Riverbend Dr A", "3000 Riverbend Dr #1"
  const streetSuffixes = '(AVE|AVENUE|ST|STREET|RD|ROAD|WAY|DR|DRIVE|CRT|COURT|BLVD|BOULEVARD|CRES|CRESCENT|PL|PLACE|LANE|LN|HWY|HIGHWAY)';
  const trailingUnitRegex = new RegExp(`(\\b${streetSuffixes}\\b)\\s+(?:#?\\s*\\w+)+$`, 'i');
  addr = addr.replace(trailingUnitRegex, '$1');

  return addr.trim();
}
