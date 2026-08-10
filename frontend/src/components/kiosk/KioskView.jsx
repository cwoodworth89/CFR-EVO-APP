import React from 'react';
import RouteOverviewPanel from './RouteOverviewPanel';
import BlockParcelPanel from './BlockParcelPanel';
import PropertySatellitePanel from './PropertySatellitePanel';
import StreetViewPanel from './StreetViewPanel';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';
import { STATIONS } from '../MapConstants';

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
    isSimulationMode,
    isTvMode,
    isRecentlyUpdated,
    elapsedFormatted,
    timeoutFormatted,
    resetTimeoutClock,
    advanceToNextCall,
    dismissActiveCall,
    exitSimulation,
    toggleTvMode,
  } = kioskState;

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
            onClick={exitSimulation}
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

  // Parse responding units list (preserving exact order dispatched)
  const rawUnits =
    activeCall?.responding_units ||
    activeCall?.units ||
    activeCall?.verified_units ||
    activeCall?.raw_units ||
    [];

  const unitList = Array.isArray(rawUnits)
    ? rawUnits
    : typeof rawUnits === 'string' && rawUnits.trim().length > 0
    ? rawUnits.split(',').map((u) => u.trim()).filter(Boolean)
    : [];

  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;

  const unitEtas = unitList.map((unit) => calculateUnitEta(unit, destLat, destLng));

  const talkGroup = activeCall?.radio_channel || activeCall?.talk_group || activeCall?.talkGroup || activeCall?.tg || null;
  const rawMapGrid = activeCall?.map_grid || activeCall?.mapGrid || activeCall?.grid || null;
  const formattedGrid = rawMapGrid ? (rawMapGrid.toString().toUpperCase().startsWith('GRID') ? rawMapGrid.toString().toUpperCase() : `GRID ${rawMapGrid}`) : null;
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
            <span className="text-sm tracking-wide uppercase">
              {queuedCalls.length} New Call{queuedCalls.length > 1 ? 's' : ''} Queued — Tap to View Next
            </span>
          </div>
          <div className="bg-slate-950 text-amber-400 px-3 py-0.5 rounded text-xs font-mono">
            Next: {queuedCalls[0]?.address || 'Dispatch Alert'} →
          </div>
        </div>
      )}

      {/* Streamlined Header HUD */}
      <header className="bg-slate-900/90 border-b border-slate-800 px-6 py-3 flex items-center justify-between shadow-xl flex-shrink-0 backdrop-blur">
        {/* Left Side: Priority Badge, Dispatched Units with Live ETAs, & Talk Group */}
        <div className="flex flex-col items-start gap-1.5 text-left max-w-md">
          <div className="flex items-center gap-2">
            <div className={`px-3 py-1 rounded-lg font-black uppercase text-[11px] tracking-wider shadow ${isEmergency ? 'bg-red-600 text-white' : 'bg-emerald-600 text-white'}`}>
              {isEmergency ? '🚨 Emergency (Code 3)' : '🟢 Routine (Code 1)'}
            </div>

            {(isSimulationMode || activeCall?.isSimulated) && (
              <div className="bg-purple-950/90 border border-purple-500/80 text-purple-200 px-2.5 py-1 rounded-lg font-mono text-[10px] font-bold flex items-center gap-1 shadow animate-pulse">
                <span>🧪</span>
                <span>SIMULATED / REVIEW</span>
              </div>
            )}

            {isRecentlyUpdated && (
              <span className="bg-sky-600 text-white px-2 py-0.5 rounded font-bold text-[10px] animate-bounce">
                ⚡ UPDATED
              </span>
            )}
          </div>

          {/* Dispatched Units with Live ETAs from Home Halls */}
          {unitEtas.length > 0 ? (
            <div className="flex flex-wrap items-center gap-1.5 mt-0.5">
              {unitEtas.map((item, idx) => (
                <div
                  key={idx}
                  className="bg-slate-950 text-sky-400 border border-sky-500/50 rounded-lg px-2.5 py-1 flex items-center gap-2 shadow-sm font-mono"
                >
                  <div className="flex items-center gap-1">
                    <span className="text-xs">{item.icon}</span>
                    <span className="text-white font-black text-xs tracking-wider">{item.unit}</span>
                    <span className="text-[10px] text-slate-400 font-semibold">({item.hall})</span>
                  </div>
                  {item.etaStr && (
                    <div className="flex items-center gap-1 bg-sky-950/90 border border-sky-700/60 px-1.5 py-0.5 rounded text-[10px] font-bold text-sky-300">
                      <span>⏱️ {item.etaStr}</span>
                      <span className="text-slate-400 text-[9px]">({item.distStr})</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-1.5 mt-0.5 text-[11px] font-mono text-slate-400 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
              <span>🚒</span>
              <span>{activeCall?.tone_name || 'Radio Broadcast Assignment'}</span>
            </div>
          )}

          {/* Talk Group */}
          {talkGroup && (
            <div className="flex items-center gap-2 font-mono text-[10px] mt-0.5">
              <span className="bg-slate-950 text-amber-300 border border-slate-800 px-2 py-0.5 rounded font-bold">
                📻 {talkGroup}
              </span>
            </div>
          )}
        </div>

        {/* Center: Extra Large Address & Centered Call Type */}
        <div className="flex flex-col items-center text-center">
          <h1 className={`font-black tracking-tight text-white uppercase font-sans ${isTvMode ? 'text-4xl' : 'text-3xl'}`}>
            {activeCall.address || 'Address Unspecified'}
            {formattedGrid && (
              <span className="text-amber-400 font-mono ml-2.5">({formattedGrid})</span>
            )}
          </h1>

          {/* Centered Call Type (One size down from address, bright amber) */}
          <div className={`font-black tracking-wider uppercase font-mono mt-1 ${
            activeCall.is_test ? 'text-orange-400' : 'text-amber-400'
          } ${isTvMode ? 'text-3xl' : 'text-2xl'}`}>
            {activeCall.is_test && !(activeCall.incident_type || '').includes('*TEST*')
              ? `*TEST* ${activeCall.incident_type || 'EMERGENCY DISPATCH'}`
              : (activeCall.incident_type || 'EMERGENCY DISPATCH')}
          </div>

          {activeCall.is_test && (
            <div className="mt-1">
              <span className="bg-amber-500/20 text-amber-300 border border-amber-500/40 px-3 py-0.5 rounded-full text-[11px] font-black font-mono tracking-wider animate-pulse">
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

        {/* Right Side: Timers & Exit Controls */}
        <div className="flex items-center gap-3">
          <div className="flex flex-col items-end font-mono leading-tight">
            <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Elapsed Time</div>
            <div className="text-xl font-black text-emerald-400">{elapsedFormatted}</div>
            <div className="text-[9px] text-slate-500">
              {(isSimulationMode || activeCall?.isSimulated) ? '⏸️ Auto-Dismiss Paused' : `Auto-Dismiss in ${timeoutFormatted}`}
            </div>
          </div>

          {(isSimulationMode || activeCall?.isSimulated) ? (
            <button
              onClick={exitSimulation}
              className="bg-purple-700 hover:bg-purple-600 text-white px-3.5 py-1.5 rounded-xl text-xs font-bold transition shadow cursor-pointer border border-purple-500 flex items-center gap-1"
            >
              <span>🚪</span>
              <span>EXIT REVIEW MODE</span>
            </button>
          ) : (
            !isTvMode && (
              <button
                onClick={dismissActiveCall}
                className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 px-3.5 py-1.5 rounded-xl text-xs font-bold transition shadow cursor-pointer"
              >
                Dismiss
              </button>
            )
          )}

          <button
            onClick={toggleTvMode}
            className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-3 py-1.5 rounded-xl text-xs font-bold transition shadow cursor-pointer"
            title="Toggle TV Viewing Mode"
          >
            {isTvMode ? '📺 TV Mode' : '💻 Normal'}
          </button>
        </div>
      </header>

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
    </div>
  );
}
