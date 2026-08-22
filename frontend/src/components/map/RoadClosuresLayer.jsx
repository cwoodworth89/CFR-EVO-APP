import React from 'react';
import RoadClosureMarker from './RoadClosureMarker';

/**
 * Road closure markers for the filtered closure set.
 *
 * A thin wrapper over RoadClosureMarker, so the container composes one layer rather than
 * an inline `.map()` — matching BaseMap, HydrantsLayer and ZonesLayer.
 *
 * `closures` is expected to be the already-filtered list from useRoadClosures, not the raw
 * feed: severity and timeframe filtering belongs with the data, not the rendering.
 */
export default function RoadClosuresLayer({ closures, visible, selectedClosure, onSelect }) {
  if (!visible || !Array.isArray(closures)) return null;

  return (
    <>
      {closures.map((closure, i) => (
        <RoadClosureMarker
          key={closure.id || i}
          closure={closure}
          isSelected={selectedClosure !== null && selectedClosure?.id === closure.id}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}
