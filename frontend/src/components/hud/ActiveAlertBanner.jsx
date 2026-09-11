import React, { useState } from 'react';
import { getUnitBadgeStyle, formatUnitEtaDisplay } from './unitFormat';
import { getReviewFlags, flagLabel } from '../../utils/reviewFlags';
import { hallColour, UNASSIGNED_HALL_COLOUR } from '../MapConstants';
import HydrantCard from '../kiosk/HydrantCard';

/**
 * The dispatch display's header, built to artboard 3A of the operator's Claude Design canvas
 * (docs/design/Dispatch Display Redesign.dc.html, "Integrated -- call details live in the
 * header, right column is nothing but views"). Three cards on one row from `lg` up:
 *
 *   the call      address and grid, the subaddress, NEAR the cross streets, the incident;
 *                 along its foot, the talk group and -- small, out of the way -- the elapsed
 *                 clock, the auto-dismiss state and the dismiss button;
 *   the units     the first-due unit (shortest OSRM ETA) with its road distance and ETA, the
 *                 rest by ETA in a two-column grid, every figure from routing_metrics;
 *   the water     the hydrant by the operator's rule, in feet, with how it was chosen.
 *
 * Below `lg` (a phone or an upright tablet) the same three cards stack, the call first.
 *
 * **Rearranged 2026-09-10 on the operator's word.** 3A gave the third card to a clock and put
 * the hydrant over the route map, where it covered the destination. The clock is not what a
 * crew reads in the first seconds ("elapsed time maybe out of the way in the main header
 * card, bottom right"), and REVIEW REPLAY / EXIT REVIEW are not on real dispatches at all
 * ("can be located somewhere else"), so they became a strip above the header in KioskView.
 * The hydrant took the card they vacated: its own fixed place, rather than a row inside the
 * units card that would slide down the screen as the unit count changes.
 *
 * What the canvas leaves out and this keeps, because each is a state the crew must be able
 * to read (CLAUDE.md s6.1): the response badge, where UNKNOWN is an amber state distinct from
 * routine (#31); the flag reasons and the changed fields, which open on a tap (#45, #34);
 * the TEST / DRILL mark. What the canvas demotes and this drops: the TV-mode toggle (removed
 * outright 2026-09-09, operator), the hall origin line, the OSRM label.
 *
 * Nothing here is estimated: an ETA or distance the record does not carry renders as
 * '--:--' and '-- KM'; a field the dispatch did not announce is not rendered at all.
 */

// Operator-facing names for the fields getVisibleChanges() reports. Falls through
// to the raw key so a newly-tracked field is still readable rather than hidden.
const UPDATE_FIELD_LABELS = {
  address: 'address',
  incident_type: 'incident',
  responding_units: 'units',
  subaddress: 'unit #',
  // "intersection" is the incident location when the call IS a junction. It is NOT
  // the XStreets, and used to be labelled "cross streets" here -- which named the
  // wrong field, since on 53 of the last 81 calls the XStreets were populated and
  // the junction was not.
  intersection: 'intersection',
  x_street_1: 'xstreet 1',
  x_street_2: 'xstreet 2',
  lat: 'location',
  lng: 'location',
  map_grid: 'map grid',
  radio_channel: 'talk group',
  response_type: 'response',
  location_type: 'location type',
  requested_address: 'requested address',
  resolution_note: 'location note',
};
const FIELD_LABELS_FOR_UPDATE = (f) => UPDATE_FIELD_LABELS[f] || f;

const LABEL = 'font-mono font-bold text-[10px] lg:text-[11px] tracking-[0.16em] text-slate-400 uppercase';
const CARD = 'bg-slate-900 border border-slate-800 rounded-xl min-w-0';

/** The cross streets as announced, each marked with how it was resolved (#51b, #56). */
function nearLine(activeCall) {
  const t = activeCall.target || {};
  const names = [activeCall.x_street_1 ?? t.x_street_1, activeCall.x_street_2 ?? t.x_street_2];
  const how = t.x_streets_how || [];
  if (!names[0] && !names[1]) return null;
  return names.map((n, i) => {
    if (!n) return null;
    const h = how[i];
    const mark = h === 'unresolved' || h === 'no-candidates' || h === 'ambiguous' ? ' (as heard)'
               : h === 'nearby-fuzzy' ? ' (?)' : '';
    return `${n}${mark}`;
  }).filter(Boolean).join(' & ');
}

/**
 * One unit row: the dispatched callsign as the record holds it, its hall's colour, OSRM's
 * figures or the unknown marks. Stepped down 2026-09-10 ("shrink the hydrant/units/etas in
 * text size to get a better fit"); the sizes scale with viewport height from `lg` up.
 */
function UnitRow({ unit, hero = false }) {
  const style = getUnitBadgeStyle(unit.unit);
  const eta = formatUnitEtaDisplay(unit.etaMin);
  const dist = unit.distKm != null && !Number.isNaN(Number(unit.distKm)) ? `${Number(unit.distKm).toFixed(1)} KM` : '-- KM';
  return (
    <div className={`flex items-center border rounded-lg ${style} ${hero ? 'gap-2.5 px-3 py-1.5 lg:px-3.5 lg:py-2' : 'gap-2 px-2.5 py-1.5 lg:py-2'}`}>
      {/* The unit's hall colour, the same as its route line on the map; slate when the record
          carries no hall for it (nothing is guessed from the callsign). */}
      <span
        className={`rounded-full flex-shrink-0 ${hero ? 'w-2.5 h-2.5' : 'w-2 h-2'}`}
        style={{ backgroundColor: unit.hallId ? hallColour(unit.hallId) : UNASSIGNED_HALL_COLOUR }}
      />
      <span className={`font-sans font-extrabold uppercase tracking-tight truncate ${hero ? 'text-lg lg:text-[clamp(1.05rem,2.3vh,1.5rem)]' : 'text-sm lg:text-[clamp(0.8rem,1.5vh,1rem)]'}`}>
        {String(unit.unit).toUpperCase()}
      </span>
      {hero && <span className="font-mono font-semibold text-[10px] lg:text-[11px] tracking-wider text-slate-400 whitespace-nowrap">{dist}</span>}
      <span className={`ml-auto font-mono font-extrabold text-white tabular-nums ${hero ? 'text-xl lg:text-[clamp(1.2rem,2.7vh,1.75rem)]' : 'text-base lg:text-[clamp(0.9rem,1.7vh,1.2rem)]'}`}>
        {eta}
      </span>
    </div>
  );
}

export default function ActiveAlertBanner({
  activeCall,
  unitEtas = [],
  unitList = [],
  talkGroup = null,
  formattedGrid = null,
  displayAddress = '',
  displayIncident = '',
  isEmergency = true,
  isResponseUnknown = false,
  isReviewMode = false,
  isRecentlyUpdated = false,
  updatedFields = [],
  // The hydrant by the operator's rule, from the route map (utils/hydrantCard.js). Null until
  // the map has measured one; the card then says which state it is in, never a guess.
  hydrantModel = null,
  onHydrantTap = null,
  // The call's documents, along the foot of the hydrant card (operator, 2026-09-10).
  prePlanUrl = null,
  onOpenPrePlan = null,
  // false on a phone: no clock, the call stays until cleared (operator, 2026-09-09).
  autoDismiss = true,
  elapsedFormatted = '00:00',
  timeoutFormatted = '03:00',
  onDismiss = null,
}) {
  // The flag reasons and the changed fields open on a tap, inline under the chips. They were
  // `title` tooltips, which the touch TV and a phone never show (operator, 2026-09-09).
  const [showFlags, setShowFlags] = useState(false);
  const [showChanges, setShowChanges] = useState(false);
  const flags = activeCall ? getReviewFlags(activeCall) : [];

  if (!activeCall) return null;

  const isReview = isReviewMode || Boolean(activeCall.isReview);
  const near = nearLine(activeCall);
  const subaddress = activeCall.subaddress || activeCall.target?.subaddress || null;

  // The dispatched units, each with OSRM's figures where the record has them. Built from the
  // unit list rather than from the metrics so a unit the router never measured is still
  // listed, with '--:--' beside it, instead of vanishing.
  //
  // Order: first due first. Operator, 2026-09-09: "First due is most important and tells
  // who's closest" -- so the large slot is the unit with the shortest OSRM ETA and the rest
  // follow by ETA. Units the router did not measure keep their dispatched order after them;
  // nothing is estimated to rank them. Ties keep dispatched order (the sort is stable).
  const metricsByUnit = new Map(unitEtas.map((e) => [String(e.unit).toUpperCase(), e]));
  const names = unitList.length ? unitList : unitEtas.map((e) => e.unit);
  const units = names
    .map((u) => {
      const m = metricsByUnit.get(String(u).toUpperCase());
      return { unit: u, etaMin: m?.etaMin ?? null, distKm: m?.distKm ?? null, hallId: m?.hallId ?? null };
    })
    .sort((a, b) => {
      const ea = a.etaMin == null ? Infinity : Number(a.etaMin);
      const eb = b.etaMin == null ? Infinity : Number(b.etaMin);
      return ea - eb;
    });
  const [hero, ...rest] = units;

  // Header type from `lg` up scales with the viewport's height, the canvas's 1920x1080 sizes
  // as the reference (70 px address, 32 incident: 6.5 / 2.8 vh of 1080), so a 1000-tall
  // laptop and an 800-tall touch display keep the same proportions instead of the fixed steps
  // that left the header half the screen (operator, 2026-09-09). A long address shrinks so it
  // stays on one line: an intersection like "LANSDOWNE DR & ABERDEEN AVE" is 26 characters
  // against the canvas's 15.
  const addrLen = String(displayAddress || '').length;
  const addrScale = addrLen <= 16 ? 1 : addrLen <= 24 ? 0.8 : 0.66;

  return (
    <header className="flex-shrink-0 z-20 px-2 lg:px-3 pt-2 lg:pt-3 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(15rem,21%)_minmax(14rem,19%)] gap-2 lg:gap-3 items-stretch">
      {/* The call */}
      <section className={`${CARD} px-4 py-3 lg:px-5 lg:py-3.5 flex flex-col items-start gap-1.5 lg:gap-2`}>
        <div className="flex items-center gap-2.5 lg:gap-3.5 flex-wrap">
          <h1 className="m-0 font-sans font-extrabold uppercase tracking-tight leading-[0.95] text-white break-words text-2xl sm:text-3xl lg:text-[calc(clamp(2rem,min(6.5vh,3.8vw),4.5rem)*var(--addr,1))]" style={{ '--addr': addrScale }}>
            {displayAddress}
          </h1>
          {/* "GRID 68", or "GRID 68 · FROM ADDRESS" when phase 1 derived it from the parcel's
              zone and phase 2 has not yet heard it (#72): a derived value is labelled. */}
          {formattedGrid && (
            <span className="border border-amber-500/50 bg-amber-500/10 text-amber-400 font-mono font-bold tracking-wider whitespace-nowrap rounded-md px-2 py-1 lg:px-2.5 lg:py-1.5 text-xs lg:text-[clamp(0.75rem,1.6vh,1.125rem)]">
              {formattedGrid}
            </span>
          )}
        </div>

        {subaddress && (
          <div className="font-mono font-medium uppercase tracking-wider text-slate-300 text-[11px] lg:text-[clamp(0.7rem,1.4vh,1rem)]">
            {subaddress}
          </div>
        )}

        {near && (
          <div className="font-mono font-medium uppercase tracking-wide text-slate-300 text-xs lg:text-[clamp(0.75rem,1.5vh,1.05rem)]">
            <span className="text-slate-400 mr-2">Near</span>{near}
          </div>
        )}

        <div className="flex items-center gap-2 lg:gap-3 flex-wrap">
          <div className={`font-sans font-bold uppercase tracking-wider text-lg lg:text-[clamp(1.05rem,2.6vh,1.9rem)] ${activeCall.is_test ? 'text-orange-400' : 'text-amber-400'}`}>
            {displayIncident}
          </div>

          {/* Coquitlam transmits "respond routine" / "respond emergency"; there is no numeric
              code (#30). UNKNOWN is its own amber state, not a fall-through to routine (#31). */}
          <span className={`font-mono font-extrabold text-[10px] lg:text-[11px] tracking-[0.14em] uppercase rounded px-2 py-1 ${
            isResponseUnknown ? 'bg-amber-500 text-slate-950'
              : isEmergency ? 'bg-red-600 text-white motion-safe:animate-pulse'
              : 'bg-emerald-600 text-white'
          }`}>
            {isResponseUnknown ? 'Response unknown' : isEmergency ? 'Emergency' : 'Routine'}
          </span>

          {activeCall.is_test && (
            <span className="bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded px-2 py-1 font-mono font-extrabold text-[10px] lg:text-[11px] tracking-wider uppercase motion-safe:animate-pulse">
              System test / drill — not a live 911 call
            </span>
          )}

          {flags.length > 0 && (
            <button
              type="button"
              onClick={() => setShowFlags((v) => !v)}
              aria-expanded={showFlags}
              className="bg-amber-500 text-slate-950 rounded px-2 py-1 touch:py-2 font-mono font-extrabold text-[10px] lg:text-[11px] tracking-wider uppercase cursor-pointer"
            >
              {flags.length} {flags.length === 1 ? 'flag' : 'flags'} {showFlags ? '▴' : '▾'}
            </button>
          )}

          {/* Names the changed fields rather than asserting a bare "UPDATED" (#34). */}
          {isRecentlyUpdated && (
            <button
              type="button"
              onClick={() => setShowChanges((v) => !v)}
              aria-expanded={showChanges}
              className="bg-sky-600 text-white rounded px-2 py-1 touch:py-2 font-mono font-bold text-[10px] lg:text-[11px] tracking-wider uppercase motion-safe:animate-bounce cursor-pointer"
            >
              Updated{updatedFields.length
                ? `: ${updatedFields.slice(0, 2).map(FIELD_LABELS_FOR_UPDATE).join(', ')}${updatedFields.length > 2 ? ` +${updatedFields.length - 2}` : ''}`
                : ''}
            </button>
          )}
        </div>

        {showFlags && flags.length > 0 && (
          <ul className="w-full bg-amber-950/70 border border-amber-700/70 rounded-lg px-3 py-2 text-xs lg:text-sm font-mono text-amber-100 flex flex-col gap-0.5 text-left">
            {flags.map((f, i) => <li key={i}>• {flagLabel(f)}</li>)}
          </ul>
        )}
        {showChanges && updatedFields.length > 0 && (
          <div className="w-full bg-sky-950/70 border border-sky-700/70 rounded-lg px-3 py-2 text-xs lg:text-sm font-mono text-sky-100 text-left">
            Changed: {updatedFields.map(FIELD_LABELS_FOR_UPDATE).join(', ')}
          </div>
        )}

        {/* The card's foot: the talk group, and at the right the call's own clock, small.
            Operator, 2026-09-10: elapsed time "out of the way in the main header card, bottom
            right". It is not what a crew reads in the first seconds; it is what the operator
            checks later. */}
        <div className="pt-0.5 w-full flex items-end justify-between gap-3 flex-wrap">
          {talkGroup ? (
            <div className="flex items-center gap-2.5 px-2.5 py-1.5 lg:px-3 lg:py-2 border border-slate-700 bg-slate-400/10 rounded-lg min-w-0">
              <span className={LABEL}>Talk group</span>
              <span className="font-mono font-bold uppercase text-white text-sm lg:text-[clamp(0.85rem,1.9vh,1.35rem)] leading-none truncate">
                {String(talkGroup)}
              </span>
            </div>
          ) : <span />}

          <div className="ml-auto flex items-end gap-2.5 lg:gap-3">
            <div className="text-right font-mono leading-none">
              <span className={LABEL}>Elapsed</span>
              <div className="mt-1 font-extrabold text-emerald-400 tabular-nums text-lg lg:text-[clamp(1rem,2.2vh,1.5rem)]">{elapsedFormatted}</div>
              {/* On a replay the strip above already says the clock is paused, so this would
                  be the same fact twice (operator, 2026-09-10). On a live call it is the only
                  place that says whether the call clears itself, so it stays. */}
              {!isReview && (
                <div className="mt-1 font-medium tracking-wider uppercase text-slate-500 text-[10px] whitespace-nowrap">
                  {autoDismiss ? `Auto-dismiss ${timeoutFormatted}` : 'Stays until cleared'}
                </div>
              )}
            </div>

            {/* On a review replay the way out is the strip above the header, not here. */}
            {!isReview && onDismiss && (
              <button
                type="button"
                onClick={onDismiss}
                className="bg-slate-950 border border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white rounded-md px-3 py-1.5 lg:py-2 touch:py-2.5 font-mono font-bold text-[10px] lg:text-[11px] tracking-[0.12em] uppercase whitespace-nowrap cursor-pointer transition"
              >
                {autoDismiss ? 'Dismiss' : 'Clear call'}
              </button>
            )}
          </div>
        </div>
      </section>

      {/* The units */}
      <section className={`${CARD} px-3 py-2.5 lg:px-4 lg:py-3 flex flex-col justify-start gap-1.5 lg:gap-2`}>
        {hero ? (
          <>
            <UnitRow unit={hero} hero />
            {rest.length > 0 && (
              <div className="flex flex-wrap gap-1.5 lg:grid lg:grid-cols-2 lg:gap-1.5">
                {rest.map((u, i) => <UnitRow key={`${u.unit}-${i}`} unit={u} />)}
              </div>
            )}
          </>
        ) : (
          // No units in the record: an unknown, shown as one (CLAUDE.md s6.1).
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-amber-700/60 bg-amber-950/40">
            <span className={LABEL}>Units</span>
            <span className="font-mono font-extrabold text-amber-300 text-base lg:text-lg">NOT HEARD</span>
          </div>
        )}
      </section>

      {/* The water */}
      <HydrantCard model={hydrantModel} onTap={onHydrantTap} prePlanUrl={prePlanUrl} onOpenPrePlan={onOpenPrePlan} />
    </header>
  );
}
