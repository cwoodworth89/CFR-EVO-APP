import React from 'react';

/**
 * Floating controls layered over the map: zoom readout, reset-view, re-centre-on-route,
 * and the build watermark.
 *
 * Extracted from MapBoard.jsx. These sit outside `<MapContainer>` as absolutely positioned
 * chrome, so they are not Leaflet layers — but they were interleaved with the layer JSX,
 * which made the container's render harder to read than it needed to be.
 *
 * The default view itself belongs to useMapInstance, which owns `isOffDefault` and knows
 * the centre and zoom that flag is measured against. This component had its own copy of
 * the reset, with the centre and zoom written out a second time, so "the default view"
 * had two definitions that nothing kept in step.
 */

function ZoomBadge({ currentZoom }) {
  return (
    <div className="pointer-events-none select-none px-2.5 py-1 rounded-lg bg-slate-950/90 border border-slate-800/80 text-[10px] font-mono text-slate-400 backdrop-blur-md shadow-lg flex items-center gap-2">
      <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">ZOOM</span>
      <span className="font-extrabold text-amber-400 font-mono text-xs">
        {typeof currentZoom === 'number' ? currentZoom.toFixed(1) : currentZoom}
      </span>
    </div>
  );
}

export default function MapViewControls({
  map,
  currentZoom,
  isOffDefault,
  userPanned,
  setUserPanned,
  targetAddress,
  targetCoords,
  homeStation,
  buildTime,
  mapStyle,
  setMapStyle,
  defaultMapStyle,
  resetView: resetMapView,
}) {
  // The basemap is part of "the view" (operator, 2026-09-08): leaving the aerial layer on
  // after a reset meant the map came back to the default position but not the default
  // picture, so the button only half did what it says. defaultMapStyle comes from
  // MODE_DEFAULTS.EXPLORE, the same value the sidebar's "Street Map" button sets, so there
  // is one definition of the default rather than a second copy here.
  const styleIsOffDefault = Boolean(defaultMapStyle) && mapStyle !== defaultMapStyle;

  const resetView = () => {
    if (styleIsOffDefault && setMapStyle) setMapStyle(defaultMapStyle);
    if (resetMapView) resetMapView();
  };

  const recentreOnRoute = () => {
    setUserPanned(false);
    if (map && targetCoords && homeStation) {
      map.fitBounds([homeStation, targetCoords], {
        // Asymmetric padding: the left sidebar and the right inspection stack both overlay
        // the map, so an evenly padded fit would tuck the route under them.
        paddingTopLeft: [340, 80],
        paddingBottomRight: [400, 80],
        animate: true,
      });
    }
  };

  return (
    <>
      <div className="absolute top-3 right-3 z-[1000] flex flex-col items-end gap-2">
        <ZoomBadge currentZoom={currentZoom} />

        {(isOffDefault || styleIsOffDefault) && (
          <button
            onClick={resetView}
            title={styleIsOffDefault
              ? 'Reset view to Coquitlam City Center (Zoom 12) and back to the street basemap'
              : 'Reset view to Coquitlam City Center (Zoom 12)'}
            className="px-3 py-1.5 rounded-lg bg-slate-950/90 hover:bg-slate-900 border border-slate-800 hover:border-cyan-500/60 text-slate-200 hover:text-cyan-300 text-xs font-semibold shadow-xl backdrop-blur-md transition-all duration-200 flex items-center gap-1.5 cursor-pointer active:scale-95 group animate-in fade-in slide-in-from-top-1 duration-200"
          >
            <svg className="w-3.5 h-3.5 text-cyan-400 group-hover:rotate-180 transition-transform duration-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>Reset View</span>
          </button>
        )}
      </div>

      {userPanned && targetAddress && (
        <button
          onClick={recentreOnRoute}
          className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1100] bg-slate-900/95 hover:bg-slate-800 text-sky-400 font-extrabold text-xs px-4.5 py-2.5 rounded-full border border-sky-500/60 shadow-2xl flex items-center gap-2 transition-all cursor-pointer animate-in fade-in slide-in-from-bottom-3 duration-200"
        >
          <span className="animate-pulse">🎯</span>
          <span>RE-CENTER ON ROUTE</span>
        </button>
      )}

      <div className="absolute bottom-3 left-3 z-[1000] pointer-events-none font-mono text-[9px] text-slate-400/85 drop-shadow-sm select-none">
        CFR EVO APP | BUILD: {buildTime} | LICENSE: POLYFORM NONCOMMERCIAL 1.0.0
      </div>
    </>
  );
}
