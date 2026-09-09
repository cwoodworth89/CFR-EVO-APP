/**
 * Which halls' routes to draw for a call, and in what order (operator design, 2026-09-06 and
 * 2026-09-09, docs/ux_notes.md section 3 item 7):
 *
 *   "Every responding hall's route on one map, each in its hall's colour, the home hall's
 *    solid and the others translucent."
 *
 * The halls come from the backend's per-unit routing_metrics (origin_hall, set by
 * routing_engine.get_unit_station_id when the dispatch was processed), never from a guess
 * here: a unit without metrics contributes no hall. The home hall is always drawn, metrics or
 * not, because the crew reading the screen is leaving from it.
 *
 * Draw order is bottom to top: the home hall last so it sits on top where routes converge on
 * the call; among the others, the later ETA underneath and the sooner on top, so the next unit
 * to arrive is the one a driver can still see. Operator, 2026-09-09: the others "approach from
 * off screen", it "only matters in the final approach".
 *
 * Pure and dependency-free so it runs under `node --test` (frontend/tests/).
 */

// Operator, 2026-09-09: "let's start with that" -- roughly half opacity and two-thirds the
// weight for the other halls; the home route keeps the weight and opacity the single route had.
export const HOME_ROUTE_STYLE = { weight: 6, opacity: 0.95 };
export const OTHER_ROUTE_STYLE = { weight: 4, opacity: 0.45 };

/**
 * @param {object} args
 * @param {Array}  args.routingMetrics  backend routing_metrics: [{ unit, origin_hall, eta_minutes }]
 * @param {string} args.homeHall        the hall this screen belongs to, "1".."4"
 * @param {Array}  args.knownHalls      hall ids that exist, e.g. STATIONS.map(s => s.id)
 * @returns {Array<{hall: string, isHome: boolean, etaMinutes: number|null, units: string[]}>}
 *          in draw order, bottom first, home hall last
 */
export function hallRoutesToDraw({ routingMetrics = [], homeHall, knownHalls = [] }) {
  const known = new Set((knownHalls || []).map(String));
  const home = homeHall != null ? String(homeHall) : null;
  const byHall = new Map();

  for (const m of routingMetrics || []) {
    if (!m || m.origin_hall == null) continue;
    const hall = String(m.origin_hall);
    if (!known.has(hall)) continue;
    const entry = byHall.get(hall) || { hall, isHome: hall === home, etaMinutes: null, units: [] };
    const unit = String(m.unit || '').trim().toUpperCase();
    if (unit && !entry.units.includes(unit)) entry.units.push(unit);
    const eta = m.eta_minutes;
    if (eta != null && Number.isFinite(Number(eta))) {
      const n = Number(eta);
      entry.etaMinutes = entry.etaMinutes == null ? n : Math.min(entry.etaMinutes, n);
    }
    byHall.set(hall, entry);
  }

  if (home && known.has(home) && !byHall.has(home)) {
    byHall.set(home, { hall: home, isHome: true, etaMinutes: null, units: [] });
  }

  const others = [...byHall.values()].filter(e => !e.isHome);
  // Later ETA first (bottom), sooner last (on top). Unknown ETAs go to the bottom: nothing is
  // known about them, so they should hide nothing. Ties break on hall number for stability.
  others.sort((a, b) => {
    const ea = a.etaMinutes == null ? Infinity : a.etaMinutes;
    const eb = b.etaMinutes == null ? Infinity : b.etaMinutes;
    if (ea !== eb) return eb - ea;
    return Number(b.hall) - Number(a.hall);
  });

  const homeEntry = byHall.get(home);
  return homeEntry ? [...others, homeEntry] : others;
}
