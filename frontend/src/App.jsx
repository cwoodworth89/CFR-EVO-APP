import React, { useState } from 'react';
import MapBoard from './components/MapBoard';
import KioskView from './components/kiosk/KioskView';
import SimulationControl from './components/admin/SimulationControl';
import { useKioskQueue } from './hooks/useKioskQueue';

function App() {
  const kioskState = useKioskQueue();
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [forceKioskMode, setForceKioskMode] = useState(false);

  const shouldRenderKiosk = forceKioskMode || !!kioskState.activeCall || kioskState.isSimulationMode;

  return (
    <div className="App w-screen h-screen overflow-hidden bg-slate-950 text-slate-100 relative">
      {/* Kiosk Mode Display */}
      {shouldRenderKiosk ? (
        <KioskView kioskState={kioskState} />
      ) : (
        /* Standard MapBoard Dashboard */
        <MapBoard />
      )}

      {/* Admin Simulation & Mode Toolbar (Floating Top-Right) */}
      <div className="fixed top-4 right-4 z-[9999] flex items-center gap-2">
        <button
          onClick={() => setForceKioskMode((prev) => !prev)}
          className="bg-slate-900/90 hover:bg-slate-800 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-bold shadow-lg backdrop-blur flex items-center gap-1.5"
        >
          <span>🖥️</span>
          <span>{forceKioskMode ? 'Exit Kiosk View' : 'Launch Kiosk View'}</span>
        </button>

        <button
          onClick={() => setShowAdminPanel((prev) => !prev)}
          className="bg-slate-900/90 hover:bg-slate-800 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-bold shadow-lg backdrop-blur flex items-center gap-1.5"
        >
          <span>⚙️</span>
          <span>Admin Simulation</span>
        </button>
      </div>

      {/* Admin Simulation Drawer Modal */}
      {showAdminPanel && (
        <div className="fixed bottom-6 right-6 z-[99999] max-w-lg">
          <SimulationControl
            onRunSimulation={kioskState.triggerSimulationCall}
            onUpdateSimulation={kioskState.triggerSimulationUpdate}
            onExitSimulation={kioskState.exitSimulation}
            isSimulationActive={kioskState.isSimulationMode}
          />
        </div>
      )}
    </div>
  );
}

export default App;