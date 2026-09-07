// node --test frontend/tests  (npm run test:node). Pure geometry, no browser.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pickRouteHydrants, APPROACH_M, SUPPLY_M, ROUTE_BAND_M, TIER } from '../src/utils/routeHydrants.js';

// A straight east-west road at lat 49.30 ending at the address at lng -122.8000.
// One degree of longitude here is about 72.6 km, so 0.001 deg is ~72.6 m.
const DEST = { lat: 49.3, lng: -122.8 };
const M_PER_DEG_LNG = 111320 * Math.cos((49.3 * Math.PI) / 180);
const east = (m) => DEST.lng + m / M_PER_DEG_LNG;             // metres east of the address
const north = (m) => DEST.lat + m / 110540;
const route = [{ lat: 49.3, lng: east(-2000) }, { lat: 49.3, lng: east(-500) }, { lat: 49.3, lng: DEST.lng }];
const hyd = (id, lat, lng, extra = {}) => ({ gisId: id, status: 'OPERATING', flowClass: 'A', lat, lng, ...extra });

test('choice #1 is the last hydrant passed, #2 the one before it, both within 300 ft of arrival', () => {
  const hydrants = [
    hyd('H40', north(6), east(-40)),     // 40 m before arrival, 6 m off the road
    hyd('H80', north(-8), east(-80)),    // 80 m before arrival
    hyd('H200', north(5), east(-200)),   // 200 m before: past 300 ft, not a choice
    hyd('FAR', north(60), east(-30)),    // 60 m off the road: not along it
  ];
  const r = pickRouteHydrants({ hydrants, routeCoords: route, destination: DEST });
  assert.equal(r.tier, TIER.APPROACH);
  assert.deepEqual(r.picks.map(p => p.gisId), ['H40', 'H80']);
  assert.equal(r.picks[0].beforeArrivalM, 40);
  assert.equal(r.picks[0].offRouteM, 6);
  assert.ok(r.picks.every(p => p.beforeArrivalM <= APPROACH_M && p.offRouteM <= ROUTE_BAND_M));
});

test('nothing on the approach: the one just past the address is found straight-line', () => {
  const hydrants = [hyd('PAST', north(3), east(45)), hyd('H200', north(5), east(-200))];
  const r = pickRouteHydrants({ hydrants, routeCoords: route, destination: DEST });
  assert.equal(r.tier, TIER.NEAR);
  assert.deepEqual(r.picks.map(p => p.gisId), ['PAST']);
  assert.equal(r.picks[0].distance, 45);
});

test('nothing within 300 ft: a hydrant within the 1,000 ft supply lay is reported as that', () => {
  const hydrants = [hyd('SUPPLY', north(0), east(250))];
  const r = pickRouteHydrants({ hydrants, routeCoords: route, destination: DEST });
  assert.equal(r.tier, TIER.SUPPLY);
  assert.equal(r.picks[0].gisId, 'SUPPLY');
  assert.ok(r.picks[0].distance <= SUPPLY_M);
});

test('nothing within 1,000 ft is the warning, and a NOT READY hydrant never counts', () => {
  const hydrants = [hyd('DEAD', north(4), east(-30), { status: 'NOT READY' }), hyd('FAR', north(0), east(400))];
  const r = pickRouteHydrants({ hydrants, routeCoords: route, destination: DEST });
  assert.equal(r.tier, TIER.NONE);
  assert.deepEqual(r.picks, []);
});

test('no route yet: the straight-line tiers still answer, and say the route was not used', () => {
  const hydrants = [hyd('H40', north(6), east(-40))];
  const r = pickRouteHydrants({ hydrants, routeCoords: [], destination: DEST });
  assert.equal(r.tier, TIER.NEAR);
  assert.equal(r.routeKnown, false);
});

test('no destination: nothing is picked and nothing is claimed', () => {
  const r = pickRouteHydrants({ hydrants: [hyd('H', 49.3, -122.8)], routeCoords: route, destination: null });
  assert.equal(r.tier, TIER.NO_TARGET);
  assert.deepEqual(r.picks, []);
});
