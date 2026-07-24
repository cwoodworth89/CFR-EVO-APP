import React from 'react';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';

export default function PropertySatellitePanel({ activeCall }) {
  const isOnline = useOnlineStatus();
  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;

  // Static Google / Esri World Imagery URL
  const satelliteTileUrl = `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/18/${latToYTile(destLat, 18)}/${lngToXTile(destLng, 18)}`;

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col items-center justify-center">
      <div className="absolute top-2 left-2 z-10 bg-slate-900/90 backdrop-blur px-3 py-1 rounded-lg border border-slate-800 text-xs font-bold text-amber-400 flex items-center gap-1.5 shadow">
        <span>🛰️</span>
        <span>3D Property Satellite View</span>
        {!isOnline && <span className="bg-amber-900/80 text-amber-200 px-1.5 py-0.5 rounded text-[10px]">WAN Failsafe Mode</span>}
      </div>

      {isOnline ? (
        <div className="w-full h-full relative">
          <img
            src={satelliteTileUrl}
            alt="3D Satellite View"
            className="w-full h-full object-cover"
            onError={(e) => {
              e.target.style.display = 'none';
            }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950/60 via-transparent to-transparent" />
          <div className="absolute bottom-2 left-2 text-[10px] text-slate-300 font-mono bg-slate-900/80 px-2 py-0.5 rounded border border-slate-800">
            WGS84: {destLat.toFixed(4)}, {destLng.toFixed(4)}
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center p-4 text-center text-slate-400 gap-2">
          <span className="text-3xl">🗺️</span>
          <p className="text-xs font-semibold">2D Vector CAD Failsafe View</p>
          <span className="text-[10px] text-slate-500">Local Shapefile Boundaries Cached</span>
        </div>
      )}
    </div>
  );
}

// Convert Lat/Lng to Tile coordinates for imagery fallback
function lngToXTile(lng, zoom) {
  return Math.floor(((lng + 180) / 360) * Math.pow(2, zoom));
}
function latToYTile(lat, zoom) {
  return Math.floor(
    ((1 - Math.log(Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)) / Math.PI) / 2) * Math.pow(2, zoom)
  );
}
