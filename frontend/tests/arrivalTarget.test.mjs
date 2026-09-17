import test from 'node:test';
import assert from 'node:assert/strict';
import { resolverTargetFromParcel, applyArrivalToCall } from '../src/utils/arrivalTarget.js';

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
