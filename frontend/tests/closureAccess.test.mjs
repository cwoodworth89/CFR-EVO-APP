import test from 'node:test';
import assert from 'node:assert/strict';
import {
  accessKey, accessStyle, passesAccessFilter, closureKey, sameClosure, ACCESS_UNKNOWN,
  closureText, NO_TEXT, closureFeedCounts, ACCESS_INFO, roadRestriction, feedSeverityLine,
  DRIVEBC_SOURCE,
} from '../src/utils/closureAccess.js';

const ALL_OFF = { filterNoAccess: false, filterAccessOnly: false, filterCaution: false };
const ALL_ON = { filterNoAccess: true, filterAccessOnly: true, filterCaution: true };

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

test('each toggle governs only its own tier', () => {
  assert.equal(passesAccessFilter({ emergencyAccess: 'NO_ACCESS' }, { ...ALL_OFF, filterNoAccess: true }), true);
  assert.equal(passesAccessFilter({ emergencyAccess: 'NO_ACCESS' }, { ...ALL_ON, filterNoAccess: false }), false);
  assert.equal(passesAccessFilter({ emergencyAccess: 'ACCESS_ONLY' }, { ...ALL_ON, filterAccessOnly: false }), false);
  assert.equal(passesAccessFilter({ emergencyAccess: 'CAUTION' }, { ...ALL_ON, filterCaution: false }), false);
});

test('an N/A closure passes with every toggle off', () => {
  assert.equal(passesAccessFilter({ emergencyAccess: null }, ALL_OFF), true);
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
const ALL_TOGGLES_OFF = { filterNoAccess: false, filterAccessOnly: false, filterCaution: false };

test('MAJOR with all lanes open is INFO, not a tier, and passes every toggle', () => {
  const c = DBC({ feedSeverity: 'MAJOR', roadState: 'ALL_LANES_OPEN' });
  assert.equal(accessKey(c), ACCESS_INFO);
  assert.equal(accessStyle(c).label, 'INFO');
  assert.equal(roadRestriction(c), 'All lanes open');
  assert.equal(feedSeverityLine(c), 'DriveBC traffic impact: MAJOR');
  assert.equal(passesAccessFilter(c, ALL_TOGGLES_OFF), true);
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
