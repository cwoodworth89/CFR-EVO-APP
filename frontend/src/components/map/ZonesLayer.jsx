import React from 'react';
import { Polygon, Marker } from 'react-leaflet';
import { getZoneLabelPoint } from './mapGeometry';
import { createSoftZoneNumberIcon } from './mapIcons';
import { HALL_COLOURS, UNASSIGNED_HALL_COLOUR } from '../MapConstants';

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

// Hall colours come from MapConstants.HALL_COLOURS, the one table the route lines and the
// ETA list use too, so a zone and the route crossing it cannot disagree (2026-09-09).
const UNASSIGNED_COLOUR = UNASSIGNED_HALL_COLOUR;

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

export default function ZonesLayer({ zones, visible, currentZoom, onImagery = false }) {
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
        const center = getZoneLabelPoint(zone);
        if (!center) return null;
        return (
          <Marker
            key={`zone-num-${zone.zone_id}`}
            position={center}
            icon={createSoftZoneNumberIcon(zone.zone_id, onImagery)}
            interactive={false}
            pane="labelsPane"
          />
        );
      })}
    </>
  );
}
