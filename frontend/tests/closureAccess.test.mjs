import test from 'node:test';
import assert from 'node:assert/strict';
import {
  accessKey, accessStyle, passesAccessFilter, closureKey, sameClosure, ACCESS_UNKNOWN,
  closureText, NO_TEXT, closureFeedCounts, ACCESS_INFO, roadRestriction, feedSeverityLine,
  DRIVEBC_SOURCE, accessBucket, countByBucket, groupByBucket, BUCKETS, DEFAULT_BUCKET_FILTER, ALL_BUCKETS_ON,
} from '../src/utils/closureAccess.js';

const ALL_OFF = { WARNING: false, CAUTION: false, INFO: false, UNSPECIFIED: false };
const ALL_ON = ALL_BUCKETS_ON;

test('the three feed states keep their labels', () => {
  assert.equal(accessStyle({ emergencyAccess: 'NO_ACCESS' }).label, 'FULL CLOSURE');
  assert.equal(accessStyle({ emergencyAccess: 'ACCESS_ONLY' }).label, 'EMERGENCY ACCESS ONLY');
  assert.equal(accessStyle({ emergencyAccess: 'CAUTION' }).label, 'CAUTION – RESTRICTIONS');
});

test('null, absent and unrecognised access are N/A, never a tier (#91)', () => {
  for (const c of [{ emergencyAccess: null }, {}, { emergencyAccess: 'MINOR' }, null]) {
    assert.equal(accessKey(c), ACCESS_UNKNOWN);
    assert.equal(accessStyle(c).label, 'N/A');
  }
});

test('N/A is visually distinct from every tier', () => {
  const na = accessStyle({ emergencyAccess: null });
  for (const k of ['NO_ACCESS', 'ACCESS_ONLY', 'CAUTION']) {
    const s = accessStyle({ emergencyAccess: k });
    assert.notEqual(na.line, s.line);
    assert.notEqual(na.pill, s.pill);
  }
});

test('four buckets: Warning is NO_ACCESS and ACCESS_ONLY; Info is INFO or all lanes open; the rest Unspecified', () => {
  assert.equal(accessBucket({ emergencyAccess: 'NO_ACCESS' }), 'WARNING');
  assert.equal(accessBucket({ emergencyAccess: 'ACCESS_ONLY' }), 'WARNING');
  assert.equal(accessBucket({ emergencyAccess: 'CAUTION' }), 'CAUTION');
  assert.equal(accessBucket({ emergencyAccess: 'INFO' }), 'INFO');                              // served from GIS's rebuild
  assert.equal(accessBucket({ emergencyAccess: null, roadState: 'ALL_LANES_OPEN' }), 'INFO');   // the api before it
  assert.equal(accessBucket({ emergencyAccess: null }), 'UNSPECIFIED');
  assert.equal(accessBucket({ emergencyAccess: 'SOMETHING_NEW' }), 'UNSPECIFIED');
  assert.equal(accessKey({ emergencyAccess: 'INFO' }), ACCESS_INFO);
  assert.equal(accessStyle({ emergencyAccess: 'INFO' }).label, 'INFO');
  assert.deepEqual(BUCKETS, ['WARNING', 'CAUTION', 'INFO', 'UNSPECIFIED']);
});

test('each toggle governs only its own bucket, with no pass-through', () => {
  for (const [c, bucket] of [
    [{ emergencyAccess: 'NO_ACCESS' }, 'WARNING'], [{ emergencyAccess: 'ACCESS_ONLY' }, 'WARNING'],
    [{ emergencyAccess: 'CAUTION' }, 'CAUTION'], [{ emergencyAccess: 'INFO' }, 'INFO'], [{ emergencyAccess: null }, 'UNSPECIFIED'],
  ]) {
    assert.equal(passesAccessFilter(c, { ...ALL_OFF, [bucket]: true }), true, bucket);
    assert.equal(passesAccessFilter(c, { ...ALL_ON, [bucket]: false }), false, bucket);
  }
  assert.equal(passesAccessFilter({ emergencyAccess: null }, ALL_OFF), false);   // N/A no longer passes by default
  assert.equal(passesAccessFilter({ emergencyAccess: 'CAUTION' }, null), false);
});

test('defaults: Warning and Caution on, Info and Unspecified off', () => {
  assert.deepEqual({ ...DEFAULT_BUCKET_FILTER }, { WARNING: true, CAUTION: true, INFO: false, UNSPECIFIED: false });
});

test('counts and grouping on both live shapes (today, and after GIS\'s rebuild)', () => {
  const at = (access, startDate) => ({ emergencyAccess: access, startDate });
  // Today: 67 N/A, 3 ACCESS_ONLY, 1 NO_ACCESS.
  const today = [...Array(67)].map(() => at(null)).concat([...Array(3)].map(() => at('ACCESS_ONLY')), [at('NO_ACCESS')]);
  assert.deepEqual(countByBucket(today), { WARNING: 4, CAUTION: 0, INFO: 0, UNSPECIFIED: 67 });
  assert.equal(today.filter((c) => passesAccessFilter(c, DEFAULT_BUCKET_FILTER)).length, 4);
  // After: ~48 CAUTION, 10 INFO, 10 N/A, 5 ACCESS_ONLY, 1 NO_ACCESS.
  const after = [...Array(48)].map(() => at('CAUTION')).concat(
    [...Array(10)].map(() => at('INFO')), [...Array(10)].map(() => at(null)), [...Array(5)].map(() => at('ACCESS_ONLY')), [at('NO_ACCESS')]);
  assert.deepEqual(countByBucket(after), { WARNING: 6, CAUTION: 48, INFO: 10, UNSPECIFIED: 10 });
  assert.equal(after.filter((c) => passesAccessFilter(c, DEFAULT_BUCKET_FILTER)).length, 54);
  // Grouping: bucket order, empty buckets absent, newest start first, no start last.
  const g = groupByBucket([
    at('CAUTION', '2026-09-01'), at(null, '2026-09-02'), at('NO_ACCESS', '2026-08-01'),
    at('ACCESS_ONLY', '2026-09-10'), at('CAUTION', null), at('CAUTION', '2026-09-05'),
  ]);
  assert.deepEqual(g.map((x) => x.bucket), ['WARNING', 'CAUTION', 'UNSPECIFIED']);
  assert.deepEqual(g[0].closures.map((c) => c.startDate), ['2026-09-10', '2026-08-01']);
  assert.deepEqual(g[1].closures.map((c) => c.startDate), ['2026-09-05', '2026-09-01', null]);
  assert.deepEqual(groupByBucket([]), []);
});

test('keys prefer rowId, fall back to id, and two unidentified closures never match', () => {
  assert.equal(closureKey({ rowId: 7, id: null }), 7);
  assert.equal(closureKey({ rowId: 7, id: 'DBC-1' }), 7);
  assert.equal(closureKey({ id: 'DBC-1' }), 'DBC-1');         // older api container
  assert.equal(sameClosure({ rowId: 7, id: null }, { rowId: 7, id: null }), true);
  assert.equal(sameClosure({ rowId: 7, id: null }, { rowId: 8, id: null }), false);
  assert.equal(sameClosure({ id: null }, { id: null }), false);
  assert.equal(sameClosure(null, { rowId: 1 }), false);
});

test('text the feed did not send renders as --, never a made-up string (#91)', () => {
  assert.equal(NO_TEXT, '--');
  for (const v of [null, undefined, '', '   ', '\n\t']) assert.equal(closureText(v), '--');
  assert.equal(closureText('LOUGHEED HWY'), 'LOUGHEED HWY');
  assert.equal(closureText('  Lane closed  '), 'Lane closed');
});

test('feed counts match what the kiosk renders, and no list is null not zero', () => {
  assert.equal(closureFeedCounts(null), null);
  assert.equal(closureFeedCounts(undefined), null);
  assert.deepEqual(closureFeedCounts([]), { total: 0, na: 0, info: 0, noStreet: 0, noHeadline: 0 });
  const served = [
    { emergencyAccess: 'NO_ACCESS', street: 'A ST', headline: 'Closed' },
    { emergencyAccess: null, street: 'B ST', headline: 'B ST' },
    { emergencyAccess: null, street: null, headline: null },
    { emergencyAccess: 'CAUTION', street: '  ', headline: 'Works' },
  ];
  assert.deepEqual(closureFeedCounts(served), { total: 4, na: 2, info: 0, noStreet: 2, noHeadline: 1 });
});

// DriveBC road-state contract, backend a002ce82, #91 ruling 5. Shapes are those the backend
// maps from the measured live feed (2026-09-16): emergencyAccess is what the backend derives.
const DBC = (over) => ({ source: DRIVEBC_SOURCE, emergencyAccess: null, roadState: null,
  roadDirection: null, feedSeverity: null, ...over });
test('MAJOR with all lanes open is INFO, not a tier, and follows the Info toggle', () => {
  const c = DBC({ feedSeverity: 'MAJOR', roadState: 'ALL_LANES_OPEN' });
  assert.equal(accessKey(c), ACCESS_INFO);
  assert.equal(accessStyle(c).label, 'INFO');
  assert.equal(roadRestriction(c), 'All lanes open');
  assert.equal(feedSeverityLine(c), 'DriveBC traffic impact: MAJOR');
  assert.equal(passesAccessFilter(c, DEFAULT_BUCKET_FILTER), false);   // Info is off by default
  assert.equal(passesAccessFilter(c, { ...DEFAULT_BUCKET_FILTER, INFO: true }), true);
});

test('MINOR, closed both directions, is NO ACCESS', () => {
  const c = DBC({ feedSeverity: 'MINOR', roadState: 'CLOSED', roadDirection: 'BOTH', emergencyAccess: 'NO_ACCESS' });
  assert.equal(accessStyle(c).label, 'FULL CLOSURE');
  assert.equal(roadRestriction(c), 'Closed both directions');
  assert.equal(feedSeverityLine(c), 'DriveBC traffic impact: MINOR');
});

test('closed northbound is Caution - Restrictions and names the direction', () => {
  const c = DBC({ roadState: 'CLOSED', roadDirection: 'N', emergencyAccess: 'CAUTION' });
  assert.equal(accessStyle(c).label, 'CAUTION – RESTRICTIONS');
  assert.equal(roadRestriction(c), 'Closed northbound');
  assert.equal(roadRestriction({ ...c, roadDirection: 'SW' }), 'Closed southwest-bound');
  assert.equal(roadRestriction({ ...c, roadDirection: 'NONE' }), 'Closed');
});

test('lane restrictions are stated in words', () => {
  assert.equal(roadRestriction(DBC({ roadState: 'SOME_LANES_CLOSED', emergencyAccess: 'CAUTION' })), 'Some lanes closed');
  assert.equal(roadRestriction(DBC({ roadState: 'SINGLE_LANE_ALTERNATING', emergencyAccess: 'CAUTION' })), 'Single lane alternating');
});

test('no road state is N/A, not INFO; a null DriveBC severity is --', () => {
  const c = DBC({});
  assert.equal(accessKey(c), ACCESS_UNKNOWN);
  assert.equal(roadRestriction(c), null);
  assert.equal(feedSeverityLine(c), 'DriveBC traffic impact: --');
});

test('municipal records and the old api shape draw no restriction or severity line', () => {
  const muni = { source: 'City of Coquitlam', emergencyAccess: null, roadState: null, roadDirection: null, feedSeverity: null };
  assert.equal(roadRestriction(muni), null);
  assert.equal(feedSeverityLine(muni), null);
  const oldDbc = { source: DRIVEBC_SOURCE, emergencyAccess: 'CAUTION' };  // fields absent
  assert.equal(roadRestriction(oldDbc), null);
  assert.equal(feedSeverityLine(oldDbc), null);
  assert.equal(accessStyle(oldDbc).label, 'CAUTION – RESTRICTIONS');
});

test('INFO and N/A are counted apart', () => {
  const served = [DBC({ roadState: 'ALL_LANES_OPEN' }), DBC({}), { source: 'City of Coquitlam', emergencyAccess: null }];
  const n = closureFeedCounts(served);
  assert.equal(n.info, 1);
  assert.equal(n.na, 2);
});
