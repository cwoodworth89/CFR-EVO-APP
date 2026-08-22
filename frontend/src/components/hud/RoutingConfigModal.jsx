import React from 'react';
import { APPARATUS_PROFILES } from './apparatusProfiles';

export default function RoutingConfigModal({
  isOpen,
  onClose,
  config = {},
  setConfig = () => {}
}) {
  if (!isOpen) return null;

  const currentProfile = config.apparatusProfile || 'ENGINE';

  return (
    <div className="fixed inset-0 z-[2000] bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200 select-none">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl text-white flex flex-col gap-5">
        
        {/* Header */}
        <div className="flex justify-between items-center pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <span className="text-lg">⚙️</span>
            <h2 className="font-extrabold text-base tracking-wide text-sky-400 font-mono">
              APPARATUS ROUTING & NAVIGATION CONFIGURATION
            </h2>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-white font-bold text-sm w-7 h-7 flex items-center justify-center rounded-full hover:bg-slate-800 transition cursor-pointer font-mono"
          >
            ✕
          </button>
        </div>

        {/* Form Controls */}
        <div className="flex flex-col gap-4 text-xs overflow-y-auto max-h-[70vh] pr-1">
          
          {/* Apparatus Profile Selector */}
          <div className="bg-slate-950 p-4 border border-slate-800 rounded-xl flex flex-col gap-2.5">
            <div className="font-black text-sky-400 font-mono text-[11px] flex items-center gap-1.5">
              <span>🚒 APPARATUS ROUTING PROFILE</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {APPARATUS_PROFILES.map(prof => (
                <button
                  key={prof.id}
                  type="button"
                  onClick={() => setConfig({ ...config, apparatusProfile: prof.id })}
                  className={`p-2.5 rounded-xl border text-left flex flex-col gap-0.5 transition-all cursor-pointer ${
                    currentProfile === prof.id
                      ? 'bg-sky-500/20 border-sky-500/60 text-white shadow-md'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-bold font-mono text-xs">
                    <span>{prof.icon}</span>
                    <span>{prof.name}</span>
                  </div>
                  <span className="text-[9.5px] text-slate-400">{prof.weight}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 1. CP Rail Avoidance Toggle & Threshold */}
          <div className="bg-slate-950 p-4 border border-slate-800 rounded-xl flex flex-col gap-3">
            <div className="flex justify-between items-center">
              <div>
                <div className="font-black text-amber-400 font-mono text-[11px] flex items-center gap-1.5">
                  <span>🚂 CP RAILWAY AVOIDANCE</span>
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  Route via overpasses (Mary Hill, Pinetree, Schoolhouse) to avoid train delays.
                </div>
              </div>
              <button 
                type="button"
                onClick={() => setConfig({ ...config, railroadAvoidanceEnabled: !config.railroadAvoidanceEnabled })}
                className={`px-3 py-1 rounded text-[10px] font-black border transition-all cursor-pointer font-mono ${
                  config.railroadAvoidanceEnabled 
                    ? "bg-emerald-500 text-slate-950 border-emerald-400 shadow-md" 
                    : "bg-slate-900 text-slate-400 border-slate-700"
                }`}
              >
                {config.railroadAvoidanceEnabled ? "ENABLED (ON)" : "DISABLED (OFF)"}
              </button>
            </div>

            {config.railroadAvoidanceEnabled && (
              <div className="pt-2 border-t border-slate-850/80 flex flex-col gap-1.5">
                <div className="flex justify-between text-[10px] font-mono">
                  <span className="text-slate-400">Overpass Detour Threshold Penalty</span>
                  <span className="text-sky-400 font-bold">{config.railroadThresholdMinutes || 2.5} min</span>
                </div>
                <input 
                  type="range"
                  min="0.5"
                  max="10.0"
                  step="0.5"
                  value={config.railroadThresholdMinutes || 2.5}
                  onChange={(e) => setConfig({ ...config, railroadThresholdMinutes: parseFloat(e.target.value) })}
                  className="w-full accent-sky-400 cursor-pointer"
                />
              </div>
            )}
          </div>

          {/* 2. EMTRAC Signal Preemption Settings */}
          <div className="bg-slate-950 p-4 border border-slate-800 rounded-xl flex flex-col gap-3">
            <div className="flex justify-between items-center">
              <div>
                <div className="font-black text-emerald-400 font-mono text-[11px] flex items-center gap-1.5">
                  <span>🚦 EMTRAC SIGNAL PREEMPTION</span>
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  Green-wave traffic signal priority system in Coquitlam.
                </div>
              </div>
              <button 
                type="button"
                onClick={() => setConfig({ ...config, emtracPreemptionEnabled: !config.emtracPreemptionEnabled })}
                className={`px-3 py-1 rounded text-[10px] font-black border transition-all cursor-pointer font-mono ${
                  config.emtracPreemptionEnabled 
                    ? "bg-emerald-500 text-slate-950 border-emerald-400 shadow-md" 
                    : "bg-slate-900 text-slate-400 border-slate-700"
                }`}
              >
                {config.emtracPreemptionEnabled ? "ENABLED (ON)" : "DISABLED (OFF)"}
              </button>
            </div>

            {config.emtracPreemptionEnabled && (
              <div className="pt-2 border-t border-slate-850/80 flex flex-col gap-1.5">
                <div className="flex justify-between text-[10px] font-mono">
                  <span className="text-slate-400">Peak Rush Hour Efficiency Reduction</span>
                  <span className="text-emerald-400 font-bold">{Math.round((config.emtracRushHourEfficiency ?? 0.85) * 100)}% Effective</span>
                </div>
                <input 
                  type="range"
                  min="0.2"
                  max="1.0"
                  step="0.05"
                  value={config.emtracRushHourEfficiency ?? 0.85}
                  onChange={(e) => setConfig({ ...config, emtracRushHourEfficiency: parseFloat(e.target.value) })}
                  className="w-full accent-emerald-400 cursor-pointer"
                />
              </div>
            )}
          </div>

          {/* 3. Steep Elevation Physics Toggle */}
          <div className="bg-slate-950 p-4 border border-slate-800 rounded-xl flex justify-between items-center">
            <div>
              <div className="font-black text-sky-400 font-mono text-[11px] flex items-center gap-1.5">
                <span>⛰️ STEEP ELEVATION DRAG PHYSICS</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                Applies incline friction on Burke Mountain, Westwood Plateau & Mariner Way.
              </div>
            </div>
            <button 
              type="button"
              onClick={() => setConfig({ ...config, elevationPhysicsEnabled: !config.elevationPhysicsEnabled })}
              className={`px-3 py-1 rounded text-[10px] font-black border transition-all cursor-pointer font-mono ${
                config.elevationPhysicsEnabled 
                  ? "bg-emerald-500 text-slate-950 border-emerald-400 shadow-md" 
                  : "bg-slate-900 text-slate-400 border-slate-700"
              }`}
            >
              {config.elevationPhysicsEnabled ? "ENABLED (ON)" : "DISABLED (OFF)"}
            </button>
          </div>

        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-slate-800 flex justify-end">
          <button 
            type="button"
            onClick={onClose}
            className="bg-sky-500 hover:bg-sky-400 text-slate-950 font-extrabold py-2 px-6 rounded-xl text-xs transition cursor-pointer shadow-md font-mono"
          >
            APPLY & CLOSE
          </button>
        </div>

      </div>
    </div>
  );
}
