// node --test frontend/tests  (npm run test:node). The camera arithmetic, pure.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  fovToZoom, zoomToFov, clampStaticFov, bearingDegrees, savedViewFromParcel, defaultViewForCall,
  viewsMatch, staticStreetViewUrl, STATIC_FOV_MAX, DEFAULT_FOV,
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
  assert.equal(savedViewFromParcel({ streetview_heading: null, front_lat: 49.27, front_lng: -122.79 }), null);
  const v = savedViewFromParcel({ streetview_heading: 214, streetview_pitch: 13, streetview_fov: 127.31, streetview_pano_id: 'p1', front_lat: 49.27, front_lng: -122.79 });
  assert.deepEqual(v, { lat: 49.27, lng: -122.79, heading: 214, pitch: 13, fov: 127.31, panoId: 'p1' });
  // Missing pitch/fov fall to the defaults; a saved heading of 0 is a real save, not "unset".
  const zero = savedViewFromParcel({ streetview_heading: 0, front_lat: 49.27, front_lng: -122.79 });
  assert.equal(zero.heading, 0);
  assert.equal(zero.fov, DEFAULT_FOV);
});

test('the default view stands at the arrival point and looks at the parcel', () => {
  // Camera on the street due south of the parcel centroid: bearing north.
  const v = defaultViewForCall({ lat: 49.2700, lng: -122.7900, target: { lat: 49.2705, lng: -122.7900 } });
  assert.equal(v.heading, 0);
  assert.equal(v.fov, DEFAULT_FOV);
  assert.equal(defaultViewForCall({ lat: null, lng: null }), null);
  assert.equal(defaultViewForCall({ lat: 0, lng: 0 }), null);
  assert.equal(bearingDegrees(49.27, -122.79, 49.27, -122.78), 90);
});

test('viewsMatch tolerates stored precision and nothing more', () => {
  const view = { heading: 214, pitch: 13, fov: 127.31, panoId: 'p1' };
  assert.ok(viewsMatch({ heading: 214.3, pitch: 12.6, fov: 127.31, panoId: 'p1' }, view));
  assert.ok(!viewsMatch({ heading: 215, pitch: 13, fov: 127.31, panoId: 'p1' }, view));
  assert.ok(!viewsMatch({ heading: 214, pitch: 13, fov: 90, panoId: 'p1' }, view));
  assert.ok(!viewsMatch({ heading: 214, pitch: 13, fov: 127.31, panoId: 'other' }, view));
  assert.ok(!viewsMatch(null, view));
});
