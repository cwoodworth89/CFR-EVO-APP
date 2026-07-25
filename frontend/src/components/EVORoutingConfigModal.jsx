import React from 'react';

export default function EVORoutingConfigModal({ isOpen, onClose, config, setConfig }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[2000] bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200 select-none">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl text-white flex flex-col gap-5">
        
        {/* Header */}
        <div className="flex justify-between items-center pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <span className="text-lg">⚙️</span>
            <h2 className="font-extrabold text-base tracking-wide text-sky-400 font-mono">
              EVO ROUTING ENGINE CONFIGURATION
            </h2>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-white font-bold text-sm w-7 h-7 flex items-center justify-center rounded-full hover:bg-slate-800 transition cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Form Controls */}
        <div className="flex flex-col gap-4 text-xs">
          
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
                onClick={() => setConfig({ ...config, railroadAvoidanceEnabled: !config.railroadAvoidanceEnabled })}
                className={`px-3 py-1 rounded text-[10px] font-black border transition-all cursor-pointer ${
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
                  <span className="text-sky-400 font-bold">{config.railroadThresholdMinutes} min</span>
                </div>
                <input 
                  type="range"
                  min="0.5"
                  max="10.0"
                  step="0.5"
                  value={config.railroadThresholdMinutes}
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
                onClick={() => setConfig({ ...config, emtracPreemptionEnabled: !config.emtracPreemptionEnabled })}
                className={`px-3 py-1 rounded text-[10px] font-black border transition-all cursor-pointer ${
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
                  <span className="text-emerald-400 font-bold">{Math.round(config.emtracRushHourEfficiency * 100)}% Effective</span>
                </div>
                <input 
                  type="range"
                  min="0.2"
                  max="1.0"
                  step="0.05"
                  value={config.emtracRushHourEfficiency}
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
              onClick={() => setConfig({ ...config, elevationPhysicsEnabled: !config.elevationPhysicsEnabled })}
              className={`px-3 py-1 rounded text-[10px] font-black border transition-all cursor-pointer ${
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
            onClick={onClose}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold py-2 px-6 rounded-xl text-xs transition cursor-pointer shadow-md"
          >
            APPLY & CLOSE
          </button>
        </div>

      </div>
    </div>
  );
}
