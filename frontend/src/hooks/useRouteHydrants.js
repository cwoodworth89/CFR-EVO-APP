import { useEffect, useMemo, useState } from 'react';
import { API_BASE_URL } from '../apiClient';
import { pickRouteHydrants, SUPPLY_M, TIER } from '../utils/routeHydrants';

// Degrees of a bounding box that holds SUPPLY_M plus margin around the destination, so the
// query returns every hydrant the picker could name and nothing it could not.
const BBOX_LAT = (SUPPLY_M * 1.5) / 110540;
const BBOX_LNG = (SUPPLY_M * 1.5) / (111320 * Math.cos((49.28 * Math.PI) / 180));

/**
 * The hydrants to show for a destination, by the operator's rule (utils/routeHydrants.js).
 * Fetches the inventory around the destination from public.hydrants once per destination
 * and re-picks when the route arrives. A failed fetch is reported, never an empty answer
 * dressed as "no hydrant" (CLAUDE.md 6.1).
 */
export function useRouteHydrants(destLat, destLng, routeCoords) {
  const [inventory, setInventory] = useState({ key: null, hydrants: [], failed: false });

  const key = destLat != null && destLng != null ? `${Number(destLat).toFixed(5)},${Number(destLng).toFixed(5)}` : null;

  useEffect(() => {
    if (!key) return undefined;
    let cancelled = false;
    const lat = Number(destLat);
    const lng = Number(destLng);
    const bbox = [lng - BBOX_LNG, lat - BBOX_LAT, lng + BBOX_LNG, lat + BBOX_LAT].map(v => v.toFixed(6)).join(',');
    fetch(`${API_BASE_URL}/api/hydrants?bbox=${bbox}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        if (cancelled) return;
        setInventory({ key, hydrants: Array.isArray(data) ? data : [], failed: false });
      })
      .catch(err => {
        if (cancelled) return;
        console.error('Hydrant inventory fetch failed:', err);
        setInventory({ key, hydrants: [], failed: true });
      });
    return () => { cancelled = true; };
  }, [key, destLat, destLng]);

  return useMemo(() => {
    if (!key) return { tier: TIER.NO_TARGET, picks: [], routeKnown: false, loading: false, failed: false };
    if (inventory.key !== key) return { tier: TIER.NO_TARGET, picks: [], routeKnown: false, loading: true, failed: false };
    if (inventory.failed) return { tier: TIER.NO_TARGET, picks: [], routeKnown: false, loading: false, failed: true };
    const result = pickRouteHydrants({
      hydrants: inventory.hydrants,
      routeCoords: routeCoords || [],
      destination: { lat: Number(destLat), lng: Number(destLng) },
    });
    return { ...result, loading: false, failed: false };
  }, [key, inventory, routeCoords, destLat, destLng]);
}
