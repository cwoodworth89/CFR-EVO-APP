import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { RoutingOverlay } from '../RoutingOverlay';
import { CoquitlamOverlays, StationsLayer } from '../MapLayers';

// Custom Map Bounds Auto-Fitter
function AutoFitBounds({ origin, destination }) {
  const map = useMap();

  useEffect(() => {
    if (!map || !origin || !destination) return;
    const bounds = L.latLngBounds(
      [origin.lat, origin.lng],
      [destination.lat, destination.lng]
    );
    map.fitBounds(bounds, { padding: [60, 60], maxZoom: 16 });
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

// Destination Target Icon
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

  const [routeInfo, setRouteInfo] = useState(null);

  const handleRouteCalculated = (coordinates) => {
    if (coordinates && coordinates.length > 0) {
      setRouteInfo({ count: coordinates.length });
    }
  };

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-2xl">
      {/* Route Badge Header */}
      <div className="absolute top-4 left-4 z-[1000] bg-slate-900/90 backdrop-blur border border-slate-800 rounded-xl px-4 py-2.5 flex items-center gap-3 text-white shadow-lg">
        <span className="text-xl">🚒</span>
        <div>
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Suggested Emergency Response Route</h3>
          <p className="text-sm font-bold text-emerald-400">
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

        {/* Coquitlam Municipal Cadastral Layer */}
        <CoquitlamOverlays visible={true} />

        {/* Station Halls Layer */}
        <StationsLayer visible={true} />

        {/* Live OSRM Emergency Response Routing Overlay */}
        <RoutingOverlay
          from={[origin.lat, origin.lng]}
          to={[destLat, destLng]}
          onRouteCalculated={handleRouteCalculated}
        />

        <Marker position={[origin.lat, origin.lng]} icon={hallIcon}>
          <Popup>Origin: {origin.name}</Popup>
        </Marker>

        <Marker position={[destLat, destLng]} icon={destIcon}>
          <Popup>Target Destination: {activeCall?.address}</Popup>
        </Marker>

        <AutoFitBounds origin={origin} destination={destination} />
      </MapContainer>
    </div>
  );
}
