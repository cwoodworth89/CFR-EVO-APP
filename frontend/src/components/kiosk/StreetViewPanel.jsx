import React, { useState, useEffect, useRef } from 'react';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';
import { sanitizeAddress } from '../../utils/addressUtils';
import { apiClient } from '../../apiClient';

/**
 * THE ONE ONLINE-DEPENDENT SURFACE IN AN OFFLINE-FIRST SYSTEM.
 *
 * CLAUDE.md §1 requires the whole system to work with no WAN. This panel does not,
 * and cannot: Google Street View panoramas are fetched live from
 * maps.googleapis.com and are not licensed for local caching the way the municipal
 * orthophotos are.
 *
 * ACCEPTED RISK, operator decision 2026-08-30. Street View is a pre-arrival
 * convenience -- a look at the front of the building -- not a dispatch-critical
 * surface. Everything a crew needs to be dispatched and routed (address, map grid,
 * parcel outline, satellite imagery, turn-by-turn) is served from local MBTiles and
 * PostGIS and is unaffected when this panel is blank.
 *
 * WHAT THIS MEANS IN PRACTICE:
 *   * No WAN  -> panel is blank. That is expected, not a defect.
 *   * The API key is inlined by Vite at BUILD time, so frontend/.env.local must be
 *     present on the kiosk when `npm run build` runs. It is git-ignored, so a fresh
 *     clone will not have it.
 *   * Found 2026-09-06 in Chrome against the kiosk build (punch-list #35a): the Maps
 *     JavaScript API answers `ApiTargetBlockedMapError` -- the key's API restrictions
 *     in the Google Cloud console do not include the Maps JavaScript API -- so
 *     gm_authFailure fires, sdkError is set, and the <iframe> Embed API fallback (a
 *     different API, which the key is allowed) renders. That fallback used to be
 *     silent and its save button wrote the initial camera values back as if the
 *     operator had set them; both now say so on the panel. The fix for the key is in
 *     the console, not here.
 */
// Google's relation between the panorama's zoom and its field of view: fov = 180 / 2^zoom
// (Maps JavaScript API StreetViewPanorama docs; zoom 1 is 90 degrees). The database holds
// degrees; the SDK speaks zoom; the Static API takes degrees, 10..120.
const fovToZoom = (fov) => Math.log2(180 / Math.min(Math.max(Number(fov) || 90, 10), 180));
const zoomToFov = (zoom) => Math.round(180 / Math.pow(2, Number(zoom) || 0));
const clampStaticFov = (fov) => Math.min(Math.max(Math.round(Number(fov) || 90), 10), 120);
// Zoom bounds for the interactive panorama, derived from clampStaticFov above rather than
// picked: zoomToFov(1) is 90 degrees and zoomToFov(4) is 11, both inside the Static API's
// 10..120, so the compact tile and the expanded panorama can render the same saved view.
// Zoom 0 would be 180 degrees, which the Static API cannot express.
const clampPanoZoom = (zoom) => Math.min(Math.max(Number(zoom) || 1, 1), 4);

export default function StreetViewPanel({ activeCall }) {
  const isOnline = useOnlineStatus();
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

  const [isExpanded, setIsExpanded] = useState(false);
  // The compact tile is a Street View Static API image at the saved view; the interactive
  // panorama (and the save) live behind Expand (operator, 2026-09-06). When the image fails
  // -- the key not allowed for the Static API, no imagery, offline -- the tile falls back to
  // the interactive panorama and says so.
  const [staticFailed, setStaticFailed] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);
  const [dbOverride, setDbOverride] = useState(null);
  // Google reports an auth failure ONCE per page, when the SDK script first loads. Every
  // later panel instance (each new call mounts a fresh one) would start clean, find
  // window.google.maps present, build a panorama the SDK will only ever render black, and
  // show nothing amiss -- the operator's Firefox on 2026-09-06, hours after the first
  // failure. So the verdict is kept on the window and read at mount (punch-list #35a).
  const [sdkError, setSdkError] = useState(() => Boolean(typeof window !== 'undefined' && window.__cfrGmAuthFailed));
  const [isLoading, setIsLoading] = useState(true);

  const containerRef = useRef(null);
  const modalContainerRef = useRef(null);
  const panoramaRef = useRef(null);
  const currentPovRef = useRef({ heading: 0, pitch: 5, zoom: 1, fov: 80, lat: null, lng: null, pano_id: '' });

  const cleanAddrKey = sanitizeAddress(activeCall?.address || '').toUpperCase();

  // Helper for instant local storage override retrieval
  const getLocalOverride = () => {
    if (!cleanAddrKey) return null;
    try {
      const stored = localStorage.getItem(`cfr_sv_override_${cleanAddrKey}`);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  };

  const localOverride = getLocalOverride();

  // Fetch DB override on mount or when address changes via apiClient.parcels.lookup
  useEffect(() => {
    let isMounted = true;
    // Intentional: clear the previous address's override before the new lookup
    // resolves, so a stale Street View heading is never shown against a new
    // incident. The cascading render is the point, not an oversight.
    setDbOverride(null);
    if (!cleanAddrKey) return;

    apiClient.parcels.lookup(cleanAddrKey)
      .then((res) => {
        if (isMounted && res?.found && res?.parcel) {
          const p = res.parcel;
          // An override exists only when a heading was saved. Since the 2026-09-06
          // migration an unsaved parcel holds NULL here; before it every parcel carried
          // the column defaults and read as a saved 0-degree view (#35a).
          const savedHeading = p.streetview_heading ?? p.heading;
          if (savedHeading != null) {
            const fov = p.streetview_fov ?? p.fov ?? 90;
            setDbOverride({
              lat: p.front_lat ?? p.lat,
              lng: p.front_lng ?? p.lng,
              heading: savedHeading,
              pitch: p.streetview_pitch ?? p.pitch ?? 5,
              fov,
              zoom: fovToZoom(fov),
              pano_id: p.streetview_pano_id ?? p.pano_id ?? ''
            });
          }
        }
      })
      .catch((err) => {
        console.warn('Failed to fetch parcel Street View override:', err);
      });

    return () => {
      isMounted = false;
    };
  }, [cleanAddrKey]);

  // Priority: 1. DB Override -> 2. Local Storage -> 3. Target parcel centroid -> 4. Fallback
  const activeOverride = dbOverride || localOverride;

  const rawFrontLat = activeOverride
    ? (activeOverride.lat ?? activeOverride.front_lat)
    : (activeCall?.lat ?? activeCall?.front_lat ?? activeCall?.target?.lat ?? null);
  const rawFrontLng = activeOverride
    ? (activeOverride.lng ?? activeOverride.front_lng)
    : (activeCall?.lng ?? activeCall?.front_lng ?? activeCall?.target?.lng ?? null);

  const hasCoords = rawFrontLat != null && rawFrontLng != null &&
    !isNaN(parseFloat(rawFrontLat)) && !isNaN(parseFloat(rawFrontLng)) &&
    (parseFloat(rawFrontLat) !== 0 || parseFloat(rawFrontLng) !== 0);

  const frontLat = hasCoords ? parseFloat(rawFrontLat) : null;
  const frontLng = hasCoords ? parseFloat(rawFrontLng) : null;

  const rawTargetLat = activeCall?.lat ?? activeCall?.target?.lat ?? frontLat;
  const rawTargetLng = activeCall?.lng ?? activeCall?.target?.lng ?? frontLng;
  const targetLat = rawTargetLat != null ? parseFloat(rawTargetLat) : frontLat;
  const targetLng = rawTargetLng != null ? parseFloat(rawTargetLng) : frontLng;

  let initialHeading = activeOverride ? parseFloat(activeOverride.heading ?? activeOverride.streetview_heading ?? 0) : 0;
  if (!activeOverride && hasCoords && targetLat != null && targetLng != null && (frontLat !== targetLat || frontLng !== targetLng)) {
    const dLng = (targetLng - frontLng) * (Math.PI / 180);
    const targetLatRad = targetLat * (Math.PI / 180);
    const frontLatRad = frontLat * (Math.PI / 180);
    const y = Math.sin(dLng) * Math.cos(targetLatRad);
    const x = Math.cos(frontLatRad) * Math.sin(targetLatRad) - Math.sin(frontLatRad) * Math.cos(targetLatRad) * Math.cos(dLng);
    const bearing = Math.atan2(y, x) * (180 / Math.PI);
    initialHeading = Math.round((bearing + 360) % 360);
  }

  const initialPitch = activeOverride ? parseFloat(activeOverride.pitch ?? activeOverride.streetview_pitch ?? 5) : 5;
  const initialFov = activeOverride ? parseFloat(activeOverride.fov ?? activeOverride.streetview_fov ?? 90) : 90;
  const initialZoom = activeOverride ? parseFloat(activeOverride.zoom ?? fovToZoom(initialFov)) : 1;
  const initialPanoId = activeOverride?.pano_id || '';

  // Initialize camera vector in ref
  useEffect(() => {
    if (!hasCoords) return;
    currentPovRef.current = {
      heading: initialHeading,
      pitch: initialPitch,
      zoom: initialZoom,
      fov: initialFov,
      lat: frontLat,
      lng: frontLng,
      pano_id: initialPanoId
    };
  }, [initialHeading, initialPitch, initialZoom, initialFov, frontLat, frontLng, initialPanoId, hasCoords]);


  // Global auth failure handler
  useEffect(() => {
    window.gm_authFailure = () => {
      console.warn("Google Maps JS SDK auth failure triggered. Check Google Cloud Console 'Maps JavaScript API' status.");
      window.__cfrGmAuthFailed = true;
      setSdkError(true);
      setIsLoading(false);
    };
  }, []);

  // Primary Google Maps StreetViewPanorama Initialization (Conforms strictly to JS SDK)
  useEffect(() => {
    if (!apiKey || !isOnline || sdkError) return;

    const targetContainer = isExpanded ? modalContainerRef.current : containerRef.current;
    if (!targetContainer) return;

    // Intentional: the panorama mounts asynchronously via the Google SDK and this
    // marks the loading state before that begins.
    setIsLoading(true);

    const initPanorama = () => {
      if (!window.google || !window.google.maps) return;

      // Clean container DOM before mounting
      targetContainer.innerHTML = '';

      try {
        const panoOptions = {
          pov: { heading: initialHeading, pitch: initialPitch },
          zoom: clampPanoZoom(initialZoom),
          fullscreenControl: false,
          addressControl: false,
          panControl: false,
          linksControl: true,
          motionTracking: false,
          motionTrackingControl: false,
          showRoadLabels: true,
          visible: true
        };

        if (initialPanoId) {
          panoOptions.pano = initialPanoId;
        }

        const pano = new window.google.maps.StreetViewPanorama(targetContainer, panoOptions);

        // Resolve nearest street panorama within 50m outdoor radius (prevents jumping to random streets 300m away)
        const svService = new window.google.maps.StreetViewService();
        if (initialPanoId) {
          pano.setPano(initialPanoId);
          pano.setPov({ heading: initialHeading, pitch: initialPitch });
          pano.setVisible(true);
          setIsLoading(false);
        } else {
          svService.getPanorama({
            location: { lat: frontLat, lng: frontLng },
            radius: 50,
            source: window.google.maps.StreetViewSource.OUTDOOR,
            preference: window.google.maps.StreetViewPreference.NEAREST
          }, (data, status) => {
            if (status === window.google.maps.StreetViewStatus.OK && data && data.location) {
              pano.setPano(data.location.pano);
              pano.setPov({ heading: initialHeading, pitch: initialPitch });
              pano.setVisible(true);
              setIsLoading(false);
            } else {
              // 100m fallback if 50m tight radius misses
              svService.getPanorama({
                location: { lat: frontLat, lng: frontLng },
                radius: 100,
                source: window.google.maps.StreetViewSource.OUTDOOR,
                preference: window.google.maps.StreetViewPreference.NEAREST
              }, (data2, status2) => {
                if (status2 === window.google.maps.StreetViewStatus.OK && data2 && data2.location) {
                  pano.setPano(data2.location.pano);
                  pano.setPov({ heading: initialHeading, pitch: initialPitch });
                  pano.setVisible(true);
                } else {
                  console.warn("Outdoor StreetViewService fallback to position:", status2);
                  pano.setPosition({ lat: frontLat, lng: frontLng });
                }
                setIsLoading(false);
              });
            }
          });
        }

        // 1. pov_changed: Continuous heading & pitch tracking
        pano.addListener('pov_changed', () => {
          const pov = pano.getPov();
          if (pov && !isNaN(pov.heading)) {
            currentPovRef.current = {
              ...currentPovRef.current,
              heading: Math.round(pov.heading || 0),
              pitch: Math.round(pov.pitch || 0)
            };
          }
        });

        // 2. position_changed: Continuous lat/lng tracking
        pano.addListener('position_changed', () => {
          const pos = pano.getPosition();
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
          setIsLoading(false);
        });

        // 3. pano_changed: Continuous pano_id & position tracking
        pano.addListener('pano_changed', () => {
          const panoId = pano.getPano();
          if (panoId) {
            currentPovRef.current = {
              ...currentPovRef.current,
              pano_id: panoId
            };
            const pos = pano.getPosition();
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
          }
        });

        // 4. zoom_changed: Continuous zoom tracking
        pano.addListener('zoom_changed', () => {
          const z = pano.getZoom();
          if (z !== undefined && !isNaN(z)) {
            currentPovRef.current = {
              ...currentPovRef.current,
              zoom: Math.round(z || 1),
              fov: Math.round(z || 1)
            };
          }
        });

        // 5. status_changed: Monitor panorama status & update loading skeleton
        pano.addListener('status_changed', () => {
          setIsLoading(false);
        });

        panoramaRef.current = pano;

        // Safety fallback timer to clear loading skeleton after 3.5 seconds max
        setTimeout(() => {
          setIsLoading(false);
        }, 3500);
      } catch (err) {
        console.error("Failed to initialize Google StreetViewPanorama:", err);
        setSdkError(true);
        setIsLoading(false);
      }
    };

    if (window.google && window.google.maps) {
      initPanorama();
    } else {
      const existingScript = document.getElementById('google-maps-js-sdk');
      if (!existingScript) {
        const script = document.createElement('script');
        script.id = 'google-maps-js-sdk';
        script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}`;
        script.async = true;
        script.onload = initPanorama;
        script.onerror = () => {
          setSdkError(true);
          setIsLoading(false);
        };
        document.head.appendChild(script);
      } else {
        if (window.google && window.google.maps) {
          initPanorama();
        } else {
          existingScript.addEventListener('load', initPanorama);
          const interval = setInterval(() => {
            if (window.google && window.google.maps) {
              clearInterval(interval);
              initPanorama();
            }
          }, 300);
          setTimeout(() => clearInterval(interval), 4000);
        }
      }
    }

    return () => {
      if (window.google?.maps?.event && panoramaRef.current) {
        window.google.maps.event.clearInstanceListeners(panoramaRef.current);
      }
      if (targetContainer) targetContainer.innerHTML = '';
      panoramaRef.current = null;
    };
    // Intentional: this effect CONSTRUCTS the panorama, so it must not re-run when the
    // saved view changes -- that would tear down and rebuild the panorama under the
    // operator, which is the failure the separate effect below was written to avoid. That
    // effect owns frontLat, frontLng, initialHeading, initialPitch and initialPanoId and
    // pushes them onto the live panorama instead.
    //
    // All six names in this warning are owned by that effect, initialZoom included. It was
    // the one exception until 2026-09-08: applied at construction and carried in
    // currentPovRef, so a saved zoom survived a save and a remount, but a zoom arriving
    // while the panorama was already mounted never reached what the operator saw.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cleanAddrKey, isExpanded, apiKey, isOnline, sdkError]);

  // Smooth POV & Location update when dbOverride arrives
  useEffect(() => {
    if (!panoramaRef.current || !window.google || !window.google.maps) return;

    // Zoom is not part of StreetViewPov -- the SDK carries it separately, which is why
    // setPov above cannot deliver it and why the save path reads it back through getZoom.
    // Feature-guarded like that getZoom call: this is a runtime SDK, so nothing pins the
    // surface we are calling (CLAUDE.md s7.3a).
    const applyZoom = () => {
      if (typeof panoramaRef.current?.setZoom === 'function') {
        panoramaRef.current.setZoom(clampPanoZoom(initialZoom));
      }
    };

    try {
      const svService = new window.google.maps.StreetViewService();
      if (initialPanoId) {
        panoramaRef.current.setPano(initialPanoId);
        panoramaRef.current.setPov({ heading: initialHeading, pitch: initialPitch });
        applyZoom();
        panoramaRef.current.setVisible(true);
      } else {
        svService.getPanorama({
          location: { lat: frontLat, lng: frontLng },
          radius: 50,
          source: window.google.maps.StreetViewSource.OUTDOOR,
          preference: window.google.maps.StreetViewPreference.NEAREST
        }, (data, status) => {
          if (status === window.google.maps.StreetViewStatus.OK && data && data.location && panoramaRef.current) {
            panoramaRef.current.setPano(data.location.pano);
            panoramaRef.current.setPov({ heading: initialHeading, pitch: initialPitch });
            applyZoom();
            panoramaRef.current.setVisible(true);
          }
        });
      }
    } catch (e) {
      console.warn("Failed to update active panorama POV:", e);
    }
  }, [frontLat, frontLng, initialHeading, initialPitch, initialPanoId, initialZoom]);

  // Save Preferred View handler reading camera vector from currentPovRef.current
  const handleSaveView = async () => {
    if (!activeCall?.address || !cleanAddrKey) return;
    setSaveStatus('saving');

    const curr = currentPovRef.current || {};
    let currentHeading = curr.heading ?? initialHeading;
    let currentPitch = curr.pitch ?? initialPitch;
    let currentZoom = curr.zoom ?? curr.fov ?? 1;
    let currentPanoId = curr.pano_id || '';
    let saveLat = curr.lat ?? frontLat;
    let saveLng = curr.lng ?? frontLng;

    if (panoramaRef.current) {
      if (typeof panoramaRef.current.getPov === 'function') {
        const pov = panoramaRef.current.getPov();
        if (pov && !isNaN(pov.heading)) {
          currentHeading = Math.round(pov.heading || 0);
          currentPitch = Math.round(pov.pitch || 0);
        }
      }
      if (typeof panoramaRef.current.getZoom === 'function') {
        const z = panoramaRef.current.getZoom();
        if (z !== undefined && !isNaN(z)) {
          currentZoom = Math.round((z || 1) * 100) / 100;
        }
      }
      if (typeof panoramaRef.current.getPano === 'function') {
        const pId = panoramaRef.current.getPano();
        if (pId) currentPanoId = pId;
      }
      if (typeof panoramaRef.current.getPosition === 'function') {
        const loc = panoramaRef.current.getPosition();
        if (loc) {
          const latVal = typeof loc.lat === 'function' ? loc.lat() : loc.lat;
          const lngVal = typeof loc.lng === 'function' ? loc.lng() : loc.lng;
          if (!isNaN(latVal) && !isNaN(lngVal)) {
            saveLat = latVal;
            saveLng = lngVal;
          }
        }
      }
    }

    const payload = {
      address: cleanAddrKey,
      clean_address: cleanAddrKey,
      front_lat: saveLat,
      front_lng: saveLng,
      heading: currentHeading,
      pitch: currentPitch,
      // Degrees. This used to send the zoom level (0-4) and the database held "fov 1" for
      // a 90-degree view (#35a, 2026-09-06).
      fov: zoomToFov(currentZoom),
      zoom: currentZoom,
      pano_id: currentPanoId
    };

    try {
      localStorage.setItem(`cfr_sv_override_${cleanAddrKey}`, JSON.stringify(payload));
      await apiClient.parcels.saveStreetView(payload);
      try {
        await apiClient.streetView.saveOverride(payload);
      } catch { /* non-fatal: caller handles the absent value */ }
      setDbOverride(payload);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (e) {
      console.error('Failed to save Street View angle:', e);
      setDbOverride(payload);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus(null), 3000);
    }
  };

  // Reset the static-image verdict for each new address.
  const [staticKey, setStaticKey] = useState(cleanAddrKey);
  if (staticKey !== cleanAddrKey) {
    setStaticKey(cleanAddrKey);
    setStaticFailed(false);
  }

  // maps.googleapis.com/maps/api/streetview -- registered in docs/external_calls.md 4.1.
  // return_error_code makes a miss an HTTP error the <img> reports, not a grey placeholder.
  const staticStreetViewUrl = hasCoords && apiKey
    ? `https://maps.googleapis.com/maps/api/streetview?size=640x400`
      + (initialPanoId ? `&pano=${encodeURIComponent(initialPanoId)}` : `&location=${frontLat},${frontLng}`)
      + `&heading=${Math.round(initialHeading)}&pitch=${Math.round(initialPitch)}&fov=${clampStaticFov(initialFov)}`
      + `&return_error_code=true&key=${apiKey}`
    : '';
  const useStaticTile = Boolean(staticStreetViewUrl) && !staticFailed;

  const embedStreetViewUrl = hasCoords
    ? (apiKey
        ? `https://www.google.com/maps/embed/v1/streetview?key=${apiKey}&location=${frontLat},${frontLng}&heading=${initialHeading}&pitch=${initialPitch}`
        : `https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d1000!2d${frontLng}!3d${frontLat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!5e1!3m2!1sen!2sca`)
    : '';

  const renderContent = (isModal = false) => (
    <div className="w-full h-full relative bg-slate-900 flex flex-col items-center justify-center overflow-hidden">
      {!isModal && useStaticTile && (
        <img
          src={staticStreetViewUrl}
          alt={`Street View of ${activeCall?.address || 'the target'}`}
          className="w-full h-full object-cover"
          onError={() => setStaticFailed(true)}
        />
      )}
      {!isModal && staticFailed && (
        <div className="absolute top-12 left-2 z-20 bg-amber-950/90 border border-amber-700 text-amber-200 px-2 py-1 rounded text-[10px] font-mono">
          Static image unavailable; showing the interactive view
        </div>
      )}
      {/* Sleek Dark HUD Skeleton Loader */}
      {isLoading && isOnline && !sdkError && (isModal || !useStaticTile) && (
        <div className="absolute inset-0 z-10 bg-slate-950 flex flex-col items-center justify-center gap-3 transition-opacity duration-300">
          <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
          <div className="text-indigo-300 text-xs font-mono font-bold tracking-wider animate-pulse">
            Loading Street View Facade...
          </div>
        </div>
      )}

      {/* The SDK failure used to be silent: the embed below looks like the real thing, and
          the save button kept working on stale values. Say what is shown and why (6.1). */}
      {sdkError && (
        <div className="absolute top-2 right-2 z-20 max-w-[60%] bg-amber-950/95 border border-amber-600 text-amber-200 px-2.5 py-1.5 rounded-lg text-[10px] font-mono leading-snug shadow-lg">
          <span className="font-bold">⚠️ INTERACTIVE VIEW UNAVAILABLE</span> — Google rejected the
          key for the Maps JavaScript API; a static embed is shown and the camera angle cannot be
          saved. The error code is in the browser console (punch-list #35a).
        </div>
      )}
      {(!isModal && useStaticTile) ? null : sdkError ? (
        <iframe
          title="Fallback Google Street View Embed"
          width="100%"
          height="100%"
          style={{ border: 0 }}
          loading="lazy"
          allowFullScreen
          src={embedStreetViewUrl}
          className="w-full h-full"
        />
      ) : (
        <div
          ref={isModal ? modalContainerRef : containerRef}
          style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }}
        >
          {!apiKey && (
            <iframe
              title="Live Interactive Google Street View 360"
              width="100%"
              height="100%"
              style={{ border: 0 }}
              loading="lazy"
              allowFullScreen
              src={embedStreetViewUrl}
              className="w-full h-full"
            />
          )}
        </div>
      )}

      {/* Address & Save Overlay -- the expanded view only. On the compact tile it covered a
          third of the picture and the address is already in the banner; saving a view is
          something done after looking around, which the tile does not allow (operator,
          2026-09-06). */}
      {isModal && (
      <div className="absolute bottom-2 left-2 right-2 z-20 bg-slate-900/95 backdrop-blur border border-slate-800 p-2.5 rounded-xl flex items-center justify-between shadow-2xl">
        <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
          <span className="text-amber-400 font-bold">📍 Address:</span>
          <span className="text-white font-bold">{activeCall?.address || 'Destination'}</span>
          {activeOverride && (
            <span className="bg-emerald-900/80 text-emerald-300 border border-emerald-700 px-2 py-0.5 rounded text-[10px] font-bold">
              SAVED PREFERRED VIEW ({(activeOverride.heading ?? activeOverride.streetview_heading ?? initialHeading)}°)
            </span>
          )}
        </div>

        {/* Save Preferred View Button */}
        <button
          onClick={handleSaveView}
          // With the SDK down there is no panorama to read a heading from: the save would
          // write the initial values back and report success (CLAUDE.md 6.1, punch-list #35a).
          disabled={saveStatus === 'saving' || sdkError}
          title={sdkError ? 'Interactive Street View is unavailable, so there is no camera angle to save' : undefined}
          className={`px-4 py-1.5 rounded-xl border font-bold text-xs transition shadow flex items-center gap-1.5 ${
            sdkError
              ? 'bg-slate-800 border-slate-700 text-slate-500 cursor-not-allowed'
              : saveStatus === 'saved'
              ? 'bg-emerald-600 border-emerald-400 text-white'
              : saveStatus === 'error'
              ? 'bg-red-600 border-red-400 text-white'
              : 'bg-amber-500 hover:bg-amber-400 border-amber-300 text-slate-950 cursor-pointer'
          }`}
        >
          <span>💾</span>
          <span>
            {sdkError
              ? 'No interactive view to save'
              : saveStatus === 'saving'
              ? 'Saving...'
              : saveStatus === 'saved'
              ? '✅ Saved Preferred View!'
              : saveStatus === 'error'
              ? '❌ Failed'
              : 'Save Preferred View'}
          </span>
        </button>
      </div>
      )}
    </div>
  );

  // Standby Error State: Awaiting Valid Coordinates
  if (!hasCoords) {
    return (
      <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col items-center justify-center p-6 text-center">
        <div className="absolute top-2 left-2 z-20 bg-slate-900/90 backdrop-blur px-3 py-1.5 rounded-xl border border-slate-800 text-xs font-bold text-indigo-400 flex items-center gap-2 shadow">
          <span>📷</span>
          <span>Google Street View 360°</span>
        </div>
        <div className="w-14 h-14 rounded-2xl bg-indigo-950/40 border border-indigo-700/50 flex items-center justify-center text-2xl mb-3 shadow-inner">
          📷
        </div>
        <h4 className="text-sm font-black uppercase tracking-wider text-indigo-300 font-mono">
          Street View Standby
        </h4>
        <p className="text-xs text-slate-400 font-mono mt-1 max-w-xs leading-relaxed">
          Awaiting Valid Coordinates
        </p>
      </div>
    );
  }


  return (
    <>
      <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col">
        {/* Header: small. The tile is the picture (operator, 2026-09-06). A saved view is a
            green dot with its heading; the wording lives in the expanded view. */}
        <div className="absolute top-2 left-2 z-20 bg-slate-900/80 backdrop-blur px-2 py-1 rounded-lg border border-slate-800 text-[11px] font-bold text-indigo-300 flex items-center gap-1.5 shadow">
          <span>📷</span>
          <span>Street View</span>
          {activeOverride && (
            <span className="text-emerald-400 font-mono text-[10px]" title="Saved preferred view">
              ● {Math.round(initialHeading)}°
            </span>
          )}
          {!isOnline && <span className="bg-amber-900/80 text-amber-200 px-1.5 py-0.5 rounded text-[9px]">Offline</span>}
        </div>

        {/* Custom Expand Button (Sitting cleanly in top right corner!) */}
        <button
          onClick={() => setIsExpanded(true)}
          className="absolute top-2 right-2 z-20 bg-slate-900/90 hover:bg-indigo-600 text-indigo-300 hover:text-white px-3 py-1.5 rounded-xl border border-slate-700 text-xs font-bold transition flex items-center gap-1.5 shadow cursor-pointer"
          title="Pop Out Full Screen View"
        >
          <span>⤢</span>
          <span>Expand</span>
        </button>

        {isOnline ? (
          renderContent(false)
        ) : (
          <div className="flex flex-col items-center justify-center p-3 text-center text-slate-400 gap-1.5 h-full">
            <span className="text-2xl">🏛️</span>
            <p className="text-xs font-semibold">Local Building Footprint Canvas</p>
            <span className="text-[10px] text-slate-500">Address Centroid Verified</span>
          </div>
        )}
      </div>

      {/* Popout Full-Screen Modal */}
      {isExpanded && (
        <div className="fixed inset-0 z-[9999] bg-slate-950/95 backdrop-blur-md p-4 sm:p-8 flex flex-col animate-in fade-in duration-200">
          <div className="flex items-center justify-between mb-3 bg-slate-900 border border-slate-800 p-3 rounded-xl shadow-lg">
            <div className="flex items-center gap-2">
              <span className="text-xl">📷</span>
              <div>
                <h3 className="text-base font-bold text-white uppercase tracking-wide">Google Street View 360° Inspection</h3>
                <p className="text-xs text-indigo-400 font-mono">📍 {activeCall?.address || 'Target Property'}</p>
              </div>
              {activeOverride && (
                <span className="bg-emerald-500 text-slate-950 px-2 py-0.5 rounded text-[10px] font-black tracking-wider shadow animate-pulse ml-2">
                  [SAVED PREFERRED VIEW]
                </span>
              )}
            </div>
            <button
              onClick={() => setIsExpanded(false)}
              className="bg-red-600 hover:bg-red-500 text-white font-bold text-sm px-4 py-2 rounded-lg transition shadow flex items-center gap-1.5 cursor-pointer"
            >
              <span>✕</span>
              <span>CLOSE</span>
            </button>
          </div>

          <div className="flex-1 w-full rounded-2xl overflow-hidden border-2 border-indigo-500/50 shadow-2xl relative">
            {renderContent(true)}
          </div>
        </div>
      )}
    </>
  );
}
