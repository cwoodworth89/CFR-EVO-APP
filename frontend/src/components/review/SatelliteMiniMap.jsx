import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Polygon, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { API_BASE_URL, TILE_BASE_URL } from '../../apiClient';

function MiniMapAutoCenter({ lat, lng, polygonPositions }) {
  const map = useMap();
  const lastKeyRef = useRef(null);

  useEffect(() => {
    if (!map || lat == null || lng == null) return;
    const currentKey = `${lat.toFixed(5)},${lng.toFixed(5)}`;
    if (lastKeyRef.current !== currentKey) {
      lastKeyRef.current = currentKey;

      if (polygonPositions && polygonPositions.length > 0) {
        try {
          const poly = L.polygon(polygonPositions);
          const bounds = poly.getBounds();
          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [20, 20], maxZoom: 17.5, animate: false });
            return;
          }
        } catch (e) {
          // fallback to setView
        }
      }
      map.setView([lat, lng], 16.5, { animate: false });
    }
  }, [map, lat, lng, polygonPositions]);

  useEffect(() => {
    if (!map) return;
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 150);
    return () => clearTimeout(timer);
  }, [map]);

  return null;
}

const miniTargetIcon = L.divIcon({
  className: 'custom-mini-target-icon',
  html: `<div style="
    background-color: #f59e0b;
    border: 2px solid #ffffff;
    border-radius: 50%;
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 5px rgba(0,0,0,0.5);
    font-size: 11px;
    box-sizing: border-box;
    color: white;
  ">🎯</div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
  popupAnchor: [0, -10]
});

export default function SatelliteMiniMap({
  lat = 49.2838,
  lng = -122.7932,
  address = '',
  rings = null,
  height = '140px'
}) {
  const destLat = typeof lat === 'number' && !isNaN(lat) ? lat : 49.2838;
  const destLng = typeof lng === 'number' && !isNaN(lng) ? lng : -122.7932;

  const polygonPositions = rings && rings.length > 0
    ? (Array.isArray(rings[0][0])
        ? rings.map(ring => ring.map(([rLng, rLat]) => [rLat, rLng]))
        : [rings.map(([rLng, rLat]) => [rLat, rLng])])
    : null;

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-slate-850 bg-slate-950 shadow-inner flex flex-col" style={{ height }}>
      {/* Header Badge */}
      <div className="absolute top-2 left-2 z-[1000] bg-slate-900/90 backdrop-blur px-2 py-0.5 rounded-lg border border-slate-800 text-[10px] font-bold text-amber-400 flex items-center gap-1 shadow pointer-events-none">
        <span>🛰️</span>
        <span>Satellite Imagery</span>
      </div>

      <div className="w-full h-full relative z-0">
        <MapContainer
          center={[destLat, destLng]}
          zoom={16.5}
          maxZoom={20}
          className="w-full h-full z-0"
          zoomControl={false}
          attributionControl={false}
        >
          {/* Local Pre-Cached High-Res Satellite Tiles */}
          <TileLayer
            url={`${TILE_BASE_URL}/services/satellite/tiles/{z}/{x}/{y}.jpg`}
            maxNativeZoom={20}
            maxZoom={22}
          />

          {polygonPositions && (
            <Polygon
              positions={polygonPositions}
              pathOptions={{ color: '#fbbf24', fillColor: '#f59e0b', fillOpacity: 0.35, weight: 2 }}
            />
          )}

          <Marker position={[destLat, destLng]} icon={miniTargetIcon}>
            <Popup>{address || 'Incident Location'}</Popup>
          </Marker>

          <MiniMapAutoCenter lat={destLat} lng={destLng} polygonPositions={polygonPositions} />
        </MapContainer>
      </div>

      <div className="absolute bottom-1 right-2 text-[8.5px] text-slate-400 font-mono bg-slate-950/80 backdrop-blur px-1.5 py-0.5 rounded border border-slate-800/80 z-[1000] pointer-events-none opacity-80">
        {destLat.toFixed(4)}, {destLng.toFixed(4)}
      </div>
    </div>
  );
}
