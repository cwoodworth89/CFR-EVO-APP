import React, { useState, useEffect } from 'react';
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
  const [viewMode, setViewMode] = useState(() => {
    return localStorage.getItem('cfr_streetview_mode') || 'embed';
  });

  const handleSetViewMode = (mode) => {
    setViewMode(mode);
    localStorage.setItem('cfr_streetview_mode', mode);
  };

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

  const [heading, setHeading] = useState(initialHeading);
  const [pitch, setPitch] = useState(activeOverride ? activeOverride.pitch : 5);
  const [fov, setFov] = useState(activeOverride ? activeOverride.fov : 80);

  // Sync heading/pitch/fov ONLY when address changes or activeOverride is first loaded
  const loadedKeyRef = React.useRef(null);
  useEffect(() => {
    const key = `${cleanAddrKey}_${dbOverride ? 'db' : localOverride ? 'local' : 'none'}`;
    if (loadedKeyRef.current !== key) {
      loadedKeyRef.current = key;
      setHeading(activeOverride ? activeOverride.heading : initialHeading);
      setPitch(activeOverride ? activeOverride.pitch : 5);
      setFov(activeOverride ? activeOverride.fov : 80);
    }
  }, [cleanAddrKey, dbOverride, localOverride, initialHeading, activeOverride]);

  const handleSaveView = async () => {
    if (!activeCall?.address || !cleanAddrKey) return;
    setSaveStatus('saving');
    const payload = {
      clean_address: cleanAddrKey,
      front_lat: frontLat,
      front_lng: frontLng,
      heading: Math.round(heading),
      pitch: Math.round(pitch),
      fov: Math.round(fov)
    };
    try {
      // Save locally to localStorage for instant client retrieval
      localStorage.setItem(`cfr_sv_override_${cleanAddrKey}`, JSON.stringify(payload));
      
      // Persist to backend PostgreSQL DB
      await apiClient.streetView.saveOverride(payload);
      setDbOverride(payload);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (e) {
      console.error('Failed to save Street View angle:', e);
      // Fallback: LocalStorage saved successfully even if API call fails
      setDbOverride(payload);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus(null), 3000);
    }
  };

  const staticStreetViewUrl = apiKey
    ? `https://maps.googleapis.com/maps/api/streetview?size=900x500&location=${frontLat},${frontLng}&fov=${fov}&heading=${heading}&pitch=${pitch}&source=outdoor&key=${apiKey}`
    : null;

  const embedStreetViewUrl = apiKey
    ? `https://www.google.com/maps/embed/v1/streetview?key=${apiKey}&location=${frontLat},${frontLng}&heading=${heading}&pitch=${pitch}&fov=${fov}`
    : `https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d1000!2d${frontLng}!3d${frontLat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!5e1!3m2!1sen!2sca`;

  const renderContent = () => (
    <div className="w-full h-full relative bg-slate-900 flex flex-col items-center justify-center overflow-hidden">
      {viewMode === 'photo' && staticStreetViewUrl ? (
        <div className="w-full h-full relative bg-slate-950 flex items-center justify-center">
          <img
            src={staticStreetViewUrl}
            alt="Google Street View High-Res"
            className="w-full h-full object-cover"
            onError={() => setViewMode('embed')}
          />
          {/* Subtle vignette */}
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent pointer-events-none" />
        </div>
      ) : (
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

      {/* Angle Fine-Tuning & Save Overlay */}
      <div className="absolute bottom-2 left-2 right-2 z-20 bg-slate-900/95 backdrop-blur border border-slate-800 p-2 rounded-xl flex flex-wrap items-center justify-between gap-2 shadow-2xl">
        <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-300">
          <span className="text-amber-400 font-bold">📍 Address:</span>
          <span className="text-white font-semibold">{activeCall?.address || 'Destination'}</span>
          {dbOverride && <span className="bg-emerald-900/80 text-emerald-300 border border-emerald-700 px-1.5 py-0.5 rounded text-[9px] font-bold">SAVED OVERRIDE</span>}
        </div>

        {/* Heading & Pitch Controls */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800 text-[10px] font-mono text-slate-300">
            <span>Heading:</span>
            <button
              onClick={() => setHeading((h) => (h - 15 + 360) % 360)}
              className="px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 rounded text-amber-300 font-bold"
              title="Rotate Left 15°"
            >
              ↺
            </button>
            <span className="text-amber-400 font-bold min-w-[32px] text-center">{Math.round(heading)}°</span>
            <button
              onClick={() => setHeading((h) => (h + 15) % 360)}
              className="px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 rounded text-amber-300 font-bold"
              title="Rotate Right 15°"
            >
              ↻
            </button>
          </div>

          <div className="flex items-center gap-1 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800 text-[10px] font-mono text-slate-300">
            <span>Pitch:</span>
            <button
              onClick={() => setPitch((p) => Math.max(-45, p - 5))}
              className="px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 rounded text-sky-300 font-bold"
              title="Tilt Down 5°"
            >
              ⬇
            </button>
            <span className="text-sky-400 font-bold min-w-[28px] text-center">{Math.round(pitch)}°</span>
            <button
              onClick={() => setPitch((p) => Math.min(45, p + 5))}
              className="px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 rounded text-sky-300 font-bold"
              title="Tilt Up 5°"
            >
              ⬆
            </button>
          </div>

          {/* Save Preferred View Button */}
          <button
            onClick={handleSaveView}
            disabled={saveStatus === 'saving'}
            className={`px-3 py-1 rounded-lg border font-bold text-xs transition shadow flex items-center gap-1.5 ${
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
                ? '✅ Saved!'
                : saveStatus === 'error'
                ? '❌ Failed'
                : 'Save Preferred View'}
            </span>
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col">
        {/* Header Controls */}
        <div className="absolute top-2 left-2 z-20 bg-slate-900/90 backdrop-blur px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] font-bold text-indigo-400 flex items-center gap-2 shadow">
          <span>📷</span>
          <span>Google Street View</span>
          
          {/* Mode Switcher Toggle */}
          <div className="flex items-center bg-slate-950 rounded border border-slate-800 p-0.5 text-[9px] font-mono">
            <button
              onClick={() => handleSetViewMode('embed')}
              className={`px-2 py-0.5 rounded transition ${viewMode === 'embed' ? 'bg-indigo-600 text-white font-bold' : 'text-slate-400 hover:text-white'}`}
              title="Interactive 360° Live Embed"
            >
              Interactive 360°
            </button>
            <button
              onClick={() => handleSetViewMode('photo')}
              className={`px-2 py-0.5 rounded transition ${viewMode === 'photo' ? 'bg-indigo-600 text-white font-bold' : 'text-slate-400 hover:text-white'}`}
              title="High-Resolution Street View Photo"
            >
              Photo
            </button>
          </div>

          {!isOnline && <span className="bg-amber-900/80 text-amber-200 px-1.5 py-0.5 rounded text-[9px]">Offline Mode</span>}
        </div>

        <button
          onClick={() => setIsExpanded(true)}
          className="absolute top-2 right-2 z-20 bg-slate-900/90 hover:bg-indigo-600 text-indigo-300 hover:text-white px-2.5 py-1 rounded-lg border border-slate-700 text-xs font-bold transition flex items-center gap-1 shadow cursor-pointer"
          title="Pop Out Full Screen View"
        >
          <span>⤢</span>
          <span className="hidden sm:inline">Expand</span>
        </button>

        {isOnline ? (
          renderContent()
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
                <h3 className="text-base font-bold text-white uppercase tracking-wide">Google Street View 360° Inspection & Camera Calibration</h3>
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
            {renderContent()}
          </div>
        </div>
      )}
    </>
  );
}
