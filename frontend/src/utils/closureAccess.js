/**
 * How a road closure's emergency access level is shown, in one place: the sidebar card,
 * the map marker's popup, the polyline colour and the access filters all read it here.
 *
 * Five states. The three access tiers (`emergencyAccess` from GET /api/road-closures), and
 * two for a null `emergencyAccess`, told apart by DriveBC's `roadState` (backend a002ce82):
 *   - INFO: `roadState` ALL_LANES_OPEN. The feed says the road is open; it is information,
 *     not a restriction. Operator ruling 2026-09-16 (#91 ruling 5): "All_lanes_open -> Info."
 *   - N/A: anything else with no tier -- the feed stated nothing usable. Operator ruling
 *     2026-09-16: "keep the box but add N/A". Before ea6151b9 an unknown was drawn as
 *     CAUTION in one place and NO_ACCESS in another.
 * Any `emergencyAccess` outside the three tiers is treated as null -- an unrecognised level
 * is not a level (CLAUDE.md 6.1).
 *
 * Colours are Tailwind's default palette, named per entry, matching what each file used
 * before this module existed.
 */

export const ACCESS_UNKNOWN = 'UNKNOWN';
export const ACCESS_INFO = 'INFO';

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
    // Operator ruling 2026-09-16 (#91 ruling 5): the CAUTION tier is "Caution - Restrictions".
    // Was LANE CLOSURE, which is false for a road closed in one direction (now CAUTION too).
    // One label for the tier, whichever feed it came from; the specific restriction, where
    // the feed states one, is printed beside it by roadRestriction().
    label: 'CAUTION – RESTRICTIONS',
    line: '#eab308',                // Tailwind yellow-500
    text: 'text-yellow-500',
    pill: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
    popupPill: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
  },
  [ACCESS_INFO]: {
    // Neutral and not a warning colour: an open road is not a tier. Distinct from N/A's slate
    // so "the feed says all lanes are open" never reads as "the feed said nothing".
    label: 'INFO',
    line: '#22d3ee',                // Tailwind cyan-400
    text: 'text-cyan-300',
    pill: 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/40',
    popupPill: 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40',
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

/**
 * The access key for a closure: one of the three tiers, ACCESS_INFO, or ACCESS_UNKNOWN.
 * `emergencyAccess: "INFO"` is served by the api from 2026-09-17 (gis-spatial-engineer: municipal
 * Info labels and DriveBC ALL_LANES_OPEN). The `roadState` inference stays so a frontend ahead of
 * that api still reads an all-lanes-open DriveBC event as Info.
 */
export function accessKey(closure) {
  const v = closure?.emergencyAccess;
  if (v === 'NO_ACCESS' || v === 'ACCESS_ONLY' || v === 'CAUTION') return v;
  if (v === 'INFO') return ACCESS_INFO;
  return closure?.roadState === 'ALL_LANES_OPEN' ? ACCESS_INFO : ACCESS_UNKNOWN;
}

/** Label and styling for a closure's access level. */
export function accessStyle(closure) {
  return ACCESS[accessKey(closure)];
}

/**
 * The four display buckets the closure sidebar's toggles name (operator ruling 2026-09-17):
 * Warning is NO_ACCESS and ACCESS_ONLY together ("both"), Caution is CAUTION, Info is INFO, and
 * Unspecified is everything the feed did not state (N/A). In this order everywhere: toggles,
 * grouping, counts.
 */
export const BUCKETS = Object.freeze(['WARNING', 'CAUTION', 'INFO', 'UNSPECIFIED']);

export const BUCKET_LABELS = Object.freeze({
  WARNING: 'Warning', CAUTION: 'Caution', INFO: 'Info', UNSPECIFIED: 'Unspecified',
});

/**
 * Which buckets show by default, every load (operator 2026-09-17: "Info/Low Impact events hidden
 * by default. Caution Events and Warning Events displayed by default"; Unspecified off, ruled
 * after). Not persisted: a hidden bucket is never carried over from an earlier session.
 */
export const DEFAULT_BUCKET_FILTER = Object.freeze({ WARNING: true, CAUTION: true, INFO: false, UNSPECIFIED: false });

/** Every bucket on: the dispatch display's route map, which has no filter controls. */
export const ALL_BUCKETS_ON = Object.freeze({ WARNING: true, CAUTION: true, INFO: true, UNSPECIFIED: true });

/** The bucket a closure belongs to. */
export function accessBucket(closure) {
  switch (accessKey(closure)) {
    case 'NO_ACCESS':
    case 'ACCESS_ONLY': return 'WARNING';
    case 'CAUTION': return 'CAUTION';
    case ACCESS_INFO: return 'INFO';
    default: return 'UNSPECIFIED';
  }
}

/**
 * Whether the bucket toggles let a closure through -- the one test both the sidebar list and the
 * map markers use, so the two can never disagree. No pass-through: a bucket that is off hides
 * its closures, Info and Unspecified included, and the toggle's count says how many.
 */
export function passesAccessFilter(closure, bucketFilter) {
  return Boolean(bucketFilter && bucketFilter[accessBucket(closure)]);
}

/** Closures per bucket, for the counts on the toggles: { WARNING: n, CAUTION: n, ... }. */
export function countByBucket(closures) {
  const counts = { WARNING: 0, CAUTION: 0, INFO: 0, UNSPECIFIED: 0 };
  for (const c of closures || []) counts[accessBucket(c)] += 1;
  return counts;
}

/**
 * One hall's closures as subgroups: bucket order, empty buckets left out, newest start first
 * inside each (a closure with no start sorts last, as the list did before).
 */
export function groupByBucket(closures) {
  const byBucket = { WARNING: [], CAUTION: [], INFO: [], UNSPECIFIED: [] };
  for (const c of closures || []) byBucket[accessBucket(c)].push(c);
  const startMs = (c) => {
    const t = c?.start instanceof Date ? c.start.getTime() : (c?.startDate ? new Date(c.startDate).getTime() : NaN);
    return Number.isFinite(t) ? t : -Infinity;
  };
  return BUCKETS
    .filter((b) => byBucket[b].length > 0)
    .map((b) => ({ bucket: b, closures: byBucket[b].slice().sort((x, y) => startMs(y) - startMs(x)) }));
}

/**
 * The key a closure is identified by in React lists and in map selection. `rowId` is the
 * database row (#91: stable across syncs, always sent) -- never shown in place of the feed's id.
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

/** Placeholder for a text field the feed did not send. */
export const NO_TEXT = '--';

/**
 * A closure text field (street, headline, description) as shown on the kiosk. Punch list
 * #91, operator ruling 2026-09-16: a field the feed sent nothing for arrives as null
 * (backend c8dc474d) and renders as "--", never a made-up string and never an empty slot.
 * Blank or whitespace-only strings are the same absence and render the same way.
 */
export function closureText(value) {
  if (value === null || value === undefined) return NO_TEXT;
  const text = String(value).trim();
  return text === '' ? NO_TEXT : text;
}

/**
 * Counts over the closures the API served, for the admin metrics panel's feed row (operator
 * 2026-09-16: "monitor for now and possibly we can create rules around patterns"). Every
 * number is a count of what was served, using the same tests the kiosk renders with, so a
 * count here always matches what the sidebar shows: `na` is what renders N/A, `noStreet` and
 * `noHeadline` are what render "--", `info` is what renders INFO. Null when there is no list,
 * never zeros.
 */
export function closureFeedCounts(closures) {
  if (!Array.isArray(closures)) return null;
  let na = 0, info = 0, noStreet = 0, noHeadline = 0;
  for (const c of closures) {
    const key = accessKey(c);
    if (key === ACCESS_UNKNOWN) na += 1;
    if (key === ACCESS_INFO) info += 1;
    if (closureText(c?.street) === NO_TEXT) noStreet += 1;
    if (closureText(c?.headline) === NO_TEXT) noHeadline += 1;
  }
  return { total: closures.length, na, info, noStreet, noHeadline };
}

/** `source` of a DriveBC record, as the backend stores it (backend/api/road_closure_service.py,
 *  the DriveBC ingest: "source": "DriveBC Open511"). */
export const DRIVEBC_SOURCE = 'DriveBC Open511';

// Open511 v1.0 roads[].direction (N..NE, NONE, BOTH), as bound directions for a crew.
const BOUND = {
  N: 'northbound', NE: 'northeast-bound', E: 'eastbound', SE: 'southeast-bound',
  S: 'southbound', SW: 'southwest-bound', W: 'westbound', NW: 'northwest-bound',
};

/**
 * The restriction DriveBC states for this closure, in words, or null when it states none.
 * Operator ruling 2026-09-16 (#91 ruling 5): "Closed per direction -> Caution - Restrictions,
 * and state the road closure direction. We often can go counterflow with the help of
 * flaggers." So a one-direction closure names its direction; the tier alone would not.
 * roadState values are Open511 v1.0 roads[].state. Null when the field is absent (an older
 * api, or Municipal 511, which never sends it) -- nothing is inferred from the tier.
 */
export function roadRestriction(closure) {
  switch (closure?.roadState) {
    case 'CLOSED': {
      const d = closure.roadDirection;
      if (BOUND[d]) return `Closed ${BOUND[d]}`;
      if (d === 'BOTH') return 'Closed both directions';
      return 'Closed';
    }
    case 'SOME_LANES_CLOSED': return 'Some lanes closed';
    case 'SINGLE_LANE_ALTERNATING': return 'Single lane alternating';
    case 'ALL_LANES_OPEN': return 'All lanes open';
    default: return null;
  }
}

/**
 * DriveBC's own severity word, as a line of information -- never a tier, never a colour.
 * Open511 v1.0 defines severity as traffic impact (MINOR "very limited impact on traffic" ..
 * MAJOR "a significant impact on traffic"), and the live feed on 2026-09-16 had 18 MAJOR events
 * with every lane open (#91 ruling 5), so the line says "traffic impact" to keep it from
 * being read as passability.
 * DriveBC record with the field sent: the word, or "--" when null. Anything else -- a
 * Municipal 511 record (not applicable there), or a response from an api that predates the
 * field -- returns null and no line is drawn.
 */
export function feedSeverityLine(closure) {
  if (closure?.source !== DRIVEBC_SOURCE || !('feedSeverity' in closure)) return null;
  return `DriveBC traffic impact: ${closureText(closure.feedSeverity)}`;
}
