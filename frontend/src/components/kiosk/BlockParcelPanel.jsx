import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, Polygon, Marker, Popup, useMap } from 'react-leaflet';
import { targetPinIcon } from '../map/mapIcons';
import { BaseMap, HydrantsLayer, CoquitlamOverlays } from '../MapLayers';
import { BASE_LAYERS } from '../MapConstants';
import { isWithinCoquitlam } from '../../utils/addressUtils';

function StableAutoCenterAndResize({ lat, lng, callKey }) {
  const map = useMap();
  const lastKeyRef = useRef(null);

  useEffect(() => {
    if (!map || lat == null || lng == null) return;
    const currentKey = callKey || `${lat.toFixed(5)},${lng.toFixed(5)}`;
    if (lastKeyRef.current !== currentKey) {
      lastKeyRef.current = currentKey;
      map.setView([lat, lng], 16.5, { animate: false });
    }
  }, [map, lat, lng, callKey]);

  useEffect(() => {
    if (!map) return;
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 200);
    return () => clearTimeout(timer);
  }, [map]);

  return null;
}

export default function BlockParcelPanel({ activeCall }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const rawDestLat = activeCall?.lat ?? activeCall?.target?.lat ?? null;
  const rawDestLng = activeCall?.lng ?? activeCall?.target?.lng ?? null;

  const hasCoords = rawDestLat != null && rawDestLng != null &&
    !isNaN(Number(rawDestLat)) && !isNaN(Number(rawDestLng)) &&
    (Number(rawDestLat) !== 0 || Number(rawDestLng) !== 0);

  const destLat = hasCoords ? Number(rawDestLat) : null;
  const destLng = hasCoords ? Number(rawDestLng) : null;
  const inCoquitlam = hasCoords ? isWithinCoquitlam(destLat, destLng) : false;

  const callKey = activeCall?.id ? String(activeCall.id) : (activeCall?.address || (hasCoords ? `${destLat},${destLng}` : 'cadastral-panel'));

  const polygonPositions = activeCall?.rings && activeCall.rings.length > 0
    ? (Array.isArray(activeCall.rings[0][0])
        ? activeCall.rings.map(ring => ring.map(([lng, lat]) => [lat, lng]))
        : [activeCall.rings.map(([lng, lat]) => [lat, lng])])
    : null;

  // Tier 1 Error State: Location Unresolved
  if (!hasCoords) {
    return (
      <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col items-center justify-center p-6 text-center">
        <div className="absolute top-2 left-2 z-20 bg-slate-900/90 backdrop-blur px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] font-bold text-amber-400 flex items-center gap-1.5 shadow">
          <span>📦</span>
          <span>Cadastral Block & Hydrants</span>
        </div>
        <div className="w-14 h-14 rounded-2xl bg-amber-950/40 border border-amber-700/50 flex items-center justify-center text-2xl mb-3 shadow-inner">
          ⚠️
        </div>
        <h4 className="text-sm font-black uppercase tracking-wider text-amber-400 font-mono">
          LOCATION UNRESOLVED
        </h4>
        <p className="text-xs text-slate-400 font-mono mt-1 max-w-xs leading-relaxed">
          Coordinates awaiting operator verification.
        </p>
      </div>
    );
  }

  // Tier 2 Error State: Not Available Outside of City
  if (!inCoquitlam) {
    return (
      <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col items-center justify-center p-6 text-center">
        <div className="absolute top-2 left-2 z-20 bg-slate-900/90 backdrop-blur px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] font-bold text-sky-400 flex items-center gap-1.5 shadow">
          <span>📦</span>
          <span>Cadastral Block & Hydrants</span>
        </div>
        <div className="w-14 h-14 rounded-2xl bg-slate-900 border border-slate-700 flex items-center justify-center text-2xl mb-3 shadow-inner">
          🌐
        </div>
        <h4 className="text-sm font-black uppercase tracking-wider text-slate-200 font-mono">
          NOT AVAILABLE OUTSIDE OF CITY
        </h4>
        <p className="text-xs text-slate-400 font-mono mt-1 max-w-xs leading-relaxed">
          7.5cm Orthophotos &amp; Cadastral Parcels Cover City of Coquitlam Only.
        </p>
      </div>
    );
  }

  const renderMapContent = () => (
    <MapContainer
      center={[destLat, destLng]}
      zoom={16.5}
      className="w-full h-full z-0"
      zoomControl={true}
    >
      {/* Offline-First Cadastral Basemap (Prioritizes local :8081 tile server with graceful online fallback) */}
      <BaseMap style="GREY" />

      <CoquitlamOverlays visible={true} />

      <HydrantsLayer visible={true} targetCoords={[destLat, destLng]} minZoom={14} />

      {polygonPositions && (
        <Polygon positions={polygonPositions} pathOptions={{ color: '#0284c7', fillColor: '#38bdf8', fillOpacity: 0.4, weight: 3 }} />
      )}

      <Marker position={[destLat, destLng]} icon={targetPinIcon}>
        <Popup>Target Destination: {activeCall?.address}</Popup>
      </Marker>

      <StableAutoCenterAndResize lat={destLat} lng={destLng} callKey={callKey} />
    </MapContainer>
  );

  return (
    <>
      <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col">
        {/* Header Controls */}
        <div className="absolute top-2 left-2 z-[1000] flex items-center gap-2">
          <div className="bg-slate-900/90 backdrop-blur px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] font-bold text-sky-400 flex items-center gap-1.5 shadow">
            <span>📦</span>
            <span>Cadastral Block & Hydrants</span>
          </div>
        </div>

        <button
          onClick={() => setIsExpanded(true)}
          className="absolute top-2 right-2 z-[1000] bg-slate-900/90 hover:bg-sky-600 text-sky-300 hover:text-white px-2.5 py-1 rounded-lg border border-slate-700 text-xs font-bold transition flex items-center gap-1 shadow"
          title="Pop Out Full Screen View"
        >
          <span>⤢</span>
          <span className="hidden sm:inline">Expand</span>
        </button>

        <div className="w-full h-full relative z-0">
          {renderMapContent()}
        </div>
      </div>

      {/* Popout Full-Screen Modal */}
      {isExpanded && (
        <div className="fixed inset-0 z-[9999] bg-slate-950/95 backdrop-blur-md p-4 sm:p-8 flex flex-col animate-in fade-in duration-200">
          <div className="flex items-center justify-between mb-3 bg-slate-900 border border-slate-800 p-3 rounded-xl shadow-lg">
            <div className="flex items-center gap-2">
              <span className="text-xl">📦</span>
              <div>
                <h3 className="text-base font-bold text-white uppercase tracking-wide">Cadastral Parcels & NFPA 291 Fire Hydrants Inspection</h3>
                <p className="text-xs text-sky-400 font-mono">📍 {activeCall?.address || 'Target Location'}</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsExpanded(false)}
                className="bg-red-600 hover:bg-red-500 text-white font-bold text-sm px-4 py-2 rounded-lg transition shadow flex items-center gap-1.5 cursor-pointer"
              >
                <span>✕</span>
                <span>CLOSE</span>
              </button>
            </div>
          </div>

          <div className="flex-1 w-full rounded-2xl overflow-hidden border-2 border-sky-500/50 shadow-2xl relative">
            {renderMapContent()}
          </div>
        </div>
      )}
    </>
  );
}

