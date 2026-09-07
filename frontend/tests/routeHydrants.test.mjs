// node --test frontend/tests  (npm run test:node). Pure geometry, no browser.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pickRouteHydrants, SUPPLY_M, ROUTE_BAND_M, ROUTE_WINDOW_M, DOORSTEP_M, TIER } from '../src/utils/routeHydrants.js';

// A straight east-west road at lat 49.30 ending at the address at lng -122.8000.
// One degree of longitude here is about 72.6 km, so 0.001 deg is ~72.6 m.
const DEST = { lat: 49.3, lng: -122.8 };
const M_PER_DEG_LNG = 111320 * Math.cos((49.3 * Math.PI) / 180);
const east = (m) => DEST.lng + m / M_PER_DEG_LNG;             // metres east of the address
const north = (m) => DEST.lat + m / 110540;
const route = [{ lat: 49.3, lng: east(-2000) }, { lat: 49.3, lng: east(-500) }, { lat: 49.3, lng: DEST.lng }];
const hyd = (id, lat, lng, extra = {}) => ({ gisId: id, status: 'OPERATING', flowClass: 'A', lat, lng, ...extra });

test('choice #1 is the last hydrant passed, #2 the one before it', () => {
  const hydrants = [
    hyd('H40', north(6), east(-40)),     // 40 m before arrival, 6 m off the road
    hyd('H80', north(-8), east(-80)),    // 80 m before arrival
    hyd('H200', north(5), east(-200)),   // 200 m before: on the route, but there are two closer
    hyd('FAR', north(60), east(-30)),    // 60 m off the road: not along it
  ];
  const r = pickRouteHydrants({ hydrants, routeCoords: route, destination: DEST });
  assert.equal(r.tier, TIER.APPROACH);
  assert.deepEqual(r.picks.map(p => p.gisId), ['H40', 'H80']);
  assert.equal(r.picks[0].beforeArrivalM, 40);
  assert.equal(r.picks[0].offRouteM, 6);
  assert.ok(r.picks.every(p => p.beforeArrivalM <= ROUTE_WINDOW_M && p.offRouteM <= ROUTE_BAND_M));
});

test('808 Miller Ave: an on-route hydrant 95 m back beats off-route ones at 64 m and 73 m', () => {
  // The shape of DISP-2026-A92117: I-029 on the approach, I-030 past the address on the far
  // side, I-074 down a side street. The operator named I-029 the hydrant of choice.
  const hydrants = [
    hyd('I-029', north(12), east(-95)),
    hyd('I-030', north(9), east(63)),
    hyd('I-074', north(-73), east(0)),
  ];
  const r = pickRouteHydrants({ hydrants, routeCoords: route, destination: DEST });
  assert.equal(r.tier, TIER.APPROACH);
  assert.equal(r.picks[0].gisId, 'I-029');
  assert.equal(r.picks[0].how, TIER.APPROACH);
});

test('a hydrant within a 50 ft roll of the marker is #1 regardless of the route; the route fills #2', () => {
  const hydrants = [
    hyd('H40', north(6), east(-40)),      // on the approach, 40 m out
    hyd('ROLL', north(-12), east(8)),     // 14 m from the marker, just past the address, off the far side
    hyd('H80', north(-8), east(-80)),
  ];
  const r = pickRouteHydrants({ hydrants, routeCoords: route, destination: DEST });
  assert.equal(r.tier, TIER.DOORSTEP);
  assert.deepEqual(r.picks.map(p => p.gisId), ['ROLL', 'H40']);
  assert.equal(r.picks[0].how, TIER.DOORSTEP);
  assert.ok(r.picks[0].distance <= DOORSTEP_M);
  assert.equal(r.picks[1].how, TIER.APPROACH);
});

test('nothing on the approach within the hose carried: the one just past the address is found straight-line', () => {
  const hydrants = [hyd('PAST', north(3), east(45)), hyd('H400', north(5), east(-400))];
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
