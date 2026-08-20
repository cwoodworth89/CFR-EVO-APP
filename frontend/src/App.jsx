import React, { useState, Suspense, lazy } from 'react';
import { useKioskQueue } from './hooks/useKioskQueue';

// Code-split primary views to optimize kiosk initial bundle size and memory profile
const MapBoard = lazy(() => import('./components/MapBoard'));
const KioskView = lazy(() => import('./components/kiosk/KioskView'));

const ViewLoadingFallback = () => (
  <div className="w-screen h-screen bg-slate-950 flex items-center justify-center text-slate-400 font-mono text-sm select-none">
    <div className="flex flex-col items-center gap-3 bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-2xl">
      <div className="w-10 h-10 rounded-full border-2 border-sky-400 border-t-transparent animate-spin"></div>
      <span className="text-xs font-bold uppercase tracking-widest text-sky-400">Loading CFR EVO Station Console...</span>
    </div>
  </div>
);

function App() {
  const kioskState = useKioskQueue();
  const [explicitKioskMode, setExplicitKioskMode] = useState(false);
  const [returnMode, setReturnMode] = useState('EXPLORE');

  const shouldRenderKiosk = explicitKioskMode || !!kioskState.activeCall || kioskState.isSimulationMode;

  const handleSimulateCall = (call) => {
    if (!call) return;

    // Track that we originated from Admin Dispatch Review panel
    setReturnMode('ADMIN_DISPATCHES');

    const targetAddr = (call.verified_address || call.target?.address || call.address || '').toUpperCase();
    let fallbackLat = 49.2838;
    let fallbackLng = -122.7907;

    if (targetAddr.includes('CHRISTMAS') && targetAddr.includes('WESTWOOD')) {
      fallbackLat = 49.2783;
      fallbackLng = -122.7935;
    }

    const units = (call.verified_units && call.verified_units.length > 0)
      ? call.verified_units
      : (call.responding_units && call.responding_units.length > 0 ? call.responding_units : []);

    const mockCall = {
      id: call.id || 'sim-' + Date.now(),
      dispatch_id: call.dispatch_id || ('DISP-SIM-' + Date.now()),
      address: call.verified_address || call.target?.address || call.address || 'Simulated Address',
      subaddress: call.target?.subaddress || '',
      intersection: call.target?.intersection || '',
      lat: call.target?.lat ?? call.lat ?? fallbackLat,
      lng: call.target?.lng ?? call.lng ?? fallbackLng,
      rings: call.target?.rings || call.rings || [],
      incident_type: call.verified_incident || call.incident_type || 'SIMULATED DISPATCH',
      responding_units: units,
      priority_code: call.priority_code || 1,
      verify_location: call.verify_location ?? (call.confidence_score ? call.confidence_score >= 90 : true),
      map_grid: call.target?.verified_map_grid || call.target?.map_grid || '',
      radio_channel: call.target?.verified_talkgroup || call.target?.radio_channel || '10 Combined Response',
      tone_name: call.target?.tone_name || '',
      isSimulated: true,
      created_at: new Date().toISOString()
    };

    kioskState.triggerSimulationCall(mockCall);
  };

  const extendedKioskState = {
    ...kioskState,
    exitSimulation: () => {
      kioskState.exitSimulation();
      setExplicitKioskMode(false);
    }
  };

  return (
    <div className="App w-screen h-screen overflow-hidden bg-slate-950 text-slate-100 relative">
      <Suspense fallback={<ViewLoadingFallback />}>
        {shouldRenderKiosk ? (
          <KioskView kioskState={extendedKioskState} />
        ) : (
          <MapBoard
            initialMode={returnMode}
            onSimulateCall={handleSimulateCall}
            onLaunchKiosk={() => {
              setReturnMode('EXPLORE');
              setExplicitKioskMode(true);
            }}
          />
        )}
      </Suspense>
    </div>
  );
}

export default App;