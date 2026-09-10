import { useMemo } from 'react';
import { RoutingOverlay } from '../RoutingOverlay';
import { STATIONS, hallColour } from '../MapConstants';
import { hallRoutesToDraw, HOME_ROUTE_STYLE, OTHER_ROUTE_STYLE } from '../../utils/hallRoutes';

/**
 * Every responding hall's route to the call on one map (operator design, docs/ux_notes.md
 * section 3 item 7): the home hall's solid in its colour and on top; the other halls'
 * translucent in theirs, the next to arrive above the later ones (utils/hallRoutes.js).
 *
 * The halls come from the dispatch's stored routing_metrics; with none, only the home route is
 * drawn. One `/api/route` call per hall, one to four per call. Only the home route reports its
 * coordinates upward: the hydrant picker measures along the approach of the crew reading the
 * screen, and the map fit follows the home route (operator, 2026-09-09: the others may
 * "approach from off screen", it "only matters in the final approach").
 */
export default function HallRoutesOverlay({ dest, homeHall, routingMetrics = [], onHomeRouteCalculated }) {
  const toDraw = useMemo(
    () => hallRoutesToDraw({ routingMetrics, homeHall, knownHalls: STATIONS.map(s => s.id) }),
    [routingMetrics, homeHall]
  );

  if (!dest || dest[0] == null || dest[1] == null) return null;

  return (
    <>
      {toDraw.map((entry, i) => {
        const station = STATIONS.find(s => s.id === entry.hall);
        if (!station) return null;
        const style = entry.isHome ? HOME_ROUTE_STYLE : OTHER_ROUTE_STYLE;
        return (
          <RoutingOverlay
            key={entry.hall}
            from={station.coords}
            to={dest}
            stationId={entry.hall}
            color={hallColour(entry.hall)}
            weight={style.weight}
            opacity={style.opacity}
            pane={`route-hall-${entry.hall}`}
            paneZIndex={450 + i}
            onRouteCalculated={entry.isHome ? onHomeRouteCalculated : undefined}
          />
        );
      })}
    </>
  );
}
