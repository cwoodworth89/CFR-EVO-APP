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

    // Build tactical waypoints array (Injecting Hall 1 tactical corridors)
    const waypoints = [L.latLng(fromLat, fromLng)];

    // Check if departing from Hall 1 (Town Centre: ~49.291, -122.790)
    const isHall1 = Math.abs(fromLat - 49.29109) < 0.008 && Math.abs(fromLng - (-122.7907)) < 0.008;

    if (isHall1) {
      // Sector A: Mariner Way / Southwest Sector (Take Guildford -> Johnson St -> Mariner to avoid Lougheed traffic medians)
      if (toLat < 49.280 && toLng < -122.800) {
        waypoints.push(L.latLng(49.2847, -122.7915)); // Pinetree & Guildford
        waypoints.push(L.latLng(49.2845, -122.8055)); // Guildford & Johnson St
        waypoints.push(L.latLng(49.2785, -122.8125)); // Johnson St & Mariner Way
      }
      // Sector B: Gordon Ave / Town Centre Sector (Pinetree South -> Lougheed -> Christmas Way -> Gordon)
      else if (toLat >= 49.275 && toLat <= 49.286 && toLng >= -122.795 && toLng <= -122.780) {
        waypoints.push(L.latLng(49.2785, -122.7915)); // Pinetree & Lougheed
        waypoints.push(L.latLng(49.2785, -122.7850)); // Lougheed & Christmas Way
      }
    }

    waypoints.push(L.latLng(toLat, toLng));

    const routingControl = L.Routing.control({
      waypoints,
      router: L.Routing.osrmv1({
        serviceUrl: 'https://router.project-osrm.org/route/v1',
        profile: 'car',
        useHints: false
      }),
      // Emergency response routing: allow arriving at destination from any direction without forcing curb U-turns
      approaches: ['unrestricted', 'unrestricted'],
      routeWhileDragging: false,
      addWaypoints: false,
      draggableWaypoints: false,
      fitSelectedRoutes: false,
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
