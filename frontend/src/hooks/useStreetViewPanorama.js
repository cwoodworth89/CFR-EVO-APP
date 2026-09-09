import { useCallback, useEffect, useRef, useState } from 'react';
import { loadGoogleMaps, isGoogleMapsAuthFailed, onGoogleMapsAuthFailure } from '../utils/googleMapsLoader';
import { fovToZoom, zoomToFov, viewsMatch } from '../utils/streetViewGeometry';

// Where to look for imagery when the view names no panorama: outdoor imagery nearest the
// camera point, first within 50 m, then 100 m. Inherited from the panel (2026-08), where
// the 50 m radius was chosen to stop the SDK jumping to a panorama on another street; not
// measured, and the operator's saved pano id makes this the exception path.
const SEARCH_RADII_M = [50, 100];

/**
 * A Google Street View panorama in a container, driven by a view object.
 *
 *   const pano = useStreetViewPanorama({ containerRef, enabled, apiKey, view, containerKey });
 *   pano.status      'idle' | 'loading' | 'ready' | 'unavailable'
 *   pano.authFailed  Google rejected the key on this page (sticky)
 *   pano.readView()  what the operator is looking at now, as a view object, or null
 *
 * The hook owns the panorama's whole life: it loads the SDK through the shared loader,
 * builds the panorama when enabled and the container exists, tears it down when either
 * goes away, pushes a CHANGED view onto a live panorama without rebuilding it, and reads
 * the camera back for a save. The panel never touches `window.google`.
 *
 * Two rules that came from defects (#35a):
 *   * A view is applied only when the panorama is not already showing it, so a save --
 *     which comes back from the database as "the view changed" -- does not re-aim a camera
 *     that is exactly there.
 *   * The SDK's zoom is recorded as it settles and never argued with from a listener: the
 *     SDK enforces a container-dependent minimum and re-fires zoom_changed with it
 *     (docs/standards/dependency-behaviour.md).
 */
export function useStreetViewPanorama({ containerRef, enabled, apiKey, view, containerKey = 'default' }) {
  const [status, setStatus] = useState('idle');
  const [authFailed, setAuthFailed] = useState(() => isGoogleMapsAuthFailed());
  const panoRef = useRef(null);
  const liveRef = useRef(null);   // { heading, pitch, fov, lat, lng, panoId } as the SDK reports it
  const viewRef = useRef(view);   // the latest view, for the construction effect to read without re-running
  viewRef.current = view;

  useEffect(() => onGoogleMapsAuthFailure(() => setAuthFailed(true)), []);

  const wantPanorama = Boolean(enabled && apiKey && view && !authFailed);

  // Construction and teardown. Keyed on the container, not the view: a changed view is
  // pushed by the effect below, never by rebuilding.
  useEffect(() => {
    if (!wantPanorama) {
      setStatus(authFailed ? 'unavailable' : 'idle');
      return undefined;
    }
    const container = containerRef.current;
    if (!container) return undefined;

    let cancelled = false;
    let pano = null;
    let mapsApi = null;
    setStatus('loading');

    const record = (patch) => { liveRef.current = { ...(liveRef.current || {}), ...patch }; };
    const positionOf = (p) => {
      const pos = p.getPosition?.();
      if (!pos) return {};
      const lat = typeof pos.lat === 'function' ? pos.lat() : pos.lat;
      const lng = typeof pos.lng === 'function' ? pos.lng() : pos.lng;
      return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : {};
    };

    const aimAt = (target) => {
      // Find imagery for a view with no panorama id: nearest outdoor panorama to the point.
      const svc = new mapsApi.StreetViewService();
      const tryRadius = (i) => {
        if (cancelled || !pano) return;
        if (i >= SEARCH_RADII_M.length) {
          console.warn('No outdoor Street View imagery within', SEARCH_RADII_M.at(-1), 'm of', target.lat, target.lng);
          pano.setPosition({ lat: target.lat, lng: target.lng });
          setStatus('ready');
          return;
        }
        svc.getPanorama({
          location: { lat: target.lat, lng: target.lng },
          radius: SEARCH_RADII_M[i],
          source: mapsApi.StreetViewSource.OUTDOOR,
          preference: mapsApi.StreetViewPreference.NEAREST,
        }, (data, st) => {
          if (cancelled || !pano) return;
          if (st === mapsApi.StreetViewStatus.OK && data?.location?.pano) {
            pano.setPano(data.location.pano);
            pano.setPov({ heading: target.heading, pitch: target.pitch });
            pano.setZoom(fovToZoom(target.fov));
            pano.setVisible(true);
            setStatus('ready');
          } else {
            tryRadius(i + 1);
          }
        });
      };
      tryRadius(0);
    };

    loadGoogleMaps(apiKey).then((maps) => {
      if (cancelled) return;
      if (isGoogleMapsAuthFailed()) { setAuthFailed(true); setStatus('unavailable'); return; }
      mapsApi = maps;
      const v = viewRef.current;
      container.innerHTML = '';
      pano = new maps.StreetViewPanorama(container, {
        pov: { heading: v.heading, pitch: v.pitch },
        zoom: fovToZoom(v.fov),
        ...(v.panoId ? { pano: v.panoId } : {}),
        fullscreenControl: false,
        addressControl: false,
        panControl: false,
        linksControl: true,
        motionTracking: false,
        motionTrackingControl: false,
        showRoadLabels: true,
        visible: true,
      });
      panoRef.current = pano;
      liveRef.current = { heading: v.heading, pitch: v.pitch, fov: v.fov, lat: v.lat, lng: v.lng, panoId: v.panoId || '' };

      pano.addListener('pov_changed', () => {
        const pov = pano.getPov();
        if (pov && Number.isFinite(pov.heading)) record({ heading: pov.heading, pitch: pov.pitch });
      });
      pano.addListener('zoom_changed', () => {
        const z = pano.getZoom();
        if (Number.isFinite(z)) record({ fov: zoomToFov(z) });
      });
      pano.addListener('pano_changed', () => {
        const id = pano.getPano();
        if (id) record({ panoId: id, ...positionOf(pano) });
      });
      pano.addListener('position_changed', () => record(positionOf(pano)));
      pano.addListener('status_changed', () => { if (!cancelled) setStatus('ready'); });

      if (v.panoId) {
        pano.setVisible(true);
        setStatus('ready');
      } else {
        aimAt(v);
      }
    }).catch((err) => {
      if (cancelled) return;
      console.error('Street View SDK unavailable:', err);
      setStatus('unavailable');
    });

    return () => {
      cancelled = true;
      if (pano && mapsApi?.event) {
        try { mapsApi.event.clearInstanceListeners(pano); } catch { /* SDK gone */ }
      }
      panoRef.current = null;
      liveRef.current = null;
      if (container) container.innerHTML = '';
    };
    // The view is read through viewRef at construction; changes to it are applied by the
    // effect below on the live panorama. Rebuilding on every view change is the failure
    // that effect exists to prevent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wantPanorama, apiKey, containerKey, authFailed]);

  // Apply a changed view to the live panorama, unless it is already showing it.
  useEffect(() => {
    const pano = panoRef.current;
    if (!pano || !view || status !== 'ready') return;
    if (viewsMatch(liveRef.current, view)) return;
    try {
      if (view.panoId) {
        pano.setPano(view.panoId);
        pano.setPov({ heading: view.heading, pitch: view.pitch });
        pano.setZoom(fovToZoom(view.fov));
        pano.setVisible(true);
      } else {
        // No id: move the camera to the point and re-aim; the SDK snaps to the nearest
        // panorama itself, which is the same search the construction path runs.
        pano.setPosition({ lat: view.lat, lng: view.lng });
        pano.setPov({ heading: view.heading, pitch: view.pitch });
        pano.setZoom(fovToZoom(view.fov));
      }
    } catch (e) {
      console.warn('Could not apply the Street View view:', e);
    }
  }, [view, status]);

  /** The camera as it stands now, as a view object; null without a panorama. */
  const readView = useCallback(() => {
    const pano = panoRef.current;
    const live = liveRef.current;
    if (!pano || !live) return null;
    const pov = pano.getPov?.();
    const z = pano.getZoom?.();
    const pos = pano.getPosition?.();
    const lat = pos ? (typeof pos.lat === 'function' ? pos.lat() : pos.lat) : live.lat;
    const lng = pos ? (typeof pos.lng === 'function' ? pos.lng() : pos.lng) : live.lng;
    return {
      lat: Number.isFinite(lat) ? lat : live.lat,
      lng: Number.isFinite(lng) ? lng : live.lng,
      heading: Math.round(pov && Number.isFinite(pov.heading) ? pov.heading : live.heading),
      pitch: Math.round(pov && Number.isFinite(pov.pitch) ? pov.pitch : live.pitch),
      fov: Number.isFinite(z) ? zoomToFov(z) : live.fov,   // degrees, full precision, never clamped
      panoId: pano.getPano?.() || live.panoId || '',
    };
  }, []);

  return { status, authFailed, readView };
}
