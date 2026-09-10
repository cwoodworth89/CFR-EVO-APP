import React, { useState } from 'react';
import RouteOverviewPanel from './RouteOverviewPanel';
import DetailStack from '../DetailStack';
import PrePlanModal from './PrePlanModal';
import ActiveAlertBanner from '../hud/ActiveAlertBanner';
import { STATIONS } from '../MapConstants';
import { useCompactViewport } from '../../hooks/useCompactViewport';

// The hall this display belongs to. Operator, 2026-09-09: "the hall is going to be hard-coded
// per kiosk deployment in the .env file" -- VITE_DEFAULT_HALL in frontend/.env.local, read at
// build time, the same setting the workstation header shows. Unset, Hall 1, which is the one
// kiosk that exists. Until 2026-09-09 nothing passed this down and the route always left Hall 1.
const KIOSK_HALL = (() => {
  const id = String(import.meta.env.VITE_DEFAULT_HALL || '1');
  const stn = STATIONS.find(s => s.id === id) || STATIONS[0];
  return { id: stn.id, lat: stn.coords[0], lng: stn.coords[1], name: stn.name };
})();

/**
 * The dispatch display, laid out to artboard 3A of the operator's Claude Design canvas
 * (docs/design/Dispatch Display Redesign.dc.html, 2026-09-09):
 *
 *   header    three cards -- the call, the units with their ETAs, the clock (ActiveAlertBanner)
 *   notices   one row, only when there is something real to say: the pre-incident plan, an
 *             operator-set arrival point
 *   body      the route map, with the route pill, the control stack and the hydrant card on
 *             it (RouteOverviewPanel), and a column of two view tiles, aerial and Street View
 *
 * The floating "Dispatch Details & ETAs" box is gone: its units moved into the header, its
 * hydrant onto the map, its arrival-point ruling into the notices row (#74, the operator's
 * complaint that it covered the destination). Below `lg` the same pieces stack in a column
 * for a phone: header, map, then the tiles as tabs (docs/briefings/mobile_accessibility_review.md).
 *
 * The canvas's ROAD CLOSURE and OCCUPANCY notices are not built: no route-corridor closure
 * check exists (road-closure-management skill) and no occupancy record exists, so there is
 * nothing real to put in them (CLAUDE.md s6.1). Its EXPAND state (artboard 3C) is not built;
 * the tiles keep their full-screen expand.
 */
export default function KioskView({ kioskState }) {

  const {
    activeCall,
    queuedCalls,
    isReviewMode,
    autoDismiss,
    isRecentlyUpdated,
    updatedFields,
    elapsedFormatted,
    timeoutFormatted,
    resetTimeoutClock,
    advanceToNextCall,
    dismissActiveCall,
    exitReview,
  } = kioskState;

  const [showPrePlanModal, setShowPrePlanModal] = useState(false);
  // The hydrant is picked along the route the map drew, so the map measures it and hands the
  // card's model up here; the header renders it and hands TAP TO ZOOM back down to the map's
  // own SNAP TO CALL (operator, 2026-09-10: the card moved off the map into the header).
  const [hydrantModel, setHydrantModel] = useState(null);
  const [snapRequest, setSnapRequest] = useState(0);
  // Below `lg`, a phone or an upright tablet: the layout stacks, the detail tiles become tabs.
  const compact = useCompactViewport();

  // There is no no-call branch here on purpose. KioskView is only ever mounted with a
  // call on it: App.jsx sends the screen back to STANDBY (the console) the moment
  // activeCall clears, whether the countdown ran out, the operator closed it, or a review
  // replay ended. The idle screen this replaced was reachable only from the mode select
  // that was removed the same day, and it reported "DB Sync: Connected" and "Audio Card:
  // Listening" as hardcoded strings, which would have read green with the agent stopped
  // (CLAUDE.md s6.1). Operator, 2026-09-08: calls drop back to Explore.

  // Response classification. Coquitlam transmits "respond routine" / "respond
  // emergency"; those two strings are what the parser emits and what
  // public.vocabulary stores, so there is nothing to translate and no numeric code
  // (operator ruling 2026-08-23, punch-list #30).
  //
  // The previous test also read `priority_code <= 2`, a field that has never existed
  // in the database or the backend. Every branch evaluated undefined, so isEmergency
  // was permanently false and every dispatch rendered routine. Punch-list #31.
  const responseType = (activeCall.response_type || '').toLowerCase().trim();
  const isEmergency = responseType === 'emergency';
  // Distinct from "not emergency": unknown is a flagged condition, not routine.
  const isResponseUnknown = responseType === '';

  // Parse responding units list (preserving exact order dispatched from database)
  const extractCallUnits = (call) => {
    if (!call) return [];

    const isReviewed = call.feedback_submitted || (call.quality_rating && call.quality_rating !== 'PENDING');

    // 1. If call is human-reviewed & verified units exist, use reviewed units!
    if (isReviewed && Array.isArray(call.verified_units) && call.verified_units.length > 0) {
      return call.verified_units;
    }

    // 2. If call is pending review (or unreviewed), use raw AI pipeline extracted data!
    const candidates = [
      call.responding_units,
      call.units,
      call.raw_units,
      call.target?.responding_units,
      call.target?.units,
      call.verified_units
    ];

    for (const cand of candidates) {
      if (Array.isArray(cand) && cand.length > 0) return cand;
      if (typeof cand === 'string' && cand.trim().length > 0) {
        const parsed = cand.split(',').map((u) => u.trim()).filter(Boolean);
        if (parsed.length > 0) return parsed;
      }
    }
    return [];
  };

  const unitList = extractCallUnits(activeCall);

  // Tier 1 (CLAUDE.md §5): coordinates are never guessed. If the geocoder did not
  // resolve a location, destLat/destLng stay null, all routing output is suppressed,
  // and the unresolved-location warning is shown instead.
  const rawDestLat = activeCall?.lat ?? activeCall?.target?.lat ?? null;
  const rawDestLng = activeCall?.lng ?? activeCall?.target?.lng ?? null;

  const hasCoords = rawDestLat != null && rawDestLng != null &&
    !isNaN(Number(rawDestLat)) && !isNaN(Number(rawDestLng)) &&
    (Number(rawDestLat) !== 0 || Number(rawDestLng) !== 0);

  // ETAs are OSRM's, resolved by the backend and persisted on the dispatch.
  // If they are absent the units render with '--:--' -- never a client-side estimate
  // (CLAUDE.md §6.1, §6.2). The hall is the record's origin_hall or nothing: it used to be
  // guessed from the digits in the callsign, which is not where a unit comes from.
  const persistedMetrics = activeCall?.routing_metrics || activeCall?.target?.routing_metrics;
  const unitEtas = (hasCoords && Array.isArray(persistedMetrics) && persistedMetrics.length > 0)
    ? persistedMetrics.map((m) => ({
        unit: m.unit,
        hallId: m.origin_hall != null ? String(m.origin_hall) : null,
        etaMin: m.eta_minutes ?? null,
        distKm: m.road_distance_km ?? m.distance_km ?? null,
      }))
    : [];

  const talkGroup = activeCall?.radio_channel || activeCall?.target?.radio_channel || activeCall?.talk_group || activeCall?.talkGroup || activeCall?.tg || null;
  const rawMapGrid = activeCall?.map_grid || activeCall?.target?.map_grid || activeCall?.mapGrid || activeCall?.grid || null;
  const gridLabel = rawMapGrid ? (rawMapGrid.toString().toUpperCase().startsWith('GRID') ? rawMapGrid.toString().toUpperCase() : `GRID ${rawMapGrid}`) : null;
  // Until phase 2 hears the grid, phase 1 shows the zone the placed parcel sits in and says so
  // (target.map_grid_source === 'parcel-zone', punch list #72). A derived value is labelled, never
  // dressed as the announced one (CLAUDE.md section 6.1).
  const gridSource = activeCall?.target?.map_grid_source || activeCall?.map_grid_source || null;
  const formattedGrid = gridLabel && gridSource === 'parcel-zone' ? `${gridLabel} · FROM ADDRESS` : gridLabel;

  const isReviewed = activeCall.feedback_submitted || (activeCall.quality_rating && activeCall.quality_rating !== 'PENDING');
  const displayAddress = (isReviewed && typeof activeCall.verified_address === 'string' && activeCall.verified_address.trim().length > 0)
    ? activeCall.verified_address.trim()
    : (activeCall.address || activeCall.target?.address || 'Address Unspecified');

  const rawIncident = (isReviewed && typeof activeCall.verified_incident === 'string' && activeCall.verified_incident.trim().length > 0)
    ? activeCall.verified_incident.trim()
    : (activeCall.incident_type || activeCall.target?.incident_type || 'EMERGENCY DISPATCH');

  const displayIncident = activeCall.is_test && !rawIncident.includes('*TEST*')
    ? `*TEST* ${rawIncident}`
    : rawIncident;

  // Green routine / red emergency are a stylistic cue for drivers; amber overrides
  // both and means "needs attention regardless of response type" (operator, #30).
  // An unknown response type is one such condition (#31).
  const borderColor = isResponseUnknown ? 'border-amber-500'
    : isEmergency ? 'border-red-600'
    : 'border-emerald-500';

  // The notices row: only what the record actually carries.
  const prePlanUrl = activeCall?.target?.pre_plan_pdf_url || activeCall?.pre_plan_pdf_url || null;
  // An operator-set arrival point: say so, and why, so the crew reads the pin as a ruling
  // rather than a wrong guess (#49). 'entrance' is the operator's; 'front' is the parcel's
  // own frontage and needs no notice.
  const arrivalSet = activeCall?.target?.arrival_point === 'entrance';
  const entranceNote = activeCall?.target?.entrance_note || null;
  const hasNotices = Boolean(prePlanUrl || arrivalSet);

  return (
    // Below `lg` the column scrolls: three header cards, a map at half the height and the
    // tiles do not fit an 852 px phone at once, and a clipped column left the tile tabs
    // unreachable (measured 2026-09-09). From `lg` up nothing scrolls, as on the hall display.
    <div
      onClick={resetTimeoutClock}
      className={`kiosk-root fixed inset-0 bg-slate-950 text-slate-100 flex flex-col z-50 select-none border-[6px] ${borderColor} transition-colors duration-500 overflow-y-auto overflow-x-hidden lg:overflow-hidden safe-area`}
    >
      {/* Queued Call Notification Banner */}
      {queuedCalls.length > 0 && (
        <div
          onClick={advanceToNextCall}
          className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-3 lg:px-6 py-2 flex flex-wrap items-center justify-between gap-2 cursor-pointer motion-safe:animate-pulse shadow-xl border-b border-amber-600 z-50 flex-shrink-0"
        >
          <span className="text-xs lg:text-sm tracking-wide uppercase font-mono">
            {queuedCalls.length} New Call{queuedCalls.length > 1 ? 's' : ''} Queued — Tap to View Next
          </span>
          <div className="bg-slate-950 text-amber-400 px-3 py-0.5 rounded text-xs font-mono font-bold max-w-full truncate">
            Next: {queuedCalls[0]?.address || 'Dispatch Alert'} →
          </div>
        </div>
      )}

      {/* Review replay: a strip, not a card. Operator, 2026-09-10: REVIEW REPLAY and EXIT
          REVIEW "can be located somewhere else as they aren't on dispatches" -- so they take
          the same full-width place the queued-call and Tier 1 banners do, and a real call
          renders none of it. The card they vacated went to the hydrant. */}
      {(isReviewMode || activeCall?.isReview) && (
        <div className="bg-violet-950 border-b border-violet-700 text-violet-200 px-3 lg:px-6 py-1.5 flex items-center justify-between gap-3 flex-shrink-0 z-50">
          <span className="font-mono font-bold text-[11px] lg:text-xs tracking-[0.14em] uppercase">
            Review replay — a past call, replayed; auto-dismiss paused
          </span>
          <button
            type="button"
            onClick={exitReview}
            className="bg-transparent border border-violet-600 text-violet-200 hover:bg-violet-900 rounded-md px-3 py-1.5 touch:py-2.5 font-mono font-bold text-[10px] lg:text-[11px] tracking-[0.12em] uppercase whitespace-nowrap cursor-pointer transition"
          >
            Exit review
          </button>
        </div>
      )}

      {/* Tier 1 Unresolved-Location Warning (CLAUDE.md §5) — all call details still
          display normally below; only routing/ETA output is withheld. */}
      {!hasCoords && (
        <div className="bg-amber-500 text-slate-950 font-bold px-3 lg:px-6 py-2 flex items-center gap-3 border-b border-amber-600 shadow-xl z-50 flex-shrink-0 motion-safe:animate-pulse">
          <span className="text-xs lg:text-sm tracking-wide uppercase font-mono">
            Location Unresolved — Coordinates Awaiting Operator Verification • Routing &amp; ETAs Unavailable
          </span>
        </div>
      )}

      {/* The header: the call, the units, the clock */}
      <ActiveAlertBanner
        activeCall={activeCall}
        unitEtas={unitEtas}
        unitList={unitList}
        talkGroup={talkGroup}
        formattedGrid={formattedGrid}
        displayAddress={displayAddress}
        displayIncident={displayIncident}
        isEmergency={isEmergency}
        isReviewMode={isReviewMode}
        isRecentlyUpdated={isRecentlyUpdated}
        isResponseUnknown={isResponseUnknown}
        updatedFields={updatedFields}
        autoDismiss={autoDismiss}
        elapsedFormatted={elapsedFormatted}
        timeoutFormatted={timeoutFormatted}
        hydrantModel={hydrantModel}
        onHydrantTap={hasCoords ? () => setSnapRequest((n) => n + 1) : null}
        onDismiss={() => dismissActiveCall('manual')}
      />

      {/* Notices: one row, rendered only when the record carries something to say. */}
      {hasNotices && (
        <div className="flex-shrink-0 px-2 lg:px-3 pt-2 lg:pt-3 flex flex-wrap gap-2 lg:gap-3">
          {arrivalSet && (
            <div className="flex-1 min-w-[16rem] flex items-center gap-3 px-3.5 py-2.5 lg:px-4 lg:py-3 rounded-xl bg-emerald-950/60 border border-emerald-700/70">
              <span className="font-mono font-extrabold text-[10px] lg:text-[11px] tracking-[0.12em] uppercase bg-emerald-400 text-slate-950 rounded px-2 py-1 whitespace-nowrap">Arrival point</span>
              <span className="font-sans font-medium text-emerald-100 text-sm lg:text-base leading-snug">
                Set by the operator{entranceNote ? ` — ${entranceNote}` : ''}
              </span>
            </div>
          )}
          {prePlanUrl && (
            <button
              type="button"
              onClick={() => setShowPrePlanModal(true)}
              className="flex items-center gap-2.5 px-3.5 py-2.5 lg:px-4 lg:py-3 rounded-xl bg-slate-950 border border-sky-800 hover:border-sky-600 cursor-pointer transition"
            >
              <span className="w-2 h-2 rounded-full bg-sky-400 flex-shrink-0" />
              <span className="font-mono font-bold text-xs lg:text-sm tracking-[0.08em] uppercase text-sky-300">Pre-incident plan</span>
            </button>
          )}
        </div>
      )}

      {/* The body: the route map and the two view tiles. From `lg` up a row, the map taking
          what the column leaves; below it a column, the map at just over half the height and
          the tiles as tabs. The column is the canvas's 740 px of 1,920, held between a floor
          and that ceiling so the tiles stay readable on the 1,280 px touch display. */}
      <main className="flex-none lg:flex-1 p-2 lg:p-3 flex flex-col lg:flex-row gap-2 lg:gap-3 min-h-0 lg:overflow-hidden">
        <section className="h-[52dvh] lg:h-auto lg:flex-1 min-w-0 min-h-0 flex-shrink-0 lg:flex-shrink">
          <RouteOverviewPanel
            activeCall={activeCall}
            stationHall={KIOSK_HALL}
            compact={compact}
            onHydrantModel={setHydrantModel}
            snapRequest={snapRequest}
          />
        </section>

        {/* Two tiles, aerial and Street View. The cadastral block tile that sat above them is
            gone (operator, 2026-09-08): SNAP TO CALL on the route map shows the parcel, the
            addresses and the hydrants at the same zoom, on the map the crew is already reading.
            On a phone the tiles are tabs under the map, a little over half a screen tall. */}
        <section className="h-[56dvh] lg:h-auto flex-shrink-0 lg:flex-none lg:w-[clamp(360px,38.5%,740px)] min-h-0">
          <DetailStack call={activeCall} compact={compact} />
        </section>
      </main>

      {/* Pre-Incident Construction Plan PDF Viewer Modal */}
      <PrePlanModal
        isOpen={showPrePlanModal}
        onClose={() => setShowPrePlanModal(false)}
        pdfUrl={prePlanUrl}
        address={activeCall?.address}
        gisId={activeCall?.target?.gis_id || activeCall?.gis_id}
      />
    </div>
  );
}
