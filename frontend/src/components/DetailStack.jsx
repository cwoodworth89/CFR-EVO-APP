import React from 'react';
import PropertySatellitePanel from './kiosk/PropertySatellitePanel';
import StreetViewPanel from './kiosk/StreetViewPanel';

/**
 * The right-hand spatial inspection stack: three equal cells, the top one selected by
 * mode, the lower two shared.
 *
 * Both surfaces already rendered this. The console showed the target address card above
 * the satellite and street views; the dispatch display showed the cadastral block above
 * the same two. Only the top cell and the container styling ever differed.
 *
 * Step 5 of docs/architecture/unified_map_surface.md — chrome that differs by *kind*
 * stays as separate components (`topCard`), while the shared structure lives here.
 *
 * `call` is the single dispatch shape from utils/dispatchModel, so both surfaces feed
 * their panels identically.
 */
export default function DetailStack({ call, topCard, className = '' }) {
  return (
    <div className={`h-full min-h-0 flex flex-col gap-3 overflow-hidden ${className}`}>
      {topCard}

      <div className="flex-1 min-h-0 relative">
        <PropertySatellitePanel activeCall={call} />
      </div>

      <div className="flex-1 min-h-0 relative">
        <StreetViewPanel activeCall={call} />
      </div>
    </div>
  );
}
