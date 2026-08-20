import React from 'react';

export default function SimulationControl({ onRunSimulation, onUpdateSimulation, onExitSimulation, isSimulationActive }) {
  const samplePhase1Call = {
    id: 'sim-' + Date.now(),
    dispatch_id: 'DISP-SIM-001',
    address: '428 Nelson St',
    subaddress: 'Apt 302',
    intersection: 'Nelson St & Austin Ave',
    lat: 49.24804,
    lng: -122.86546,
    responding_units: ['E3', 'Q5'],
    incident_type: 'STRUCTURE FIRE - FIRST ALARM',
    priority_code: 1,
    verify_location: false,
    map_grid: 'H-12',
    radio_channel: '10 Combined Response',
    tone_name: 'Station 3 Tones',
    created_at: new Date().toISOString()
  };

  const samplePhase2Update = {
    id: samplePhase1Call.id,
    dispatch_id: samplePhase1Call.dispatch_id,
    address: '428 Nelson St',
    subaddress: 'Apt 302',
    intersection: 'Nelson St & Austin Ave',
    lat: 49.24804,
    lng: -122.86546,
    responding_units: ['E3', 'Q5'],
    incident_type: 'STRUCTURE FIRE - VERIFIED',
    priority_code: 1,
    verify_location: true,
    map_grid: 'H-12',
    radio_channel: '10 Combined Response',
    created_at: new Date().toISOString()
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 text-slate-100 shadow-xl flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">🚀</span>
          <h2 className="text-base font-bold text-white">Kiosk Dispatch Simulation Harness</h2>
        </div>
        {isSimulationActive && (
          <span className="bg-amber-950 text-amber-300 border border-amber-800 px-2.5 py-0.5 rounded-full text-xs font-mono font-bold animate-pulse">
            Simulation Active
          </span>
        )}
      </div>

      <p className="text-xs text-slate-400">
        Inject simulated Phase 1 & Phase 2 dispatch database entries to test Kiosk Call Summary mode, queuing, and real-time UPDATE triggers on demand.
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={() => onRunSimulation(samplePhase1Call)}
          className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-xl text-xs font-bold transition shadow flex items-center gap-2"
        >
          <span>▶️</span>
          <span>Run Simulation (Phase 1 Alert)</span>
        </button>

        <button
          onClick={() => onUpdateSimulation(samplePhase2Update)}
          className="bg-sky-600 hover:bg-sky-500 text-white px-4 py-2 rounded-xl text-xs font-bold transition shadow flex items-center gap-2"
        >
          <span>⚡</span>
          <span>Trigger UPDATE Event (Phase 2)</span>
        </button>

        {isSimulationActive && (
          <button
            onClick={onExitSimulation}
            className="bg-rose-600 hover:bg-rose-500 text-white px-4 py-2 rounded-xl text-xs font-bold transition shadow flex items-center gap-2"
          >
            <span>⏹️</span>
            <span>Exit Simulation</span>
          </button>
        )}
      </div>
    </div>
  );
}
