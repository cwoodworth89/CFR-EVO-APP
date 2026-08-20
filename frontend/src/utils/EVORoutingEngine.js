/* Coquitlam Fire Rescue EVO Routing Physics Engine (CFR-EVORoutingEngine) */
import * as turf from '@turf/turf';

// 3-Tier Apparatus Physics Profiles
export const APPARATUS_TIERS = {
  LIGHT: {
    key: 'LIGHT',
    name: '⚡ LIGHT APPARATUS',
    subtitle: 'Medic, Squad (SQ1-4), Command Car, LAV, Specialty',
    weightTons: 5,
    speedCode3KmH: 52.0,
    speedCode1KmH: 38.0,
    roadFactorCode3: 1.25,
    roadFactorCode1: 1.35,
    speedFactor: 1.155,       // Agile, fast acceleration/braking
    turnPenaltySec: 3,        // 3 seconds per 90-degree turn
    uphillDragFactor: 1.05,   // Minimal speed loss on steep climbs
    downhillSpeedCapKm: null, // Uncapped standard response
    color: '#38bdf8'          // Sky Blue
  },
  GENERAL: {
    key: 'GENERAL',
    name: '🚒 GENERAL APPARATUS',
    subtitle: 'Engine (E1-4), Rescue (R1-4), Quint (Q5), Pumper',
    weightTons: 22,
    speedCode3KmH: 45.0,
    speedCode1KmH: 32.0,
    roadFactorCode3: 1.35,
    roadFactorCode1: 1.45,
    speedFactor: 1.00,        // Standard baseline
    turnPenaltySec: 5,        // 5 seconds per 90-degree turn
    uphillDragFactor: 1.30,   // Moderate speed loss on steep climbs
    downhillSpeedCapKm: 60,   // 60 km/h safety retarder cap
    color: '#10b981'          // Emerald Green
  },
  HEAVY: {
    key: 'HEAVY',
    name: '🚚 HEAVY APPARATUS',
    subtitle: 'Ladder (L1-4), Tower Platform, Water Tender (T1-4, WT4)',
    weightTons: 35,
    speedCode3KmH: 38.0,
    speedCode1KmH: 28.0,
    roadFactorCode3: 1.45,
    roadFactorCode1: 1.55,
    speedFactor: 0.844,       // Heavy inertia
    turnPenaltySec: 8,        // 8 seconds per 90-degree turn
    uphillDragFactor: 1.65,   // High hill-climb drag (Burke Mtn, Westwood Plateau)
    downhillSpeedCapKm: 50,   // 50 km/h safety braking cap on steep descents
    color: '#f59e0b'          // Amber / Orange
  }
};

// Default Configuration Settings
export const DEFAULT_ROUTING_CONFIG = {
  railroadAvoidanceEnabled: true,
  railroadThresholdMinutes: 3.0, // Overpass detour threshold
  emtracPreemptionEnabled: true,
  emtracRushHourEfficiency: 0.60, // 60% preemption efficiency during peak rush hour
  elevationPhysicsEnabled: true
};

// Classify a unit identifier string into its 3-tier apparatus profile
export function classifyApparatusUnit(unitStr) {
  if (!unitStr) return APPARATUS_TIERS.GENERAL;
  const clean = unitStr.trim().toUpperCase();

  // ⚡ LIGHT APPARATUS: Squad, Medic, Command Car, LAV, Specialty
  if (/\b(SQ|SQUAD|M|MEDIC|CAR|LAV|CHIEF|COMMAND|S|SPECIALTY)\d*\b/i.test(clean)) {
    return APPARATUS_TIERS.LIGHT;
  }
  // 🚚 HEAVY APPARATUS: Ladder, Tower, Tender, WT
  if (/\b(L|LADDER|T|TENDER|WT|TANKER|TOWER|PLATFORM)\d*\b/i.test(clean)) {
    return APPARATUS_TIERS.HEAVY;
  }
  // 🚒 GENERAL APPARATUS: Engine, Rescue, Quint, Pumper
  return APPARATUS_TIERS.GENERAL;
}

// Main CFR-EVORoutingEngine calculation function
export function calculateEVORouteMetrics({
  originCoords, // [lat, lng]
  targetCoords, // [lat, lng]
  dispatchedUnits = [], // Array of unit strings e.g. ["E1", "L1", "SQ1"]
  routeCoordinates = [], // Array of points from OSRM
  config = DEFAULT_ROUTING_CONFIG,
  timeOfDay = new Date()
}) {
  if (!originCoords || !targetCoords) return null;

  // Calculate base route distance (km) using route points or straight line distance * 1.3
  let distanceKm = 0;
  if (routeCoordinates && routeCoordinates.length > 1) {
    const line = turf.lineString(routeCoordinates.map(c => [c.lng || c[1], c.lat || c[0]]));
    distanceKm = turf.length(line, { units: 'kilometers' });
  } else {
    const fromPt = turf.point([originCoords[1], originCoords[0]]);
    const toPt = turf.point([targetCoords[1], targetCoords[0]]);
    distanceKm = turf.distance(fromPt, toPt, { units: 'kilometers' }) * 1.3;
  }

  // Detect time of day rush hour (AM: 07:00-09:00, PM: 15:30-18:30)
  const currentHour = timeOfDay.getHours();
  const currentMinute = timeOfDay.getMinutes();
  const timeVal = currentHour + currentMinute / 60;
  const isAmRush = timeVal >= 7.0 && timeVal <= 9.0;
  const isPmRush = timeVal >= 15.5 && timeVal <= 18.5;
  const isRushHour = isAmRush || isPmRush;

  // Check for CP Rail crossing interaction across Coquitlam corridor
  const crossesRailroad = (originCoords[0] < 49.26 && targetCoords[0] > 49.26) || (originCoords[0] > 49.26 && targetCoords[0] < 49.26) || (originCoords[1] < -122.80 && targetCoords[1] > -122.80);
  let railroadWarning = null;
  const railDelayKm = 0; // No rerouting or detour distance added per operational driver advisory directive

  // Proximity check for Colony Farm Rd & Kingsway Ave (Riverbend Corridor)
  const targetPt = turf.point([targetCoords[1], targetCoords[0]]);
  const colonyPt = turf.point([-122.8142995, 49.2397800]);
  const kingswayPt = turf.point([-122.7911077, 49.2650819]);

  const distToColony = turf.distance(targetPt, colonyPt, { units: 'kilometers' });
  const distToKingsway = turf.distance(targetPt, kingswayPt, { units: 'kilometers' });

  if (distToColony <= 1.2) {
    railroadWarning = {
      type: 'ADVISORY',
      badge: '🚂 RAIL CROSSING AHEAD (Colony Farm Rd)',
      color: 'amber'
    };
  } else if (distToKingsway <= 0.8) {
    railroadWarning = {
      type: 'ADVISORY',
      badge: '🚂 RAIL CROSSING AHEAD (Kingsway Ave / Riverbend)',
      color: 'amber'
    };
  } else if (crossesRailroad) {
    railroadWarning = {
      type: 'ADVISORY',
      badge: '🚂 RAIL CROSSING AHEAD (CP Rail Line)',
      color: 'amber'
    };
  }

  // If no units provided, default to Engine + Ladder + Squad benchmark
  const unitsToProcess = dispatchedUnits.length > 0 ? dispatchedUnits : ['SQ1', 'E1', 'L1'];

  // Process ETAs for each dispatched unit
  const unitResults = unitsToProcess.map(unitStr => {
    const tier = classifyApparatusUnit(unitStr);
    
    // Base average response speed (km/h) with EMTRAC green-wave preemption
    let baseSpeedKm = tier.speedCode3KmH || 45.0;

    // Apply rush hour preemption reduction
    if (isRushHour && config.emtracPreemptionEnabled) {
      baseSpeedKm *= (1.0 - (0.40 * (1.0 - config.emtracRushHourEfficiency)));
    }

    // Apply uphill incline grade friction (e.g. Burke Mtn / Westwood Plateau)
    const effectiveDistance = distanceKm + railDelayKm;
    let travelTimeMin = (effectiveDistance / baseSpeedKm) * 60;

    // Turn penalty (assuming ~1.2 turns per km)
    const estimatedTurns = Math.round(effectiveDistance * 1.2);
    travelTimeMin += (estimatedTurns * tier.turnPenaltySec) / 60;

    // Apply downhill speed cap if applicable
    if (tier.downhillSpeedCapKm) {
      const maxSpeedMin = (effectiveDistance / tier.downhillSpeedCapKm) * 60;
      travelTimeMin = Math.max(travelTimeMin, maxSpeedMin);
    }

    return {
      unit: unitStr,
      tierKey: tier.key,
      tierName: tier.name,
      tierSubtitle: tier.subtitle,
      color: tier.color,
      distanceKm: effectiveDistance.toFixed(1),
      etaMinutes: Math.max(0.5, travelTimeMin).toFixed(1)
    };
  });

  return {
    distanceKm: (distanceKm + railDelayKm).toFixed(1),
    railroadWarning,
    isRushHour,
    units: unitResults
  };
}
