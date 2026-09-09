import React, { useState } from 'react';
import { getUnitBadgeStyle, getShortCallsign, formatUnitEtaDisplay } from './unitFormat';
import { getReviewFlags, flagLabel } from '../../utils/reviewFlags';

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
  isTvMode = false,
  elapsedFormatted = '00:00',
  timeoutFormatted = '03:00',
  onDismiss = null,
  onExitReview = null,
  onToggleTvMode = null,
  onOpenPrePlan = null,
}) {
  const hydrantId = activeCall?.target?.nearest_city_hydrant ?? activeCall?.nearest_city_hydrant ?? null;
  const hydrantDist = activeCall?.target?.nearest_city_dist ?? activeCall?.nearest_city_dist ?? null;

  // The flag reasons and the changed fields open on a tap, inline under the badges. They
  // were `title` tooltips, which the touch TV and a phone never show: the crew could read
  // "3 Flags" and not what they were (operator, 2026-09-09: "I'd probably be okay going to
  // a click"). The list makes the banner taller rather than floating over the map, so it
  // needs no z-index above the details box and cannot cover the route.
  const [showFlags, setShowFlags] = useState(false);
  const [showChanges, setShowChanges] = useState(false);
  const flags = activeCall ? getReviewFlags(activeCall) : [];

  if (!activeCall) return null;

  return (
    <header className="bg-slate-900/90 border-b border-slate-800 px-3 lg:px-6 py-2 lg:py-3 flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-2 lg:gap-0 shadow-xl flex-shrink-0 backdrop-blur z-20">
      {/* Left: Priority Code, Responding Units with Live ETAs, Talk Group & Pre-Plan */}
      <div className="flex flex-col items-start gap-1.5 text-left lg:max-w-md order-2 lg:order-none">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Coquitlam transmits "respond routine" / "respond emergency" -- those are the
              terms, and there is no numeric code (operator ruling 2026-08-23, #30).
              UNKNOWN is its own amber state, not a silent fall-through to routine (#31). */}
          <div className={`px-3 py-1 rounded-lg font-black uppercase text-[11px] tracking-wider shadow ${
            isResponseUnknown ? 'bg-amber-500 text-slate-950'
              : isEmergency ? 'bg-red-600 text-white motion-safe:animate-pulse'
              : 'bg-emerald-600 text-white'
          }`}>
            {isResponseUnknown ? '⚠️ Response Unknown'
              : isEmergency ? '🚨 Emergency' : '🟢 Routine'}
          </div>

          {(isReviewMode || activeCall?.isReview) && (
            <div className="bg-purple-950/90 border border-purple-500/80 text-purple-200 px-2.5 py-1 rounded-lg font-mono text-[10px] font-bold flex items-center gap-1 shadow motion-safe:animate-pulse">
              <span>🧪</span>
              <span>REVIEW REPLAY</span>
            </div>
          )}

          {/* Names the changed fields rather than asserting a bare "UPDATED".
              The operator reported being told a call had updated with nothing to
              show for it -- see punch-list #34. The badge now only renders when
              getVisibleChanges() found something, and says what. */}
          {/* Named reasons the system thinks this call needs attention (#45). The
              crew sees WHAT is uncertain, not a score. Reasons are on hover here and
              listed in full in the review panel. */}
          {flags.length > 0 && (
            <button
              type="button"
              onClick={() => setShowFlags((v) => !v)}
              aria-expanded={showFlags}
              className="bg-amber-500 text-slate-950 px-2 py-0.5 touch:py-1.5 rounded font-black text-[10px] uppercase tracking-wider cursor-pointer"
              title={flags.map(f => `• ${flagLabel(f)}`).join('\n')}
            >
              ⚠️ {flags.length} {flags.length === 1 ? 'Flag' : 'Flags'} {showFlags ? '▴' : '▾'}
            </button>
          )}

          {isRecentlyUpdated && (
            <button
              type="button"
              onClick={() => setShowChanges((v) => !v)}
              aria-expanded={showChanges}
              className="bg-sky-600 text-white px-2 py-0.5 touch:py-1.5 rounded font-bold text-[10px] motion-safe:animate-bounce cursor-pointer"
              title={updatedFields.length
                ? `Changed: ${updatedFields.map(FIELD_LABELS_FOR_UPDATE).join(', ')}`
                : undefined}
            >
              ⚡ UPDATED{updatedFields.length
                ? `: ${updatedFields.slice(0, 2).map(FIELD_LABELS_FOR_UPDATE).join(', ')}${updatedFields.length > 2 ? ` +${updatedFields.length - 2}` : ''}`
                : ''}
            </button>
          )}
        </div>

        {showFlags && flags.length > 0 && (
          <ul className="w-full bg-amber-950/70 border border-amber-700/70 rounded-lg px-2.5 py-1.5 text-[11px] font-mono text-amber-100 flex flex-col gap-0.5 text-left">
            {flags.map((f, i) => <li key={i}>• {flagLabel(f)}</li>)}
          </ul>
        )}
        {showChanges && updatedFields.length > 0 && (
          <div className="w-full bg-sky-950/70 border border-sky-700/70 rounded-lg px-2.5 py-1.5 text-[11px] font-mono text-sky-100 text-left">
            Changed: {updatedFields.map(FIELD_LABELS_FOR_UPDATE).join(', ')}
          </div>
        )}

        {/* Tone-Matched Unit Response Badges */}
        {unitEtas.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5 mt-1">
            {unitEtas.map((item, idx) => {
              const badgeStyle = getUnitBadgeStyle(item.unit);
              const shortCallsign = getShortCallsign(item.unit);
              const formattedEta = formatUnitEtaDisplay(item.etaMin);
              return (
                <div
                  key={idx}
                  className={`px-2.5 py-0.5 rounded-lg border text-xs font-mono font-black tracking-wider flex items-center gap-1.5 shadow-sm ${badgeStyle}`}
                >
                  <span>{shortCallsign}</span>
                  <span className="opacity-40 text-[10px]">:</span>
                  <span className="text-white font-black">{formattedEta} ETA</span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-1.5 mt-1">
            {unitList.map((u, idx) => {
              const badgeStyle = getUnitBadgeStyle(u);
              const shortCallsign = getShortCallsign(u);
              return (
                <div
                  key={idx}
                  className={`px-2.5 py-0.5 rounded-lg border text-xs font-mono font-black tracking-wider flex items-center gap-1.5 shadow-sm ${badgeStyle}`}
                >
                  <span>{shortCallsign}</span>
                </div>
              );
            })}
          </div>
        )}

        {/* Talk Group & Hydrant Quick-Read */}
        <div className="flex items-center gap-2 font-mono text-[10px] mt-1">
          {talkGroup && (
            <span className="bg-slate-950 text-amber-300 border border-slate-800 px-2 py-1 rounded-lg font-bold">
              📻 {talkGroup}
            </span>
          )}
          {/* Nearest hydrant. Rendered ONLY when the dispatch actually carries one.
              This previously fell back to the literal strings 'D-163' and '42' when the
              fields were absent -- and they are absent on every dispatch, because the
              backend has never emitted nearest_city_hydrant or nearest_city_dist. So the
              kiosk named a specific hydrant, at a specific distance, on every call, and
              none of it was data (CLAUDE.md §6.1, punch-list #24). */}
          {hydrantId && (
            <div className="bg-slate-950/90 text-sky-400 border border-sky-800/80 px-2.5 py-1 rounded-lg flex items-center gap-1.5 shadow-sm">
              <span>💧</span>
              <span className="font-bold text-white">City Hydrant:</span>
              <span className="text-sky-300 font-black">{hydrantId}</span>
              {hydrantDist != null && <span className="text-slate-400">({hydrantDist}m)</span>}
            </div>
          )}
          {(activeCall?.target?.pre_plan_pdf_url || activeCall?.pre_plan_pdf_url) && onOpenPrePlan && (
            <button
              type="button"
              onClick={onOpenPrePlan}
              className="bg-sky-950/90 hover:bg-sky-900 text-sky-300 hover:text-white border border-sky-600 px-3 py-1 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 shadow-md motion-safe:animate-pulse cursor-pointer"
              title="Open Pre-Incident Construction Plan PDF"
            >
              <span>📄</span>
              <span>Pre-Incident Plan</span>
            </button>
          )}
        </div>
      </div>

      {/* Center: Extra Large Address & Centered Incident Type */}
      {/* On a phone this column comes first and the address wraps; from `sm` up the sizes
          are exactly what the hall display has always had; below `lg` the columns stack. */}
      <div className="flex flex-col items-center text-center px-1 lg:px-4 order-1 lg:order-none min-w-0">
        <h1 className={`font-black tracking-tight text-white uppercase font-sans break-words ${isTvMode ? 'text-3xl sm:text-5xl' : 'text-2xl sm:text-4xl'}`}>
          {displayAddress}
          {formattedGrid && (
            <span className="text-amber-400 font-mono ml-2.5">({formattedGrid})</span>
          )}
        </h1>

        {/* XStreets -- the block-confirmation reference, as the run sheet labels it.
            Rendered only when announced: absent is absent, never a placeholder (§6.1).
            Deliberately quieter than the address, which stays the primary target. */}
        {/* The fields live in target; the top level never carried them, which is why this
            line never rendered (punch list #51b). A name the resolver could not match to a
            road near the address is shown as heard with a mark, never rewritten (#56). */}
        {(() => {
          const t = activeCall.target || {};
          const names = [activeCall.x_street_1 ?? t.x_street_1, activeCall.x_street_2 ?? t.x_street_2];
          const how = t.x_streets_how || [];
          if (!names[0] && !names[1]) return null;
          const shown = names.map((n, i) => {
            if (!n) return null;
            const h = how[i];
            const mark = h === 'unresolved' || h === 'no-candidates' || h === 'ambiguous' ? ' (as heard)'
                       : h === 'nearby-fuzzy' ? ' (?)' : '';
            return `${n}${mark}`;
          }).filter(Boolean).join(' & ');
          return (
            <div className={`font-mono font-bold tracking-wide text-slate-300 mt-0.5 ${
              isTvMode ? 'text-lg sm:text-xl' : 'text-sm sm:text-base'
            }`}>
              <span className="text-slate-500 uppercase mr-1.5">Near</span>
              {shown}
            </div>
          );
        })()}

        <div className={`font-black tracking-wider uppercase font-mono mt-1 ${
          activeCall.is_test ? 'text-orange-400' : 'text-amber-400'
        } ${isTvMode ? 'text-xl sm:text-3xl' : 'text-lg sm:text-2xl'}`}>
          {displayIncident}
        </div>

        {activeCall.is_test && (
          <div className="mt-1">
            <span className="bg-amber-500/20 text-amber-300 border border-amber-500/40 px-3 py-0.5 rounded-full text-[11px] font-black font-mono tracking-wider motion-safe:animate-pulse">
              ⚠️ SYSTEM TEST / DRILL — NOT A LIVE 911 CALL ⚠️
            </span>
          </div>
        )}

        {activeCall.subaddress && (
          <div className="mt-1">
            <span className="bg-slate-800 text-sky-300 border border-slate-700 px-3 py-0.5 rounded text-xs font-bold font-mono">
              🏢 {activeCall.subaddress}
            </span>
          </div>
        )}
      </div>

      {/* Right: Elapsed Time, Auto-Dismiss Countdown & Exit Controls */}
      <div className="flex items-center justify-between lg:justify-start gap-3 order-3 lg:order-none">
        <div className="flex flex-col items-end font-mono leading-tight">
          <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Elapsed Time</div>
          <div className="text-xl font-black text-emerald-400">{elapsedFormatted}</div>
          <div className="text-[9px] text-slate-500">
            {(isReviewMode || activeCall?.isReview) ? '⏸️ Auto-Dismiss Paused' : `Auto-Dismiss in ${timeoutFormatted}`}
          </div>
        </div>

        {(isReviewMode || activeCall?.isReview) ? (
          onExitReview && (
            <button
              type="button"
              onClick={onExitReview}
              className="bg-purple-700 hover:bg-purple-600 text-white px-3.5 py-1.5 touch:py-2.5 rounded-xl text-xs font-bold transition shadow cursor-pointer border border-purple-500 flex items-center gap-1 font-mono"
            >
              <span>🚪</span>
              <span>EXIT REVIEW</span>
            </button>
          )
        ) : (
          !isTvMode && onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 px-3.5 py-1.5 touch:py-2.5 rounded-xl text-xs font-bold transition shadow cursor-pointer font-mono"
            >
              Dismiss
            </button>
          )
        )}

        {onToggleTvMode && (
          <button
            type="button"
            onClick={onToggleTvMode}
            className="hidden lg:inline-flex bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-3 py-1.5 rounded-xl text-xs font-bold transition shadow cursor-pointer font-mono"
            title="Toggle TV Viewing Mode"
          >
            {isTvMode ? '📺 TV Mode' : '💻 Normal'}
          </button>
        )}
      </div>
    </header>
  );
}
