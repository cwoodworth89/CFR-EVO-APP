import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet-routing-machine';
import 'leaflet-routing-machine/dist/leaflet-routing-machine.css';
import { API_BASE_URL } from '../apiClient';

export function RoutingOverlay({ from, to, onRouteCalculated }) {
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

    const fetchLocalRoute = async () => {
      try {
        const resp = await fetch(`${API_BASE_URL}/api/route?start_lat=${fromLat}&start_lng=${fromLng}&dest_lat=${toLat}&dest_lng=${toLng}&station_id=1`);
        if (resp.ok) {
          const data = await resp.json();
          if (data && data.polyline && isMounted) {
            const latLngs = data.polyline.map(pt => L.latLng(pt[0], pt[1]));
            
            // Render high-visibility glowing emerald emergency route polyline
            polylineLayer = L.polyline(latLngs, {
              color: '#00e676',
              weight: 6,
              opacity: 0.95,
              lineCap: 'round',
              lineJoin: 'round'
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
  }, [map, fromLat, fromLng, toLat, toLng]);

  return null;
}
