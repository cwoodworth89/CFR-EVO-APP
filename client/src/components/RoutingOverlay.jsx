import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet-routing-machine';
import 'leaflet-routing-machine/dist/leaflet-routing-machine.css';

export function RoutingOverlay({ from, to, onRouteCalculated }) {
  const map = useMap();

  useEffect(() => {
    if (!map || !from || !to) return;

    // Check if L.Routing is available (loaded via CDN)
    if (!L.Routing || !L.Routing.control) {
      console.warn("Leaflet Routing Machine is not loaded.");
      return;
    }

    const routingControl = L.Routing.control({
      waypoints: [
        L.latLng(from[0], from[1]),
        L.latLng(to[0], to[1])
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
        if (onRouteCalculated) {
          onRouteCalculated(coordinates);
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
  }, [map, from, to]);

  return null;
}
