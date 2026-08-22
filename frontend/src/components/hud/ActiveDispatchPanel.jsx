import React from 'react';
import SatelliteMiniMap from './SatelliteMiniMap';

export default function ActiveDispatchPanel({ activeDispatch, setActiveDispatch, nearestHydrants = [], setTargetAddress }) {
  const target = activeDispatch.target || {};
  const lat = target.lat || activeDispatch.latitude;
  const lng = target.lng || activeDispatch.longitude;
  const address = target.address || activeDispatch.address || "Unknown Address";
  const incidentType = activeDispatch.incident_type || "Emergency Call";
  const units = activeDispatch.responding_units || [];

  const handleDismiss = () => {
    setActiveDispatch(null);
    setTargetAddress(null);
  };

  const googleApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';
  const hasGoogleKey = googleApiKey && googleApiKey !== 'your-google-api-key-here';
  
  const streetViewUrl = hasGoogleKey
    ? `https://maps.googleapis.com/maps/api/streetview?size=400x250&location=${lat},${lng}&key=${googleApiKey}`
    : null;

  return (
    <div className="flex flex-col h-full bg-slate-905 text-slate-100 overflow-y-auto w-full select-none">
      {/* Active Alert Banner */}
      <div className={`p-4 text-center border-b animate-pulse flex flex-col gap-0.5 shadow-md flex-shrink-0 ${
        activeDispatch.is_test 
          ? "bg-gradient-to-r from-amber-600 via-orange-600 to-amber-600 border-amber-500"
          : "bg-gradient-to-r from-red-600 to-orange-600 border-red-700"
      }`}>
        <span className="text-[10px] text-white/95 font-black uppercase tracking-widest font-mono">
          {activeDispatch.is_test ? "⚠️ *TEST* DISPATCH ACTIVE ⚠️" : "🚨 DISPATCH OVERRIDE ACTIVE 🚨"}
        </span>
        <span className="text-xs text-white/80 font-bold tracking-wider font-mono">
          {activeDispatch.is_test ? "SYSTEM QA / TRAINING DRILL" : "STATION KIOSK ALERT"}
        </span>
      </div>

      <div className="p-5 flex-grow flex flex-col gap-6 overflow-y-auto">
        {/* Core Dispatch Details */}
        <div className="bg-slate-950 p-4 border border-slate-800 rounded-2xl flex flex-col gap-1 flex-shrink-0">
          <span className="text-[9px] text-red-400 font-extrabold uppercase font-mono tracking-wider">INCIDENT LOCATION</span>
          <h2 className="text-xl text-white font-black leading-tight tracking-wide uppercase select-text">{address}</h2>
          <div className="border-t border-slate-900 mt-2.5 pt-2 flex flex-col gap-0.5 text-left">
            <span className="text-[8px] text-slate-500 font-extrabold uppercase font-mono">CALL TYPE</span>
            <div className="text-sm text-amber-500 font-black tracking-wide uppercase">
              {activeDispatch.is_test && !incidentType.includes("*TEST*") ? `*TEST* ${incidentType}` : incidentType}
            </div>
          </div>
        </div>

        {/* Responding Units */}
        <div className="flex flex-col gap-2 bg-slate-950 p-4 border border-slate-800 rounded-2xl flex-shrink-0 text-left">
          <span className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider">RESPONDING UNITS (ORDER ANNOUNCED)</span>
          {units.length > 0 ? (
            <div className="flex flex-wrap gap-2 mt-1">
              {units.map((unit, idx) => (
                <span 
                  key={idx}
                  className="px-3 py-1.5 rounded-lg text-xs font-black tracking-wider shadow border bg-slate-900 text-sky-400 border-sky-500/30"
                >
                  🚒 {unit}
                </span>
              ))}
            </div>
          ) : (
            <div className="text-xs text-slate-500 italic">No units listed in broadcast.</div>
          )}
        </div>

        {/* Nearest Hydrants */}
        <div className="flex flex-col gap-2 bg-slate-950 p-4 border border-slate-800 rounded-2xl flex-shrink-0 text-left">
          <span className="text-[9px] text-cyan-400 font-extrabold uppercase font-mono tracking-wider">💧 NEAREST CITY HYDRANTS</span>
          <div className="flex flex-col gap-2 mt-1">
            {nearestHydrants.slice(0, 3).map((hyd, idx) => {
              const isPrimary = idx === 0;
              return (
                <div 
                  key={idx}
                  className={`flex justify-between items-center p-2 rounded-xl text-xs border ${
                    isPrimary 
                      ? 'bg-slate-900 border-cyan-500/30' 
                      : 'bg-slate-900/60 border-slate-850'
                  }`}
                >
                  <div className="flex flex-col text-left">
                    <div className="font-black text-white font-mono flex items-center gap-1.5">
                      <span>{hyd.gisId}</span>
                      {isPrimary && (
                        <span className="px-1.5 py-0.2 rounded text-[7px] bg-cyan-500/20 text-cyan-400 font-black tracking-wider uppercase font-sans">
                          Closest
                        </span>
                      )}
                    </div>
                    {hyd.flowClass && (
                      <div className="text-[9px] text-sky-400 font-bold font-mono">Flow: {hyd.flowClass}</div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="font-extrabold text-emerald-400 font-mono">{hyd.distance}m</div>
                    <div className="text-[8px] text-slate-500 font-extrabold uppercase font-mono">Distance</div>
                  </div>
                </div>
              );
            })}
            {nearestHydrants.length === 0 && (
              <div className="text-xs text-slate-500 italic">Calculating closest hydrants...</div>
            )}
          </div>
        </div>

        {/* TV Kiosk Satellite View */}
        <div className="flex flex-col gap-2 bg-slate-950 p-4 border border-slate-800 rounded-2xl flex-shrink-0 text-left">
          <span className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider flex justify-between items-center">
            <span>🛰️ GOOGLE SATELLITE VIEW</span>
            <span className="text-emerald-500 text-[8px] font-black uppercase">ZOOM LEVEL 18</span>
          </span>
          <div className="mt-1">
            {lat && lng ? (
              <SatelliteMiniMap lat={lat} lng={lng} />
            ) : (
              <div className="h-44 w-full bg-slate-900 border border-slate-850 rounded-xl flex items-center justify-center text-xs text-slate-500 italic">
                Coordinates missing
              </div>
            )}
          </div>
        </div>

        {/* TV Kiosk Street View */}
        <div className="flex flex-col gap-2 bg-slate-950 p-4 border border-slate-800 rounded-2xl flex-shrink-0 text-left">
          <span className="text-[9px] text-slate-400 font-extrabold uppercase font-mono tracking-wider flex justify-between items-center">
            <span>📷 STREET VIEW (ALPHA SIDE FRONTAGE)</span>
            <span className="text-indigo-400 text-[8px] font-black uppercase">STREET FRONTAGE</span>
          </span>
          <div className="mt-1">
            {lat && lng ? (
              hasGoogleKey ? (
                <div className="h-44 w-full rounded-xl overflow-hidden border border-slate-800">
                  <img src={streetViewUrl} alt="Google Street View" className="w-full h-full object-cover" />
                </div>
              ) : (
                <div className="bg-slate-900 border border-slate-850 rounded-xl p-3.5 flex flex-col gap-2 relative overflow-hidden text-left">
                  <div className="text-[9px] text-slate-450 font-bold leading-relaxed">
                    Google Maps API Key not configured. Visual mock and coordinates computed:
                  </div>
                  <div className="grid grid-cols-2 gap-2 font-mono text-[9px] bg-slate-950/80 p-2 rounded border border-slate-850 text-center">
                    <div>
                      <div className="text-[7px] text-slate-500 font-black">LATITUDE</div>
                      <div className="text-white font-bold">{lat.toFixed(5)}</div>
                    </div>
                    <div>
                      <div className="text-[7px] text-slate-500 font-black">LONGITUDE</div>
                      <div className="text-white font-bold">{lng.toFixed(5)}</div>
                    </div>
                  </div>
                  <a 
                    href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}`}
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-extrabold py-2 px-3 rounded-lg text-[10px] flex items-center justify-center gap-1.5 transition-all text-center w-full shadow border border-indigo-500 mt-1"
                  >
                    🌐 OPEN GOOGLE STREET VIEW
                  </a>
                </div>
              )
            ) : (
              <div className="h-44 w-full bg-slate-900 border border-slate-850 rounded-xl flex items-center justify-center text-xs text-slate-500 italic">
                Coordinates missing
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Dismiss Button */}
      <div className="p-4 border-t border-slate-850 bg-slate-950 mt-auto flex-shrink-0">
        <button
          onClick={handleDismiss}
          className="bg-slate-800 hover:bg-slate-700 text-rose-455 hover:text-rose-300 font-extrabold py-3 px-6 rounded-xl w-full transition-all border border-slate-700 hover:border-slate-650 shadow-md flex items-center justify-center gap-1.5 cursor-pointer text-xs"
        >
          ✕ DISMISS DISPATCH OVERRIDE
        </button>
      </div>
    </div>
  );
}
