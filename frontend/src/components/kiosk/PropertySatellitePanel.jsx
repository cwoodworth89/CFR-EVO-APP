import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, Polygon, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { BaseMap, CoquitlamOverlays } from '../MapLayers';
import { API_BASE_URL, TILE_BASE_URL } from '../../apiClient';

function StableAutoCenterAndResize({ lat, lng, polygonPositions, callKey }) {
  const map = useMap();
  const lastKeyRef = useRef(null);

  // Auto-fit property bounds and zoom out 1 step for full surrounding context
  useEffect(() => {
    if (!map || lat == null || lng == null) return;
    const currentKey = callKey || `${lat.toFixed(5)},${lng.toFixed(5)}`;
    if (lastKeyRef.current !== currentKey) {
      lastKeyRef.current = currentKey;

      if (polygonPositions && polygonPositions.length > 0) {
        try {
          const poly = L.polygon(polygonPositions);
          const bounds = poly.getBounds();
          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [45, 45], maxZoom: 17.5, animate: false });
            const fitZoom = map.getZoom();
            // Zoom out 1 step from fitted bounds so full parcel and surrounding roads are visible
            map.setZoom(Math.max(fitZoom - 1, 15.5), { animate: false });
            return;
          }
        } catch (e) {
          console.warn('Failed to fit parcel bounds:', e);
        }
      }

      // Default fallback zoom level (16.5 instead of 18)
      map.setView([lat, lng], 16.5, { animate: false });
    }
  }, [map, lat, lng, polygonPositions, callKey]);

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
    background-color: #f59e0b;
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

export default function PropertySatellitePanel({ activeCall }) {
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
      maxZoom={22}
      className="w-full h-full z-0"
      zoomControl={true}
      attributionControl={false}
    >
      {/* High-Resolution 7.5cm Satellite Basemap (Local MBTiles Server on Port 8081) */}
      <BaseMap style="SATELLITE" />

      {/* Authentic Coquitlam Cadastral Parcels & Civic Address Labels */}
      <CoquitlamOverlays visible={true} minZoom={14} />

      {polygonPositions && (
        <Polygon positions={polygonPositions} pathOptions={{ color: '#fbbf24', fillColor: '#f59e0b', fillOpacity: 0.35, weight: 3 }} />
      )}

      <Marker position={[destLat, destLng]} icon={targetIcon}>
        <Popup>📍 Destination: {activeCall?.address || 'Target Location'}</Popup>
      </Marker>

      <StableAutoCenterAndResize lat={destLat} lng={destLng} polygonPositions={polygonPositions} callKey={callKey} />
    </MapContainer>
  );

  return (
    <>
      <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col">
        {/* Header Controls */}
        <div className="absolute top-2 left-2 z-[1000] bg-slate-900/90 backdrop-blur px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] font-bold text-amber-400 flex items-center gap-1.5 shadow">
          <span>🛰️</span>
          <span>Property Satellite View</span>
        </div>

        <button
          onClick={() => setIsExpanded(true)}
          className="absolute top-2 right-2 z-[1000] bg-slate-900/90 hover:bg-amber-600 text-amber-300 hover:text-white px-2.5 py-1 rounded-lg border border-slate-700 text-xs font-bold transition flex items-center gap-1 shadow cursor-pointer"
          title="Pop Out Full Screen View"
        >
          <span>⤢</span>
          <span className="hidden sm:inline">Expand</span>
        </button>

        <div className="w-full h-full relative z-0">
          {renderMapContent()}
          <div className="absolute bottom-1.5 left-2 text-[9px] text-slate-400 font-mono bg-slate-950/80 backdrop-blur px-2 py-0.5 rounded border border-slate-800/80 z-[1000] pointer-events-none opacity-80">
            WGS84: {destLat.toFixed(5)}, {destLng.toFixed(5)}
          </div>
        </div>
      </div>

      {/* Popout Full-Screen Modal */}
      {isExpanded && (
        <div className="fixed inset-0 z-[9999] bg-slate-950/95 backdrop-blur-md p-4 sm:p-8 flex flex-col animate-in fade-in duration-200">
          <div className="flex items-center justify-between mb-3 bg-slate-900 border border-slate-800 p-3 rounded-xl shadow-lg">
            <div className="flex items-center gap-3">
              <span className="text-xl">🛰️</span>
              <div>
                <h3 className="text-base font-bold text-white uppercase tracking-wide">Property High-Res Satellite Inspection</h3>
                <p className="text-xs text-amber-400 font-mono">📍 {activeCall?.address || 'Target Property'}</p>
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

          <div className="flex-1 w-full rounded-2xl overflow-hidden border-2 border-amber-500/50 shadow-2xl relative">
            {renderMapContent()}
          </div>
        </div>
      )}
    </>
  );
}
