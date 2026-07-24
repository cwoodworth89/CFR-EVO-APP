import React from 'react';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';

export default function StreetViewPanel({ activeCall }) {
  const isOnline = useOnlineStatus();
  const destLat = activeCall?.lat ?? 49.2838;
  const destLng = activeCall?.lng ?? -122.7932;

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col items-center justify-center">
      <div className="absolute top-2 left-2 z-10 bg-slate-900/90 backdrop-blur px-3 py-1 rounded-lg border border-slate-800 text-xs font-bold text-indigo-400 flex items-center gap-1.5 shadow">
        <span>📷</span>
        <span>Street View Panorama</span>
        {!isOnline && <span className="bg-amber-900/80 text-amber-200 px-1.5 py-0.5 rounded text-[10px]">WAN Failsafe Mode</span>}
      </div>

      {isOnline ? (
        <div className="w-full h-full relative bg-slate-900 flex items-center justify-center">
          <iframe
            title="Google Street View"
            width="100%"
            height="100%"
            style={{ border: 0 }}
            loading="lazy"
            allowFullScreen
            src={`https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d1500!2d${destLng}!3d${destLat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!5e1!3m2!1sen!2sca!4v1700000000000`}
            className="w-full h-full opacity-90 hover:opacity-100 transition-opacity"
          />
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center p-4 text-center text-slate-400 gap-2">
          <span className="text-3xl">🏛️</span>
          <p className="text-xs font-semibold">Local Building Footprint Canvas</p>
          <span className="text-[10px] text-slate-500">Address Centroid Verified</span>
        </div>
      )}
    </div>
  );
}
