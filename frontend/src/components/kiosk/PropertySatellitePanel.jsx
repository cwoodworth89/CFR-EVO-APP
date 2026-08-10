import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Polygon, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';

function StableAutoCenterAndResize({ lat, lng, callKey }) {
  const map = useMap();
  const lastKeyRef = useRef(null);

  // Only recenter when target call changes, preserving manual panning
  useEffect(() => {
    if (!map || lat == null || lng == null) return;
    const currentKey = callKey || `${lat.toFixed(5)},${lng.toFixed(5)}`;
    if (lastKeyRef.current !== currentKey) {
      lastKeyRef.current = currentKey;
      map.setView([lat, lng], 18, { animate: false });
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

const targetIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-gold.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

export default function PropertySatellitePanel({ activeCall }) {
  const isOnline = useOnlineStatus();
  const [isExpanded, setIsExpanded] = useState(false);

  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;
  const callKey = activeCall?.id ? String(activeCall.id) : (activeCall?.address || `${destLat},${destLng}`);

  const polygonCoords = activeCall?.rings && activeCall.rings.length > 0
    ? activeCall.rings[0].map(([lng, lat]) => [lat, lng])
    : null;

  const renderMapContent = () => (
    <MapContainer
      center={[destLat, destLng]}
      zoom={18}
      maxZoom={20}
      className="w-full h-full z-0"
      zoomControl={true}
    >
      <TileLayer
        attribution="Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        maxNativeZoom={19}
        maxZoom={20}
      />

      {polygonCoords && (
        <Polygon positions={polygonCoords} pathOptions={{ color: '#fbbf24', fillColor: '#f59e0b', fillOpacity: 0.35, weight: 3 }} />
      )}

      <Marker position={[destLat, destLng]} icon={targetIcon}>
        <Popup>📍 Destination: {activeCall?.address || 'Target Location'}</Popup>
      </Marker>

      <StableAutoCenterAndResize lat={destLat} lng={destLng} callKey={callKey} />
    </MapContainer>
  );

  return (
    <>
      <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col">
        {/* Header Controls */}
        <div className="absolute top-2 left-2 z-[1000] bg-slate-900/90 backdrop-blur px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] font-bold text-amber-400 flex items-center gap-1.5 shadow">
          <span>🛰️</span>
          <span>Property Satellite View</span>
          {!isOnline && <span className="bg-amber-900/80 text-amber-200 px-1.5 py-0.5 rounded text-[9px]">Offline Mode</span>}
        </div>

        <button
          onClick={() => setIsExpanded(true)}
          className="absolute top-2 right-2 z-[1000] bg-slate-900/90 hover:bg-amber-600 text-amber-300 hover:text-white px-2.5 py-1 rounded-lg border border-slate-700 text-xs font-bold transition flex items-center gap-1 shadow"
          title="Pop Out Full Screen View"
        >
          <span>⤢</span>
          <span className="hidden sm:inline">Expand</span>
        </button>

        {isOnline ? (
          <div className="w-full h-full relative z-0">
            {renderMapContent()}
            <div className="absolute bottom-2 left-2 text-[10px] text-slate-300 font-mono bg-slate-900/90 px-2 py-0.5 rounded border border-slate-800 z-[1000] pointer-events-none">
              WGS84: {destLat.toFixed(5)}, {destLng.toFixed(5)}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center p-3 text-center text-slate-400 gap-1.5 h-full">
            <span className="text-2xl">🗺️</span>
            <p className="text-xs font-semibold">Offline Satellite Standby</p>
            <span className="text-[10px] text-slate-500">WAN Offline</span>
          </div>
        )}
      </div>

      {/* Popout Full-Screen Modal */}
      {isExpanded && (
        <div className="fixed inset-0 z-[9999] bg-slate-950/95 backdrop-blur-md p-4 sm:p-8 flex flex-col animate-in fade-in duration-200">
          <div className="flex items-center justify-between mb-3 bg-slate-900 border border-slate-800 p-3 rounded-xl shadow-lg">
            <div className="flex items-center gap-2">
              <span className="text-xl">🛰️</span>
              <div>
                <h3 className="text-base font-bold text-white uppercase tracking-wide">Property High-Res Satellite Inspection</h3>
                <p className="text-xs text-amber-400 font-mono">📍 {activeCall?.address || 'Target Property'}</p>
              </div>
            </div>
            <button
              onClick={() => setIsExpanded(false)}
              className="bg-red-600 hover:bg-red-500 text-white font-bold text-sm px-4 py-2 rounded-lg transition shadow flex items-center gap-1.5"
            >
              <span>✕</span>
              <span>CLOSE</span>
            </button>
          </div>

          <div className="flex-1 w-full rounded-2xl overflow-hidden border-2 border-amber-500/50 shadow-2xl relative">
            {renderMapContent()}
          </div>
        </div>
      )}
    </>
  );
}
