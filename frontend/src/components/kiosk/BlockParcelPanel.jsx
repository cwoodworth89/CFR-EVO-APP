import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, Polygon, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { BaseMap, HydrantsLayer, CoquitlamOverlays } from '../MapLayers';
import { BASE_LAYERS } from '../MapConstants';

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

const targetIcon = L.divIcon({
  className: 'custom-target-icon',
  html: `<div style="
    background-color: #4f46e5;
    border: 2px solid #ffffff;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.4);
    font-size: 13px;
    box-sizing: border-box;
    color: white;
  ">🎯</div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  popupAnchor: [0, -12]
});

export default function BlockParcelPanel({ activeCall }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;
  const callKey = activeCall?.id ? String(activeCall.id) : (activeCall?.address || `${destLat},${destLng}`);

  const polygonPositions = activeCall?.rings && activeCall.rings.length > 0
    ? (Array.isArray(activeCall.rings[0][0])
        ? activeCall.rings.map(ring => ring.map(([lng, lat]) => [lat, lng]))
        : [activeCall.rings.map(([lng, lat]) => [lat, lng])])
    : null;

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

      <Marker position={[destLat, destLng]} icon={targetIcon}>
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
