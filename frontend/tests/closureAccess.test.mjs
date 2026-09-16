import test from 'node:test';
import assert from 'node:assert/strict';
import {
  accessKey, accessStyle, passesAccessFilter, closureKey, sameClosure, ACCESS_UNKNOWN,
  closureText, NO_TEXT,
} from '../src/utils/closureAccess.js';

const ALL_OFF = { filterNoAccess: false, filterAccessOnly: false, filterCaution: false };
const ALL_ON = { filterNoAccess: true, filterAccessOnly: true, filterCaution: true };

test('the three feed states keep their labels', () => {
  assert.equal(accessStyle({ emergencyAccess: 'NO_ACCESS' }).label, 'FULL CLOSURE');
  assert.equal(accessStyle({ emergencyAccess: 'ACCESS_ONLY' }).label, 'EMERGENCY ACCESS ONLY');
  assert.equal(accessStyle({ emergencyAccess: 'CAUTION' }).label, 'LANE CLOSURE');
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
