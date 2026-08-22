import React, { useState, Suspense, lazy } from 'react';
import { useKioskQueue } from './hooks/useKioskQueue';
import { toActiveCall } from './utils/dispatchModel';

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

  const shouldRenderKiosk = explicitKioskMode || !!kioskState.activeCall || kioskState.isReviewMode;

  // Replay a real historical dispatch in Kiosk view exactly as it was received.
  //
  // No data is invented here: toActiveCall passes every field through from the database
  // record, and unresolved coordinates stay null so the kiosk renders the Tier 1 warning
  // instead of routing to a guessed location (CLAUDE.md §5).
  //
  // This used to be a thirty-line field-by-field translation living here, one of three
  // that disagreed with each other. It is now the same function the live MQTT path uses,
  // so a review replay and a live call reach the kiosk in exactly the same shape.
  const handleReviewCall = (call) => {
    if (!call) return;
    setReturnMode('ADMIN_DISPATCHES');
    kioskState.triggerReviewCall({ ...toActiveCall(call), isReview: true });
  };

  const extendedKioskState = {
    ...kioskState,
    exitReview: () => {
      kioskState.exitReview();
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
            onReviewCall={handleReviewCall}
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