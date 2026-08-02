import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, useMapEvents, ZoomControl } from 'react-leaflet';
import L from 'leaflet';
import { RoutingOverlay } from '../RoutingOverlay';
import { CoquitlamOverlays, StationsLayer } from '../MapLayers';
import { BASE_LAYERS } from '../MapConstants';

// Custom Map Bounds Auto-Fitter
function AutoFitBounds({ origin, destination, userPanned }) {
  const map = useMap();

  useEffect(() => {
    if (!map || !origin || !destination || userPanned) return;
    const bounds = L.latLngBounds(
      [origin.lat, origin.lng],
      [destination.lat, destination.lng]
    );
    map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
  }, [map, origin, destination, userPanned]);

  return null;
}

// Interactivity listener to detect manual pan/zoom
function MapInteractivity({ onPan }) {
  useMapEvents({
    dragstart: () => onPan && onPan(),
    zoomstart: () => onPan && onPan()
  });
  return null;
}

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
  const origin = stationHall || {
    lat: 49.29109654571679,
    lng: -122.79072561861948,
    name: 'Hall 1 (1300 Pinetree Way)'
  };
  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;
  const destination = { lat: destLat, lng: destLng };

  const [routeInfo, setRouteInfo] = useState(null);
  const [userPanned, setUserPanned] = useState(false);
  const [mapInstance, setMapInstance] = useState(null);

  const handleRouteCalculated = (coordinates) => {
    if (coordinates && coordinates.length > 0) {
      setRouteInfo({ count: coordinates.length });
    }
  };

  const handleRecenter = () => {
    setUserPanned(false);
    if (mapInstance && origin && destination) {
      const bounds = L.latLngBounds(
        [origin.lat, origin.lng],
        [destination.lat, destination.lng]
      );
      mapInstance.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
    }
  };

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-2xl">
      {/* Route Badge Header */}
      <div className="absolute top-3 left-3 z-[1000] bg-slate-900/90 backdrop-blur border border-slate-800 rounded-xl px-3.5 py-2 flex items-center gap-2.5 text-white shadow-lg pointer-events-none">
        <span className="text-lg">🚒</span>
        <div>
          <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Suggested Emergency Route</h3>
          <p className="text-xs font-bold text-emerald-400">
            From {origin.name || 'Station Hall'} → {activeCall?.address || 'Destination'}
          </p>
        </div>
      </div>

      {/* Floating Re-Center Button when user pans or zooms */}
      {userPanned && (
        <button
          onClick={handleRecenter}
          className="absolute top-3 right-14 z-[1000] bg-sky-600 hover:bg-sky-500 text-white font-mono text-xs font-black px-3.5 py-2 rounded-xl shadow-xl border border-sky-400 flex items-center gap-1.5 cursor-pointer animate-pulse"
        >
          <span>🎯</span>
          <span>RE-CENTER ROUTE</span>
        </button>
      )}

      <MapContainer
        center={[destLat, destLng]}
        zoom={13}
        className="w-full h-full z-0"
        zoomControl={false}
        dragging={true}
        scrollWheelZoom={true}
        doubleClickZoom={true}
        touchZoom={true}
        ref={setMapInstance}
      >
        <MapInteractivity onPan={() => setUserPanned(true)} />
        <ZoomControl position="bottomright" />

        {/* Original CartoDB light_nolabels Basemap for vector layer compatibility */}
        <TileLayer
          attribution={BASE_LAYERS.GREY.attribution}
          url={BASE_LAYERS.GREY.url}
          subdomains={BASE_LAYERS.GREY.subdomains}
          maxZoom={22}
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

        <Marker position={[destLat, destLng]} icon={destIcon}>
          <Popup>Target Destination: {activeCall?.address}</Popup>
        </Marker>

        <AutoFitBounds origin={origin} destination={destination} userPanned={userPanned} />
      </MapContainer>
    </div>
  );
}
