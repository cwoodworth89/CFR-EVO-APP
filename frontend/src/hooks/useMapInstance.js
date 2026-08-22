import { useState, useEffect, useCallback } from 'react';
import { COQUITLAM_CENTER } from '../components/MapConstants';

/**
 * The Leaflet map handle and the view state that goes with it: current zoom, whether the
 * operator has moved the map, and whether the view has left its default.
 *
 * MapBoard and RouteOverviewPanel each grew their own copy of this — `map` versus
 * `mapInstance`, two `userPanned` flags, two sets of gesture listeners. This is the shared
 * one; see docs/architecture/unified_map_surface.md.
 *
 * Deliberately does NOT own fit-bounds *policy*. MapBoard pads for its two sidebars while
 * the dispatch map pads relative to container size and re-fits when the call changes —
 * those are layout decisions, so `fitTo` takes the options rather than inventing them.
 */
export function useMapInstance({
  defaultCenter = COQUITLAM_CENTER,
  defaultZoom = 12,
} = {}) {
  const [map, setMap] = useState(null);
  const [currentZoom, setCurrentZoom] = useState(defaultZoom);
  const [isOffDefault, setIsOffDefault] = useState(false);
  const [userPanned, setUserPanned] = useState(false);

  useEffect(() => {
    if (!map) return;

    const updateMapState = () => {
      const zoom = map.getZoom();
      setCurrentZoom(zoom);
      const center = map.getCenter();
      const latDiff = Math.abs(center.lat - defaultCenter[0]);
      const lngDiff = Math.abs(center.lng - defaultCenter[1]);
      const zoomDiff = Math.abs(zoom - defaultZoom);

      // Off default if panned roughly 300 m or more, or zoomed away from the default.
      setIsOffDefault(latDiff > 0.003 || lngDiff > 0.003 || zoomDiff > 0.15);
    };

    // Only a real gesture counts as the operator taking control. Programmatic flyTo and
    // fitBounds also fire these events, but without an originalEvent — treating those as
    // a manual pan would make the map refuse to follow the next dispatch.
    const onUserGesture = (e) => {
      if (e && e.originalEvent) setUserPanned(true);
    };

    map.on('zoomend moveend', updateMapState);
    map.on('dragstart zoomstart touchstart', onUserGesture);
    updateMapState();
    return () => {
      map.off('zoomend moveend', updateMapState);
      map.off('dragstart zoomstart touchstart', onUserGesture);
    };
  }, [map, defaultCenter, defaultZoom]);

  /** Return to the default view and hand control back to automatic following. */
  const resetView = useCallback(() => {
    setUserPanned(false);
    if (map) map.flyTo(defaultCenter, defaultZoom, { animate: true, duration: 0.8 });
  }, [map, defaultCenter, defaultZoom]);

  /** Fit the given [lat, lng] points. Padding is the caller's decision. */
  const fitTo = useCallback((points, options = {}) => {
    if (!map || !Array.isArray(points) || points.length === 0) return;
    map.fitBounds(points, { animate: true, ...options });
  }, [map]);

  /**
   * Recompute the map's size after a layout change.
   *
   * Leaflet caches container dimensions, so a sidebar opening leaves grey tiles until it
   * is told. The delay lets the CSS transition settle first.
   */
  const invalidateSoon = useCallback((delay = 350) => {
    if (!map) return undefined;
    const timer = setTimeout(() => map.invalidateSize(), delay);
    return () => clearTimeout(timer);
  }, [map]);

  return {
    map,
    setMap,
    currentZoom,
    isOffDefault,
    userPanned,
    setUserPanned,
    resetView,
    fitTo,
    invalidateSoon,
  };
}
