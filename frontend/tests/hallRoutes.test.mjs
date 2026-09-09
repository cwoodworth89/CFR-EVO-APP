import { test } from 'node:test';
import assert from 'node:assert/strict';
import { hallRoutesToDraw } from '../src/utils/hallRoutes.js';

const KNOWN = ['1', '2', '3', '4'];

test('home hall is drawn last (on top) and always present, even with no metrics', () => {
  const out = hallRoutesToDraw({ routingMetrics: [], homeHall: '2', knownHalls: KNOWN });
  assert.deepEqual(out.map(e => e.hall), ['2']);
  assert.equal(out[0].isHome, true);
  assert.equal(out[0].etaMinutes, null);
});

test('other halls are ordered later ETA first, sooner on top, home last', () => {
  // 808 Miller Ave, 2026-09-07: Q5/E3 from Hall 3, E2/R2 from Hall 2, L1/C5 from Hall 1.
  const metrics = [
    { unit: 'Q5', origin_hall: 3, eta_minutes: 4 },
    { unit: 'E3', origin_hall: 3, eta_minutes: 4 },
    { unit: 'E2', origin_hall: 2, eta_minutes: 6 },
    { unit: 'R2', origin_hall: 2, eta_minutes: 6 },
    { unit: 'L1', origin_hall: 1, eta_minutes: 9 },
    { unit: 'C5', origin_hall: 1, eta_minutes: 9 },
  ];
  const out = hallRoutesToDraw({ routingMetrics: metrics, homeHall: '3', knownHalls: KNOWN });
  assert.deepEqual(out.map(e => e.hall), ['1', '2', '3']);
  assert.deepEqual(out.map(e => e.isHome), [false, false, true]);
  assert.deepEqual(out[0].units, ['L1', 'C5']);
  assert.equal(out[1].etaMinutes, 6);
});

test('a hall with no ETA sits at the bottom; the home hall on top even when it is the slowest', () => {
  const metrics = [
    { unit: 'E1', origin_hall: 1, eta_minutes: 12 },
    { unit: 'E4', origin_hall: 4, eta_minutes: null },
    { unit: 'E2', origin_hall: 2, eta_minutes: 3 },
  ];
  const out = hallRoutesToDraw({ routingMetrics: metrics, homeHall: '1', knownHalls: KNOWN });
  assert.deepEqual(out.map(e => e.hall), ['4', '2', '1']);
});

test('units without a hall, and halls that do not exist, contribute nothing', () => {
  const metrics = [
    { unit: 'X9', eta_minutes: 2 },
    { unit: 'E7', origin_hall: 7, eta_minutes: 2 },
    { unit: 'E2', origin_hall: '2', eta_minutes: 5 },
  ];
  const out = hallRoutesToDraw({ routingMetrics: metrics, homeHall: '1', knownHalls: KNOWN });
  assert.deepEqual(out.map(e => e.hall), ['2', '1']);
});

test('the per-hall ETA is the soonest of its units, and units are not repeated', () => {
  const metrics = [
    { unit: 'E2', origin_hall: 2, eta_minutes: 7 },
    { unit: 'L2', origin_hall: 2, eta_minutes: 5 },
    { unit: 'e2', origin_hall: 2, eta_minutes: 7 },
  ];
  const out = hallRoutesToDraw({ routingMetrics: metrics, homeHall: '1', knownHalls: KNOWN });
  const h2 = out.find(e => e.hall === '2');
  assert.equal(h2.etaMinutes, 5);
  assert.deepEqual(h2.units, ['E2', 'L2']);
});
