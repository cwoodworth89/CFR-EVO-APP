import React from 'react';

// Unit styling for 10-foot high-visibility apparatus bay ergonomics
export const getUnitBadgeStyle = (unitStr) => {
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

export const getShortCallsign = (unitStr) => {
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

export const formatUnitEtaDisplay = (etaMin) => {
  if (etaMin == null || isNaN(etaMin)) return '02:30';
  const totalSec = Math.round(etaMin * 60);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  const padM = String(mins).padStart(2, '0');
  const padS = String(secs).padStart(2, '0');
  return `${padM}:${padS}`;
};

export default function ActiveAlertBanner({
  activeCall,
  unitEtas = [],
  unitList = [],
  talkGroup = null,
  formattedGrid = null,
  displayAddress = '',
  displayIncident = '',
  isEmergency = true,
  isSimulationMode = false,
  isRecentlyUpdated = false,
  isTvMode = false,
  elapsedFormatted = '00:00',
  timeoutFormatted = '03:00',
  onDismiss = null,
  onExitSimulation = null,
  onToggleTvMode = null,
  onOpenPrePlan = null,
}) {
  if (!activeCall) return null;

  return (
    <header className="bg-slate-900/90 border-b border-slate-800 px-6 py-3 flex items-center justify-between shadow-xl flex-shrink-0 backdrop-blur z-20">
      {/* Left: Priority Code, Responding Units with Live ETAs, Talk Group & Pre-Plan */}
      <div className="flex flex-col items-start gap-1.5 text-left max-w-md">
        <div className="flex items-center gap-2">
          <div className={`px-3 py-1 rounded-lg font-black uppercase text-[11px] tracking-wider shadow ${
            isEmergency ? 'bg-red-600 text-white animate-pulse' : 'bg-emerald-600 text-white'
          }`}>
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
          <div className="bg-slate-950/90 text-sky-400 border border-sky-800/80 px-2.5 py-1 rounded-lg flex items-center gap-1.5 shadow-sm">
            <span>💧</span>
            <span className="font-bold text-white">City Hydrant:</span>
            <span className="text-sky-300 font-black">{activeCall?.target?.nearest_city_hydrant || activeCall?.nearest_city_hydrant || 'D-163'}</span>
            <span className="text-slate-400">({activeCall?.target?.nearest_city_dist || activeCall?.nearest_city_dist || '42'}m)</span>
          </div>
          {(activeCall?.target?.pre_plan_pdf_url || activeCall?.pre_plan_pdf_url) && onOpenPrePlan && (
            <button
              type="button"
              onClick={onOpenPrePlan}
              className="bg-sky-950/90 hover:bg-sky-900 text-sky-300 hover:text-white border border-sky-600 px-3 py-1 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 shadow-md animate-pulse cursor-pointer"
              title="Open Pre-Incident Construction Plan PDF"
            >
              <span>📄</span>
              <span>Pre-Incident Plan</span>
            </button>
          )}
        </div>
      </div>

      {/* Center: Extra Large Address & Centered Incident Type */}
      <div className="flex flex-col items-center text-center px-4">
        <h1 className={`font-black tracking-tight text-white uppercase font-sans ${isTvMode ? 'text-4xl sm:text-5xl' : 'text-3xl sm:text-4xl'}`}>
          {displayAddress}
          {formattedGrid && (
            <span className="text-amber-400 font-mono ml-2.5">({formattedGrid})</span>
          )}
        </h1>

        <div className={`font-black tracking-wider uppercase font-mono mt-1 ${
          activeCall.is_test ? 'text-orange-400' : 'text-amber-400'
        } ${isTvMode ? 'text-2xl sm:text-3xl' : 'text-xl sm:text-2xl'}`}>
          {displayIncident}
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

      {/* Right: Elapsed Time, Auto-Dismiss Countdown & Exit Controls */}
      <div className="flex items-center gap-3">
        <div className="flex flex-col items-end font-mono leading-tight">
          <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Elapsed Time</div>
          <div className="text-xl font-black text-emerald-400">{elapsedFormatted}</div>
          <div className="text-[9px] text-slate-500">
            {(isSimulationMode || activeCall?.isSimulated) ? '⏸️ Auto-Dismiss Paused' : `Auto-Dismiss in ${timeoutFormatted}`}
          </div>
        </div>

        {(isSimulationMode || activeCall?.isSimulated) ? (
          onExitSimulation && (
            <button
              type="button"
              onClick={onExitSimulation}
              className="bg-purple-700 hover:bg-purple-600 text-white px-3.5 py-1.5 rounded-xl text-xs font-bold transition shadow cursor-pointer border border-purple-500 flex items-center gap-1 font-mono"
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
              className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 px-3.5 py-1.5 rounded-xl text-xs font-bold transition shadow cursor-pointer font-mono"
            >
              Dismiss
            </button>
          )
        )}

        {onToggleTvMode && (
          <button
            type="button"
            onClick={onToggleTvMode}
            className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-3 py-1.5 rounded-xl text-xs font-bold transition shadow cursor-pointer font-mono"
            title="Toggle TV Viewing Mode"
          >
            {isTvMode ? '📺 TV Mode' : '💻 Normal'}
          </button>
        )}
      </div>
    </header>
  );
}
