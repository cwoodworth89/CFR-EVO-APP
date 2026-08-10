import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Polygon, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { HydrantsLayer, CoquitlamOverlays } from '../MapLayers';
import { BASE_LAYERS } from '../MapConstants';

function AutoCenterAndResize({ center }) {
  const map = useMap();
  useEffect(() => {
    if (!map || !center) return;
    map.setView([center.lat, center.lng], 16.5);
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 150);
    return () => clearTimeout(timer);
  }, [map, center]);
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

export default function BlockParcelPanel({ activeCall }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;
  const center = { lat: destLat, lng: destLng };

  const polygonCoords = activeCall?.rings && activeCall.rings.length > 0
    ? activeCall.rings[0].map(([lng, lat]) => [lat, lng])
    : null;

  const renderMapContent = () => (
    <MapContainer
      center={[destLat, destLng]}
      zoom={16.5}
      className="w-full h-full z-0"
      zoomControl={true}
    >
      <TileLayer
        attribution={BASE_LAYERS.GREY.attribution}
        url={BASE_LAYERS.GREY.url}
        subdomains={BASE_LAYERS.GREY.subdomains}
        maxZoom={22}
      />

      <CoquitlamOverlays visible={true} />

      <HydrantsLayer visible={true} mode="EXPLORE" zoom={16.5} />

      {polygonCoords && (
        <Polygon positions={polygonCoords} pathOptions={{ color: '#0284c7', fillColor: '#38bdf8', fillOpacity: 0.4, weight: 3 }} />
      )}

      <Marker position={[destLat, destLng]} icon={targetIcon}>
        <Popup>Target Destination: {activeCall?.address}</Popup>
      </Marker>

      <AutoCenterAndResize center={center} />
    </MapContainer>
  );

  return (
    <>
      <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col">
        {/* Header Controls */}
        <div className="absolute top-2 left-2 z-[1000] bg-slate-900/90 backdrop-blur px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] font-bold text-sky-400 flex items-center gap-1.5 shadow">
          <span>📦</span>
          <span>Cadastral Block & Hydrants</span>
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
            <button
              onClick={() => setIsExpanded(false)}
              className="bg-red-600 hover:bg-red-500 text-white font-bold text-sm px-4 py-2 rounded-lg transition shadow flex items-center gap-1.5"
            >
              <span>✕</span>
              <span>CLOSE</span>
            </button>
          </div>

          <div className="flex-1 w-full rounded-2xl overflow-hidden border-2 border-sky-500/50 shadow-2xl relative">
            {renderMapContent()}
          </div>
        </div>
      )}
    </>
  );
}
