import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet-routing-machine';
import 'leaflet-routing-machine/dist/leaflet-routing-machine.css';

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

    // Check if L.Routing is available (loaded via CDN)
    if (!L.Routing || !L.Routing.control) {
      console.warn("Leaflet Routing Machine is not loaded.");
      return;
    }

    const routingControl = L.Routing.control({
      waypoints: [
        L.latLng(fromLat, fromLng),
        L.latLng(toLat, toLng)
      ],
      routeWhileDragging: false,
      addWaypoints: false,
      draggableWaypoints: false,
      fitSelectedRoutes: true,
      show: false, // Hides the textual routing directions panel
      createMarker: () => null, // Disables default start/end waypoint markers (we render our own Hall/Target icons)
      lineOptions: {
        styles: [
          { color: '#4f46e5', weight: 6, opacity: 0.8 } // High-contrast Indigo route line overlay
        ],
        extendToWaypoints: true,
        missingRouteTolerance: 10
      }
    }).addTo(map);

    routingControl.on('routesfound', (e) => {
      const routes = e.routes;
      if (routes && routes.length > 0) {
        const coordinates = routes[0].coordinates; // array of L.LatLng
        if (onRouteCalculatedRef.current) {
          onRouteCalculatedRef.current(coordinates);
        }
      }
    });

    // Force-hide the LRM instruction container container if it ignores the 'show' parameter
    const container = routingControl.getContainer();
    if (container) {
      container.style.display = 'none';
    }

    return () => {
      try {
        map.removeControl(routingControl);
      } catch (e) {
        console.warn("Clean up Leaflet routing control error:", e);
      }
    };
  }, [map, fromLat, fromLng, toLat, toLng]);

  return null;
}
