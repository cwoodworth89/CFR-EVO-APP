/**
 * One loader for the Google Maps JavaScript SDK.
 *
 * The panel used to append a <script> itself and then poll `window.google.maps` every
 * 300 ms for four seconds, with a second panel instance racing the first. This module
 * loads the script once per page, the way Google documents it (`loading=async` with a
 * `callback`), and hands every caller the same promise.
 *
 * Auth is decided by Google ONCE per page load, when the script runs, and reported through
 * the global `gm_authFailure` -- not through the load promise, which resolves normally. A
 * panel mounted hours later (each new call mounts a fresh one) would otherwise find the
 * SDK present, build a panorama Google will only ever render black, and show nothing
 * amiss (the operator's Firefox, 2026-09-06, #35a). So the verdict is kept here, and any
 * panel can read it or subscribe to it.
 *
 * maps.googleapis.com is registered in docs/external_calls.md 4.1. Street View is the one
 * accepted online dependency (operator, 2026-08-30).
 */

const SCRIPT_ID = 'google-maps-js-sdk';
const CALLBACK_NAME = '__cfrGoogleMapsReady';
const LOAD_TIMEOUT_MS = 20000; // a script that has not run in 20 s is not going to; report it

let loadPromise = null;
let authFailed = false;
const authListeners = new Set();

function installAuthHook() {
  if (typeof window === 'undefined') return;
  if (window.gm_authFailure && window.gm_authFailure.__cfr) return;
  const hook = () => {
    console.warn('Google Maps JavaScript API rejected the key (gm_authFailure). The error code is in the console; the fix is on the key in the Cloud console (#35a).');
    authFailed = true;
    authListeners.forEach((fn) => { try { fn(); } catch { /* a listener's problem */ } });
  };
  hook.__cfr = true;
  window.gm_authFailure = hook;
}

/** True once Google has rejected the key on this page; sticky until reload. */
export function isGoogleMapsAuthFailed() {
  return authFailed;
}

/** Called when Google rejects the key. Returns the unsubscribe function. */
export function onGoogleMapsAuthFailure(fn) {
  authListeners.add(fn);
  return () => authListeners.delete(fn);
}

/**
 * Resolves with `window.google.maps` once the SDK is usable; rejects if the script fails
 * to load or never calls back. Safe to call from every panel; the script is added once.
 */
export function loadGoogleMaps(apiKey) {
  if (typeof window === 'undefined') return Promise.reject(new Error('no window'));
  installAuthHook();
  if (window.google?.maps?.StreetViewPanorama) return Promise.resolve(window.google.maps);
  if (loadPromise) return loadPromise;
  if (!apiKey) return Promise.reject(new Error('no Google Maps API key in the build (VITE_GOOGLE_MAPS_API_KEY)'));

  loadPromise = new Promise((resolve, reject) => {
    const finish = (err) => {
      clearTimeout(timer);
      delete window[CALLBACK_NAME];
      if (err) {
        loadPromise = null; // let a later panel try again
        reject(err);
      } else {
        resolve(window.google.maps);
      }
    };
    const timer = setTimeout(() => finish(new Error(`Google Maps SDK did not load within ${LOAD_TIMEOUT_MS / 1000} s`)), LOAD_TIMEOUT_MS);

    window[CALLBACK_NAME] = () => finish(null);

    let script = document.getElementById(SCRIPT_ID);
    if (!script) {
      script = document.createElement('script');
      script.id = SCRIPT_ID;
      script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&loading=async&callback=${CALLBACK_NAME}`;
      script.async = true;
      script.onerror = () => finish(new Error('Google Maps SDK script failed to load'));
      document.head.appendChild(script);
    } else if (window.google?.maps?.StreetViewPanorama) {
      // A script from a previous panel is already here and ready.
      finish(null);
    }
  });
  return loadPromise;
}
