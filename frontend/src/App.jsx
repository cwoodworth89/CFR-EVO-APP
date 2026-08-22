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

  const shouldRenderKiosk = explicitKioskMode || !!kioskState.activeCall || kioskState.isReviewMode;

  // Replay a real historical dispatch in Kiosk view exactly as it was received.
  // No data is invented here: every field is passed through from the database record,
  // and unresolved coordinates stay null so the kiosk renders the Tier 1 warning
  // instead of routing to a guessed location (see CLAUDE.md §5).
  const handleReviewCall = (call) => {
    if (!call) return;

    // Track that we originated from Admin Dispatch Review panel
    setReturnMode('ADMIN_DISPATCHES');

    const units = (call.verified_units && call.verified_units.length > 0)
      ? call.verified_units
      : (call.responding_units && call.responding_units.length > 0 ? call.responding_units : []);

    const reviewCall = {
      ...call,
      id: call.id,
      dispatch_id: call.dispatch_id,
      address: call.verified_address || call.target?.address || call.address || null,
      subaddress: call.target?.subaddress || '',
      intersection: call.target?.intersection || '',
      lat: call.target?.lat ?? call.lat ?? null,
      lng: call.target?.lng ?? call.lng ?? null,
      rings: call.target?.rings || call.rings || [],
      // Street-section fields. A "<street> and <street>" dispatch has no point location;
      // these drive the amber section banner and the highlighted polyline. Dropping them
      // would make the section's representative midpoint look like an exact match.
      location_type: call.target?.location_type || null,
      segment: call.target?.segment || null,
      endpoints: call.target?.endpoints || null,
      length_m: call.target?.length_m ?? null,
      street: call.target?.street || null,
      resolution_note: call.target?.resolution_note || null,
      incident_type: call.verified_incident || call.incident_type || null,
      responding_units: units,
      priority_code: call.priority_code,
      verify_location: call.verify_location ?? (call.confidence_score ? call.confidence_score >= 90 : true),
      map_grid: call.target?.verified_map_grid || call.target?.map_grid || '',
      radio_channel: call.target?.verified_talkgroup || call.target?.radio_channel || '',
      tone_name: call.target?.tone_name || '',
      isReview: true
    };

    kioskState.triggerReviewCall(reviewCall);
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