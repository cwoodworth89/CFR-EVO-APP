import React from 'react';
import { CircleMarker, Tooltip } from 'react-leaflet';

/**
 * The recommended hydrants only, numbered, for the dispatch map. The full hydrant layer
 * drew every hydrant in the city from zoom 12 and the operator's reaction was "I don't
 * need to see all of those hydrants. Just the recommended ones" (2026-09-06, #74).
 * Colour is the NFPA 291 class as the City rated it; grey means unrated.
 */
const CLASS_COLOUR = { AA: '#38bdf8', A: '#4ade80', B: '#fb923c', C: '#f87171' };

export default function PickedHydrantsLayer({ picks = [] }) {
  return (
    <>
      {picks.map((h, i) => {
        if (h.lat == null || h.lng == null) return null;
        const fc = String(h.flowClass || '').toUpperCase();
        const isPrivate = String(h.status || '').toUpperCase() === 'PRIVATE';
        const fill = CLASS_COLOUR[fc] || '#94a3b8';
        return (
          <CircleMarker
            key={h.gisId || i}
            center={[Number(h.lat), Number(h.lng)]}
            radius={9}
            pathOptions={{ color: isPrivate ? '#f59e0b' : '#ffffff', fillColor: fill, fillOpacity: 1, weight: 3, className: 'animate-pulse' }}
          >
            <Tooltip permanent direction="top" offset={[0, -8]} className="cfr-hydrant-pick-label">
              <span style={{ fontFamily: 'ui-monospace, monospace', fontWeight: 800, fontSize: 11 }}>
                #{i + 1} {h.gisId} {fc || 'UNRATED'}{isPrivate ? ' PRIVATE' : ''}
              </span>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </>
  );
}
