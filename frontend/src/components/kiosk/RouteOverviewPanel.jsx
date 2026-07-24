import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';

// Custom Map Bounds Auto-Fitter
function AutoFitBounds({ origin, destination }) {
  const map = useMap();

  useEffect(() => {
    if (!map || !origin || !destination) return;
    const bounds = L.latLngBounds(
      [origin.lat, origin.lng],
      [destination.lat, destination.lng]
    );
    map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
  }, [map, origin, destination]);

  return null;
}

// Hall Icon
const hallIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// Destination Icon
const destIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-gold.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

export default function RouteOverviewPanel({ activeCall, stationHall }) {
  const origin = stationHall || { lat: 49.2882, lng: -122.7915, name: 'Hall 1 (Pinetree Way)' };
  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;
  const destination = { lat: destLat, lng: destLng };

  const polylineCoords = [
    [origin.lat, origin.lng],
    [(origin.lat + destLat) / 2 + 0.001, (origin.lng + destLng) / 2],
    [destLat, destLng]
  ];

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-2xl">
      <div className="absolute top-4 left-4 z-[1000] bg-slate-900/90 backdrop-blur border border-slate-800 rounded-xl px-4 py-2 flex items-center gap-3 text-white shadow-lg">
        <span className="text-xl">🚒</span>
        <div>
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Suggested Response Route</h3>
          <p className="text-sm font-semibold text-emerald-400">
            From {origin.name || 'Station Hall'} → {activeCall?.address || 'Destination'}
          </p>
        </div>
      </div>

      <MapContainer
        center={[destLat, destLng]}
        zoom={13}
        className="w-full h-full z-0"
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Polyline
          positions={polylineCoords}
          color="#10b981"
          weight={6}
          opacity={0.9}
          dashArray="10, 10"
        />
        <Marker position={[origin.lat, origin.lng]} icon={hallIcon}>
          <Popup>Origin: {origin.name}</Popup>
        </Marker>
        <Marker position={[destLat, destLng]} icon={destIcon}>
          <Popup>Destination: {activeCall?.address}</Popup>
        </Marker>
        <AutoFitBounds origin={origin} destination={destination} />
      </MapContainer>
    </div>
  );
}
