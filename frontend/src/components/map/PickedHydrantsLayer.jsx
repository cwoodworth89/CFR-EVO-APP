import React, { useMemo } from 'react';
import { Marker, Tooltip } from 'react-leaflet';
import L from 'leaflet';

/**
 * The recommended hydrants, as small numbered badges on the dispatch map.
 *
 * The full hydrant layer drew every hydrant in the city from zoom 12 and the operator's
 * reaction was "I don't need to see all of those hydrants. Just the recommended ones"
 * (2026-09-06, #74). The first version of this layer then labelled each pick with a
 * permanent tooltip box, and the operator's reaction to that was "I don't like the pop up
 * boxes there. It makes it hard to understand the route" (2026-09-07). So: a 22 px circle
 * in the NFPA 291 class colour with the pick's number in it, nothing else on the map; the
 * id, class and how it was chosen are in the details box and on hover.
 */
const CLASS_COLOUR = { AA: '#38bdf8', A: '#4ade80', B: '#fb923c', C: '#f87171' };

function badgeIcon(n, fill, isPrivate) {
  const ring = isPrivate ? '#f59e0b' : '#ffffff';
  return L.divIcon({
    className: 'cfr-hydrant-pick',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    html: `<div style="width:22px;height:22px;border-radius:50%;background:${fill};border:2px solid ${ring};`
      + `box-shadow:0 0 0 3px rgba(15,23,42,.55);display:flex;align-items:center;justify-content:center;`
      + `font:900 12px ui-monospace,monospace;color:#0f172a;line-height:1">${n}</div>`,
  });
}

export default function PickedHydrantsLayer({ picks = [] }) {
  const icons = useMemo(() => picks.map((h, i) => {
    const fc = String(h.flowClass || '').toUpperCase();
    const isPrivate = String(h.status || '').toUpperCase() === 'PRIVATE';
    return badgeIcon(i + 1, CLASS_COLOUR[fc] || '#94a3b8', isPrivate);
  }), [picks]);

  return (
    <>
      {picks.map((h, i) => {
        if (h.lat == null || h.lng == null) return null;
        const fc = String(h.flowClass || '').toUpperCase();
        const isPrivate = String(h.status || '').toUpperCase() === 'PRIVATE';
        return (
          <Marker key={h.gisId || i} position={[Number(h.lat), Number(h.lng)]} icon={icons[i]} zIndexOffset={1000}>
            <Tooltip direction="top" offset={[0, -12]}>
              <span style={{ fontFamily: 'ui-monospace, monospace', fontWeight: 800, fontSize: 11 }}>
                #{i + 1} {h.gisId} {fc || 'UNRATED'}{isPrivate ? ' PRIVATE' : ''} · {h.distance} m
              </span>
            </Tooltip>
          </Marker>
        );
      })}
    </>
  );
}
