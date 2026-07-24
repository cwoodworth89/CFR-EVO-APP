import React, { useState } from 'react';
import MapBoard from './components/MapBoard';
import KioskView from './components/kiosk/KioskView';
import { useKioskQueue } from './hooks/useKioskQueue';

function App() {
  const kioskState = useKioskQueue();
  const [explicitKioskMode, setExplicitKioskMode] = useState(false);

  const shouldRenderKiosk = explicitKioskMode || !!kioskState.activeCall || kioskState.isSimulationMode;

  const handleSimulateCall = (call) => {
    if (!call) return;

    const mockCall = {
      id: call.id || 'sim-' + Date.now(),
      address: call.verified_address || call.target?.address || call.address || 'Simulated Address',
      subaddress: call.target?.subaddress || '',
      intersection: call.target?.intersection || '',
      lat: call.target?.lat ?? call.lat ?? 49.27305,
      lng: call.target?.lng ?? call.lng ?? -122.88452,
      rings: call.target?.rings || call.rings || [],
      incident_type: call.verified_incident || call.incident_type || 'SIMULATED DISPATCH',
      priority_code: call.priority_code || 1,
      verify_location: call.verify_location ?? (call.confidence_score ? call.confidence_score >= 90 : true),
      map_grid: call.target?.verified_map_grid || call.target?.map_grid || '',
      radio_channel: call.target?.verified_talkgroup || call.target?.radio_channel || '',
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
      {shouldRenderKiosk ? (
        <KioskView kioskState={extendedKioskState} />
      ) : (
        <MapBoard
          onSimulateCall={handleSimulateCall}
          onLaunchKiosk={() => setExplicitKioskMode(true)}
        />
      )}
    </div>
  );
}

export default App;