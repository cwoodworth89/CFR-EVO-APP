/**
 * Which hydrants to show a driver for a call, in the order the operator asked for
 * (department operational policy, operator 2026-09-06, punch-list #74):
 *
 *   1. "Choice #1 and #2": the two hydrants ALONG THE ROUTE OF TRAVEL closest to the call,
 *      within 300 ft of arrival, measured along the route. The last hydrant the apparatus
 *      passes is #1.
 *   2. None there: look around the address itself within 300 ft, straight-line --
 *      "sometimes it's just past the address" -- which the route line cannot see because
 *      OSRM ends the route at the address.
 *   3. Still none: the engines carry 1,000 ft of supply hose, so a hydrant within that
 *      straight-line reach is reported as such, and nothing within it is a warning.
 *
 * Pure and dependency-free so it runs under `node --test` (frontend/tests/). Coordinates are
 * projected onto a local metre grid around the destination; at city scale the error is
 * well under one percent of the distances involved.
 */

// 300 ft. Operator 2026-09-06: "If there's no hydrant within 300ft of the route, check if
// there is one (sometimes it's just past the address). If nothing within 300ft warn the driver."
export const APPROACH_M = 91.44;

// 1,000 ft. Operator 2026-09-06: "Our trucks carry 1000ft of supply hose, but there aren't
// many places in the city that would be needed."
export const SUPPLY_M = 304.8;

// How far from the OSRM route line a hydrant can sit and still be "along the route".
// Measured 2026-09-06 on public.hydrants against public.roads centrelines, 2,837 OPERATING
// hydrants: p50 8.4 m, p90 11.9 m, p95 35 m. 30 m takes the arterial half-width and the
// setback with margin; the p95 tail is hydrants on lanes the roads table does not carry.
export const ROUTE_BAND_M = 30;

// Statuses in public.hydrants a crew cannot use. NOT READY is the City's own word for it;
// the older names are kept from the map layer's list.
export const UNUSABLE_STATUS = new Set(['NOT READY', 'ABANDONED', 'OUT_OF_SERVICE', 'INACTIVE']);

export const TIER = {
  APPROACH: 'approach',   // on the route, within APPROACH_M of arrival
  NEAR: 'near',           // within APPROACH_M of the address, straight-line
  SUPPLY: 'supply',       // within SUPPLY_M of the address, straight-line: a supply lay
  NONE: 'none',           // nothing within SUPPLY_M
  NO_TARGET: 'no_target',
};

const M_PER_DEG_LAT = 110540;   // WGS84 metres per degree of latitude, mid-latitudes
const M_PER_DEG_LNG_EQ = 111320;

function projector(lat0, lng0) {
  const kx = M_PER_DEG_LNG_EQ * Math.cos((lat0 * Math.PI) / 180);
  return (lat, lng) => [(lng - lng0) * kx, (lat - lat0) * M_PER_DEG_LAT];
}

/** Nearest point on segment ab to p, as [distance, t] with t in [0, 1]. */
function segmentDistance(p, a, b) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  let t = 0;
  if (len2 > 0) {
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
  }
  const cx = a[0] + t * dx;
  const cy = a[1] + t * dy;
  return [Math.hypot(p[0] - cx, p[1] - cy), t];
}

function usable(h) {
  const st = String(h.status || '').toUpperCase();
  return !UNUSABLE_STATUS.has(st) && Number.isFinite(Number(h.lat)) && Number.isFinite(Number(h.lng));
}

/**
 * @param {object} args
 * @param {Array<{gisId, status, flowClass, lat, lng}>} args.hydrants  the inventory (any extent)
 * @param {Array<{lat, lng}>} args.routeCoords  the OSRM route as drawn, origin first, arrival last; may be empty
 * @param {{lat, lng}|null} args.destination
 * @returns {{tier: string, picks: Array, routeKnown: boolean}}
 *   each pick carries `distance` (metres, the figure to show), `how` (TIER), and for
 *   approach picks `beforeArrivalM` and `offRouteM`.
 */
export function pickRouteHydrants({ hydrants = [], routeCoords = [], destination = null }) {
  if (!destination || destination.lat == null || destination.lng == null) {
    return { tier: TIER.NO_TARGET, picks: [], routeKnown: false };
  }
  const lat0 = Number(destination.lat);
  const lng0 = Number(destination.lng);
  const project = projector(lat0, lng0);
  const pool = hydrants.filter(usable).map(h => {
    const [x, y] = project(Number(h.lat), Number(h.lng));
    return { h, x, y, straight: Math.hypot(x, y) };
  }).filter(e => e.straight <= SUPPLY_M * 4);   // a cheap cull; the tiers below decide

  const routeKnown = Array.isArray(routeCoords) && routeCoords.length > 1;

  // Tier 1: along the route, within APPROACH_M of arrival.
  if (routeKnown) {
    const pts = routeCoords.map(c => project(Number(c.lat), Number(c.lng)));
    const cum = [0];
    for (let i = 1; i < pts.length; i++) {
      cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    }
    const total = cum[cum.length - 1];
    const approach = [];
    for (const e of pool) {
      let best = null;
      for (let i = 1; i < pts.length; i++) {
        const [d, t] = segmentDistance([e.x, e.y], pts[i - 1], pts[i]);
        if (best === null || d < best.d) {
          const along = cum[i - 1] + t * (cum[i] - cum[i - 1]);
          best = { d, along };
        }
      }
      if (!best || best.d > ROUTE_BAND_M) continue;
      const beforeArrivalM = Math.round(total - best.along);
      if (beforeArrivalM > APPROACH_M) continue;
      approach.push({
        ...e.h, how: TIER.APPROACH, distance: beforeArrivalM,
        beforeArrivalM, offRouteM: Math.round(best.d),
      });
    }
    if (approach.length) {
      approach.sort((a, b) => a.beforeArrivalM - b.beforeArrivalM);
      return { tier: TIER.APPROACH, picks: approach.slice(0, 2), routeKnown };
    }
  }

  // Tier 2: around the address, straight-line, within APPROACH_M.
  const near = pool.filter(e => e.straight <= APPROACH_M)
    .sort((a, b) => a.straight - b.straight)
    .map(e => ({ ...e.h, how: TIER.NEAR, distance: Math.round(e.straight) }));
  if (near.length) return { tier: TIER.NEAR, picks: near.slice(0, 2), routeKnown };

  // Tier 3: within the supply hose the engines carry.
  const supply = pool.filter(e => e.straight <= SUPPLY_M)
    .sort((a, b) => a.straight - b.straight)
    .map(e => ({ ...e.h, how: TIER.SUPPLY, distance: Math.round(e.straight) }));
  if (supply.length) return { tier: TIER.SUPPLY, picks: supply.slice(0, 1), routeKnown };

  return { tier: TIER.NONE, picks: [], routeKnown };
}
