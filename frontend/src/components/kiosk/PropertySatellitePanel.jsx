import React from 'react';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';

export default function PropertySatellitePanel({ activeCall }) {
  const isOnline = useOnlineStatus();
  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;

  // High-Resolution ESRI World Imagery Bounding Box Export URL centered on property
  // Widened delta span (~200m) for comfortable aerial context of entire building complex & access roads
  const deltaLat = 0.0018;
  const deltaLng = 0.0028;
  const minLng = destLng - deltaLng;
  const maxLng = destLng + deltaLng;
  const minLat = destLat - deltaLat;
  const maxLat = destLat + deltaLat;

  const satelliteExportUrl = `https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export?bbox=${minLng},${minLat},${maxLng},${maxLat}&bboxSR=4326&imageSR=4326&size=800,400&f=image`;

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col items-center justify-center">
      {/* Header Badge */}
      <div className="absolute top-2 left-2 z-20 bg-slate-900/90 backdrop-blur px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] font-bold text-amber-400 flex items-center gap-1.5 shadow">
        <span>🛰️</span>
        <span>3D Property Satellite View</span>
        {!isOnline && <span className="bg-amber-900/80 text-amber-200 px-1.5 py-0.5 rounded text-[9px]">WAN Failsafe Mode</span>}
      </div>

      {isOnline ? (
        <div className="w-full h-full relative">
          <img
            src={satelliteExportUrl}
            alt="Property Satellite View"
            className="w-full h-full object-cover"
            onError={(e) => {
              e.target.style.display = 'none';
            }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950/60 via-transparent to-transparent pointer-events-none" />

          {/* Static Target Location Pin Overlay (Clean non-bouncing CAD pin) */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
            <div className="flex flex-col items-center">
              <div className="bg-slate-950/90 text-amber-300 text-[10px] font-black px-2 py-1 rounded-lg shadow-xl border border-amber-500/60 uppercase tracking-wider font-mono flex items-center gap-1">
                <span>📍</span>
                <span>{activeCall?.address || 'Target Property'}</span>
              </div>
              <div className="w-0.5 h-2.5 bg-amber-400 shadow-md" />
              <div className="w-2.5 h-2.5 rounded-full border-2 border-amber-300 bg-amber-500 shadow-md" />
            </div>
          </div>

          <div className="absolute bottom-2 left-2 text-[10px] text-slate-300 font-mono bg-slate-900/80 px-2 py-0.5 rounded border border-slate-800 z-20">
            WGS84: {destLat.toFixed(4)}, {destLng.toFixed(4)}
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center p-3 text-center text-slate-400 gap-1.5">
          <span className="text-2xl">🗺️</span>
          <p className="text-xs font-semibold">2D Vector CAD Failsafe View</p>
          <span className="text-[10px] text-slate-500">Local Shapefile Boundaries Cached</span>
        </div>
      )}
    </div>
  );
}
