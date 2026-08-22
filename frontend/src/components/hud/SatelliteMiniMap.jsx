import React from 'react';
import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import L from 'leaflet';
import { TILE_BASE_URL } from '../../apiClient';

export default function SatelliteMiniMap({ lat, lng }) {
  if (!lat || !lng) return null;

  const position = [lat, lng];
  
  // Custom red target icon
  const miniTargetIcon = L.divIcon({
    className: 'custom-mini-target-icon',
    html: `<div style="
      background-color: #ef4444;
      border: 2px solid #ffffff;
      border-radius: 50%;
      width: 12px;
      height: 12px;
      box-shadow: 0 0 10px rgba(239, 68, 68, 0.8);
    "></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6]
  });

  return (
    <div className="h-44 w-full rounded-xl overflow-hidden border border-slate-800 relative z-[990]">
      <MapContainer 
        key={`${lat}-${lng}`}
        center={position} 
        zoom={18} 
        zoomControl={false}
        attributionControl={false}
        doubleClickZoom={false}
        scrollWheelZoom={false}
        dragging={false}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          url={`${TILE_BASE_URL}/services/satellite/tiles/{z}/{x}/{y}.jpg`}
          maxNativeZoom={20}
          maxZoom={22}
        />
        <Marker position={position} icon={miniTargetIcon} />
      </MapContainer>
    </div>
  );
}
