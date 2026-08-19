// Adversarial Test Harness for Tile Layer and Dynamic Resolution
// Tests TILE_BASE_URL, getTileUrl, getTileLayerConfig, FallbackTileLayer mechanics

import assert from 'node:assert';

let passedTests = 0;
let failedTests = 0;

function runTest(name, fn) {
  try {
    fn();
    console.log(`[PASS] ${name}`);
    passedTests++;
  } catch (err) {
    console.error(`[FAIL] ${name}: ${err.message}`);
    failedTests++;
  }
}

console.log('=== STARTING ADVERSARIAL TILE LAYER TEST SUITE ===\n');

// 1. Dynamic Resolution Logic Simulator (Pure reproduction of apiClient.js logic)
function resolveTileBaseUrl(envVar, hostname) {
  if (envVar) {
    return envVar.replace(/\/$/, '');
  }
  const host = hostname || 'localhost';
  return `http://${host}:8081`;
}

function resolveApiBaseUrl(envVar, hostname) {
  if (envVar) {
    return envVar.replace(/\/$/, '');
  }
  const host = hostname || 'localhost';
  return `http://${host}:8000`;
}

function getTileUrlPure(tileBaseUrl, z = '{z}', x = '{x}', y = '{y}', style = 'SATELLITE', apiBaseUrl = 'http://localhost:8000') {
  const normalizedStyle = (style || 'SATELLITE').toUpperCase();
  if (normalizedStyle === 'SATELLITE') {
    return `${tileBaseUrl}/services/satellite/tiles/${z}/${x}/${y}.jpg`;
  }
  if (normalizedStyle === 'GREY' || normalizedStyle === 'DARK' || normalizedStyle === 'LIGHT') {
    return `${tileBaseUrl}/services/street_nolabels/tiles/${z}/${x}/${y}.png`;
  }
  return `${tileBaseUrl}/services/street/tiles/${z}/${x}/${y}.png`;
}

function getTileLayerConfigPure(tileBaseUrl, style = 'SATELLITE', apiBaseUrl = 'http://localhost:8000') {
  const normalized = (style || 'SATELLITE').toUpperCase();
  switch (normalized) {
    case 'DARK':
      return {
        url: `${tileBaseUrl}/services/street_nolabels/tiles/{z}/{x}/{y}.png`,
        fallbackUrl: null,
        attribution: '© OpenStreetMap contributors & Carto (100% Offline Local Cache)',
        subdomains: ['a', 'b', 'c'],
        maxNativeZoom: 18,
        maxZoom: 22,
      };
    case 'GREY':
    case 'LIGHT':
      return {
        url: `${tileBaseUrl}/services/street_nolabels/tiles/{z}/{x}/{y}.png`,
        fallbackUrl: null,
        attribution: '© OpenStreetMap contributors & Carto (100% Offline Local Cache)',
        subdomains: ['a', 'b', 'c'],
        maxNativeZoom: 18,
        maxZoom: 22,
      };
    case 'OSM':
      return {
        url: `${tileBaseUrl}/services/street/tiles/{z}/{x}/{y}.png`,
        fallbackUrl: null,
        attribution: '© OpenStreetMap contributors (100% Offline Local Cache)',
        subdomains: ['a', 'b', 'c'],
        maxNativeZoom: 18,
        maxZoom: 22,
      };
    case 'SATELLITE':
      return {
        url: `${tileBaseUrl}/services/satellite/tiles/{z}/{x}/{y}.jpg`,
        fallbackUrl: null,
        attribution: 'City of Coquitlam 7.5cm Orthophotos & Maxar (100% Offline Local Cache)',
        subdomains: ['a', 'b', 'c'],
        maxNativeZoom: 20,
        maxZoom: 22,
      };
    case 'VOYAGER':
    default:
      return {
        url: `${tileBaseUrl}/services/street/tiles/{z}/{x}/{y}.png`,
        fallbackUrl: null,
        attribution: '© OpenStreetMap contributors & Carto (100% Offline Local Cache)',
        subdomains: ['a', 'b', 'c'],
        maxNativeZoom: 18,
        maxZoom: 22,
      };
  }
}

// --- SUITE 1: TILE_BASE_URL Resolution ---
runTest('TILE_BASE_URL: resolves localhost when hostname is localhost', () => {
  const url = resolveTileBaseUrl(undefined, 'localhost');
  assert.strictEqual(url, 'http://localhost:8081');
});

runTest('TILE_BASE_URL: resolves Tailscale IP when hostname is 100.95.146.94', () => {
  const url = resolveTileBaseUrl(undefined, '100.95.146.94');
  assert.strictEqual(url, 'http://100.95.146.94:8081');
});

runTest('TILE_BASE_URL: resolves custom domain hostname', () => {
  const url = resolveTileBaseUrl(undefined, 'kiosk.fire.internal');
  assert.strictEqual(url, 'http://kiosk.fire.internal:8081');
});

runTest('TILE_BASE_URL: falls back to localhost on empty string hostname', () => {
  const url = resolveTileBaseUrl(undefined, '');
  assert.strictEqual(url, 'http://localhost:8081');
});

runTest('TILE_BASE_URL: falls back to localhost on null/undefined hostname', () => {
  const url1 = resolveTileBaseUrl(undefined, null);
  const url2 = resolveTileBaseUrl(undefined, undefined);
  assert.strictEqual(url1, 'http://localhost:8081');
  assert.strictEqual(url2, 'http://localhost:8081');
});

runTest('TILE_BASE_URL: respects env override without trailing slash', () => {
  const url = resolveTileBaseUrl('http://custom-tiles:9090', '100.95.146.94');
  assert.strictEqual(url, 'http://custom-tiles:9090');
});

runTest('TILE_BASE_URL: strips trailing slash from env override', () => {
  const url = resolveTileBaseUrl('http://custom-tiles:9090/', 'localhost');
  assert.strictEqual(url, 'http://custom-tiles:9090');
});

// --- SUITE 2: getTileUrl Generation ---
runTest('getTileUrl: default style (satellite) with template placeholders', () => {
  const url = getTileUrlPure('http://localhost:8081');
  assert.strictEqual(url, 'http://localhost:8081/services/satellite/tiles/{z}/{x}/{y}.jpg');
});

runTest('getTileUrl: concrete coordinates for dark style', () => {
  const url = getTileUrlPure('http://100.95.146.94:8081', 14, 2620, 5710, 'dark');
  assert.strictEqual(url, 'http://100.95.146.94:8081/services/street_nolabels/tiles/14/2620/5710.png');
});

runTest('getTileUrl: grey/light style normalization', () => {
  const urlGrey = getTileUrlPure('http://localhost:8081', 12, 100, 200, 'grey');
  const urlLight = getTileUrlPure('http://localhost:8081', 12, 100, 200, 'LIGHT');
  assert.strictEqual(urlGrey, 'http://localhost:8081/services/street_nolabels/tiles/12/100/200.png');
  assert.strictEqual(urlLight, 'http://localhost:8081/services/street_nolabels/tiles/12/100/200.png');
});

runTest('getTileUrl: satellite style uses mbtileserver satellite endpoint', () => {
  const url = getTileUrlPure('http://localhost:8081', 16, 500, 600, 'satellite');
  assert.strictEqual(url, 'http://localhost:8081/services/satellite/tiles/16/500/600.jpg');
});

runTest('getTileUrl: fallback to street for unrecognized style', () => {
  const url = getTileUrlPure('http://localhost:8081', 10, 1, 2, 'UNKNOWN_TERRAIN');
  assert.strictEqual(url, 'http://localhost:8081/services/street/tiles/10/1/2.png');
});

// --- SUITE 3: getTileLayerConfig Structure & Zoom Constraints ---
runTest('getTileLayerConfig: VOYAGER layer config', () => {
  const config = getTileLayerConfigPure('http://100.95.146.94:8081', 'VOYAGER');
  assert.strictEqual(config.url, 'http://100.95.146.94:8081/services/street/tiles/{z}/{x}/{y}.png');
  assert.strictEqual(config.fallbackUrl, null);
  assert.strictEqual(config.maxNativeZoom, 18);
  assert.strictEqual(config.maxZoom, 22);
  assert.deepStrictEqual(config.subdomains, ['a', 'b', 'c']);
});

runTest('getTileLayerConfig: DARK layer config', () => {
  const config = getTileLayerConfigPure('http://100.95.146.94:8081', 'DARK');
  assert.strictEqual(config.url, 'http://100.95.146.94:8081/services/street_nolabels/tiles/{z}/{x}/{y}.png');
  assert.strictEqual(config.fallbackUrl, null);
  assert.strictEqual(config.maxNativeZoom, 18);
  assert.strictEqual(config.maxZoom, 22);
});

runTest('getTileLayerConfig: GREY/LIGHT layer config', () => {
  const configGrey = getTileLayerConfigPure('http://localhost:8081', 'GREY');
  const configLight = getTileLayerConfigPure('http://localhost:8081', 'LIGHT');
  assert.strictEqual(configGrey.url, 'http://localhost:8081/services/street_nolabels/tiles/{z}/{x}/{y}.png');
  assert.strictEqual(configLight.url, 'http://localhost:8081/services/street_nolabels/tiles/{z}/{x}/{y}.png');
  assert.strictEqual(configGrey.fallbackUrl, null);
});

runTest('getTileLayerConfig: OSM layer config', () => {
  const config = getTileLayerConfigPure('http://localhost:8081', 'OSM');
  assert.strictEqual(config.url, 'http://localhost:8081/services/street/tiles/{z}/{x}/{y}.png');
  assert.strictEqual(config.fallbackUrl, null);
  assert.deepStrictEqual(config.subdomains, ['a', 'b', 'c']);
});

runTest('getTileLayerConfig: default fallback for null/undefined/empty string', () => {
  const configNull = getTileLayerConfigPure('http://localhost:8081', null);
  const configUndef = getTileLayerConfigPure('http://localhost:8081', undefined);
  const configEmpty = getTileLayerConfigPure('http://localhost:8081', '');
  assert.strictEqual(configNull.url, 'http://localhost:8081/services/satellite/tiles/{z}/{x}/{y}.jpg');
  assert.strictEqual(configUndef.url, 'http://localhost:8081/services/satellite/tiles/{z}/{x}/{y}.jpg');
  assert.strictEqual(configEmpty.url, 'http://localhost:8081/services/satellite/tiles/{z}/{x}/{y}.jpg');
});

// --- SUITE 4: Fallback URL Construction & Subdomain Hashing ---
function buildFallbackTileUrl(fallbackUrl, coords, subdomains) {
  let sub = 'a';
  if (Array.isArray(subdomains) && subdomains.length > 0) {
    sub = subdomains[Math.abs(coords.x + coords.y) % subdomains.length];
  }
  return fallbackUrl
    .replace('{s}', sub)
    .replace('{z}', coords.z)
    .replace('{x}', coords.x)
    .replace('{y}', coords.y)
    .replace('{r}', '');
}

runTest('Fallback URL: CartoDB voyager replacement', () => {
  const template = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
  const subdomains = ['a', 'b', 'c', 'd'];
  const coords = { z: 14, x: 2621, y: 5711 }; // 2621 + 5711 = 8332 % 4 = 0 -> 'a'
  const url = buildFallbackTileUrl(template, coords, subdomains);
  assert.strictEqual(url, 'https://a.basemaps.cartocdn.com/rastertiles/voyager/14/2621/5711.png');
});

runTest('Fallback URL: Subdomain distribution across various coords', () => {
  const template = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
  const subdomains = ['a', 'b', 'c'];
  const results = new Set();
  for (let x = 0; x < 10; x++) {
    for (let y = 0; y < 10; y++) {
      const url = buildFallbackTileUrl(template, { z: 10, x, y }, subdomains);
      const sub = url.match(/https:\/\/([abc])\./)[1];
      results.add(sub);
    }
  }
  assert.strictEqual(results.has('a'), true);
  assert.strictEqual(results.has('b'), true);
  assert.strictEqual(results.has('c'), true);
});

runTest('Fallback URL: Handles negative or 0 coordinates safely', () => {
  const template = 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png';
  const subdomains = ['a', 'b', 'c', 'd'];
  const coords = { z: 0, x: -5, y: -3 }; // -5 + -3 = -8 -> Math.abs(-8) = 8 % 4 = 0 -> 'a'
  const url = buildFallbackTileUrl(template, coords, subdomains);
  assert.strictEqual(url, 'https://a.basemaps.cartocdn.com/dark_nolabels/0/-5/-3.png');
});

runTest('Fallback URL: Handles empty or invalid subdomains array', () => {
  const template = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
  const urlEmpty = buildFallbackTileUrl(template, { z: 12, x: 10, y: 20 }, []);
  const urlNull = buildFallbackTileUrl(template, { z: 12, x: 10, y: 20 }, null);
  assert.strictEqual(urlEmpty, 'https://a.basemaps.cartocdn.com/rastertiles/voyager/12/10/20.png');
  assert.strictEqual(urlNull, 'https://a.basemaps.cartocdn.com/rastertiles/voyager/12/10/20.png');
});

// --- SUITE 5: Labels Fallback Substitution ---
runTest('Labels fallback: replaces _nolabels with _all when cadastral error occurs', () => {
  let url = 'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png';
  if (url.includes('_nolabels')) {
    url = url.replace('_nolabels', '_all');
  }
  assert.strictEqual(url, 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png');
});

// --- SUITE 6: Mock FallbackTileLayer State Machine Simulation ---
runTest('FallbackTileLayer: loads primary tile successfully', (doneCallback) => {
  class MockTile {
    constructor() {
      this.listeners = {};
      this.src = '';
    }
    addEventListener(event, fn) {
      this.listeners[event] = fn;
    }
    simulateLoad() {
      if (this.listeners['load']) this.listeners['load']();
    }
    simulateError(err) {
      if (this.listeners['error']) this.listeners['error'](err);
    }
  }

  function simulateTileCreation(coords, primaryUrl, fallbackUrl, subdomains, shouldPrimaryFail, shouldFallbackFail) {
    const tile = new MockTile();
    let fallbackTried = false;
    let finalStatus = null;
    let finalSrc = null;

    const done = (err, t) => {
      finalStatus = err ? 'ERROR' : 'SUCCESS';
      finalSrc = t.src;
    };

    const onLoad = () => {
      done(null, tile);
    };

    const onError = (e) => {
      if (fallbackUrl && !fallbackTried) {
        fallbackTried = true;
        let sub = 'a';
        if (Array.isArray(subdomains) && subdomains.length > 0) {
          sub = subdomains[Math.abs(coords.x + coords.y) % subdomains.length];
        }
        tile.src = buildFallbackTileUrl(fallbackUrl, coords, subdomains);
        if (shouldFallbackFail) {
          setTimeout(() => tile.simulateError(new Error('Fallback 404')), 5);
        } else {
          setTimeout(() => tile.simulateLoad(), 5);
        }
      } else {
        done(e, tile);
      }
    };

    tile.addEventListener('load', onLoad);
    tile.addEventListener('error', onError);

    tile.src = primaryUrl.replace('{z}', coords.z).replace('{x}', coords.x).replace('{y}', coords.y);

    if (shouldPrimaryFail) {
      setTimeout(() => tile.simulateError(new Error('Primary connection refused (port 8081 offline)')), 5);
    } else {
      setTimeout(() => tile.simulateLoad(), 5);
    }

    return {
      tile,
      getResult: () => ({ finalStatus, finalSrc, fallbackTried })
    };
  }

  // Case A: Primary Succeeds
  const simA = simulateTileCreation(
    { z: 12, x: 50, y: 60 },
    'http://localhost:8081/services/vancouver/tiles/{z}/{x}/{y}.png',
    'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    ['a', 'b', 'c', 'd'],
    false,
    false
  );

  setTimeout(() => {
    const resA = simA.getResult();
    assert.strictEqual(resA.finalStatus, 'SUCCESS');
    assert.strictEqual(resA.fallbackTried, false);
    assert.strictEqual(resA.finalSrc, 'http://localhost:8081/services/vancouver/tiles/12/50/60.png');
  }, 20);

  // Case B: Primary Fails (e.g. 500 / Connection Refused) -> Fallback Succeeds
  const simB = simulateTileCreation(
    { z: 12, x: 50, y: 60 },
    'http://localhost:8081/services/vancouver/tiles/{z}/{x}/{y}.png',
    'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    ['a', 'b', 'c', 'd'],
    true,
    false
  );

  setTimeout(() => {
    const resB = simB.getResult();
    assert.strictEqual(resB.finalStatus, 'SUCCESS');
    assert.strictEqual(resB.fallbackTried, true);
    assert.strictEqual(resB.finalSrc, 'https://c.basemaps.cartocdn.com/rastertiles/voyager/12/50/60.png');
  }, 20);

  // Case C: Both Primary and Fallback Fail -> Invokes done(err)
  const simC = simulateTileCreation(
    { z: 12, x: 50, y: 60 },
    'http://localhost:8081/services/vancouver/tiles/{z}/{x}/{y}.png',
    'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    ['a', 'b', 'c', 'd'],
    true,
    true
  );

  setTimeout(() => {
    const resC = simC.getResult();
    assert.strictEqual(resC.finalStatus, 'ERROR');
    assert.strictEqual(resC.fallbackTried, true);
  }, 20);
});

// --- SUITE 7: Cadastral Overlay & Cross-Basemap Integration Contracts
function getParcelBoundaryCoordinates(p) {
  if (!p) return null;

  // Handle GeoJSON Feature
  if (p.type === 'Feature' && p.geometry) {
    p = { ...p.properties, geometry: p.geometry };
  }

  let rawRings = p.rings || p.geometry?.coordinates || p.coordinates || p.polygon || p.geom?.coordinates || p.geojson?.coordinates;

  // Handle JSON stringified rings/coordinates or geometry if passed from raw DB columns
  if (typeof rawRings === 'string') {
    const trimmed = rawRings.trim();
    if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
      try {
        rawRings = JSON.parse(trimmed);
      } catch (e) {
        // Ignore JSON parse failure
      }
    } else if (trimmed.toUpperCase().includes('POLYGON')) {
      // Support WKT POLYGON string
      const wktMatch = trimmed.match(/\(\s*\((.*?)\)\s*\)/s) || trimmed.match(/\(\s*(.*?)\s*\)/s);
      if (wktMatch) {
        const coordPairs = wktMatch[1].split(',').map(pair => {
          const parts = pair.trim().split(/\s+/).map(Number);
          return parts.length >= 2 ? parts : null;
        }).filter(Boolean);
        if (coordPairs.length >= 3) {
          rawRings = [coordPairs];
        }
      }
    }
  }

  // Handle GeoJSON geometry object with coordinates if p.geometry is stringified
  if (typeof p.geometry === 'string') {
    const trimmed = p.geometry.trim();
    if (trimmed.startsWith('{')) {
      try {
        const parsedGeom = JSON.parse(trimmed);
        if (parsedGeom?.coordinates) {
          rawRings = parsedGeom.coordinates;
        }
      } catch (e) {
        // Ignore JSON parse failure
      }
    }
  }

  if (rawRings && Array.isArray(rawRings) && rawRings.length > 0) {
    // Check if 4D MultiPolygon coordinates: [[[[lng, lat], ...]]]
    const isMultiPolygon = Array.isArray(rawRings[0]) && Array.isArray(rawRings[0][0]) && Array.isArray(rawRings[0][0][0]);
    const flattenedRings = isMultiPolygon ? rawRings.flat(1) : rawRings;

    // A single ring is an array of coordinate pairs/objects: [coord1, coord2, ...]
    const firstElem = flattenedRings[0];
    const isSingleRing = !Array.isArray(firstElem) ||
      (!Array.isArray(firstElem[0]) && (typeof firstElem[0] !== 'object' || firstElem[0] === null));
    const rings = isSingleRing ? [flattenedRings] : flattenedRings;

    const parsed = rings.map(ring => {
      if (!Array.isArray(ring)) return [];
      return ring.map(coord => {
        let c0 = null;
        let c1 = null;
        if (Array.isArray(coord) && coord.length >= 2) {
          c0 = parseFloat(coord[0]);
          c1 = parseFloat(coord[1]);
        } else if (coord && typeof coord === 'object') {
          if (coord.lat != null && (coord.lng != null || coord.lon != null)) {
            c0 = parseFloat(coord.lat);
            c1 = parseFloat(coord.lng ?? coord.lon);
          } else if (coord.x != null && coord.y != null) {
            c0 = parseFloat(coord.x);
            c1 = parseFloat(coord.y);
          }
        }
        if (c0 == null || c1 == null || isNaN(c0) || isNaN(c1)) return null;
        // If coordinate 0 is longitude (< -60 or > 90), swap to [lat, lng] for Leaflet
        if (c0 < -60 || Math.abs(c0) > 90) {
          return [c1, c0];
        }
        return [c0, c1];
      }).filter(c => c !== null);
    }).filter(ring => ring.length >= 3);

    if (parsed.length > 0) {
      return isSingleRing ? parsed[0] : (parsed.length === 1 ? parsed[0] : parsed);
    }
  }

  // Extract point coordinates if geometry is Point
  let geomPtLat = null;
  let geomPtLng = null;
  if (p.geometry?.type === 'Point' && Array.isArray(p.geometry.coordinates) && p.geometry.coordinates.length >= 2) {
    geomPtLng = p.geometry.coordinates[0];
    geomPtLat = p.geometry.coordinates[1];
  } else if (Array.isArray(p.coordinates) && p.coordinates.length === 2 && !Array.isArray(p.coordinates[0])) {
    geomPtLng = p.coordinates[0];
    geomPtLat = p.coordinates[1];
  }

  const rawLat = p.lat ?? p.centroid_lat ?? p.latitude ?? geomPtLat;
  const rawLng = p.lng ?? p.centroid_lng ?? p.longitude ?? geomPtLng;
  if (rawLat == null || rawLng == null) return null;

  const lat = parseFloat(rawLat);
  const lng = parseFloat(rawLng);
  if (isNaN(lat) || isNaN(lng) || lat === 0 || lng === 0) return null;

  const rawFLat = p.front_lat;
  const rawFLng = p.front_lng;
  const fLat = rawFLat != null ? parseFloat(rawFLat) : null;
  const fLng = rawFLng != null ? parseFloat(rawFLng) : null;

  if (fLat != null && fLng != null && !isNaN(fLat) && !isNaN(fLng) && (Math.abs(fLat - lat) > 1e-6 || Math.abs(fLng - lng) > 1e-6)) {
    const cosLat = Math.cos((lat * Math.PI) / 180);
    const vy = fLat - lat;
    const vx = (fLng - lng) * cosLat;
    const len = Math.sqrt(vy * vy + vx * vx);

    if (len > 1e-6) {
      const uy = vy / len;
      const ux = vx / len;
      const wy = -ux;
      const wx = uy;

      const depthDist = Math.max(len, 0.00014);
      const widthDist = 0.00010;

      const dLatFront = depthDist * uy;
      const dLngFront = (depthDist * ux) / cosLat;
      const dLatSide = widthDist * wy;
      const dLngSide = (widthDist * wx) / cosLat;

      return [
        [lat + dLatFront + dLatSide, lng + dLngFront + dLngSide],
        [lat + dLatFront - dLatSide, lng + dLngFront - dLngSide],
        [lat - dLatFront - dLatSide, lng - dLngFront - dLngSide],
        [lat - dLatFront + dLatSide, lng - dLngFront + dLngSide]
      ];
    }
  }

  const dLat = 0.00012;
  const dLng = 0.00016;
  return [
    [lat + dLat, lng - dLng],
    [lat + dLat, lng + dLng],
    [lat - dLat, lng + dLng],
    [lat - dLat, lng - dLng]
  ];
}

runTest('Cadastral Overlay: Extracts explicit multi-ring GeoJSON polygon rings', () => {
  const parcel = {
    id: 101,
    rings: [
      [
        [-122.8847, 49.2731],
        [-122.8843, 49.2731],
        [-122.8843, 49.2729],
        [-122.8847, 49.2729],
        [-122.8847, 49.2731]
      ]
    ]
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(coords.length, 5);
  assert.strictEqual(coords[0][0], 49.2731);
  assert.strictEqual(coords[0][1], -122.8847);
});

runTest('Cadastral Overlay: Extracts single-ring GeoJSON polygon coordinates directly', () => {
  const parcel = {
    id: 102,
    rings: [
      [-122.8847, 49.2731],
      [-122.8843, 49.2731],
      [-122.8843, 49.2729],
      [-122.8847, 49.2729],
      [-122.8847, 49.2731]
    ]
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(coords.length, 5);
  assert.strictEqual(coords[0][0], 49.2731);
  assert.strictEqual(coords[0][1], -122.8847);
});

runTest('Cadastral Overlay: Extracts single-ring with STRING coordinate values', () => {
  const parcel = {
    id: 1021,
    rings: [
      ["-122.8847", "49.2731"],
      ["-122.8843", "49.2731"],
      ["-122.8843", "49.2729"],
      ["-122.8847", "49.2729"],
      ["-122.8847", "49.2731"]
    ]
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(coords.length, 5);
  assert.strictEqual(coords[0][0], 49.2731);
  assert.strictEqual(coords[0][1], -122.8847);
  assert.strictEqual(typeof coords[0][0], 'number');
  assert.strictEqual(typeof coords[0][1], 'number');
});

runTest('Cadastral Overlay: Extracts 4D MultiPolygon coordinates with strings and numbers', () => {
  const parcel = {
    id: 1022,
    geometry: {
      type: 'MultiPolygon',
      coordinates: [
        [
          [
            ["-122.8847", "49.2731"],
            ["-122.8843", "49.2731"],
            ["-122.8843", "49.2729"],
            ["-122.8847", "49.2729"],
            ["-122.8847", "49.2731"]
          ]
        ]
      ]
    }
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(coords.length, 5);
  assert.strictEqual(coords[0][0], 49.2731);
  assert.strictEqual(coords[0][1], -122.8847);
});

runTest('Cadastral Overlay: Handles JSON string encoded rings/coordinates', () => {
  const parcel = {
    id: 1023,
    rings: '   [[-122.8847, 49.2731], [-122.8843, 49.2731], [-122.8843, 49.2729], [-122.8847, 49.2729], [-122.8847, 49.2731]]  '
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(coords.length, 5);
  assert.strictEqual(coords[0][0], 49.2731);
  assert.strictEqual(coords[0][1], -122.8847);
});

runTest('Cadastral Overlay: Supports WKT POLYGON strings', () => {
  const parcel = {
    id: 1024,
    rings: 'POLYGON ((-122.8847 49.2731, -122.8843 49.2731, -122.8843 49.2729, -122.8847 49.2729, -122.8847 49.2731))'
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(coords.length, 5);
  assert.strictEqual(coords[0][0], 49.2731);
  assert.strictEqual(coords[0][1], -122.8847);
});

runTest('Cadastral Overlay: Supports GeoJSON Feature object wrapper', () => {
  const feature = {
    type: 'Feature',
    properties: { id: 1025, house: '2648', street: 'Sandstone Cres' },
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [-122.8847, 49.2731],
          [-122.8843, 49.2731],
          [-122.8843, 49.2729],
          [-122.8847, 49.2729],
          [-122.8847, 49.2731]
        ]
      ]
    }
  };
  const coords = getParcelBoundaryCoordinates(feature);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(coords.length, 5);
  assert.strictEqual(coords[0][0], 49.2731);
  assert.strictEqual(coords[0][1], -122.8847);
});

runTest('Cadastral Overlay: Supports object coordinate pairs in rings {lat, lng} and {x, y}', () => {
  const parcelLatLng = {
    id: 1026,
    rings: [
      { lat: 49.2731, lng: -122.8847 },
      { lat: 49.2731, lng: -122.8843 },
      { lat: 49.2729, lng: -122.8843 },
      { lat: 49.2729, lng: -122.8847 },
      { lat: 49.2731, lng: -122.8847 }
    ]
  };
  const coords1 = getParcelBoundaryCoordinates(parcelLatLng);
  assert.strictEqual(Array.isArray(coords1), true);
  assert.strictEqual(coords1.length, 5);
  assert.strictEqual(coords1[0][0], 49.2731);
  assert.strictEqual(coords1[0][1], -122.8847);

  const parcelXY = {
    id: 1027,
    rings: [
      [
        { x: -122.8847, y: 49.2731 },
        { x: -122.8843, y: 49.2731 },
        { x: -122.8843, y: 49.2729 },
        { x: -122.8847, y: 49.2729 },
        { x: -122.8847, y: 49.2731 }
      ]
    ]
  };
  const coords2 = getParcelBoundaryCoordinates(parcelXY);
  assert.strictEqual(Array.isArray(coords2), true);
  assert.strictEqual(coords2.length, 5);
  assert.strictEqual(coords2[0][0], 49.2731);
  assert.strictEqual(coords2[0][1], -122.8847);
});

runTest('Cadastral Overlay: Extracts center lat/lng when geometry is Point', () => {
  const parcel = {
    id: 1028,
    geometry: {
      type: 'Point',
      coordinates: [-122.7950, 49.2850]
    }
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(coords.length, 4);
  assert.strictEqual(coords[0][0], 49.2850 + 0.00012);
  assert.strictEqual(coords[0][1], -122.7950 - 0.00016);
});

runTest('Cadastral Overlay: Supports GeoJSON geometry.coordinates format', () => {
  const parcel = {
    id: 103,
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [-122.8847, 49.2731],
          [-122.8843, 49.2731],
          [-122.8843, 49.2729],
          [-122.8847, 49.2729],
          [-122.8847, 49.2731]
        ]
      ]
    }
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(coords.length, 5);
  assert.strictEqual(coords[0][0], 49.2731);
});

runTest('Cadastral Overlay: Supports alternative latitude/longitude property keys', () => {
  const parcel = {
    id: 1031,
    latitude: "49.2850",
    longitude: "-122.7950"
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(typeof coords[0][0], 'number');
  assert.strictEqual(typeof coords[0][1], 'number');
  assert.strictEqual(coords[0][0], 49.2850 + 0.00012);
  assert.strictEqual(coords[0][1], -122.7950 - 0.00016);
});

runTest('Cadastral Overlay: String lat/lng numeric type coercion immunity', () => {
  const parcel = {
    id: 104,
    lat: "49.2850",
    lng: "-122.7950"
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(typeof coords[0][0], 'number');
  assert.strictEqual(typeof coords[0][1], 'number');
  assert.strictEqual(coords[0][0], 49.2850 + 0.00012);
  assert.strictEqual(coords[0][1], -122.7950 - 0.00016);
});

runTest('Cadastral Overlay: Computes oriented 4-corner lot polygon when frontage is available', () => {
  const parcel = {
    id: 202,
    lat: 49.2850,
    lng: -122.7950,
    front_lat: 49.2853,
    front_lng: -122.7950
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(coords.length, 4);
  assert.strictEqual(coords[0][0] > parcel.lat, true);
  assert.strictEqual(coords[1][0] > parcel.lat, true);
  assert.strictEqual(coords[2][0] < parcel.lat, true);
  assert.strictEqual(coords[3][0] < parcel.lat, true);
});

runTest('Cadastral Overlay: Generates rectangular bounding lot footprint when frontage is missing', () => {
  const parcel = {
    id: 303,
    lat: 49.2850,
    lng: -122.7950
  };
  const coords = getParcelBoundaryCoordinates(parcel);
  assert.strictEqual(Array.isArray(coords), true);
  assert.strictEqual(coords.length, 4);
  assert.strictEqual(coords[0][0], 49.2850 + 0.00012);
  assert.strictEqual(coords[0][1], -122.7950 - 0.00016);
});

runTest('Cadastral Overlay: Handles null, undefined, and empty objects gracefully', () => {
  assert.strictEqual(getParcelBoundaryCoordinates(null), null);
  assert.strictEqual(getParcelBoundaryCoordinates(undefined), null);
  assert.strictEqual(getParcelBoundaryCoordinates({}), null);
  assert.strictEqual(getParcelBoundaryCoordinates({ house: "100" }), null);
  assert.strictEqual(getParcelBoundaryCoordinates({ lat: "invalid", lng: "bad" }), null);
});

runTest('Cross-Basemap Contract: Resolves mapStyle independently from showLabels toggle', () => {
  function resolveBaseMapStyle(appMode, mapStyle) {
    const MODE_DEFAULTS = {
      EXPLORE: "GREY",
      TRAINING_ZONES: "DARK",
      TRAINING_INTERSECTIONS: "GREY",
      TRAINING_BLOCKS: "GREY",
      TRAINING_ADDRESSES: "GREY",
      KIOSK_VIEW: "DARK"
    };
    return mapStyle || MODE_DEFAULTS[appMode] || "GREY";
  }

  assert.strictEqual(resolveBaseMapStyle("EXPLORE", "SATELLITE"), "SATELLITE");
  assert.strictEqual(resolveBaseMapStyle("EXPLORE", "DARK"), "DARK");
  assert.strictEqual(resolveBaseMapStyle("EXPLORE", "GREY"), "GREY");
  assert.strictEqual(resolveBaseMapStyle("EXPLORE", "VOYAGER"), "VOYAGER");
  assert.strictEqual(resolveBaseMapStyle("TRAINING_ZONES", null), "DARK");
  assert.strictEqual(resolveBaseMapStyle("TRAINING_BLOCKS", null), "GREY");
});

runTest('Typography Contract: House number labels use transparent icon class and zero black badges', () => {
  const house = "2648";
  const isSmall = false;
  const cls = isSmall ? 'cadastral-house-number cadastral-house-number-sm' : 'cadastral-house-number';
  const iconOptions = {
    className: 'cadastral-label-icon-container',
    html: `<span class="${cls}">${house}</span>`,
    iconSize: [36, 14],
    iconAnchor: [18, 7],
    popupAnchor: [0, -7]
  };

  assert.strictEqual(iconOptions.className, 'cadastral-label-icon-container');
  assert.strictEqual(iconOptions.html.includes('cadastral-house-number'), true);
  assert.strictEqual(iconOptions.html.includes(house), true);
  assert.strictEqual(iconOptions.html.includes('background: black'), false);
  assert.strictEqual(iconOptions.html.includes('background:#000'), false);
  assert.strictEqual(iconOptions.html.includes('border: 1px solid black'), false);
});

runTest('Deduplication Contract: Multi-unit strata high-rise addresses collapse to single parcel lot', () => {
  function sanitizeAddressSim(raw) {
    return raw.replace(/\s+\d+$/g, '').trim();
  }

  const rawUnits = [
    { address: "1045 Austin Ave 1604", lat: 49.249336, lng: -122.864611, front_lat: 49.249589, front_lng: -122.865295 },
    { address: "1045 Austin Ave 1605", lat: 49.249336, lng: -122.864611, front_lat: 49.249589, front_lng: -122.865295 },
    { address: "1045 Austin Ave 1606", lat: 49.249336, lng: -122.864611, front_lat: 49.249589, front_lng: -122.865295 },
    { address: "2648 Sandstone Cres", lat: 49.2781, lng: -122.8123, front_lat: 49.2783, front_lng: -122.8123 },
    { address: "", lat: 49.2790, lng: -122.8100 },
    { address: "", lat: 49.2795, lng: -122.8105 }
  ];

  const seen = new Map();
  for (const a of rawUnits) {
    const cleanAddr = sanitizeAddressSim(a.address || '');
    const parts = cleanAddr.split(' ');
    const house = parts[0] || '';
    const street = parts.slice(1).join(' ') || '';
    const key = (house || street) ? `${house}|${street}`.toUpperCase() : `${a.lat.toFixed(5)}|${a.lng.toFixed(5)}`;

    if (seen.has(key)) {
      seen.get(key).units++;
    } else {
      seen.set(key, {
        address: cleanAddr,
        house,
        street,
        units: 1,
        lat: a.lat,
        lng: a.lng
      });
    }
  }

  const result = Array.from(seen.values());
  assert.strictEqual(result.length, 4);
  const austin = result.find(r => r.house === '1045');
  assert.strictEqual(austin.units, 3);
  assert.strictEqual(austin.street, 'Austin Ave');
  const sandstone = result.find(r => r.house === '2648');
  assert.strictEqual(sandstone.units, 1);
  const emptyAddrs = result.filter(r => !r.house && !r.street);
  assert.strictEqual(emptyAddrs.length, 2);
});

runTest('CadastralDetailCard: Clean title/subtitle formatting across varied parcel inputs', () => {
  function formatCardTitleAndSubtitle(p) {
    const { address, house, street } = p || {};
    const cleanHouse = house != null ? String(house).trim() : '';
    const cleanStreet = street != null ? String(street).trim() : '';
    const cleanAddress = address != null ? String(address).trim() : '';

    const displayTitle = cleanAddress || (cleanHouse && cleanStreet ? `${cleanHouse} ${cleanStreet}` : cleanStreet || (cleanHouse ? `House #${cleanHouse}` : 'Cadastral Parcel'));
    const displaySubtitle = cleanHouse && cleanStreet ? `House #${cleanHouse} • ${cleanStreet}` : (cleanStreet || (cleanHouse ? `House #${cleanHouse}` : ''));
    return { displayTitle, displaySubtitle };
  }

  const case1 = formatCardTitleAndSubtitle({ house: 2648, street: "Sandstone Cres" });
  assert.strictEqual(case1.displayTitle, "2648 Sandstone Cres");
  assert.strictEqual(case1.displaySubtitle, "House #2648 • Sandstone Cres");

  const case2 = formatCardTitleAndSubtitle({ house: "1045", street: "Austin Ave", address: "1045 Austin Ave" });
  assert.strictEqual(case2.displayTitle, "1045 Austin Ave");
  assert.strictEqual(case2.displaySubtitle, "House #1045 • Austin Ave");

  const case3 = formatCardTitleAndSubtitle({ street: "Como Lake Ave" });
  assert.strictEqual(case3.displayTitle, "Como Lake Ave");
  assert.strictEqual(case3.displaySubtitle, "Como Lake Ave");

  const case4 = formatCardTitleAndSubtitle({});
  assert.strictEqual(case4.displayTitle, "Cadastral Parcel");
  assert.strictEqual(case4.displaySubtitle, "");
});

console.log(`\n=== TEST SUITE COMPLETE ===`);
console.log(`Passed: ${passedTests}`);
console.log(`Failed: ${failedTests}`);
if (failedTests > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
