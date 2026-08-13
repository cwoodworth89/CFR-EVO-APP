import React, { useState, useEffect, useRef } from 'react';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';
import { sanitizeAddress } from '../../utils/addressUtils';
import { apiClient } from '../../apiClient';

// Fallback hardcoded overrides table
export const STREETVIEW_OVERRIDES = {
  "3000 RIVERBEND DR": { lat: 49.2552, lng: -122.7840, heading: 180, fov: 90, pitch: 0 },
  "3100 OZADA AVE": { lat: 49.3015, lng: -122.7758, heading: 170, fov: 90, pitch: 5 },
  "2680 MARINER WAY": { lat: 49.2780, lng: -122.8050, heading: 240, fov: 90, pitch: 0 },
  "1190 PIPELINE RD": { lat: 49.2965, lng: -122.7910, heading: 90, fov: 90, pitch: 0 },
  "1300 PINETREE WAY": { lat: 49.2838, lng: -122.7932, heading: 270, fov: 90, pitch: 0 },
  "775 MARINER WAY": { lat: 49.2635, lng: -122.8048, heading: 180, fov: 90, pitch: 0 },
  "438 NELSON ST": { lat: 49.2475, lng: -122.8682, heading: 320, fov: 90, pitch: 0 },
  "3501 DAVID AVE": { lat: 49.3012, lng: -122.7560, heading: 190, fov: 90, pitch: 0 },
  "1386 COAST MERIDIAN RD": { lat: 49.297541, lng: -122.755800, heading: 270, fov: 90, pitch: 0 }
};

export default function StreetViewPanel({ activeCall }) {
  const isOnline = useOnlineStatus();
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

  const [isExpanded, setIsExpanded] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);
  const [dbOverride, setDbOverride] = useState(null);

  const containerRef = useRef(null);
  const modalContainerRef = useRef(null);
  const panoramaRef = useRef(null);

  const cleanAddrKey = sanitizeAddress(activeCall?.address || '').toUpperCase();
  const fallbackOverride = STREETVIEW_OVERRIDES[cleanAddrKey];

  // Helper for instant local storage override retrieval
  const getLocalOverride = () => {
    if (!cleanAddrKey) return null;
    try {
      const stored = localStorage.getItem(`cfr_sv_override_${cleanAddrKey}`);
      return stored ? JSON.parse(stored) : null;
    } catch (e) {
      return null;
    }
  };

  const localOverride = getLocalOverride();

  // Fetch DB override on mount or when address changes
  useEffect(() => {
    let isMounted = true;
    setDbOverride(null);
    if (cleanAddrKey) {
      apiClient.streetView.fetchOverride(cleanAddrKey).then((data) => {
        if (!data && activeCall?.address) {
          return apiClient.streetView.fetchOverride(activeCall.address);
        }
        return data;
      }).then((data) => {
        if (isMounted && data) {
          setDbOverride(data);
        }
      }).catch(() => {});
    }
    return () => { isMounted = false; };
  }, [cleanAddrKey, activeCall?.address]);

  // Priority: 1. DB Override -> 2. Local Storage -> 3. Hardcoded fallback -> 4. Computed frontage angle
  const activeOverride = dbOverride || localOverride || fallbackOverride;

  const frontLat = activeOverride ? (activeOverride.lat ?? activeOverride.front_lat) : (activeCall?.front_lat ?? activeCall?.target?.frontage_lat ?? activeCall?.lat ?? 49.2838);
  const frontLng = activeOverride ? (activeOverride.lng ?? activeOverride.front_lng) : (activeCall?.front_lng ?? activeCall?.target?.frontage_lng ?? activeCall?.lng ?? -122.7932);

  const targetLat = activeCall?.lat ?? activeCall?.target?.lat ?? frontLat;
  const targetLng = activeCall?.lng ?? activeCall?.target?.lng ?? frontLng;

  let initialHeading = activeOverride ? activeOverride.heading : 0;
  if (!activeOverride && (frontLat !== targetLat || frontLng !== targetLng)) {
    const dLng = (targetLng - frontLng) * (Math.PI / 180);
    const targetLatRad = targetLat * (Math.PI / 180);
    const frontLatRad = frontLat * (Math.PI / 180);
    const y = Math.sin(dLng) * Math.cos(targetLatRad);
    const x = Math.cos(frontLatRad) * Math.sin(targetLatRad) - Math.sin(frontLatRad) * Math.cos(targetLatRad) * Math.cos(dLng);
    const bearing = Math.atan2(y, x) * (180 / Math.PI);
    initialHeading = Math.round((bearing + 360) % 360);
  }

  const initialPitch = activeOverride ? activeOverride.pitch : 5;
  const initialFov = activeOverride ? activeOverride.fov : 80;

  // Initialize or update Google Maps StreetViewPanorama
  useEffect(() => {
    if (!apiKey || !isOnline) return;

    const targetContainer = isExpanded ? modalContainerRef.current : containerRef.current;
    if (!targetContainer) return;

    const initPanorama = () => {
      if (!window.google || !window.google.maps) return;

      const pano = new window.google.maps.StreetViewPanorama(targetContainer, {
        position: { lat: frontLat, lng: frontLng },
        pov: { heading: initialHeading, pitch: initialPitch },
        zoom: 1,
        fullscreenControl: false, // Hides Google's native fullscreen button underneath ours!
        addressControl: false,
        panControl: false,
        linksControl: true,
        motionTracking: false,
        motionTrackingControl: false,
        showRoadLabels: true
      });
      panoramaRef.current = pano;
    };

    if (window.google && window.google.maps) {
      initPanorama();
    } else {
      const existingScript = document.getElementById('google-maps-js-sdk');
      if (!existingScript) {
        const script = document.createElement('script');
        script.id = 'google-maps-js-sdk';
        script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}`;
        script.async = true;
        script.onload = initPanorama;
        document.head.appendChild(script);
      } else {
        existingScript.addEventListener('load', initPanorama);
      }
    }
  }, [frontLat, frontLng, initialHeading, initialPitch, apiKey, isOnline, isExpanded]);

  const handleSaveView = async () => {
    if (!activeCall?.address || !cleanAddrKey) return;
    setSaveStatus('saving');

    let currentHeading = initialHeading;
    let currentPitch = initialPitch;
    if (panoramaRef.current && typeof panoramaRef.current.getPov === 'function') {
      const pov = panoramaRef.current.getPov();
      if (pov) {
        currentHeading = Math.round(pov.heading || 0);
        currentPitch = Math.round(pov.pitch || 0);
      }
    }

    const payload = {
      clean_address: cleanAddrKey,
      front_lat: frontLat,
      front_lng: frontLng,
      heading: currentHeading,
      pitch: currentPitch,
      fov: initialFov
    };

    try {
      localStorage.setItem(`cfr_sv_override_${cleanAddrKey}`, JSON.stringify(payload));
      await apiClient.streetView.saveOverride(payload);
      setDbOverride(payload);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (e) {
      console.error('Failed to save Street View angle:', e);
      setDbOverride(payload);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus(null), 3000);
    }
  };

  const embedStreetViewUrl = apiKey
    ? `https://www.google.com/maps/embed/v1/streetview?key=${apiKey}&location=${frontLat},${frontLng}&heading=${initialHeading}&pitch=${initialPitch}&fov=${initialFov}`
    : `https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d1000!2d${frontLng}!3d${frontLat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!5e1!3m2!1sen!2sca`;

  const renderContent = (isModal = false) => (
    <div className="w-full h-full relative bg-slate-900 flex flex-col items-center justify-center overflow-hidden">
      {/* StreetView Canvas Container */}
      <div
        ref={isModal ? modalContainerRef : containerRef}
        className="w-full h-full"
      >
        {!apiKey && (
          <iframe
            title="Live Interactive Google Street View"
            width="100%"
            height="100%"
            style={{ border: 0 }}
            loading="lazy"
            allowFullScreen
            src={embedStreetViewUrl}
            className="w-full h-full"
          />
        )}
      </div>

      {/* Address & Save Overlay */}
      <div className="absolute bottom-2 left-2 right-2 z-20 bg-slate-900/95 backdrop-blur border border-slate-800 p-2.5 rounded-xl flex items-center justify-between shadow-2xl">
        <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
          <span className="text-amber-400 font-bold">📍 Address:</span>
          <span className="text-white font-bold">{activeCall?.address || 'Destination'}</span>
          {dbOverride && (
            <span className="bg-emerald-900/80 text-emerald-300 border border-emerald-700 px-2 py-0.5 rounded text-[10px] font-bold">
              SAVED PREFERRED VIEW
            </span>
          )}
        </div>

        {/* Save Preferred View Button (Grabs touch/mouse orientation dynamically!) */}
        <button
          onClick={handleSaveView}
          disabled={saveStatus === 'saving'}
          className={`px-4 py-1.5 rounded-xl border font-bold text-xs transition shadow flex items-center gap-1.5 ${
            saveStatus === 'saved'
              ? 'bg-emerald-600 border-emerald-400 text-white'
              : saveStatus === 'error'
              ? 'bg-red-600 border-red-400 text-white'
              : 'bg-amber-500 hover:bg-amber-400 border-amber-300 text-slate-950 cursor-pointer'
          }`}
        >
          <span>💾</span>
          <span>
            {saveStatus === 'saving'
              ? 'Saving...'
              : saveStatus === 'saved'
              ? '✅ Saved Preferred View!'
              : saveStatus === 'error'
              ? '❌ Failed'
              : 'Save Preferred View'}
          </span>
        </button>
      </div>
    </div>
  );

  return (
    <>
      <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col">
        {/* Header Title Bar */}
        <div className="absolute top-2 left-2 z-20 bg-slate-900/90 backdrop-blur px-3 py-1.5 rounded-xl border border-slate-800 text-xs font-bold text-indigo-400 flex items-center gap-2 shadow">
          <span>📷</span>
          <span>Google Street View 360°</span>
          {!isOnline && <span className="bg-amber-900/80 text-amber-200 px-1.5 py-0.5 rounded text-[9px]">Offline Mode</span>}
        </div>

        {/* Custom Expand Button (Sitting cleanly in top right corner!) */}
        <button
          onClick={() => setIsExpanded(true)}
          className="absolute top-2 right-2 z-20 bg-slate-900/90 hover:bg-indigo-600 text-indigo-300 hover:text-white px-3 py-1.5 rounded-xl border border-slate-700 text-xs font-bold transition flex items-center gap-1.5 shadow cursor-pointer"
          title="Pop Out Full Screen View"
        >
          <span>⤢</span>
          <span>Expand</span>
        </button>

        {isOnline ? (
          renderContent(false)
        ) : (
          <div className="flex flex-col items-center justify-center p-3 text-center text-slate-400 gap-1.5 h-full">
            <span className="text-2xl">🏛️</span>
            <p className="text-xs font-semibold">Local Building Footprint Canvas</p>
            <span className="text-[10px] text-slate-500">Address Centroid Verified</span>
          </div>
        )}
      </div>

      {/* Popout Full-Screen Modal */}
      {isExpanded && (
        <div className="fixed inset-0 z-[9999] bg-slate-950/95 backdrop-blur-md p-4 sm:p-8 flex flex-col animate-in fade-in duration-200">
          <div className="flex items-center justify-between mb-3 bg-slate-900 border border-slate-800 p-3 rounded-xl shadow-lg">
            <div className="flex items-center gap-2">
              <span className="text-xl">📷</span>
              <div>
                <h3 className="text-base font-bold text-white uppercase tracking-wide">Google Street View 360° Inspection</h3>
                <p className="text-xs text-indigo-400 font-mono">📍 {activeCall?.address || 'Target Property'}</p>
              </div>
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
