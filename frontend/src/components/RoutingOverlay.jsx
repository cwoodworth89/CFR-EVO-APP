import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import { API_BASE_URL } from '../apiClient';

/**
 * One route line: `from` -> `to` through our own OSRM (`/api/route`), drawn as a Leaflet
 * polyline. Distance, duration and geometry are the router's (CLAUDE.md 6.2); nothing is
 * estimated here, and a failed fetch draws nothing.
 *
 * `pane` / `paneZIndex` put the line in its own map pane so stacking is deterministic when
 * several routes are drawn (map/HallRoutesOverlay.jsx): routes finish loading in any order,
 * and without panes whichever arrived last would sit on top. Leaflet's overlayPane is 400 and
 * markerPane 600, so 450..460 keeps every route above the parcel fill and under the markers.
 *
 * `leaflet-routing-machine` used to be imported here and never called; its default
 * router.project-osrm.org / api.mapbox.com URLs rode along in the bundle (post-freeze backlog,
 * 2026-08-31). Gone 2026-09-09.
 */
export function RoutingOverlay({
  from,
  to,
  onRouteCalculated,
  stationId = '1',
  color = '#00e676',
  weight = 6,
  opacity = 0.95,
  pane,
  paneZIndex = 450,
}) {
  const map = useMap();

  const fromLat = from ? from[0] : null;
  const fromLng = from ? from[1] : null;
  const toLat = to ? to[0] : null;
  const toLng = to ? to[1] : null;

  // Store the callback in a ref to avoid infinite re-renders or stale closures
  const onRouteCalculatedRef = useRef(onRouteCalculated);
  useEffect(() => {
    onRouteCalculatedRef.current = onRouteCalculated;
  });

  useEffect(() => {
    if (!map || fromLat === null || fromLng === null || toLat === null || toLng === null) return;

    let isMounted = true;
    let polylineLayer = null;

    if (pane && !map.getPane(pane)) {
      const p = map.createPane(pane);
      p.style.zIndex = String(paneZIndex);
    }

    const fetchLocalRoute = async () => {
      try {
        const resp = await fetch(`${API_BASE_URL}/api/route?start_lat=${fromLat}&start_lng=${fromLng}&dest_lat=${toLat}&dest_lng=${toLng}&station_id=${encodeURIComponent(stationId)}`);
        if (resp.ok) {
          const data = await resp.json();
          if (data && data.polyline && isMounted) {
            const latLngs = data.polyline.map(pt => L.latLng(pt[0], pt[1]));

            polylineLayer = L.polyline(latLngs, {
              color,
              weight,
              opacity,
              lineCap: 'round',
              lineJoin: 'round',
              ...(pane ? { pane } : {}),
            }).addTo(map);

            if (onRouteCalculatedRef.current) {
              onRouteCalculatedRef.current(latLngs.map(l => ({ lat: l.lat, lng: l.lng })));
            }
          }
        }
      } catch (err) {
        console.warn("Local route fetch error:", err);
      }
    };

    fetchLocalRoute();

    return () => {
      isMounted = false;
      if (polylineLayer && map) {
        try {
          map.removeLayer(polylineLayer);
        } catch (e) {
          console.warn("Clean up routing polyline error:", e);
        }
      }
    };
  }, [map, fromLat, fromLng, toLat, toLng, stationId, color, weight, opacity, pane, paneZIndex]);

  return null;
}
