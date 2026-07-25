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
      <div className="fixed inset-0 bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 z-50 select-none">
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
        {/* Left Side: Status Badges */}
        <div className="flex flex-col gap-1.5 items-start">
          <div className="flex items-center gap-2">
            <div className={`px-3 py-1 rounded-lg font-black uppercase text-[11px] tracking-wider shadow ${isEmergency ? 'bg-red-600 text-white' : 'bg-emerald-600 text-white'}`}>
              {isEmergency ? '🚨 Emergency (Code 3)' : '🟢 Routine (Code 1)'}
            </div>

            {(isSimulationMode || activeCall?.isSimulated) && (
              <div className="bg-purple-950/90 border border-purple-500/80 text-purple-200 px-2.5 py-1 rounded-lg font-mono text-[10px] font-bold flex items-center gap-1 shadow animate-pulse">
                <span>🧪</span>
                <span>SIMULATED CALL</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            {!activeCall.verify_location && (
              <div className="bg-amber-950/80 border border-amber-600/80 text-amber-300 px-2.5 py-0.5 rounded font-mono text-[10px] font-bold flex items-center gap-1 animate-pulse">
                <span>⚠️</span>
                <span>UNVERIFIED LOCATION - PHASE 1</span>
              </div>
            )}

            {isRecentlyUpdated && (
              <div className="bg-sky-600 text-white px-2.5 py-0.5 rounded font-mono text-[10px] font-bold flex items-center gap-1 animate-bounce shadow">
                <span>⚡</span>
                <span>CALL UPDATED</span>
              </div>
            )}
          </div>
        </div>

        {/* Center: Extra Large Address & Subheader */}
        <div className="flex flex-col items-center text-center">
          <h1 className={`font-black tracking-tight text-white uppercase font-sans ${isTvMode ? 'text-4xl' : 'text-3xl'}`}>
            {activeCall.address || 'Address Unspecified'}
          </h1>
          <div className="flex items-center gap-2.5 mt-0.5">
            <span className="text-sm font-black text-amber-400 tracking-wider uppercase font-mono">
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

        {/* Right Side: Timers & Exit Controls */}
        <div className="flex items-center gap-3">
          <div className="flex flex-col items-end font-mono leading-tight">
            <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Elapsed Time</div>
            <div className="text-xl font-black text-emerald-400">{elapsedFormatted}</div>
            <div className="text-[9px] text-slate-500">Auto-Dismiss in {timeoutFormatted}</div>
          </div>

          {(isSimulationMode || activeCall?.isSimulated) ? (
            <button
              onClick={exitSimulation}
              className="bg-purple-700 hover:bg-purple-600 text-white px-3.5 py-1.5 rounded-xl text-xs font-bold transition shadow cursor-pointer border border-purple-500 flex items-center gap-1"
            >
              <span>🚪</span>
              <span>EXIT SIMULATION</span>
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
