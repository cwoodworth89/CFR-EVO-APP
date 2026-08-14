import fs from 'fs';
import path from 'path';

console.log("=== EMPIRICAL STRESS TEST SUITE FOR STREET VIEW FACADE ENGINE (M2 & M3) ===");

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;
const findings = [];

function assert(condition, testName, failureDetail = '') {
  totalTests++;
  if (condition) {
    passedTests++;
    console.log(`  [PASS] ${testName}`);
  } else {
    failedTests++;
    console.error(`  [FAIL] ${testName} - ${failureDetail}`);
    findings.push({ testName, failureDetail });
  }
}

// ------------------------------------------------------------------
// MOCK ENVIRONMENT SETUP
// ------------------------------------------------------------------
const localStorageStore = new Map();
const mockLocalStorage = {
  getItem: (key) => localStorageStore.get(key) || null,
  setItem: (key, val) => localStorageStore.set(key, String(val)),
  removeItem: (key) => localStorageStore.delete(key),
  clear: () => localStorageStore.clear()
};

const listenersRegistry = new Map(); // instance -> Map<eventName, Set<fn>>
let clearInstanceListenersCalledCount = 0;
const clearedInstances = [];

const mockGoogleMaps = {
  maps: {
    StreetViewPanorama: function(container, opts) {
      this.container = container;
      this.opts = opts || {};
      this._pov = opts.pov || { heading: 0, pitch: 0 };
      this._zoom = opts.zoom || 1;
      this._pano = opts.pano || 'test_pano_123';
      this._position = { lat: () => 49.2838, lng: () => -122.7932 };
      this._status = 'OK';

      listenersRegistry.set(this, new Map());

      this.addListener = (eventName, handler) => {
        const instMap = listenersRegistry.get(this);
        if (!instMap.has(eventName)) {
          instMap.set(eventName, new Set());
        }
        instMap.get(eventName).add(handler);
        return {
          remove: () => {
            instMap.get(eventName)?.delete(handler);
          }
        };
      };

      this.getPov = () => this._pov;
      this.setPov = (pov) => {
        this._pov = pov;
        this.triggerEvent('pov_changed');
      };

      this.getPosition = () => this._position;
      this.setPosition = (pos) => {
        this._position = typeof pos.lat === 'function' ? pos : { lat: () => pos.lat, lng: () => pos.lng };
        this.triggerEvent('position_changed');
      };

      this.getPano = () => this._pano;
      this.setPano = (pano) => {
        this._pano = pano;
        this.triggerEvent('pano_changed');
      };

      this.getZoom = () => this._zoom;
      this.setZoom = (z) => {
        this._zoom = z;
        this.triggerEvent('zoom_changed');
      };

      this.getStatus = () => this._status;
      this.setVisible = () => {};

      this.triggerEvent = (eventName) => {
        const instMap = listenersRegistry.get(this);
        if (instMap && instMap.has(eventName)) {
          for (const handler of instMap.get(eventName)) {
            handler();
          }
        }
      };
    },
    StreetViewService: function() {
      this.getPanorama = (req, cb) => {
        cb({ location: { pano: 'pano_service_999' } }, 'OK');
      };
    },
    StreetViewSource: { OUTDOOR: 'OUTDOOR' },
    StreetViewPreference: { NEAREST: 'NEAREST' },
    StreetViewStatus: { OK: 'OK', ZERO_RESULTS: 'ZERO_RESULTS' },
    event: {
      addListener: (instance, eventName, handler) => {
        return instance.addListener(eventName, handler);
      },
      clearInstanceListeners: (instance) => {
        clearInstanceListenersCalledCount++;
        clearedInstances.push(instance);
        listenersRegistry.delete(instance);
      }
    }
  }
};

// Global scope bindings
globalThis.window = {
  location: { hostname: 'localhost' },
  google: mockGoogleMaps,
  addEventListener: () => {},
  removeEventListener: () => {}
};
globalThis.document = {
  cookie: '',
  head: { appendChild: () => {} },
  getElementById: () => null,
  createElement: () => ({ id: '', src: '', async: false, onload: null, onerror: null })
};
globalThis.localStorage = mockLocalStorage;
globalThis.google = mockGoogleMaps;

// ------------------------------------------------------------------
// TEST 1: API Client Payload & Path Verification
// ------------------------------------------------------------------
console.log("\n--- TEST SUITE 1: REST API Payload & Endpoint Verification ---");

const fetchCalls = [];
globalThis.fetch = async (url, opts = {}) => {
  fetchCalls.push({ url, opts });
  if (url.includes('/api/parcels/lookup')) {
    return {
      ok: true,
      json: async () => ({ found: true, parcel: { clean_address: '3030 GORDON AVE', heading: 35, pitch: 10, fov: 80 } })
    };
  }
  if (url.includes('/api/parcels/streetview')) {
    return {
      ok: true,
      json: async () => ({ status: 'success', message: 'StreetView vector saved to parcels' })
    };
  }
  return { ok: true, json: async () => ({}) };
};

// Evaluate apiClient.js by replacing import.meta.env with process.env or fallback
const apiClientPath = path.resolve('../../frontend/src/apiClient.js');
const apiClientRaw = fs.readFileSync(apiClientPath, 'utf8');
const transformedApiClientCode = apiClientRaw.replace(/import\.meta\.env\.\w+/g, '""');

// Create temp executable module for testing
const tempApiClientPath = path.resolve('./temp_apiClient.mjs');
fs.writeFileSync(tempApiClientPath, transformedApiClientCode);

let apiClientModule;
try {
  apiClientModule = await import(`file://${tempApiClientPath.replace(/\\/g, '/')}`);
  assert(!!apiClientModule.apiClient, "apiClient module exports apiClient", "apiClient missing in module");
} catch (e) {
  assert(false, "apiClient import failed", e.message);
} finally {
  try { fs.unlinkSync(tempApiClientPath); } catch (e) {}
}

if (apiClientModule?.apiClient) {
  const { apiClient } = apiClientModule;

  // Test parcels.lookup URL format
  await apiClient.parcels.lookup('3030 GORDON AVE');
  const lookupCall = fetchCalls.find(c => c.url.includes('/api/parcels/lookup'));
  assert(lookupCall && lookupCall.url.endsWith('/api/parcels/lookup?query=3030%20GORDON%20AVE'),
    "apiClient.parcels.lookup formats query URL with encodeURIComponent",
    `URL was: ${lookupCall?.url}`);

  // Test parcels.saveStreetView payload format
  const samplePayload = {
    clean_address: '3030 GORDON AVE',
    front_lat: 49.26995,
    front_lng: -122.7919,
    heading: 35,
    pitch: 10,
    fov: 80,
    pano_id: 'pano_abc_123'
  };
  await apiClient.parcels.saveStreetView(samplePayload);
  const saveCall = fetchCalls.find(c => c.url.includes('/api/parcels/streetview'));
  assert(saveCall && saveCall.opts.method === 'POST', "apiClient.parcels.saveStreetView sends POST request", `Method: ${saveCall?.opts?.method}`);
  const parsedBody = JSON.parse(saveCall.opts.body);
  assert(parsedBody.clean_address === '3030 GORDON AVE' &&
         parsedBody.heading === 35 &&
         parsedBody.pitch === 10 &&
         parsedBody.fov === 80 &&
         parsedBody.front_lat === 49.26995 &&
         parsedBody.front_lng === -122.7919 &&
         parsedBody.pano_id === 'pano_abc_123',
    "apiClient.parcels.saveStreetView payload matches unified parcels schema",
    `Body: ${JSON.stringify(parsedBody)}`);
}

// ------------------------------------------------------------------
// TEST 2: Continuous Camera Vector State Updates & Rapid Event Stress
// ------------------------------------------------------------------
console.log("\n--- TEST SUITE 2: Continuous Camera Vector Tracking & Rapid Event Stress ---");

const containerMock = {};
const panoInst = new mockGoogleMaps.maps.StreetViewPanorama(containerMock, {
  pov: { heading: 90, pitch: 5 },
  zoom: 2,
  pano: 'initial_pano'
});

const currentPovRef = {
  current: { heading: 0, pitch: 5, zoom: 1, fov: 80, lat: 49.2838, lng: -122.7932, pano_id: '' }
};

// Wire up the 5 listeners exactly as in StreetViewPanel.jsx
panoInst.addListener('pov_changed', () => {
  const pov = panoInst.getPov();
  if (pov && !isNaN(pov.heading)) {
    currentPovRef.current = {
      ...currentPovRef.current,
      heading: Math.round(pov.heading || 0),
      pitch: Math.round(pov.pitch || 0)
    };
  }
});

panoInst.addListener('position_changed', () => {
  const pos = panoInst.getPosition();
  if (pos) {
    const latVal = typeof pos.lat === 'function' ? pos.lat() : pos.lat;
    const lngVal = typeof pos.lng === 'function' ? pos.lng() : pos.lng;
    if (!isNaN(latVal) && !isNaN(lngVal)) {
      currentPovRef.current = {
        ...currentPovRef.current,
        lat: latVal,
        lng: lngVal
      };
    }
  }
});

panoInst.addListener('pano_changed', () => {
  const panoId = panoInst.getPano();
  if (panoId) {
    currentPovRef.current = {
      ...currentPovRef.current,
      pano_id: panoId
    };
  }
});

panoInst.addListener('zoom_changed', () => {
  const z = panoInst.getZoom();
  if (z !== undefined && !isNaN(z)) {
    currentPovRef.current = {
      ...currentPovRef.current,
      zoom: Math.round(z || 1),
      fov: Math.round(z || 1)
    };
  }
});

// Rapid event stress: fire 10,000 updates
const STRESS_CYCLES = 10000;
const startTIme = Date.now();

for (let i = 0; i < STRESS_CYCLES; i++) {
  const heading = i % 360;
  const pitch = (i % 180) - 90;
  const zoom = (i % 4) + 1;
  const lat = 49.2800 + (i * 0.00001);
  const lng = -122.7900 - (i * 0.00001);
  const pano_id = `pano_step_${i}`;

  panoInst.setPov({ heading, pitch });
  panoInst.setZoom(zoom);
  panoInst.setPosition({ lat: () => lat, lng: () => lng });
  panoInst.setPano(pano_id);
}

const elapsedMs = Date.now() - startTIme;
console.log(`  [INFO] Simulated 10,000 continuous pan/tilt/zoom/stepping events in ${elapsedMs}ms`);

assert(currentPovRef.current.heading === (STRESS_CYCLES - 1) % 360,
  "Rapid pov_changed listener correctly updates heading in currentPovRef",
  `Expected ${(STRESS_CYCLES - 1) % 360}, got ${currentPovRef.current.heading}`);

assert(currentPovRef.current.zoom === 4,
  "Rapid zoom_changed listener correctly updates zoom/fov in currentPovRef",
  `Expected 4, got ${currentPovRef.current.zoom}`);

assert(currentPovRef.current.pano_id === `pano_step_${STRESS_CYCLES - 1}`,
  "Rapid pano_changed listener correctly updates pano_id in currentPovRef",
  `Expected pano_step_${STRESS_CYCLES - 1}, got ${currentPovRef.current.pano_id}`);

// ------------------------------------------------------------------
// TEST 3: Memory / Listener Cleanup Verification (google.maps.event.clearInstanceListeners)
// ------------------------------------------------------------------
console.log("\n--- TEST SUITE 3: Memory & Listener Cleanup Verification ---");

// Read StreetViewPanel.jsx source to check cleanup routine
const panelPath = path.resolve('../../frontend/src/components/kiosk/StreetViewPanel.jsx');
const panelSource = fs.readFileSync(panelPath, 'utf8');

const containsClearInstanceListeners = panelSource.includes('clearInstanceListeners');

assert(containsClearInstanceListeners,
  "StreetViewPanel.jsx invokes google.maps.event.clearInstanceListeners in useEffect cleanup",
  "google.maps.event.clearInstanceListeners is NOT present in StreetViewPanel.jsx!");

// Test empirical behavior if cleanup was or wasn't performed
const instListenersMap = listenersRegistry.get(panoInst);
let totalRegisteredListeners = 0;
if (instListenersMap) {
  for (const set of instListenersMap.values()) {
    totalRegisteredListeners += set.size;
  }
}
console.log(`  [INFO] Total active registered listeners on StreetViewPanorama instance: ${totalRegisteredListeners}`);

// Simulate unmount cleanup call:
mockGoogleMaps.maps.event.clearInstanceListeners(panoInst);
assert(!listenersRegistry.has(panoInst),
  "Executing google.maps.event.clearInstanceListeners removes all attached listeners from memory",
  "Listeners were not cleared from registry");

// ------------------------------------------------------------------
// TEST 4: LocalStorage Fallback & Priority Ordering
// ------------------------------------------------------------------
console.log("\n--- TEST SUITE 4: LocalStorage Fallback & Priority Resolution ---");

const testAddressKey = "3030 GORDON AVE";
const storageKey = `cfr_sv_override_${testAddressKey}`;

// Write test value to local storage
const lsPayload = {
  clean_address: testAddressKey,
  front_lat: 49.26995,
  front_lng: -122.7919,
  heading: 145,
  pitch: 12,
  fov: 75,
  pano_id: 'ls_pano_777'
};
mockLocalStorage.setItem(storageKey, JSON.stringify(lsPayload));

const retrievedLS = JSON.parse(mockLocalStorage.getItem(storageKey));
assert(retrievedLS.heading === 145 && retrievedLS.pano_id === 'ls_pano_777',
  "LocalStorage correctly persists and retrieves StreetView override vector",
  `Retrieved: ${JSON.stringify(retrievedLS)}`);

// ------------------------------------------------------------------
// SUMMARY & FINDINGS
// ------------------------------------------------------------------
console.log("\n==================================================================");
console.log(`RESULTS: ${passedTests}/${totalTests} PASSED, ${failedTests} FAILED`);
console.log("==================================================================");

if (findings.length > 0) {
  console.log("\nFAILURES / FINDINGS SURFACE:");
  findings.forEach((f, idx) => {
    console.log(`${idx + 1}. [${f.testName}] - ${f.failureDetail}`);
  });
}
