import React, { useState } from 'react';
import RouteOverviewPanel from './RouteOverviewPanel';
import BlockParcelPanel from './BlockParcelPanel';
import PropertySatellitePanel from './PropertySatellitePanel';
import StreetViewPanel from './StreetViewPanel';
import PrePlanModal from './PrePlanModal';
import ActiveAlertBanner from '../hud/ActiveAlertBanner';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';
import { STATIONS } from '../MapConstants';

// Color coding tone matching: Engine = Orange, Rescue = Red, Ladder = Cyan, Chief = Gold, Medic = Emerald
const getUnitBadgeStyle = (unitStr) => {
  const u = (unitStr || '').toUpperCase().trim();
  if (u.startsWith('E') || u.startsWith('ENG') || u.includes('ENGINE')) {
    return 'bg-orange-500/20 text-orange-400 border-orange-500/50';
  }
  if (u.startsWith('R') || u.startsWith('RESCUE') || u.includes('RESCUE')) {
    return 'bg-rose-500/20 text-rose-400 border-rose-500/50';
  }
  if (u.startsWith('L') || u.startsWith('TR') || u.includes('LADDER') || u.includes('TRUCK')) {
    return 'bg-sky-500/20 text-sky-300 border-sky-500/50';
  }
  if (u.startsWith('C') || u.startsWith('CHIEF') || u.includes('CHIEF') || u.startsWith('B')) {
    return 'bg-amber-500/20 text-amber-300 border-amber-500/50';
  }
  if (u.startsWith('M') || u.startsWith('MEDIC') || u.startsWith('S') || u.startsWith('AMB')) {
    return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50';
  }
  return 'bg-slate-800 text-slate-200 border-slate-700';
};

const getShortCallsign = (unitStr) => {
  const u = (unitStr || '').trim().toUpperCase();
  if (!u) return '';
  const numMatch = u.match(/\d+/);
  const num = numMatch ? numMatch[0] : '';

  if (u.includes('ENGINE') || u.startsWith('ENG') || u.startsWith('E')) return `E${num || u}`;
  if (u.includes('RESCUE') || u.startsWith('R')) return `R${num || u}`;
  if (u.includes('LADDER') || u.includes('TRUCK') || u.startsWith('L')) return `L${num || u}`;
  if (u.includes('CHIEF') || u.startsWith('C')) return `C${num || u}`;
  if (u.includes('MEDIC') || u.startsWith('M')) return `M${num || u}`;
  return u;
};

const formatUnitEtaDisplay = (etaMin) => {
  // No fabricated placeholder: an unknown ETA renders as '--:--', never a plausible number.
  if (etaMin == null || isNaN(etaMin)) return '--:--';
  const totalSec = Math.round(etaMin * 60);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  const padM = String(mins).padStart(2, '0');
  const padS = String(secs).padStart(2, '0');
  return `${padM}:${padS}`;
};

function getUnitIcon(unit) {
  const u = String(unit).toUpperCase();
  if (u.startsWith('M')) return '🚑'; // Medic
  if (u.startsWith('L')) return '🚒'; // Ladder
  if (u.startsWith('E')) return '🚒'; // Engine
  if (u.startsWith('R')) return '🚒'; // Rescue
  if (u.startsWith('C') || u.startsWith('B')) return '🚨'; // Chief / Battalion
  if (u.startsWith('WT') || u.startsWith('W')) return '💧'; // Water Tender
  if (u.startsWith('SQ')) return '⚡'; // Squad
  return '🚒';
}

function calculateUnitEta(unitName, destLat, destLng) {
  const cleanUnit = String(unitName).trim().toUpperCase();
  const numMatch = cleanUnit.match(/\d+/);
  const hallId = numMatch ? numMatch[0] : '1';
  const station = STATIONS.find((s) => s.id === hallId) || STATIONS[0];

  if (!destLat || !destLng || !station?.coords) {
    return {
      unit: cleanUnit,
      hall: `Hall ${hallId}`,
      etaStr: null,
      distStr: null,
      icon: getUnitIcon(cleanUnit),
    };
  }

  // Haversine crow-flies distance
  const [stnLat, stnLng] = station.coords;
  const toRad = (x) => (x * Math.PI) / 180;
  const dLat = toRad(destLat - stnLat);
  const dLng = toRad(destLng - stnLng);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(stnLat)) * Math.cos(toRad(destLat)) *
    Math.sin(dLng / 2) * Math.sin(dLng / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const crowKm = 6371 * c;

  // Emergency urban road network factor (~1.35x crow-flies)
  const roadKm = crowKm * 1.35;
  // Emergency vehicle response speed (~45 km/h) + 30s apron turnout
  const totalMinutes = (roadKm / 45) * 60 + 0.5;
  const etaMin = Math.max(1, Math.round(totalMinutes));

  return {
    unit: cleanUnit,
    hall: `Hall ${hallId}`,
    etaMin,
    etaStr: `~${etaMin} min`,
    distStr: `${roadKm.toFixed(1)} km`,
    icon: getUnitIcon(cleanUnit),
  };
}

export default function KioskView({ kioskState }) {
  const isOnline = useOnlineStatus();

  const {
    activeCall,
    queuedCalls,
    isReviewMode,
    isTvMode,
    isRecentlyUpdated,
    elapsedFormatted,
    timeoutFormatted,
    resetTimeoutClock,
    advanceToNextCall,
    dismissActiveCall,
    exitReview,
    toggleTvMode,
  } = kioskState;

  const [showPrePlanModal, setShowPrePlanModal] = useState(false);

  // Station Idle Monitor Screen
  if (!activeCall) {
    return (
      <div className="fixed inset-0 bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 z-50 select-none">
        <div className="flex flex-col items-center gap-5 text-center max-w-lg">
          <div className="w-20 h-20 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-4xl shadow-inner">
            🚒
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Coquitlam Fire Rescue Kiosk</h1>
          <p className="text-sm text-slate-400 font-medium">In-Station Dispatch Monitor Active • Listening for Radio Feed & Database Events...</p>
          
          {/* Centered Vertically Stacked System Health Indicators */}
          <div className="flex flex-col items-center justify-center gap-2 w-full mt-2">
            {/* DB Real-Time Sync Badge */}
            <div className="flex items-center justify-center gap-2 text-xs font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-4 py-1.5 rounded-full shadow-sm w-72">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span>DB Sync: Connected</span>
            </div>

            {/* Audio Card Listener Status Badge */}
            <div className="flex items-center justify-center gap-2 text-xs font-mono text-sky-400 bg-sky-950/60 border border-sky-800/60 px-4 py-1.5 rounded-full shadow-sm w-72">
              <span className="w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
              <span>🎙️ Audio Card: Listening (UCA202)</span>
            </div>

            {/* WAN Connection Status Badge */}
            <div className={`flex items-center justify-center gap-2 text-xs font-mono px-4 py-1.5 rounded-full shadow-sm border w-72 ${
              isOnline
                ? 'text-emerald-400 bg-emerald-950/60 border-emerald-800/60'
                : 'text-amber-300 bg-amber-950/80 border-amber-600/80 animate-pulse'
            }`}>
              <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              <span>🌐 WAN: {isOnline ? 'Connected' : 'Offline (Failsafe)'}</span>
            </div>
          </div>

          <button
            onClick={exitReview}
            className="mt-4 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl font-semibold text-xs transition shadow-lg cursor-pointer flex items-center gap-1.5"
          >
            <span>🚪</span>
            <span>Exit Kiosk View</span>
          </button>
        </div>
      </div>
    );
  }

  // Priority classification for border
  const isEmergency =
    activeCall.priority_code <= 2 ||
    String(activeCall.priority_code).toLowerCase() === 'emergency' ||
    String(activeCall.response_type).toLowerCase() === 'emergency';

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

  let unitList = extractCallUnits(activeCall);

  // Tier 1 (CLAUDE.md §5): coordinates are never guessed. If the geocoder did not
  // resolve a location, destLat/destLng stay null, all routing output is suppressed,
  // and the unresolved-location warning is shown instead.
  const rawDestLat = activeCall?.lat ?? activeCall?.target?.lat ?? null;
  const rawDestLng = activeCall?.lng ?? activeCall?.target?.lng ?? null;

  const hasCoords = rawDestLat != null && rawDestLng != null &&
    !isNaN(Number(rawDestLat)) && !isNaN(Number(rawDestLng)) &&
    (Number(rawDestLat) !== 0 || Number(rawDestLng) !== 0);

  const destLat = hasCoords ? Number(rawDestLat) : null;
  const destLng = hasCoords ? Number(rawDestLng) : null;

  const persistedMetrics = activeCall?.routing_metrics || activeCall?.target?.routing_metrics;
  const unitEtas = !hasCoords
    ? [] // No location data — units render as plain badges with no ETA or distance
    : (persistedMetrics && Array.isArray(persistedMetrics) && persistedMetrics.length > 0)
    ? persistedMetrics.map((m) => ({
        unit: m.unit,
        hall: `Hall ${m.origin_hall || (m.unit.match(/\d+/) ? m.unit.match(/\d+/)[0] : '1')}`,
        etaMin: m.eta_minutes,
        etaStr: `~${m.eta_minutes} min`,
        distStr: `${m.road_distance_km || m.distance_km} km`,
        icon: getUnitIcon(m.unit),
      }))
    : unitList.map((unit) => calculateUnitEta(unit, destLat, destLng));

  const talkGroup = activeCall?.radio_channel || activeCall?.target?.radio_channel || activeCall?.talk_group || activeCall?.talkGroup || activeCall?.tg || null;
  const rawMapGrid = activeCall?.map_grid || activeCall?.target?.map_grid || activeCall?.mapGrid || activeCall?.grid || null;
  const formattedGrid = rawMapGrid ? (rawMapGrid.toString().toUpperCase().startsWith('GRID') ? rawMapGrid.toString().toUpperCase() : `GRID ${rawMapGrid}`) : null;

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

  const borderColor = isEmergency ? 'border-red-600' : 'border-emerald-500';

  return (
    <div
      onClick={resetTimeoutClock}
      className={`fixed inset-0 bg-slate-950 text-slate-100 flex flex-col z-50 select-none border-[6px] ${borderColor} transition-colors duration-500 overflow-hidden`}
    >
      {/* Queued Call Notification Banner */}
      {queuedCalls.length > 0 && (
        <div
          onClick={advanceToNextCall}
          className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-6 py-2 flex items-center justify-between cursor-pointer animate-pulse shadow-xl border-b border-amber-600 z-50 flex-shrink-0"
        >
          <div className="flex items-center gap-3">
            <span className="text-lg">⚠️</span>
            <span className="text-sm tracking-wide uppercase font-mono">
              {queuedCalls.length} New Call{queuedCalls.length > 1 ? 's' : ''} Queued — Tap to View Next
            </span>
          </div>
          <div className="bg-slate-950 text-amber-400 px-3 py-0.5 rounded text-xs font-mono font-bold">
            Next: {queuedCalls[0]?.address || 'Dispatch Alert'} →
          </div>
        </div>
      )}

      {/* Tier 1 Unresolved-Location Warning (CLAUDE.md §5) — all call details still
          display normally below; only routing/ETA output is withheld. */}
      {!hasCoords && (
        <div className="bg-amber-500 text-slate-950 font-bold px-6 py-2 flex items-center gap-3 border-b border-amber-600 shadow-xl z-50 flex-shrink-0 animate-pulse">
          <span className="text-lg">⚠️</span>
          <span className="text-sm tracking-wide uppercase font-mono">
            Location Unresolved — Coordinates Awaiting Operator Verification • Routing &amp; ETAs Unavailable
          </span>
        </div>
      )}

      {/* Modular High-Visibility Active Alert Banner Header */}
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
        isTvMode={isTvMode}
        elapsedFormatted={elapsedFormatted}
        timeoutFormatted={timeoutFormatted}
        onDismiss={dismissActiveCall}
        onExitReview={exitReview}
        onToggleTvMode={toggleTvMode}
        onOpenPrePlan={() => setShowPrePlanModal(true)}
      />

      {/* Main Content Layout (2/3 Main Route Map, 1/3 Equal Height Detail Stack) */}
      <main className="flex-1 p-3 grid grid-cols-12 gap-3 min-h-0 overflow-hidden">
        {/* Left ~2/3 Suggested Route Panel */}
        <section className="col-span-8 h-full min-h-0">
          <RouteOverviewPanel activeCall={activeCall} />
        </section>

        {/* Right ~1/3 Equal-Height 3-Panel Detail Stack */}
        <section className="col-span-4 h-full min-h-0 flex flex-col gap-3 overflow-hidden">
          <div className="flex-1 min-h-0 relative">
            <BlockParcelPanel activeCall={activeCall} />
          </div>
          <div className="flex-1 min-h-0 relative">
            <PropertySatellitePanel activeCall={activeCall} />
          </div>
          <div className="flex-1 min-h-0 relative">
            <StreetViewPanel activeCall={activeCall} />
          </div>
        </section>
      </main>

      {/* Pre-Incident Construction Plan PDF Viewer Modal */}
      <PrePlanModal
        isOpen={showPrePlanModal}
        onClose={() => setShowPrePlanModal(false)}
        pdfUrl={activeCall?.target?.pre_plan_pdf_url || activeCall?.pre_plan_pdf_url}
        address={activeCall?.address}
        gisId={activeCall?.target?.gis_id || activeCall?.gis_id}
      />
    </div>
  );
}
