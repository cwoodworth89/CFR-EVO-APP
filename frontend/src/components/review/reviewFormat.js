/**
 * Timestamp formatting and tone derivation for the call review surfaces.
 *
 * Extracted from ReviewTable.jsx. `getCallTones` is also used by DispatchReview.jsx, so it
 * was already shared across components while living in one of them.
 */

// Helper to format timestamps to Pacific Time matching database and local logs
export const formatTimestampPT = (ts) => {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return ts;
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Los_Angeles',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    
    const parts = formatter.formatToParts(d);
    const partMap = {};
    parts.forEach(p => { partMap[p.type] = p.value; });
    
    return `${partMap.year}-${partMap.month}-${partMap.day} ${partMap.hour}:${partMap.minute}:${partMap.second}`;
  } catch {
    try {
      const d = new Date(ts);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
    } catch {
      return ts;
    }
  }
};

export const deriveTonesFromUnitsList = (units) => {
  if (!Array.isArray(units)) return [];
  const derived = [];
  units.forEach(u => {
    const lowerUnit = String(u).trim().toLowerCase();
    if (lowerUnit.startsWith('e') || lowerUnit.includes('engine')) {
      derived.push('engine');
    }
    if (lowerUnit.startsWith('m') || lowerUnit.startsWith('r') || lowerUnit.includes('medic') || lowerUnit.includes('rescue')) {
      derived.push('rescue');
    }
    if (lowerUnit.startsWith('c') || lowerUnit.includes('car') || lowerUnit.includes('chief')) {
      derived.push('chief');
    }
  });
  return derived;
};

export const getCallTones = (call) => {
  if (!call) return [];
  const dbTones = (call.target?.tone_name || '')
    .split(',')
    .map(t => {
      const clean = t.trim().toLowerCase();
      if (clean.includes('chief')) return 'chief';
      if (clean.includes('engine')) return 'engine';
      if (clean.includes('rescue')) return 'rescue';
      return clean;
    })
    .filter(Boolean);
  const units = (call.verified_units && call.verified_units.length > 0)
    ? call.verified_units
    : (call.responding_units || []);
  const derived = deriveTonesFromUnitsList(units);
  return Array.from(new Set([...dbTones, ...derived]));
};
