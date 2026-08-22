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

/**
 * The two things this app can be showing.
 *
 * DISPATCH is entered by any of three routes, which is why it was previously three
 * booleans OR'd together at the point of use: a live call arrives, a historical call is
 * replayed for review, or the operator opens the kiosk deliberately from the console.
 */
// Not exported: App.jsx also exports a component, and a non-component export here trips
// react-refresh/only-export-components. Move this to its own module when a second file
// needs it.
const MODE = {
  STANDBY: 'STANDBY',   // console: map, layer controls, search
  DISPATCH: 'DISPATCH', // kiosk: active or replayed incident
};

function App() {
  const kioskState = useKioskQueue();
  const [explicitKioskMode, setExplicitKioskMode] = useState(false);
  const [returnMode, setReturnMode] = useState('EXPLORE');

  const mode = (explicitKioskMode || kioskState.activeCall || kioskState.isReviewMode)
    ? MODE.DISPATCH
    : MODE.STANDBY;

  // A live call interrupting a review sends the operator back to the MAP when it is
  // dismissed, not to the admin panel the review was launched from.
  //
  // Starting a review sets returnMode to ADMIN_DISPATCHES so closing the replay returns
  // to the list being worked through. But once a real dispatch has taken over, that
  // context is gone: the crew responded to an incident, and dropping them into a review
  // table afterwards is wrong. Decided 2026-08-22.
  //
  // Synced during render rather than in an effect: an effect renders the stale mode once
  // before correcting itself, which is a visible flash of the admin panel.
  const activeIsLive = !!kioskState.activeCall && !kioskState.activeCall.isReview;
  if (activeIsLive && returnMode !== 'EXPLORE') {
    setReturnMode('EXPLORE');
  }

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
        {mode === MODE.DISPATCH ? (
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