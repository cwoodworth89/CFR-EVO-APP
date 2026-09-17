// node --test frontend/tests  (npm run test:node). The camera arithmetic, pure.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  fovToZoom, zoomToFov, clampStaticFov, bearingDegrees, savedViewFromParcel, defaultViewForCall,
  viewsMatch, staticStreetViewUrl, STATIC_FOV_MAX, DEFAULT_FOV,
  lotCentre, aimPointForCall, headingToAim, streetViewMetadataUrl, viewFromMetadata, resolveStreetView,
} from '../src/utils/streetViewGeometry.js';

test('fov and zoom round-trip at full precision, zoom 0 included', () => {
  for (const fov of [180, 127.31, 120, 90, 45, 22.5, 10]) {
    assert.ok(Math.abs(zoomToFov(fovToZoom(fov)) - fov) < 1e-9, `fov ${fov}`);
  }
  assert.equal(zoomToFov(0), 180);      // fully zoomed out is zoom 0, which is falsy: the #35a trap
  assert.equal(zoomToFov(1), 90);
  assert.equal(fovToZoom(90), 1);
  assert.equal(fovToZoom('garbage'), fovToZoom(DEFAULT_FOV));
});

test('the Static API request is bounded, the stored angle is not', () => {
  assert.equal(clampStaticFov(180), STATIC_FOV_MAX);
  assert.equal(clampStaticFov(127.31), STATIC_FOV_MAX);   // the SDK's widest is past the tile's maximum
  assert.equal(clampStaticFov(100.6), 101);
  assert.equal(clampStaticFov(3), 10);
  const url = staticStreetViewUrl({ lat: 49.27, lng: -122.79, heading: 214.4, pitch: 13, fov: 180, panoId: '' }, 'KEY');
  assert.match(url, /fov=120/);
  assert.match(url, /heading=214&pitch=13/);
  assert.match(url, /location=49\.27,-122\.79&radius=100&source=outdoor/);   // the SDK's reach, not the API's 50 m default
  assert.match(url, /return_error_code=true/);
  const byPano = staticStreetViewUrl({ lat: 1, lng: 2, heading: 0, pitch: 0, fov: 90, panoId: 'abc def' }, 'KEY');
  assert.match(byPano, /pano=abc%20def/);
  assert.doesNotMatch(byPano, /location=/);
});

test('a saved view comes from the parcel row and an unsaved parcel gives null', () => {
  assert.equal(savedViewFromParcel({ streetview_heading: null, streetview_lat: 49.27, streetview_lng: -122.79 }), null);
  const v = savedViewFromParcel({ streetview_heading: 214, streetview_pitch: 13, streetview_fov: 127.31, streetview_pano_id: 'p1', streetview_lat: 49.27, streetview_lng: -122.79 });
  assert.deepEqual(v, { lat: 49.27, lng: -122.79, heading: 214, pitch: 13, fov: 127.31, panoId: 'p1' });
  // Missing pitch/fov fall to the defaults; a saved heading of 0 is a real save, not "unset".
  const zero = savedViewFromParcel({ streetview_heading: 0, streetview_lat: 49.27, streetview_lng: -122.79 });
  assert.equal(zero.heading, 0);
  assert.equal(zero.fov, DEFAULT_FOV);
});

// A square lot 20 m on a side north of a frontage point, in GeoJSON [lng, lat] order.
// At 49.28 N: 1 m of latitude = 1/111320 deg; 1 m of longitude = 1/(111320 cos 49.28) deg.
const M_LAT = 1 / 111320;
const M_LNG = 1 / (111320 * Math.cos(49.28 * Math.PI / 180));
const FRONT = { lat: 49.28, lng: -122.80 };
const squareLot = (cLat, cLng, half = 10) => [[
  [cLng - half * M_LNG, cLat - half * M_LAT], [cLng + half * M_LNG, cLat - half * M_LAT],
  [cLng + half * M_LNG, cLat + half * M_LAT], [cLng - half * M_LNG, cLat + half * M_LAT],
  [cLng - half * M_LNG, cLat - half * M_LAT],
]];
// The shape toActiveCall actually produces: lat/lng ARE target.lat/lng, target kept.
const recordCall = (target) => ({ target, lat: target.lat, lng: target.lng });
const near = (a, b, tol = 1) => Math.abs(((a - b + 540) % 360) - 180) <= tol;

test('bearing: a known panorama to a known lot centre, all four quadrants', () => {
  const pano = FRONT;
  const at = (north, east) => ({ lat: pano.lat + north * M_LAT, lng: pano.lng + east * M_LNG });
  const cases = [
    [at(30, 0), 0], [at(0, 30), 90], [at(-30, 0), 180], [at(0, -30), 270],   // the axes
    [at(30, 30), 45], [at(-30, 30), 135], [at(-30, -30), 225], [at(30, -30), 315],   // the quadrants
  ];
  for (const [aim, expected] of cases) {
    const h = headingToAim(pano.lat, pano.lng, aim);
    assert.ok(near(h, expected), `expected ${expected}, got ${h}`);
  }
  assert.equal(bearingDegrees(49.27, -122.79, 49.27, -122.78), 90);
});

test('the lot centre is the polygon centroid; no ring is null', () => {
  const c = lotCentre(squareLot(49.2802, -122.8001));
  assert.ok(Math.abs(c.lat - 49.2802) < 1e-9 && Math.abs(c.lng - -122.8001) < 1e-9);
  // Anticlockwise or clockwise, same centre.
  const cw = lotCentre([squareLot(49.2802, -122.8001)[0].slice().reverse()]);
  assert.ok(Math.abs(cw.lat - 49.2802) < 1e-9);
  assert.equal(lotCentre(null), null);
  assert.equal(lotCentre([]), null);
  assert.equal(lotCentre([[[1, 2], [3, 4]]]), null);
});

test('the default view on a real record shape faces the lot, never north by default (#93)', () => {
  // Frontage point on the street, lot centre 20 m due east: 90, where it used to be 0.
  const east = recordCall({ ...FRONT, rings: squareLot(FRONT.lat, FRONT.lng + 20 * M_LNG) });
  const v = defaultViewForCall(east);
  assert.ok(near(v.heading, 90), `got ${v.heading}`);
  assert.equal(v.aim.kind, 'lot');
  assert.equal(v.lat, FRONT.lat);
  assert.equal(v.fov, DEFAULT_FOV);
  // No polygon: the aim is the call's own point, which is the camera -- no direction, null.
  const junction = defaultViewForCall(recordCall({ ...FRONT }));
  assert.equal(junction.heading, null);
  assert.equal(junction.aim.kind, 'point');
  assert.equal(defaultViewForCall({ lat: null, lng: null }), null);
  assert.equal(defaultViewForCall({ lat: 0, lng: 0 }), null);
});

test('no heading, no Static image request', () => {
  assert.equal(staticStreetViewUrl({ lat: 49.28, lng: -122.8, heading: null, pitch: 5, fov: 90, panoId: '' }, 'KEY'), '');
});

test('the metadata request is the image search: location, 100 m, outdoor, key', () => {
  assert.equal(
    streetViewMetadataUrl({ lat: 49.28, lng: -122.8 }, 'KEY'),
    'https://maps.googleapis.com/maps/api/streetview/metadata?location=49.28,-122.8&radius=100&source=outdoor&key=KEY',
  );
  assert.equal(streetViewMetadataUrl({ lat: 49.28, lng: -122.8 }, ''), '');
  assert.equal(streetViewMetadataUrl({ lat: 0, lng: 0 }, 'KEY'), '');
});

test('fallback chain (#93)', () => {
  const lotNorth = recordCall({ ...FRONT, rings: squareLot(FRONT.lat + 25 * M_LAT, FRONT.lng) });
  const def = defaultViewForCall(lotNorth);
  const saved = { lat: 1, lng: 2, heading: 214, pitch: 13, fov: 90, panoId: 'p1' };

  // A saved view wins, whatever Google says.
  assert.deepEqual(resolveStreetView({ savedView: saved, defaultView: def, meta: { status: 'OK' } }), { kind: 'saved', view: saved });
  assert.equal(resolveStreetView({ savedView: null, defaultView: null, meta: null }).kind, 'standby');
  assert.equal(resolveStreetView({ savedView: null, defaultView: def, meta: null }).kind, 'resolving');

  // OK: camera moves to the panorama, pinned by id; heading computed from there. The panorama
  // stands 20 m east of the frontage point, the lot centre is 25 m north of the frontage
  // point: the camera looks north-west (atan2(-20, 25) -> about 321).
  const ok = resolveStreetView({ savedView: null, defaultView: def, meta: {
    status: 'OK', pano_id: 'PANO', location: { lat: FRONT.lat, lng: FRONT.lng + 20 * M_LNG } } });
  assert.equal(ok.kind, 'metadata');
  assert.equal(ok.view.panoId, 'PANO');
  assert.ok(near(ok.view.heading, 321), `got ${ok.view.heading}`);
  assert.match(staticStreetViewUrl(ok.view, 'KEY'), /pano=PANO&heading=321/);

  assert.equal(resolveStreetView({ savedView: null, defaultView: def, meta: { status: 'ZERO_RESULTS' } }).kind, 'no-imagery');

  // Anything else: the location request, heading frontage -> lot centre (0 here, a real
  // bearing: the lot is due north), never an invented one.
  for (const status of ['REQUEST_DENIED', 'OVER_QUERY_LIMIT', 'UNKNOWN_ERROR', 'INVALID_REQUEST', 'FETCH_FAILED', 'NO_KEY']) {
    const r = resolveStreetView({ savedView: null, defaultView: def, meta: { status } });
    assert.equal(r.kind, 'fallback', status);
    assert.equal(r.view, def);
    assert.ok(near(r.view.heading, 0));
    assert.match(staticStreetViewUrl(r.view, 'KEY'), /location=49\.28,-122\.8&radius=100/);
  }
  // OK but malformed (no id) is not OK.
  assert.equal(resolveStreetView({ savedView: null, defaultView: def, meta: { status: 'OK', location: { lat: 49.28, lng: -122.8 } } }).kind, 'fallback');

  // A junction (no polygon): only the panorama's position gives a direction.
  const junction = defaultViewForCall(recordCall({ ...FRONT }));
  const jOk = resolveStreetView({ savedView: null, defaultView: junction, meta: {
    status: 'OK', pano_id: 'J', location: { lat: FRONT.lat - 15 * M_LAT, lng: FRONT.lng } } });
  assert.equal(jOk.kind, 'metadata');
  assert.ok(near(jOk.view.heading, 0));
  const jDenied = resolveStreetView({ savedView: null, defaultView: junction, meta: { status: 'REQUEST_DENIED' } });
  assert.equal(jDenied.kind, 'no-heading');
  assert.equal(jDenied.view, null);
});

test('a view with no heading does not pin the live heading', () => {
  assert.ok(viewsMatch({ heading: 123, pitch: 5, fov: 90, panoId: '' }, { heading: null, pitch: 5, fov: 90, panoId: '' }));
});

test('viewsMatch tolerates stored precision and nothing more', () => {
  const view = { heading: 214, pitch: 13, fov: 127.31, panoId: 'p1' };
  assert.ok(viewsMatch({ heading: 214.3, pitch: 12.6, fov: 127.31, panoId: 'p1' }, view));
  assert.ok(!viewsMatch({ heading: 215, pitch: 13, fov: 127.31, panoId: 'p1' }, view));
  assert.ok(!viewsMatch({ heading: 214, pitch: 13, fov: 90, panoId: 'p1' }, view));
  assert.ok(!viewsMatch({ heading: 214, pitch: 13, fov: 127.31, panoId: 'other' }, view));
  assert.ok(!viewsMatch(null, view));
});

// The three points are separate and do not change each other (operator, 2026-09-11; punch
// list #78). The camera used to be read from, and written to, the computed frontage.
test('a saved view comes from the camera position, never from the frontage', () => {
  const frontageOnly = savedViewFromParcel({
    streetview_heading: 214, front_lat: 49.27, front_lng: -122.79,
  });
  assert.equal(frontageOnly, null, 'front_lat must not stand in for the camera');

  const both = savedViewFromParcel({
    streetview_heading: 214,
    streetview_lat: 49.2705, streetview_lng: -122.7905,
    front_lat: 49.27, front_lng: -122.79,
    entrance_lat: 49.2712, entrance_lng: -122.7912,
  });
  assert.equal(both.lat, 49.2705);
  assert.equal(both.lng, -122.7905);
});
