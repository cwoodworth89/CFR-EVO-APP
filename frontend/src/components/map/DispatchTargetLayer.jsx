import React from 'react';
import { Polygon, Polyline, CircleMarker } from 'react-leaflet';
import HallRoutesOverlay from './HallRoutesOverlay';
import PickedHydrantsLayer from './PickedHydrantsLayer';
import { CADASTRAL_MIN_ZOOM } from '../MapConstants';

/**
 * Everything the map draws for an active dispatch target: the parcel outline, the
 * highlighted street section, the nearest-hydrant rings, and the route line.
 *
 * Extracted from MapBoard.jsx. Unlike ZonesLayer and RoadClosuresLayer this is not a pure
 * lift — it is the layer coupled to routing, because `RoutingOverlay` both renders the
 * route and reports the computed coordinates back up through `onRouteCalculated`. That
 * callback is why the container still owns `routeCoordinates`.
 *
 * Renders nothing without a target, so a dispatch with unresolved coordinates draws no
 * marker at all rather than a marker at a guessed position (CLAUDE.md §5 Tier 1).
 */
export default function DispatchTargetLayer({
  targetAddress,
  targetPolygon,
  targetCoords,
  nearestHydrants = [],
  currentZoom = 0,
  originStation,
  homeHall = '1',
  routingMetrics = [],
  onRouteCalculated,
}) {
  if (!targetAddress) return null;

  return (
    <>
      {/* Street section: a "<street> and <street>" dispatch has no point
          location, so the stretch of road inside the announced map grid is
          highlighted instead. Amber, thick and dashed so it reads as an area
          of search rather than as a route line or a parcel outline. */}
      {targetAddress.location_type === 'street_section'
        && Array.isArray(targetAddress.segment)
        && targetAddress.segment.map((line, i) => (
          <Polyline
            key={`street-section-${i}`}
            positions={line.map(([lng, lat]) => [lat, lng])}
            pathOptions={{
              color: '#f59e0b',
              weight: 10,
              opacity: 0.75,
              dashArray: '14,10',
              lineCap: 'round'
            }}
          />
        ))}
      {targetPolygon && currentZoom >= CADASTRAL_MIN_ZOOM && (
        <Polygon 
          positions={targetPolygon} 
          pathOptions={{ 
            color: targetAddress.buildingName ? '#f59e0b' : '#0284c7', 
            fillColor: targetAddress.buildingName ? '#f59e0b' : '#38bdf8', 
            fillOpacity: targetAddress.buildingName ? 0.08 : 0.15, 
            weight: 2,
            dashArray: '4,4'
          }}
        />
      )}
      {targetAddress.buildingName && (
        <CircleMarker
          center={[targetAddress.lat, targetAddress.lng]}
          radius={20}
          pathOptions={{
            color: '#f59e0b',
            fillColor: '#38bdf8',
            fillOpacity: 0.25,
            weight: 2.5,
            className: 'animate-pulse'
          }}
        />
      )}
      {/* No marker at the centroid: the parcel outline is the target, and the route's end
          marks the arrival point on the street (operator, 2026-09-08: "we can get rid of that
          target emoji"). */}

      {/* The picked hydrants as solid numbered dots, the same badges the kiosk draws. The
          translucent rings that were here read as clutter at city zoom (operator,
          2026-09-08: "keep them the solid dots"). */}
      <PickedHydrantsLayer picks={nearestHydrants} />

      {/* Every responding hall's route when the target is a dispatch with routing_metrics;
          on an address search there are no metrics and only the home hall's route draws. */}
      {originStation && targetCoords && (
        <HallRoutesOverlay
          dest={targetCoords}
          homeHall={homeHall}
          routingMetrics={routingMetrics}
          onHomeRouteCalculated={onRouteCalculated}
        />
      )}
    </>
  );
}
