import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Polygon, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { HydrantsLayer, CoquitlamOverlays } from '../MapLayers';
import { BASE_LAYERS } from '../MapConstants';

// Force Leaflet map resize invalidation on render & center map
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
  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;
  const center = { lat: destLat, lng: destLng };

  // Polygon parcel boundary if provided by Phase 1/2 backend
  const polygonCoords = activeCall?.rings && activeCall.rings.length > 0
    ? activeCall.rings[0].map(([lng, lat]) => [lat, lng])
    : null;

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col">
      <div className="absolute top-2 left-2 z-[1000] bg-slate-900/90 backdrop-blur px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] font-bold text-sky-400 flex items-center gap-1.5 shadow">
        <span>📦</span>
        <span>Cadastral Block & Hydrants</span>
      </div>

      <MapContainer
        center={[destLat, destLng]}
        zoom={16.5}
        className="w-full h-full z-0"
        zoomControl={false}
      >
        <TileLayer
          attribution={BASE_LAYERS.GREY.attribution}
          url={BASE_LAYERS.GREY.url}
          subdomains={BASE_LAYERS.GREY.subdomains}
          maxZoom={22}
        />

        {/* Official Coquitlam Municipal Cadastral Roads & Parcels */}
        <CoquitlamOverlays visible={true} />

        {/* Real Fire Hydrants System Overlay */}
        <HydrantsLayer visible={true} mode="EXPLORE" zoom={16.5} />

        {polygonCoords && (
          <Polygon positions={polygonCoords} pathOptions={{ color: '#0284c7', fillColor: '#38bdf8', fillOpacity: 0.4, weight: 3 }} />
        )}

        <Marker position={[destLat, destLng]} icon={targetIcon}>
          <Popup>Target Destination: {activeCall?.address}</Popup>
        </Marker>

        <AutoCenterAndResize center={center} />
      </MapContainer>
    </div>
  );
}
