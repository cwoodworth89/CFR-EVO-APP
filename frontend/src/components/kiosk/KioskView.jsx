import React from 'react';
import RouteOverviewPanel from './RouteOverviewPanel';
import BlockParcelPanel from './BlockParcelPanel';
import PropertySatellitePanel from './PropertySatellitePanel';
import StreetViewPanel from './StreetViewPanel';

export default function KioskView({ kioskState }) {
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

  if (!activeCall) {
    return (
      <div className="fixed inset-0 bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 z-50">
        <div className="flex flex-col items-center gap-4 text-center max-w-md">
          <div className="w-20 h-20 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-4xl shadow-inner">
            🚒
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Coquitlam Fire Rescue Kiosk</h1>
          <p className="text-sm text-slate-400 font-medium">In-Station Dispatch Monitor Active • Listening for Database Events...</p>
          <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-3 py-1.5 rounded-full">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            <span>DB Real-Time Sync: Connected</span>
          </div>

          {isSimulationMode && (
            <button
              onClick={exitSimulation}
              className="mt-4 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl font-semibold text-xs transition shadow-lg"
            >
              Exit Simulation Mode
            </button>
          )}
        </div>
      </div>
    );
  }

  // Priority classification for border
  const isEmergency =
    activeCall.priority_code <= 2 ||
    String(activeCall.priority_code).toLowerCase() === 'emergency' ||
    String(activeCall.response_type).toLowerCase() === 'emergency';

  const borderColor = isEmergency ? 'border-red-600' : 'border-emerald-500';

  return (
    <div
      onClick={resetTimeoutClock}
      className={`fixed inset-0 bg-slate-950 text-slate-100 flex flex-col z-50 select-none border-8 ${borderColor} transition-colors duration-500 overflow-hidden`}
    >
      {/* Queued Call Notification Banner */}
      {queuedCalls.length > 0 && (
        <div
          onClick={advanceToNextCall}
          className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-6 py-2.5 flex items-center justify-between cursor-pointer animate-pulse shadow-xl border-b border-amber-600 z-50"
        >
          <div className="flex items-center gap-3">
            <span className="text-xl">⚠️</span>
            <span className="text-base tracking-wide uppercase">
              {queuedCalls.length} New Call{queuedCalls.length > 1 ? 's' : ''} Queued — Tap to View Next
            </span>
          </div>
          <div className="bg-slate-950 text-amber-400 px-3 py-1 rounded-lg text-xs font-mono">
            Next: {queuedCalls[0]?.address || 'Dispatch Alert'} →
          </div>
        </div>
      )}

      {/* Header Banner */}
      <header className="bg-slate-900/95 border-b border-slate-800 px-6 py-4 flex items-center justify-between shadow-2xl backdrop-blur">
        {/* Left Status Badges */}
        <div className="flex items-center gap-3">
          <div className={`px-4 py-1.5 rounded-xl font-bold uppercase text-xs tracking-wider shadow ${isEmergency ? 'bg-red-600 text-white' : 'bg-emerald-600 text-white'}`}>
            {isEmergency ? '🚨 Emergency (Code 3)' : '🟢 Routine (Code 1)'}
          </div>

          {!activeCall.verify_location && (
            <div className="bg-amber-950/80 border border-amber-600/80 text-amber-300 px-3 py-1.5 rounded-xl font-mono text-xs font-bold flex items-center gap-1.5 animate-pulse">
              <span>⚠️</span>
              <span>UNVERIFIED LOCATION - PHASE 1</span>
            </div>
          )}

          {isRecentlyUpdated && (
            <div className="bg-sky-600 text-white px-3 py-1.5 rounded-xl font-mono text-xs font-bold flex items-center gap-1.5 animate-bounce shadow-lg">
              <span>⚡</span>
              <span>LOCATION VERIFIED / CALL UPDATED</span>
            </div>
          )}
        </div>

        {/* Center Prominent Address */}
        <div className="flex flex-col items-center text-center">
          <h1 className={`font-black tracking-tight text-white uppercase font-sans ${isTvMode ? 'text-4xl' : 'text-3xl'}`}>
            {activeCall.address || 'Address Unspecified'}
          </h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-base font-bold text-amber-400 tracking-wide uppercase font-mono">
              {activeCall.incident_type || 'EMERGENCY DISPATCH'}
            </span>
            {activeCall.subaddress && (
              <span className="bg-slate-800 text-sky-300 border border-slate-700 px-2 py-0.5 rounded text-xs font-semibold">
                🏢 {activeCall.subaddress}
              </span>
            )}
            {activeCall.intersection && (
              <span className="bg-slate-800 text-amber-300 border border-slate-700 px-2 py-0.5 rounded text-xs font-semibold">
                🔀 {activeCall.intersection}
              </span>
            )}
          </div>
        </div>

        {/* Right Timers & Controls */}
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end font-mono">
            <div className="text-xs text-slate-400 font-bold uppercase tracking-wider">Elapsed Time</div>
            <div className="text-2xl font-black text-emerald-400">{elapsedFormatted}</div>
            <div className="text-[10px] text-slate-500">Auto-Dismiss in {timeoutFormatted}</div>
          </div>

          {!isTvMode && (
            <button
              onClick={dismissActiveCall}
              className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 px-4 py-2 rounded-xl text-xs font-bold transition shadow"
            >
              Dismiss
            </button>
          )}

          <button
            onClick={toggleTvMode}
            className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-3 py-2 rounded-xl text-xs font-bold transition shadow"
            title="Toggle TV Viewing Mode"
          >
            {isTvMode ? '📺 TV Mode (Active)' : '💻 Normal Mode'}
          </button>

          {isSimulationMode && (
            <button
              onClick={exitSimulation}
              className="bg-rose-600 hover:bg-rose-700 text-white px-3 py-2 rounded-xl text-xs font-bold transition shadow"
            >
              Exit Simulation
            </button>
          )}
        </div>
      </header>

      {/* Main Content Layout (2/3 Route Map, 1/3 Multi-Detail Stack) */}
      <main className="flex-1 p-4 grid grid-cols-12 gap-4 overflow-hidden">
        {/* Left ~2/3 Suggested Route Panel */}
        <section className="col-span-8 h-full">
          <RouteOverviewPanel activeCall={activeCall} />
        </section>

        {/* Right ~1/3 Multi-Detail Stack (Parcel, Satellite, StreetView) */}
        <section className="col-span-4 h-full grid grid-rows-3 gap-4">
          <div className="row-span-1 h-full">
            <BlockParcelPanel activeCall={activeCall} />
          </div>
          <div className="row-span-1 h-full">
            <PropertySatellitePanel activeCall={activeCall} />
          </div>
          <div className="row-span-1 h-full">
            <StreetViewPanel activeCall={activeCall} />
          </div>
        </section>
      </main>
    </div>
  );
}
