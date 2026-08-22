import { useState, useEffect, useMemo } from 'react';
import { apiClient } from '../apiClient';

/** Poll interval for the local road closure feed. The backend syncs from the municipal
 *  source once a day, so this only needs to be frequent enough to pick up a manual
 *  re-sync within a shift. */
const REFRESH_MS = 300000; // 5 minutes

/**
 * Road closures from the local FastAPI `/api/road-closures`, plus the filtered subset the
 * map and alert count render.
 *
 * Extracted from MapBoard.jsx. Nothing here touches the map instance or the dispatch
 * target, so it lifts out cleanly; the caller passes the current filter state (owned by
 * useMapLayerPreferences) and gets back both the raw list and the filtered one.
 */
export function useRoadClosures({
  filterNoAccess, filterAccessOnly, filterCaution,
  showActiveNow, showNext24h, showNext7d,
}) {
  const [roadClosures, setRoadClosures] = useState([]);

  useEffect(() => {
    const loadClosures = () => {
      apiClient.roadClosures.fetchAll()
        .then(rawEvents => {
          if (!Array.isArray(rawEvents)) return;
          const now = new Date();
          const processed = rawEvents.map(evt => {
            const start = evt.startDate ? new Date(evt.startDate) : null;
            const end = evt.endDate ? new Date(evt.endDate) : null;

            let isActive = false, isFuture = false, isExpired = false;
            if (start && now < start) {
              isFuture = true;
            } else if (end && now > end) {
              isExpired = true;
            } else {
              isActive = true;
            }
            // `start` and `end` are carried onto the object deliberately. Previously they
            // were computed here as locals and discarded, while the timeframe filter below
            // tested `closure.start` -- a field the API never returns (it sends `startDate`
            // and `endDate`). That made `is24hFuture` and `is7dFuture` permanently falsy,
            // so the "Next 24h" and "Next 7d" toggles matched nothing at all.
            return { ...evt, start, end, isActive, isFuture, isExpired };
          });
          setRoadClosures(processed);
        })
        .catch(err => {
          console.warn('Failed to load local road closures:', err);
        });
    };

    loadClosures();
    const interval = setInterval(loadClosures, REFRESH_MS);
    return () => clearInterval(interval);
  }, []);

  // Closures the map and the alert count actually render, by access severity and by
  // timeframe window.
  const activeClosures = useMemo(() => roadClosures.filter(closure => {
    if (closure.emergencyAccess === 'NO_ACCESS' && !filterNoAccess) return false;
    if (closure.emergencyAccess === 'ACCESS_ONLY' && !filterAccessOnly) return false;
    if (closure.emergencyAccess === 'CAUTION' && !filterCaution) return false;

    const now = new Date();
    const isCurrentlyActive = closure.isActive;
    const untilStart = closure.start ? closure.start.getTime() - now.getTime() : null;
    const is24hFuture = closure.isFuture && untilStart !== null && untilStart <= 24 * 3600 * 1000;
    const is7dFuture = closure.isFuture && untilStart !== null && untilStart <= 7 * 86400 * 1000;

    return (showActiveNow && isCurrentlyActive)
      || (showNext24h && is24hFuture)
      || (showNext7d && is7dFuture);
  }), [
    roadClosures, filterNoAccess, filterAccessOnly, filterCaution,
    showActiveNow, showNext24h, showNext7d,
  ]);

  return { roadClosures, activeClosures };
}
