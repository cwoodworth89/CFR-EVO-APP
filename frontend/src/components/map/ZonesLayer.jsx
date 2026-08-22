import React from 'react';
import { Polygon, Marker } from 'react-leaflet';
import { getZoneCentroid } from './mapGeometry';
import { createSoftZoneNumberIcon } from './mapIcons';

/**
 * Emergency response zone polygons, colour-coded by responding hall, with their map-grid
 * numbers as separate labels.
 *
 * Extracted from MapBoard.jsx so the zone rendering is a layer like BaseMap and
 * HydrantsLayer, rather than inline JSX in the container. That consistency is what lets a
 * mode-selected layer set be composed later.
 *
 * Both the polygons and the labels are deliberately zoom-gated: above zoom 16 the operator
 * is looking at individual properties and the zone fill obscures the parcel detail, so it
 * is dropped. Labels appear only from zoom 13, below which they collide with each other.
 */

const HALL_COLOURS = {
  1: '#f43f5e', // crimson
  2: '#3b82f6', // royal blue
  3: '#10b981', // emerald
  4: '#a855f7', // purple
};
const UNASSIGNED_COLOUR = '#475569'; // slate

/** Zone fill/stroke, keyed on responding hall. Falls back to slate when unassigned.
 *  Not exported: only this layer styles zones, and a non-component export here would trip
 *  react-refresh/only-export-components. */
function getZoneStyle(zone) {
  const stationName = zone.station || '';
  let color = UNASSIGNED_COLOUR;

  if (stationName.includes('Hall 1') || zone.unit_id === 'E1') color = HALL_COLOURS[1];
  else if (stationName.includes('Hall 2') || zone.unit_id === 'E2') color = HALL_COLOURS[2];
  else if (stationName.includes('Hall 3') || zone.unit_id === 'E3' || zone.unit_id === 'Q5') color = HALL_COLOURS[3];
  else if (stationName.includes('Hall 4') || zone.unit_id === 'E4') color = HALL_COLOURS[4];

  return {
    color,
    fillColor: color,
    fillOpacity: 0.10,
    weight: 1.8,
    dashArray: '4 4',
  };
}

export default function ZonesLayer({ zones, visible, currentZoom }) {
  if (!visible || !Array.isArray(zones) || currentZoom >= 16) return null;

  const showLabels = currentZoom >= 13;

  return (
    <>
      {zones.map((zone) => (
        <Polygon
          key={zone.zone_id}
          positions={zone.geometry.coordinates[0].map(c => [c[1], c[0]])}
          pathOptions={getZoneStyle(zone)}
          pane="underlayPane"
        />
      ))}

      {showLabels && zones.map((zone) => {
        const center = getZoneCentroid(zone);
        if (!center) return null;
        return (
          <Marker
            key={`zone-num-${zone.zone_id}`}
            position={center}
            icon={createSoftZoneNumberIcon(zone.zone_id)}
            interactive={false}
            pane="labelsPane"
          />
        );
      })}
    </>
  );
}
