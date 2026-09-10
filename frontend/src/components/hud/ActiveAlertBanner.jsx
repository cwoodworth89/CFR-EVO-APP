import React, { useState } from 'react';
import { getUnitBadgeStyle, formatUnitEtaDisplay } from './unitFormat';
import { getReviewFlags, flagLabel } from '../../utils/reviewFlags';
import { hallColour, UNASSIGNED_HALL_COLOUR } from '../MapConstants';

/**
 * The dispatch display's header, built to artboard 3A of the operator's Claude Design canvas
 * (docs/design/Dispatch Display Redesign.dc.html, "Integrated -- call details live in the
 * header, right column is nothing but views"). Three cards on one row from `lg` up:
 *
 *   the call      address and grid, the subaddress, NEAR the cross streets, the incident,
 *                 the talk group -- what the run sheet reads out;
 *   the units     the first dispatched unit large with its road distance and ETA, the rest
 *                 in a two-column grid, every ETA OSRM's from the stored routing_metrics;
 *   the clock     elapsed, the auto-dismiss state, REVIEW REPLAY and EXIT REVIEW or CLEAR.
 *
 * Below `lg` (a phone or an upright tablet) the same three cards stack, the call first.
 *
 * What the canvas leaves out and this keeps, because each is a state the crew must be able
 * to read (CLAUDE.md s6.1): the response badge, where UNKNOWN is an amber state distinct from
 * routine (#31); the flag reasons and the changed fields, which open on a tap (#45, #34);
 * the TEST / DRILL mark. What the canvas demotes and this drops: the TV-mode toggle (a
 * deployment setting, not a per-call control), the hall origin line, the OSRM label.
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

/** One unit row: the dispatched callsign as the record holds it, its hall's colour, OSRM's figures or the unknown marks. */
function UnitRow({ unit, hero = false }) {
  const style = getUnitBadgeStyle(unit.unit);
  const eta = formatUnitEtaDisplay(unit.etaMin);
  const dist = unit.distKm != null && !Number.isNaN(Number(unit.distKm)) ? `${Number(unit.distKm).toFixed(1)} KM` : '-- KM';
  // Below `lg` the rows are chips in a wrap and the type steps down; a phone's header has to
  // leave room for the map under it.
  return (
    <div className={`flex items-center border rounded-lg ${style} ${hero ? 'gap-2.5 lg:gap-3.5 px-3 py-2 lg:px-4 lg:py-3' : 'gap-2 lg:gap-2.5 px-2.5 py-1.5 lg:px-3 lg:py-2.5'}`}>
      {/* The unit's hall colour, the same as its route line on the map; slate when the record
          carries no hall for it (nothing is guessed from the callsign). */}
      <span
        className={`rounded-full flex-shrink-0 ${hero ? 'w-3 h-3' : 'w-2.5 h-2.5'}`}
        style={{ backgroundColor: unit.hallId ? hallColour(unit.hallId) : UNASSIGNED_HALL_COLOUR }}
      />
      <span className={`font-sans font-extrabold uppercase tracking-tight truncate ${hero ? 'text-xl lg:text-2xl 2xl:text-3xl' : 'text-sm lg:text-base 2xl:text-xl'}`}>
        {String(unit.unit).toUpperCase()}
      </span>
      {hero && <span className="font-mono font-semibold text-[11px] lg:text-xs tracking-wider text-slate-400 whitespace-nowrap">{dist}</span>}
      <span className={`ml-auto font-mono font-extrabold text-white tabular-nums ${hero ? 'text-2xl lg:text-3xl 2xl:text-4xl' : 'text-base lg:text-lg 2xl:text-2xl'}`}>
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
  // false on a phone: no clock, the call stays until cleared (operator, 2026-09-09).
  autoDismiss = true,
  elapsedFormatted = '00:00',
  timeoutFormatted = '03:00',
  onDismiss = null,
  onExitReview = null,
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

  // The dispatched units in dispatched order, each with OSRM's figures where the record has
  // them. Built from the unit list rather than from the metrics so a unit the router never
  // measured is still listed, with '--:--' beside it, instead of vanishing.
  const metricsByUnit = new Map(unitEtas.map((e) => [String(e.unit).toUpperCase(), e]));
  const names = unitList.length ? unitList : unitEtas.map((e) => e.unit);
  const units = names.map((u) => {
    const m = metricsByUnit.get(String(u).toUpperCase());
    return { unit: u, etaMin: m?.etaMin ?? null, distKm: m?.distKm ?? null, hallId: m?.hallId ?? null };
  });
  const [hero, ...rest] = units;

  return (
    <header className="flex-shrink-0 z-20 px-2 lg:px-3 pt-2 lg:pt-3 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(340px,29%)_auto] gap-2 lg:gap-3 items-stretch">
      {/* The call */}
      <section className={`${CARD} px-4 py-3 lg:px-6 lg:py-4 flex flex-col items-start gap-1.5 lg:gap-2.5`}>
        <div className="flex items-center gap-2.5 lg:gap-3.5 flex-wrap">
          <h1 className="m-0 font-sans font-extrabold uppercase tracking-tight leading-[0.95] text-white break-words text-2xl sm:text-3xl lg:text-4xl xl:text-5xl 2xl:text-7xl">
            {displayAddress}
          </h1>
          {/* "GRID 68", or "GRID 68 · FROM ADDRESS" when phase 1 derived it from the parcel's
              zone and phase 2 has not yet heard it (#72): a derived value is labelled. */}
          {formattedGrid && (
            <span className="border border-amber-500/50 bg-amber-500/10 text-amber-400 font-mono font-bold tracking-wider whitespace-nowrap rounded-md px-2 py-1 lg:px-3 lg:py-2 text-xs lg:text-base 2xl:text-xl">
              {formattedGrid}
            </span>
          )}
        </div>

        {subaddress && (
          <div className="font-mono font-medium uppercase tracking-wider text-slate-300 text-[11px] lg:text-sm xl:text-base">
            {subaddress}
          </div>
        )}

        {near && (
          <div className="font-mono font-medium uppercase tracking-wide text-slate-300 text-xs lg:text-base xl:text-lg">
            <span className="text-slate-400 mr-2">Near</span>{near}
          </div>
        )}

        <div className="flex items-center gap-2 lg:gap-3 flex-wrap">
          <div className={`font-sans font-bold uppercase tracking-wider text-lg lg:text-xl xl:text-2xl 2xl:text-3xl ${activeCall.is_test ? 'text-orange-400' : 'text-amber-400'}`}>
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

        {talkGroup && (
          <div className="flex items-center gap-2.5 lg:gap-3 mt-0.5 px-2.5 py-1.5 lg:px-3.5 lg:py-2.5 border border-slate-700 bg-slate-400/10 rounded-lg max-w-full">
            <span className={LABEL}>Talk group</span>
            <span className="font-mono font-bold uppercase text-white text-sm lg:text-lg 2xl:text-2xl leading-none truncate">
              {String(talkGroup)}
            </span>
          </div>
        )}
      </section>

      {/* The units */}
      <section className={`${CARD} px-3 py-2.5 lg:px-5 lg:py-4 flex flex-col gap-1.5 lg:gap-3`}>
        {hero ? (
          <>
            <UnitRow unit={hero} hero />
            {rest.length > 0 && (
              <div className="flex flex-wrap gap-1.5 lg:grid lg:grid-cols-2 lg:gap-2">
                {rest.map((u, i) => <UnitRow key={`${u.unit}-${i}`} unit={u} />)}
              </div>
            )}
          </>
        ) : (
          // No units in the record: an unknown, shown as one (CLAUDE.md s6.1).
          <div className="flex items-center gap-3 px-3.5 py-3 rounded-lg border border-amber-700/60 bg-amber-950/40">
            <span className={LABEL}>Units</span>
            <span className="font-mono font-extrabold text-amber-300 text-lg lg:text-xl">NOT HEARD</span>
          </div>
        )}
      </section>

      {/* The clock */}
      {/* One slim row on a phone; a column at the right of the header from `lg`. */}
      <section className={`${CARD} px-3 py-2 lg:px-5 lg:py-4 flex flex-row flex-wrap lg:flex-col lg:flex-nowrap items-center lg:items-end justify-between gap-2 lg:gap-3.5`}>
        <div className="flex items-baseline gap-2 lg:block text-left lg:text-right font-mono leading-none">
          <div className={LABEL}>Elapsed</div>
          <div className="lg:mt-1.5 font-extrabold text-emerald-400 tabular-nums text-xl lg:text-3xl 2xl:text-[42px]">{elapsedFormatted}</div>
          <div className="lg:mt-1.5 font-medium tracking-wider uppercase text-slate-400 text-[10px] lg:text-[11px] whitespace-nowrap">
            {isReview ? 'Auto-dismiss paused'
              : autoDismiss ? `Auto-dismiss ${timeoutFormatted}`
              : 'Stays until cleared'}
          </div>
        </div>

        <div className="flex items-center gap-2 lg:gap-2.5">
          {isReview && (
            <span className="border border-violet-700 bg-violet-950 text-violet-300 rounded-md px-2 py-1.5 lg:px-2.5 lg:py-2 font-mono font-bold text-[10px] lg:text-[11px] tracking-[0.12em] uppercase whitespace-nowrap">
              Review replay
            </span>
          )}
          {isReview ? (
            onExitReview && (
              <button
                type="button"
                onClick={onExitReview}
                className="bg-transparent border border-violet-700 text-violet-300 hover:bg-violet-950 rounded-md px-3 py-2 lg:px-3.5 lg:py-2.5 touch:py-2.5 font-mono font-bold text-[11px] lg:text-xs tracking-[0.12em] uppercase whitespace-nowrap cursor-pointer transition"
              >
                Exit review
              </button>
            )
          ) : (
            onDismiss && (
              <button
                type="button"
                onClick={onDismiss}
                className="bg-slate-950 border border-slate-700 text-slate-200 hover:bg-slate-800 rounded-md px-3 py-2 lg:px-3.5 lg:py-2.5 touch:py-2.5 font-mono font-bold text-[11px] lg:text-xs tracking-[0.12em] uppercase whitespace-nowrap cursor-pointer transition"
              >
                {autoDismiss ? 'Dismiss' : 'Clear call'}
              </button>
            )
          )}
        </div>
      </section>
    </header>
  );
}
