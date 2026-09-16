/**
 * How a road closure's emergency access level is shown, in one place: the sidebar card,
 * the map marker's popup, the polyline colour and the access filters all read it here.
 *
 * Four states. The three the feed can state (`emergencyAccess` from GET /api/road-closures)
 * and a fourth, N/A, for a closure whose feed gave no usable severity. Punch list #91,
 * operator ruling 2026-09-16: "keep the box but add N/A". The API sends `null` for that
 * (backend `ea6151b9`); before it, an unknown was drawn as CAUTION in one place and
 * NO_ACCESS in another. Any value outside the three is treated the same as null -- an
 * unrecognised level is not a level (CLAUDE.md 6.1).
 *
 * Colours are Tailwind's default palette, named per entry, matching what each file used
 * before this module existed.
 */

export const ACCESS_UNKNOWN = 'UNKNOWN';

const ACCESS = {
  NO_ACCESS: {
    label: 'FULL CLOSURE',
    line: '#ef4444',                // Tailwind red-500
    text: 'text-red-500',
    pill: 'bg-red-500/10 text-red-400 border border-red-500/20',
    popupPill: 'bg-red-500/20 text-red-400 border border-red-500/30',
  },
  ACCESS_ONLY: {
    label: 'EMERGENCY ACCESS ONLY',
    line: '#f59e0b',                // Tailwind amber-500
    text: 'text-amber-500',
    pill: 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
    popupPill: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  },
  CAUTION: {
    label: 'LANE CLOSURE',
    line: '#eab308',                // Tailwind yellow-500
    text: 'text-yellow-500',
    pill: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
    popupPill: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
  },
  [ACCESS_UNKNOWN]: {
    // Neutral on purpose: none of red / amber / yellow, so it cannot be read as a tier.
    label: 'N/A',
    line: '#94a3b8',                // Tailwind slate-400
    text: 'text-slate-300',
    pill: 'bg-slate-500/10 text-slate-300 border border-slate-500/40',
    popupPill: 'bg-slate-500/20 text-slate-300 border border-slate-500/40',
  },
};

/** The access key for a closure: one of the three feed states, or ACCESS_UNKNOWN. */
export function accessKey(closure) {
  const v = closure?.emergencyAccess;
  return v === 'NO_ACCESS' || v === 'ACCESS_ONLY' || v === 'CAUTION' ? v : ACCESS_UNKNOWN;
}

/** Label and styling for a closure's access level. */
export function accessStyle(closure) {
  return ACCESS[accessKey(closure)];
}

/**
 * Whether the three access toggles let a closure through. An N/A closure always passes:
 * the operator ruled it is kept and shown, and no toggle names it, so hiding it behind
 * one would make an unknown disappear because a known tier was switched off.
 */
export function passesAccessFilter(closure, { filterNoAccess, filterAccessOnly, filterCaution }) {
  switch (accessKey(closure)) {
    case 'NO_ACCESS': return !!filterNoAccess;
    case 'ACCESS_ONLY': return !!filterAccessOnly;
    case 'CAUTION': return !!filterCaution;
    default: return true;
  }
}

/**
 * The key a closure is identified by in React lists and in map selection. `rowId` is the
 * database row (#91: stable across syncs, always sent) -- never shown as the feed's id.
 * Falls back to `id` for a response from an api container older than ea6151b9, and to
 * null when neither exists, so callers can refuse to match two unidentified closures.
 */
export function closureKey(closure) {
  return closure?.rowId ?? closure?.id ?? null;
}

/** Same closure? False when either is unidentified, so null never equals null. */
export function sameClosure(a, b) {
  const ka = closureKey(a);
  return ka !== null && ka === closureKey(b);
}
