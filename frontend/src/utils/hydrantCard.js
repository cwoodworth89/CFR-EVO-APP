import { TIER } from './routeHydrants.js';

/**
 * What the hydrant card on the dispatch map says, from the picker's answer.
 *
 * The card is artboard 3A of the operator's Claude Design canvas (docs/design/Dispatch
 * Display Redesign.dc.html): one hydrant, numbered as it is on the map, its NFPA 291 class,
 * its distance in feet, and -- where the title does not already say it -- one line on how it
 * was chosen. A second row appears only
 * where the operator's rule produces a decision rather than a list: the nearest is private
 * and a City hydrant is shown for supply, or the first choice is a long lay and a closer
 * off-route hydrant sits beside it (docs/ux_notes.md section 3 item 4). Two straight-line
 * picks are a list, so the second is not shown.
 *
 * Pure: no React, no fetch, so it is tested under node (tests/hydrantCard.test.mjs).
 */

// 1 ft = 0.3048 m exactly (international foot, 1959 agreement between the English-speaking
// standards bodies). The picker measures in metres; the crew's own rule is stated in feet
// (50 ft roll, 300 ft, 1,000 ft supply lay), and the canvas shows feet.
export const M_PER_FT = 0.3048;

export function metresToFeet(m) {
  if (m == null || Number.isNaN(Number(m))) return null;
  return Math.round(Number(m) / M_PER_FT);
}

// NFPA 291 class colours, one table for the numbered badges on the map
// (map/PickedHydrantsLayer.jsx) and the rows of the card, so they cannot disagree:
// AA light blue, A green, B orange, C red; unrated slate; a private hydrant's ring amber.
export const HYDRANT_CLASS_COLOUR = Object.freeze({ AA: '#38bdf8', A: '#4ade80', B: '#fb923c', C: '#f87171' });
export const HYDRANT_UNRATED_COLOUR = '#94a3b8';
export const HYDRANT_PRIVATE_RING = '#f59e0b';

export const CARD_STATE = Object.freeze({
  AWAITING: 'awaiting',   // no location yet: nothing to measure from
  LOADING: 'loading',     // inventory fetch in flight
  FAILED: 'failed',       // inventory fetch failed: not "no hydrant"
  NONE: 'none',           // nothing within the 1,000 ft supply lay
  PICKS: 'picks',
});

const isPrivate = (h) => String(h?.status || '').toUpperCase() === 'PRIVATE';

/** The one line under a pick: how the rule chose it. Mirrors the tiers in routeHydrants.js. */
export function hydrantHow(pick, { first = true, routeKnown = true } = {}) {
  if (!pick) return '';
  switch (pick.how) {
    case TIER.DOORSTEP:
      return 'within a 50 ft roll of the address';
    case TIER.APPROACH:
      return 'before arrival, on the route';
    case TIER.NEAR:
      if (pick.closerAlternative) return 'from the address, off route: the closer option';
      return `from the address, straight-line${first ? (routeKnown ? '; none on the approach within 1,000 ft' : '; route pending') : ''}`;
    case TIER.SUPPLY:
      return 'within the 1,000 ft supply lay; none within 300 ft';
    default:
      return '';
  }
}

function row(pick, n, opts) {
  return {
    n,
    id: pick.gisId,
    flowClass: pick.flowClass || null,        // null renders UNRATED; nothing is assumed
    isPrivate: isPrivate(pick),
    feet: metresToFeet(pick.distance),
    metres: pick.distance ?? null,
    how: hydrantHow(pick, opts),
    longLay: Boolean(pick.longLay),
  };
}

/**
 * @param {object} args
 * @param {boolean} args.hasCoords   the call has a usable location
 * @param {object}  args.hydrants    the useRouteHydrants() result: { tier, picks, routeKnown, loading, failed }
 * @returns {{ state: string, title: string|null, warn: boolean, rows: Array, note: string|null }}
 */
export function hydrantCardModel({ hasCoords, hydrants }) {
  if (!hasCoords) return { state: CARD_STATE.AWAITING, title: null, warn: false, rows: [], note: 'Awaiting location' };
  if (!hydrants || hydrants.failed) return { state: CARD_STATE.FAILED, title: null, warn: true, rows: [], note: 'Hydrant lookup failed' };
  if (hydrants.loading) return { state: CARD_STATE.LOADING, title: null, warn: false, rows: [], note: 'Hydrant inventory loading' };
  if (hydrants.tier === TIER.NONE || !hydrants.picks?.length) {
    return { state: CARD_STATE.NONE, title: null, warn: true, rows: [], note: null };
  }

  const [first, second] = hydrants.picks;
  const routeKnown = Boolean(hydrants.routeKnown);
  const rows = [row(first, 1, { first: true, routeKnown })];

  // The two decision cases; anything else is one hydrant.
  const privateFirst = isPrivate(first) && second && !isPrivate(second);
  const longLay = Boolean(first.longLay) && second?.closerAlternative;
  if (second && (privateFirst || longLay)) rows.push(row(second, 2, { first: false, routeKnown }));

  let title = 'FIRST HYDRANT';
  let warn = false;
  let note = `${rows[0].isPrivate ? 'Private' : 'City'} · ${rows[0].how}`;
  if (privateFirst) {
    title = 'PRIVATE IS CLOSER';
    warn = true;
    note = `Nearest is private${first.flowClass ? '' : ' and unrated'}; nearest City hydrant shown for supply`;
  } else if (longLay || first.longLay) {
    // The amber LONG LAY chip is the whole message and the two distances say the rest
    // (operator, 2026-09-10: "get rid of the first choice is 500ft away text, that's clear").
    title = 'LONG LAY';
    warn = true;
    note = null;
  }

  return { state: CARD_STATE.PICKS, title, warn, rows, note };
}
