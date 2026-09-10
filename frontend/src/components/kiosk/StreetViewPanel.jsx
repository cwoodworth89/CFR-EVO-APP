import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';
import { useAdminSession } from '../../hooks/useAdminSession';
import { useStreetViewPanorama } from '../../hooks/useStreetViewPanorama';
import { sanitizeAddress } from '../../utils/addressUtils';
import { apiClient } from '../../apiClient';
import {
  savedViewFromParcel, defaultViewForCall, staticStreetViewUrl, embedStreetViewUrl,
} from '../../utils/streetViewGeometry';
import TileFrame from './TileFrame';

/**
 * THE ONE ONLINE-DEPENDENT SURFACE IN AN OFFLINE-FIRST SYSTEM.
 *
 * CLAUDE.md §1 requires the whole system to work with no WAN. This panel does not, and
 * cannot: Google Street View panoramas are fetched live from maps.googleapis.com and are
 * not licensed for local caching the way the municipal orthophotos are
 * (docs/standards/google-maps-platform-terms-excerpts.md).
 *
 * ACCEPTED RISK, operator decision 2026-08-30. Street View is a pre-arrival convenience --
 * a look at the front of the building -- not a dispatch-critical surface. Everything a crew
 * needs to be dispatched and routed is served locally and is unaffected when this is blank.
 *
 * HOW IT IS BUILT (hardened 2026-09-08, after the #35a saga):
 *   * One VIEW object -- { lat, lng, heading, pitch, fov, panoId } -- is the whole camera.
 *     fov is degrees at full precision; zoom is derived on the way to the SDK. The
 *     arithmetic is pure and tested: utils/streetViewGeometry.js.
 *   * The saved view comes from the DATABASE and nowhere else. A per-machine localStorage
 *     copy used to shadow it, so a laptop that saved last week could out-vote a kiosk
 *     save from yesterday. Gone.
 *   * The SDK is loaded once per page by lib/googleMapsLoader.js, the documented way, with
 *     the auth verdict kept there; no polling, no globals in this file.
 *   * The panorama's life -- build, apply a changed view, read the camera back, tear down
 *     -- is hooks/useStreetViewPanorama.js. This file is layout.
 *   * The compact tile is a Static API image at the view; the interactive panorama and
 *     the save live behind Expand (operator, 2026-09-06). If the image fails, the tile
 *     falls back to the interactive view and says so.
 *
 * What still needs the operator: Street View Static API and Maps JavaScript API on the
 * key's restrictions in the Cloud console. The panel says which one is missing.
 */
export default function StreetViewPanel({ activeCall }) {
  const isOnline = useOnlineStatus();
  const admin = useAdminSession();   // the save is an operator ruling: unlocked only
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

  const cleanAddrKey = sanitizeAddress(activeCall?.address || '').toUpperCase();

  const [isExpanded, setIsExpanded] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);        // null | 'saving' | 'saved' | 'error'
  const [savedView, setSavedView] = useState(null);          // from public.parcels, or null
  const [lookupFailed, setLookupFailed] = useState(false);
  const [staticFailed, setStaticFailed] = useState(false);

  // Reset the per-address verdicts when the address changes, during render (React's
  // documented pattern) so no frame shows the previous address's state.
  const [addrKey, setAddrKey] = useState(cleanAddrKey);
  if (addrKey !== cleanAddrKey) {
    setAddrKey(cleanAddrKey);
    setSavedView(null);
    setLookupFailed(false);
    setStaticFailed(false);
    setSaveStatus(null);
    setIsExpanded(false);
  }

  // The saved view for this address, from the parcel row. Cleared above before the lookup
  // resolves, so a stale view is never shown against a new incident.
  useEffect(() => {
    if (!cleanAddrKey) return undefined;
    let cancelled = false;
    apiClient.parcels.lookup(cleanAddrKey)
      .then((res) => {
        if (cancelled) return;
        setSavedView(res?.found ? savedViewFromParcel(res.parcel) : null);
        setLookupFailed(false);
      })
      .catch((err) => {
        if (cancelled) return;
        console.warn('Parcel lookup for the saved Street View failed:', err);
        setLookupFailed(true);
      });
    return () => { cancelled = true; };
  }, [cleanAddrKey]);

  // The view to show: the operator's saved one, else the camera at the arrival point
  // looking at the parcel. Memoised so the hook applies it only when it actually changes.
  const view = useMemo(
    () => savedView || defaultViewForCall(activeCall),
    // activeCall's identity changes on every MQTT update; only its coordinates matter here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [savedView, activeCall?.lat, activeCall?.lng, activeCall?.front_lat, activeCall?.front_lng, activeCall?.target?.lat, activeCall?.target?.lng],
  );

  const staticUrl = staticStreetViewUrl(view, apiKey);
  const useStaticTile = Boolean(staticUrl) && !staticFailed;

  const tileContainerRef = useRef(null);
  const modalContainerRef = useRef(null);
  const pano = useStreetViewPanorama({
    containerRef: isExpanded ? modalContainerRef : tileContainerRef,
    containerKey: isExpanded ? 'modal' : 'tile',
    // Interactive in the expanded view always; in the tile only when the static image failed.
    enabled: isOnline && Boolean(view) && (isExpanded || !useStaticTile),
    apiKey,
    view,
  });
  const sdkDown = pano.authFailed || pano.status === 'unavailable';

  const handleSaveView = async () => {
    if (!cleanAddrKey) return;
    const live = pano.readView();
    if (!live) {
      setSaveStatus('error');
      return;
    }
    setSaveStatus('saving');
    const payload = {
      address: cleanAddrKey,
      clean_address: cleanAddrKey,
      front_lat: live.lat,
      front_lng: live.lng,
      heading: live.heading,
      pitch: live.pitch,
      // Degrees, full precision, NOT clamped: operator ruling 2026-09-08. The SDK can frame
      // wider than the Static API's 120-degree tile; the expanded panel is the framing tool
      // and is trusted, the tile is a thumbnail doing its best.
      fov: live.fov,
      pano_id: live.panoId,
    };
    try {
      await apiClient.parcels.saveStreetView(payload);
      setSavedView({ ...live });
      setSaveStatus('saved');
    } catch (e) {
      // A failed save is a failed save. This used to report "saved" on the catch path.
      console.error('Failed to save the Street View:', e);
      setSaveStatus('error');
    }
    setTimeout(() => setSaveStatus(null), 3000);
  };

  // ---------------------------------------------------------------------------------------
  const renderContent = (isModal) => {
    const showStatic = !isModal && useStaticTile;
    const showEmbed = !showStatic && (sdkDown || !apiKey);
    return (
      <div className="w-full h-full relative bg-slate-900 flex flex-col items-center justify-center overflow-hidden">
        {showStatic && (
          <img
            src={staticUrl}
            alt={`Street View of ${activeCall?.address || 'the target'}`}
            className="w-full h-full object-cover"
            onError={() => setStaticFailed(true)}
          />
        )}
        {/* A static miss is not a failure the crew needs to read about: the interactive view
            takes over and the header says "live". An <img> error carries no status, so a
            key problem and "no imagery here" look the same from this side; the console has
            the code either way (operator, 2026-09-08: the amber box was in the picture). */}
        {!showStatic && !showEmbed && pano.status === 'loading' && (
          <div className="absolute inset-0 z-10 bg-slate-950 flex flex-col items-center justify-center gap-3">
            <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
            <div className="text-indigo-300 text-xs font-mono font-bold tracking-wider motion-safe:animate-pulse">Loading Street View…</div>
          </div>
        )}
        {sdkDown && (
          <div className="absolute top-2 right-2 z-20 max-w-[60%] bg-amber-950/95 border border-amber-600 text-amber-200 px-2.5 py-1.5 rounded-lg text-[10px] font-mono leading-snug shadow-lg">
            <span className="font-bold">⚠️ INTERACTIVE VIEW UNAVAILABLE</span> — {pano.authFailed
              ? 'Google rejected the key for the Maps JavaScript API; a static embed is shown and the camera angle cannot be saved. The error code is in the browser console (punch-list #35a).'
              : 'the Maps JavaScript SDK did not load; a static embed is shown.'}
          </div>
        )}
        {showEmbed && (
          <iframe
            title="Fallback Google Street View Embed"
            width="100%"
            height="100%"
            style={{ border: 0 }}
            loading="lazy"
            allowFullScreen
            src={embedStreetViewUrl(view, apiKey)}
            className="w-full h-full"
          />
        )}
        {!showStatic && !showEmbed && (
          <div
            ref={isModal ? modalContainerRef : tileContainerRef}
            style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }}
          />
        )}

        {/* Address & Save: the expanded view only (operator, 2026-09-06). */}
        {isModal && (
          <div className="absolute bottom-2 left-2 right-2 z-20 bg-slate-900/95 backdrop-blur border border-slate-800 p-2.5 rounded-xl flex items-center justify-between shadow-2xl">
            <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
              <span className="text-amber-400 font-bold">📍 Address:</span>
              <span className="text-white font-bold">{activeCall?.address || 'Destination'}</span>
              {savedView && (
                <span className="bg-emerald-900/80 text-emerald-300 border border-emerald-700 px-2 py-0.5 rounded text-[10px] font-bold">
                  SAVED PREFERRED VIEW ({Math.round(savedView.heading)}°)
                </span>
              )}
              {lookupFailed && (
                <span className="bg-amber-900/80 text-amber-200 border border-amber-700 px-2 py-0.5 rounded text-[10px] font-bold" title="The parcel lookup failed, so a saved view may exist and not be shown">
                  SAVED VIEW UNKNOWN
                </span>
              )}
            </div>
            {admin.unlocked && (
            <button
              onClick={handleSaveView}
              disabled={saveStatus === 'saving' || sdkDown || pano.status !== 'ready'}
              title={sdkDown ? 'Interactive Street View is unavailable, so there is no camera angle to save' : undefined}
              className={`px-4 py-1.5 rounded-xl border font-bold text-xs transition shadow flex items-center gap-1.5 ${
                sdkDown || pano.status !== 'ready'
                  ? 'bg-slate-800 border-slate-700 text-slate-500 cursor-not-allowed'
                  : saveStatus === 'saved'
                  ? 'bg-emerald-600 border-emerald-400 text-white'
                  : saveStatus === 'error'
                  ? 'bg-red-600 border-red-400 text-white'
                  : 'bg-amber-500 hover:bg-amber-400 border-amber-300 text-slate-950 cursor-pointer'
              }`}
            >
              <span>💾</span>
              <span>
                {sdkDown ? 'No interactive view to save'
                  : saveStatus === 'saving' ? 'Saving…'
                  : saveStatus === 'saved' ? '✅ Saved Preferred View'
                  : saveStatus === 'error' ? '❌ Save failed'
                  : 'Save Preferred View'}
              </span>
            </button>
            )}
          </div>
        )}
      </div>
    );
  };

  // Tier 1: no usable coordinates, no camera, no guess (CLAUDE.md 5).
  if (!view) {
    return (
      <TileFrame label="Street view">
        <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center">
          <h4 className="text-sm font-black uppercase tracking-wider text-slate-200 font-mono">Standby</h4>
          <p className="text-xs text-slate-400 font-mono mt-1 max-w-xs leading-relaxed">Awaiting valid coordinates</p>
        </div>
      </TileFrame>
    );
  }

  // The header bar says what the picture is: the saved heading (a green dot is a human
  // ruling), or that the saved view could not be looked up, or that the tile is the live
  // panorama because the static image was not there, or that the internet is off.
  const meta = (
    <>
      {savedView && (
        <span className="text-emerald-400 font-mono font-bold text-[11px] lg:text-xs" title="Saved preferred view">· {Math.round(savedView.heading)}°</span>
      )}
      {lookupFailed && (
        <span className="text-amber-300 font-mono text-[10px]" title="The parcel lookup failed; a saved view may exist and not be shown">saved view unknown</span>
      )}
      {staticFailed && !sdkDown && (
        <span className="text-slate-400 font-mono text-[10px]" title="No static image within 100 m of this point; the interactive panorama is shown instead">live</span>
      )}
      {!isOnline && <span className="bg-amber-900/80 text-amber-200 px-1.5 py-0.5 rounded text-[9px] font-mono">Offline</span>}
    </>
  );

  return (
    <>
      <TileFrame label="Street view" meta={meta} onExpand={() => setIsExpanded(true)} expandTitle="Open the interactive view">
        {isOnline ? (
          renderContent(false)
        ) : (
          <div className="flex flex-col items-center justify-center p-3 text-center text-slate-400 gap-1.5 h-full">
            <p className="text-xs font-semibold">Street View needs the internet</p>
            <span className="text-[10px] text-slate-500">The only panel that does; everything else is local</span>
          </div>
        )}
      </TileFrame>

      {isExpanded && (
        <div className="fixed inset-0 z-[9999] bg-slate-950/95 backdrop-blur-md p-4 sm:p-8 flex flex-col animate-in fade-in duration-200">
          <div className="flex items-center justify-between mb-3 bg-slate-900 border border-slate-800 p-3 rounded-xl shadow-lg">
            <div className="flex items-center gap-2">
              <span className="text-xl">📷</span>
              <div>
                <h3 className="text-base font-bold text-white uppercase tracking-wide">Street View</h3>
                <p className="text-xs text-indigo-400 font-mono">📍 {activeCall?.address || 'Target Property'}</p>
              </div>
              {savedView && (
                <span className="bg-emerald-500 text-slate-950 px-2 py-0.5 rounded text-[10px] font-black tracking-wider shadow ml-2">
                  SAVED PREFERRED VIEW
                </span>
              )}
            </div>
            <button
              onClick={() => setIsExpanded(false)}
              className="bg-red-600 hover:bg-red-500 text-white font-bold text-sm px-4 py-2 rounded-lg transition shadow flex items-center gap-1.5 cursor-pointer"
            >
              <span>✕</span>
              <span>CLOSE</span>
            </button>
          </div>
          <div className="flex-1 w-full rounded-2xl overflow-hidden border-2 border-indigo-500/50 shadow-2xl relative">
            {renderContent(true)}
          </div>
        </div>
      )}
    </>
  );
}
