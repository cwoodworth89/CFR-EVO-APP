import test from 'node:test';
import assert from 'node:assert/strict';
import { resolverTargetFromParcel, applyArrivalToCall, unitEtasForMovedCall, destinationKey } from '../src/utils/arrivalTarget.js';

const parcel = (over = {}) => ({
  lat: 49.2790, lng: -122.8010,               // centroid
  front_lat: 49.2785, front_lng: -122.8010,   // computed frontage
  entrance_lat: null, entrance_lng: null, entrance_note: null,
  ...over,
});

test('the resolver precedence: entrance, then frontage, then centroid', () => {
  assert.deepEqual(
    resolverTargetFromParcel(parcel({ entrance_lat: 49.2795, entrance_lng: -122.8008, entrance_note: 'Main Lobby entrance' })),
    { lat: 49.2795, lng: -122.8008, arrival_point: 'entrance', entrance_note: 'Main Lobby entrance' },
  );
  // A cleared arrival point: back to the computed frontage, as the next call would get.
  assert.deepEqual(resolverTargetFromParcel(parcel()), { lat: 49.2785, lng: -122.8010, arrival_point: 'front', entrance_note: null });
  assert.deepEqual(
    resolverTargetFromParcel(parcel({ front_lat: null, front_lng: null })),
    { lat: 49.2790, lng: -122.8010, arrival_point: 'centroid', entrance_note: null },
  );
  assert.equal(resolverTargetFromParcel(parcel({ front_lat: null, front_lng: null, lat: null, lng: null })), null);
  assert.equal(resolverTargetFromParcel(null), null);
});

test('applying moves the call on screen and nothing else', () => {
  const call = {
    dispatch_id: 'DISP-X', address: '1145 Heffley Cres', lat: 49.2785, lng: -122.8010,
    routing_metrics: [{ unit: 'E1', duration: 300 }],
    target: { lat: 49.2785, lng: -122.8010, rings: [[[1, 2]]], arrival_point: 'front' },
  };
  const target = { lat: 49.2795, lng: -122.8008, arrival_point: 'entrance', entrance_note: 'Main Lobby entrance' };
  const moved = applyArrivalToCall(call, target);
  assert.equal(moved.lat, 49.2795);
  assert.equal(moved.target.lat, 49.2795);
  assert.equal(moved.target.lng, -122.8008);
  assert.equal(moved.target.arrival_point, 'entrance');
  assert.equal(moved.target.entrance_note, 'Main Lobby entrance');
  assert.equal(moved.target.rings, call.target.rings);       // same parcel
  assert.equal(moved.routing_metrics, call.routing_metrics); // recorded figures left as recorded
  assert.equal(moved.address, call.address);
  assert.equal(call.lat, 49.2785);                            // the record object is not mutated
});

test('no target, a bad target, or an ambiguous junction leaves the call as it is', () => {
  const call = { lat: 1, lng: 2, target: { lat: 1, lng: 2 } };
  assert.equal(applyArrivalToCall(call, null), call);
  assert.equal(applyArrivalToCall(call, { lat: 0, lng: 0 }), call);
  const ambiguous = { ...call, candidates: [{ lat: 1, lng: 2 }, { lat: 3, lng: 4 }] };
  assert.equal(applyArrivalToCall(ambiguous, { lat: 5, lng: 6, arrival_point: 'entrance' }), ambiguous);
});

test('a moved call takes each unit\'s ETA from its hall\'s live route, never the recorded one', () => {
  const recorded = [
    { unit: 'E1', origin_hall: 1, eta_minutes: 4, road_distance_km: 2.1 },
    { unit: 'L1', origin_hall: 1, eta_minutes: 4, road_distance_km: 2.1 },
    { unit: 'E3', origin_hall: 3, eta_minutes: 9, road_distance_km: 5.6 },
    { unit: 'R9', origin_hall: null, eta_minutes: 7, road_distance_km: 4.0 },
  ];
  // Hall 1 answered for the new point; hall 3 has not yet.
  const live = unitEtasForMovedCall(recorded, { 1: { etaMinutes: 5, distanceKm: 2.6, degraded: false } });
  assert.deepEqual(live, [
    { unit: 'E1', hallId: '1', etaMin: 5, distKm: 2.6 },
    { unit: 'L1', hallId: '1', etaMin: 5, distKm: 2.6 },
    { unit: 'E3', hallId: '3', etaMin: null, distKm: null },   // not the recorded 9
    { unit: 'R9', hallId: null, etaMin: null, distKm: null },  // no hall, no route
  ]);
  // No router: a degraded answer is a straight line with no ETA; both show unknown.
  const degraded = unitEtasForMovedCall(recorded.slice(0, 1), { 1: { etaMinutes: null, distanceKm: 1.9, degraded: true } });
  assert.deepEqual(degraded, [{ unit: 'E1', hallId: '1', etaMin: null, distKm: null }]);
  assert.deepEqual(unitEtasForMovedCall(null, {}), []);
});

test('route results are tagged with the destination they were computed to', () => {
  assert.equal(destinationKey(49.2795, -122.8008), '49.2795,-122.8008');
  assert.equal(destinationKey('49.2795', '-122.8008'), '49.2795,-122.8008');
  assert.equal(destinationKey(null, 1), '');
});
