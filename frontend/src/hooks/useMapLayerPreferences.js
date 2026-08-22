import { useState, useCallback, useMemo } from 'react';
import { MODE_DEFAULTS } from '../components/MapConstants';

/**
 * Which map layers are visible, and how road closures are filtered.
 *
 * Extracted from MapBoard.jsx, which held fourteen independent `useState` calls for this
 * and then threaded each one through to LeftSidebar and RightSidebar as its own prop pair.
 * The values are pure view preferences — no fetching, no geometry, no coupling to the
 * dispatch target — so they are the cleanest cluster to lift out of that component.
 *
 * Returns a single object so the sidebars can be given `{...layers}` instead of forty
 * lines of pass-through.
 */
export function useMapLayerPreferences() {
  const [mapStyle, setMapStyle] = useState('GREY');
  const [showLabels, setShowLabels] = useState(true);
  const [showHydrants, setShowHydrants] = useState(true);
  const [showZones, setShowZones] = useState(true);
  const [showRoadClosures, setShowRoadClosures] = useState(true);
  const [showRailroadCrossings, setShowRailroadCrossings] = useState(false);
  const [showFireHalls, setShowFireHalls] = useState(true);

  // Road closure time windows
  const [showActiveNow, setShowActiveNow] = useState(true);
  const [showNext24h, setShowNext24h] = useState(false);
  const [showNext7d, setShowNext7d] = useState(false);

  // Road closure emergency-access filters
  const [filterNoAccess, setFilterNoAccess] = useState(true);
  const [filterAccessOnly, setFilterAccessOnly] = useState(true);
  const [filterCaution, setFilterCaution] = useState(true);

  /**
   * Reset the layer preferences that a mode change owns.
   *
   * Deliberately does NOT touch the sidebars: they are chrome, not layers, and MapBoard
   * still decides those. Behaviour is unchanged from the inline version — EXPLORE turns
   * zones, hydrants and closures back on, every other mode leaves them as the operator
   * left them.
   */
  const applyModeDefaults = useCallback((mode) => {
    setMapStyle(MODE_DEFAULTS[mode] || 'GREY');
    setShowLabels(mode === 'EXPLORE');
    if (mode === 'EXPLORE') {
      setShowZones(true);
      setShowHydrants(true);
      setShowRoadClosures(true);
    }
  }, []);

  return useMemo(() => ({
    mapStyle, setMapStyle,
    showLabels, setShowLabels,
    showHydrants, setShowHydrants,
    showZones, setShowZones,
    showRoadClosures, setShowRoadClosures,
    showRailroadCrossings, setShowRailroadCrossings,
    showFireHalls, setShowFireHalls,
    showActiveNow, setShowActiveNow,
    showNext24h, setShowNext24h,
    showNext7d, setShowNext7d,
    filterNoAccess, setFilterNoAccess,
    filterAccessOnly, setFilterAccessOnly,
    filterCaution, setFilterCaution,
    applyModeDefaults,
  }), [
    mapStyle, showLabels, showHydrants, showZones, showRoadClosures,
    showRailroadCrossings, showFireHalls, showActiveNow, showNext24h, showNext7d,
    filterNoAccess, filterAccessOnly, filterCaution, applyModeDefaults,
  ]);
}
