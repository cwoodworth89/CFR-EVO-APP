import React from 'react';
import { MapContainer, TileLayer, Marker, Polygon, Popup } from 'react-leaflet';
import L from 'leaflet';

const hydrantIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [20, 32],
  iconAnchor: [10, 32],
  popupAnchor: [1, -28],
  shadowSize: [32, 32]
});

export default function BlockParcelPanel({ activeCall }) {
  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;

  // Parcel ring boundary from active call or default box
  const polygonCoords = activeCall?.rings && activeCall.rings.length > 0
    ? activeCall.rings[0].map(([lng, lat]) => [lat, lng])
    : [
        [destLat + 0.0003, destLng - 0.0004],
        [destLat + 0.0003, destLng + 0.0004],
        [destLat - 0.0003, destLng + 0.0004],
        [destLat - 0.0003, destLng - 0.0004]
      ];

  // Simulated nearest hydrant offset
  const hydrantLat = destLat + 0.0004;
  const hydrantLng = destLng - 0.0005;

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col">
      <div className="absolute top-2 left-2 z-[1000] bg-slate-900/90 backdrop-blur px-3 py-1 rounded-lg border border-slate-800 text-xs font-bold text-sky-400 flex items-center gap-1.5 shadow">
        <span>📦</span>
        <span>Block & Parcel Detail</span>
      </div>

      <MapContainer
        center={[destLat, destLng]}
        zoom={18}
        className="w-full h-full z-0"
        zoomControl={false}
        dragging={false}
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Polygon positions={polygonCoords} pathOptions={{ color: '#0284c7', fillColor: '#38bdf8', fillOpacity: 0.35, weight: 3 }} />
        <Marker position={[hydrantLat, hydrantLng]} icon={hydrantIcon}>
          <Popup>Nearest Hydrant #H-402 (Class AA - 1500 GPM)</Popup>
        </Marker>
      </MapContainer>
    </div>
  );
}
