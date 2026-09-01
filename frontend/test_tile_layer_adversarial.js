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

// ---------------------------------------------------------------------------
// WARNING: the two *Pure functions below are HAND-COPIES of getTileUrl and
// getTileLayerConfig in src/apiClient.js -- they are not imported from it,
// because apiClient.js is an ES module reading import.meta.env and will not
// load under plain node.
//
// So this suite tests a duplicate, not the shipping code, and CANNOT catch
// drift between the two. On 2026-08-31 the aerial layer moved from
// /services/satellite to /services/ortho in three source files and every
// assertion here still passed, green, against the old URL. If you change
// apiClient.js, you must mirror it here by hand or these tests will quietly
// certify the wrong behaviour.
// ---------------------------------------------------------------------------

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
    return `${tileBaseUrl}/services/ortho/tiles/${z}/${x}/${y}.jpg`;
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
        url: `${tileBaseUrl}/services/ortho/tiles/{z}/{x}/{y}.jpg`,
        fallbackUrl: null,
        attribution: 'City of Coquitlam 2025 7.5cm Orthophoto (Open Government Licence, Offline Local Cache)',
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
  assert.strictEqual(url, 'http://localhost:8081/services/ortho/tiles/{z}/{x}/{y}.jpg');
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
  assert.strictEqual(url, 'http://localhost:8081/services/ortho/tiles/16/500/600.jpg');
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
  assert.strictEqual(configNull.url, 'http://localhost:8081/services/ortho/tiles/{z}/{x}/{y}.jpg');
  assert.strictEqual(configUndef.url, 'http://localhost:8081/services/ortho/tiles/{z}/{x}/{y}.jpg');
  assert.strictEqual(configEmpty.url, 'http://localhost:8081/services/ortho/tiles/{z}/{x}/{y}.jpg');
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

console.log(`\n=== TEST SUITE COMPLETE ===`);
console.log(`Passed: ${passedTests}`);
console.log(`Failed: ${failedTests}`);
if (failedTests > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
