import React from 'react';
import RoadClosureMarker from './RoadClosureMarker';
import { closureKey, sameClosure } from '../../utils/closureAccess';

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
          // rowId, not the feed's id: id is null when the feed sent none (#91), and two
          // id-less closures would share a key and both highlight as selected.
          key={closureKey(closure) ?? `idx-${i}`}
          closure={closure}
          isSelected={sameClosure(selectedClosure, closure)}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}
