import React from 'react';
import { Marker, Polygon, Polyline, CircleMarker, Tooltip } from 'react-leaflet';
import { targetIcon } from './mapIcons';
import { RoutingOverlay } from '../RoutingOverlay';

/**
 * Everything the map draws for an active dispatch target: the parcel outline, the target
 * marker, the highlighted street section, the nearest-hydrant rings, and the route line.
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
  targetMarkerRef,
  nearestHydrants = [],
  originStation,
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
      {targetPolygon && (
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
      <Marker 
        ref={targetMarkerRef}
        position={[targetAddress.lat, targetAddress.lng]} 
        icon={targetIcon}
      />

      {/* Highlight Top 3 closest hydrants (No tracer line) */}
      {nearestHydrants.map((hyd, idx) => {
        const isPrimary = idx === 0;
        return (
          <CircleMarker 
            key={`${hyd.gisId}-${idx}`}
            center={[hyd.lat, hyd.lng]} 
            radius={isPrimary ? 16 : 12} 
            pathOptions={{ 
              color: isPrimary ? '#06b6d4' : '#c084fc', // Cyan for closest, Lavender for others
              fillColor: isPrimary ? '#22d3ee' : '#e9d5ff', 
              fillOpacity: isPrimary ? 0.15 : 0.1, 
              weight: isPrimary ? 2 : 1.5,
              className: isPrimary ? 'animate-pulse' : '' 
            }} 
          >
            <Tooltip direction="top" className="font-bold text-xs bg-slate-950 text-white border border-slate-800 p-2 shadow-xl">
              <div className="flex flex-col gap-0.5" style={{ minWidth: '120px' }}>
                <span className={`text-[9px] uppercase font-mono tracking-wider ${isPrimary ? 'text-cyan-400' : 'text-purple-400'}`}>
                  {isPrimary ? 'NEAREST HYDRANT' : `HYDRANT OPTION #${idx + 1}`}
                </span>
                <span className="text-white text-sm font-bold">{hyd.gisId}</span>
                <span className="text-slate-400 text-[10px] mt-1 font-mono">Distance: {hyd.distance}m</span>
                {hyd.flowClass && (
                  <span className="text-sky-400 text-xs font-semibold">Flow Class: {hyd.flowClass}</span>
                )}
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}

      {originStation && (
        <RoutingOverlay 
          from={originStation} 
          to={targetCoords} 
          onRouteCalculated={onRouteCalculated}
        />
      )}
    </>
  );
}
