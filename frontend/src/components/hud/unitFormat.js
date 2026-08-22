/**
 * Apparatus callsign and ETA formatting for the 10-foot kiosk HUD.
 *
 * Extracted from ActiveAlertBanner.jsx: pure functions, no JSX, and exporting them from a
 * component file is what `react-refresh/only-export-components` flags.
 */

// Unit styling for 10-foot high-visibility apparatus bay ergonomics
export const getUnitBadgeStyle = (unitStr) => {
  const u = (unitStr || '').toUpperCase().trim();
  if (u.startsWith('E') || u.startsWith('ENG') || u.includes('ENGINE')) {
    return 'bg-orange-500/20 text-orange-400 border-orange-500/50';
  }
  if (u.startsWith('R') || u.startsWith('RESCUE') || u.includes('RESCUE')) {
    return 'bg-rose-500/20 text-rose-400 border-rose-500/50';
  }
  if (u.startsWith('L') || u.startsWith('TR') || u.includes('LADDER') || u.includes('TRUCK')) {
    return 'bg-sky-500/20 text-sky-300 border-sky-500/50';
  }
  if (u.startsWith('C') || u.startsWith('CHIEF') || u.includes('CHIEF') || u.startsWith('B')) {
    return 'bg-amber-500/20 text-amber-300 border-amber-500/50';
  }
  if (u.startsWith('M') || u.startsWith('MEDIC') || u.startsWith('S') || u.startsWith('AMB')) {
    return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50';
  }
  return 'bg-slate-800 text-slate-200 border-slate-700';
};

export const getShortCallsign = (unitStr) => {
  const u = (unitStr || '').trim().toUpperCase();
  if (!u) return '';
  const numMatch = u.match(/\d+/);
  const num = numMatch ? numMatch[0] : '';

  if (u.includes('ENGINE') || u.startsWith('ENG') || u.startsWith('E')) return `E${num || u}`;
  if (u.includes('RESCUE') || u.startsWith('R')) return `R${num || u}`;
  if (u.includes('LADDER') || u.includes('TRUCK') || u.startsWith('L')) return `L${num || u}`;
  if (u.includes('CHIEF') || u.startsWith('C')) return `C${num || u}`;
  if (u.includes('MEDIC') || u.startsWith('M')) return `M${num || u}`;
  return u;
};

export const formatUnitEtaDisplay = (etaMin) => {
  // No fabricated placeholder: an unknown ETA renders as '--:--', never a plausible number.
  if (etaMin == null || isNaN(etaMin)) return '--:--';
  const totalSec = Math.round(etaMin * 60);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  const padM = String(mins).padStart(2, '0');
  const padS = String(secs).padStart(2, '0');
  return `${padM}:${padS}`;
};
