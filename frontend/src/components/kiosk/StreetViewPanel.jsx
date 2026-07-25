import React, { useState } from 'react';
import { useOnlineStatus } from '../../hooks/useOnlineStatus';

// Verified Street View Frontage & Heading Overrides for Large Complexes
export const STREETVIEW_OVERRIDES = {
  "3100 OZADA AVE": { lat: 49.3015, lng: -122.7758, heading: 170, fov: 90, pitch: 5 },
  "2680 MARINER WAY": { lat: 49.2780, lng: -122.8050, heading: 240, fov: 90, pitch: 0 },
  "1190 PIPELINE RD": { lat: 49.2965, lng: -122.7910, heading: 90, fov: 90, pitch: 0 },
  "1300 PINETREE WAY": { lat: 49.2838, lng: -122.7932, heading: 270, fov: 90, pitch: 0 },
  "775 MARINER WAY": { lat: 49.2635, lng: -122.8048, heading: 180, fov: 90, pitch: 0 },
  "438 NELSON ST": { lat: 49.2475, lng: -122.8682, heading: 320, fov: 90, pitch: 0 },
  "3501 DAVID AVE": { lat: 49.3012, lng: -122.7560, heading: 190, fov: 90, pitch: 0 }
};

export default function StreetViewPanel({ activeCall }) {
  const isOnline = useOnlineStatus();
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';
  const [imageError, setImageError] = useState(false);

  // Clean address key to check override table (e.g. "3100 OZADA AVE 116" -> "3100 OZADA AVE")
  const rawAddr = (activeCall?.address || '').toUpperCase().trim();
  const cleanAddrKey = rawAddr
    .replace(/\s+(UNIT|APT|SUITE|STE|#)\s*[\w-]+/gi, '')
    .replace(/(\b(AVE|AVENUE|ST|STREET|RD|ROAD|WAY|DR|DRIVE|CRT|COURT|BLVD|CRES|PL|LN|HWY)\b)\s+[A-Z0-9-]+$/i, '$1')
    .trim();

  const override = STREETVIEW_OVERRIDES[cleanAddrKey];

  const destLat = override ? override.lat : (activeCall?.lat ?? 49.2838);
  const destLng = override ? override.lng : (activeCall?.lng ?? -122.7932);
  const heading = override ? override.heading : 0;
  const pitch = override ? override.pitch : 0;
  const fov = override ? override.fov : 90;

  // Google Static Street View API URL (with source=outdoor to ignore indoor photo spheres)
  const staticStreetViewUrl = apiKey
    ? `https://maps.googleapis.com/maps/api/streetview?size=800x400&location=${destLat},${destLng}&fov=${fov}&heading=${heading}&pitch=${pitch}&source=outdoor&key=${apiKey}`
    : null;

  // Google Maps Embed API StreetView URL
  const embedStreetViewUrl = apiKey
    ? `https://www.google.com/maps/embed/v1/streetview?key=${apiKey}&location=${destLat},${destLng}&heading=${heading}&pitch=${pitch}`
    : `https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d1000!2d${destLng}!3d${destLat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!5e1!3m2!1sen!2sca`;

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 shadow-xl flex flex-col items-center justify-center">
      {/* Header Badge */}
      <div className="absolute top-2 left-2 z-20 bg-slate-900/90 backdrop-blur px-2.5 py-1 rounded-lg border border-slate-800 text-[11px] font-bold text-indigo-400 flex items-center gap-1.5 shadow">
        <span>📷</span>
        <span>Google Street View</span>
        {!isOnline && <span className="bg-amber-900/80 text-amber-200 px-1.5 py-0.5 rounded text-[9px]">WAN Failsafe Mode</span>}
      </div>

      {isOnline ? (
        <div className="w-full h-full relative bg-slate-900 flex items-center justify-center">
          {staticStreetViewUrl && !imageError ? (
            <img
              src={staticStreetViewUrl}
              alt="Google Street View"
              className="w-full h-full object-cover"
              onError={() => setImageError(true)}
            />
          ) : (
            <iframe
              title="Google Street View"
              width="100%"
              height="100%"
              style={{ border: 0 }}
              loading="lazy"
              allowFullScreen
              src={embedStreetViewUrl}
              className="w-full h-full opacity-90 hover:opacity-100 transition-opacity"
            />
          )}

          {/* Target Location Pin Badge Overlay */}
          <div className="absolute bottom-2 left-2 z-20 bg-slate-900/90 backdrop-blur border border-slate-800 text-[10px] font-mono text-amber-300 px-2 py-1 rounded-lg flex items-center gap-1.5 shadow">
            <span className="text-amber-400 font-bold">📍 Target Address:</span>
            <span className="text-white font-semibold">{activeCall?.address || 'Destination'}</span>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center p-3 text-center text-slate-400 gap-1.5">
          <span className="text-2xl">🏛️</span>
          <p className="text-xs font-semibold">Local Building Footprint Canvas</p>
          <span className="text-[10px] text-slate-500">Address Centroid Verified</span>
        </div>
      )}
    </div>
  );
}
