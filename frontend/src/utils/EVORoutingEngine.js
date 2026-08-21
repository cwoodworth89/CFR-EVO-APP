/* Coquitlam Fire Rescue EVO Routing (CFR-EVORoutingEngine)
 *
 * Stock OSRM. Distance and ETA are the router's own figures, resolved by the
 * backend (`/api/route`, `routing_metrics`) and passed through here.
 *
 * This module deliberately does NOT model apparatus physics, rush hour,
 * elevation, or turn penalties. Those were previously estimated client-side from
 * invented constants and disagreed with the router's own answer. Apparatus-aware
 * adjustment is planned as the CFR customized route configuration feature and
 * will layer on top of the OSRM baseline, not replace it.
 */
import * as turf from '@turf/turf';

// Apparatus tier metadata.
//
// Presentation fields (name, subtitle, color, weightTons) are live and used for
// unit badges. The `staged` physics fields are seed data for the planned CFR route
// configuration feature and are NOT applied to any ETA today.
//
// PROVENANCE REQUIRED (CLAUDE.md 6.3): the staged figures carry no cited source.
// They must be sourced (NFPA 1710, department policy, or measurement on this system)
// or replaced before being applied to operational output.
export const APPARATUS_TIERS = {
  LIGHT: {
    key: 'LIGHT',
    name: '⚡ LIGHT APPARATUS',
    subtitle: 'Medic, Squad (SQ1-4), Command Car, LAV, Specialty',
    weightTons: 5,
    color: '#38bdf8',
    staged: { speedCode3KmH: 52.0, speedCode1KmH: 38.0, turnPenaltySec: 3 }
  },
  GENERAL: {
    key: 'GENERAL',
    name: '🚒 GENERAL APPARATUS',
    subtitle: 'Engine (E1-4), Rescue (R1-4), Quint (Q5), Pumper',
    weightTons: 22,
    color: '#10b981',
    staged: { speedCode3KmH: 45.0, speedCode1KmH: 32.0, turnPenaltySec: 5 }
  },
  HEAVY: {
    key: 'HEAVY',
    name: '🚚 HEAVY APPARATUS',
    subtitle: 'Ladder (L1-4), Tower Platform, Water Tender (T1-4, WT4)',
    weightTons: 35,
    color: '#f59e0b',
    staged: { speedCode3KmH: 38.0, speedCode1KmH: 28.0, turnPenaltySec: 8 }
  }
};

// Placeholder for the upcoming CFR customized route configuration feature.
export const DEFAULT_ROUTING_CONFIG = {};

// Classify a unit identifier string into its apparatus tier (presentation only).
export function classifyApparatusUnit(unitStr) {
  if (!unitStr) return APPARATUS_TIERS.GENERAL;
  const clean = unitStr.trim().toUpperCase();

  if (/\b(SQ|SQUAD|M|MEDIC|CAR|LAV|CHIEF|COMMAND|S|SPECIALTY)\d*\b/i.test(clean)) {
    return APPARATUS_TIERS.LIGHT;
  }
  if (/\b(L|LADDER|T|TENDER|WT|TANKER|TOWER|PLATFORM)\d*\b/i.test(clean)) {
    return APPARATUS_TIERS.HEAVY;
  }
  return APPARATUS_TIERS.GENERAL;
}

/**
 * Builds per-unit route display metrics.
 *
 * Distance is measured from the actual OSRM polyline when available. ETA is only
 * ever the router's own duration, supplied via `unitMetrics` (the backend's
 * persisted `routing_metrics`). When no router figure exists, etaMinutes is null
 * and the UI shows it as unknown — it is never estimated.
 */
export function calculateEVORouteMetrics({
  originCoords,        // [lat, lng]
  targetCoords,        // [lat, lng]
  dispatchedUnits = [],
  routeCoordinates = [], // OSRM polyline
  unitMetrics = []       // backend routing_metrics: [{ unit, eta_minutes, road_distance_km }]
}) {
  if (!originCoords || !targetCoords) return null;

  // Route length from real geometry when we have it; otherwise unknown.
  let distanceKm = null;
  if (routeCoordinates && routeCoordinates.length > 1) {
    const line = turf.lineString(routeCoordinates.map(c => [c.lng ?? c[1], c.lat ?? c[0]]));
    distanceKm = turf.length(line, { units: 'kilometers' });
  }

  const byUnit = new Map(
    (unitMetrics || []).map(m => [String(m.unit || '').trim().toUpperCase(), m])
  );

  const units = dispatchedUnits.map((unitStr) => {
    const tier = classifyApparatusUnit(unitStr);
    const m = byUnit.get(String(unitStr).trim().toUpperCase());
    const eta = m?.eta_minutes;
    const dist = m?.road_distance_km ?? distanceKm;

    return {
      unit: unitStr,
      tierKey: tier.key,
      tierName: tier.name,
      tierSubtitle: tier.subtitle,
      color: tier.color,
      distanceKm: dist != null ? Number(dist).toFixed(1) : null,
      etaMinutes: eta != null ? Number(eta).toFixed(0) : null
    };
  });

  return {
    distanceKm: distanceKm != null ? distanceKm.toFixed(1) : null,
    units
  };
}
