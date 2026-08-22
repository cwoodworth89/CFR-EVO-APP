import React from 'react';
import { STATIONS as STATIONS_LIST } from '../MapConstants';

export function Header({ 
  appMode, 
  setAppMode, 
  rightSidebarOpen,
  setRightSidebarOpen,
  setShowRoadClosures,
  alertsCount,
  gisOffline
}) {
  const isExplore = appMode === "EXPLORE";

  const handleModeChange = (e) => {
    const selectedValue = e.target.value;
    setAppMode(selectedValue);
  };

  return (
    <div className="bg-slate-950 text-white p-3 shadow-md z-[1100] flex justify-between items-center border-b border-slate-800 h-16 relative select-none">
        {/* Left Side: Brand Logo */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold tracking-wider flex items-center gap-1.5 select-none uppercase">
              CFR <span className="text-emerald-500 font-extrabold">DISPATCH</span>
              <span className="text-slate-500 font-normal text-[10px] uppercase tracking-widest ml-1.5 border-l border-slate-800 pl-2 font-mono">
                {(() => {
                  const defaultHallId = import.meta.env.VITE_DEFAULT_HALL || "1";
                  const configStn = STATIONS_LIST.find(s => s.id === defaultHallId) || STATIONS_LIST[0];
                  const configStnName = configStn ? configStn.name.split(" Fire Hall")[0] : `HALL ${defaultHallId}`;
                  return `${configStnName} (Hall ${defaultHallId})`;
                })()}
              </span>
            </h1>
            
            {gisOffline && (
              <span className="bg-rose-500/10 text-rose-400 border border-rose-500/20 text-[9px] font-mono font-bold px-2 py-0.5 rounded flex items-center gap-1.5 select-none animate-pulse">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                COQUITLAM GIS OFFLINE
              </span>
            )}
          </div>
        </div>

        {/* Center: Mode Select Dropdown */}
        <div className="flex items-center">
          <div className="relative">
            <select 
              value={isExplore ? "EXPLORE" : appMode} 
              onChange={handleModeChange}
              className="bg-slate-900 border border-slate-700 hover:border-slate-650 text-white rounded-lg pl-3 pr-8 py-1.5 text-xs font-bold focus:outline-none focus:border-sky-500 cursor-pointer shadow-sm appearance-none min-w-[220px]"
              style={{ 
                backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>")`, 
                backgroundPosition: 'right 8px center', 
                backgroundRepeat: 'no-repeat', 
                backgroundSize: '14px' 
              }}
            >
              <option value="EXPLORE">🧭 Notifications / Explore</option>
              <option value="KIOSK_VIEW">🖥️ KIOSK: IN-STATION MODE</option>
              <option value="DRIVER_SETUP">📱 MOBILE: DRIVER PUSH SETUP</option>
              <option value="ADMIN_DISPATCHES">🛡️ ADMIN: DISPATCH REVIEW</option>
            </select>
          </div>
        </div>

        {/* Right Side: Alerts & Mobile Setup Triggers */}
        <div className="flex gap-3 items-center">
          <button
            onClick={() => setAppMode("DRIVER_SETUP")}
            className="px-3 py-1.5 text-xs font-black rounded-lg border bg-amber-500/20 border-amber-500/40 text-amber-300 hover:bg-amber-500/30 hover:border-amber-500/60 transition-all flex items-center gap-1.5 cursor-pointer shadow-md"
            title="Open Driver Mobile Alerts QR Setup"
          >
            📱 DRIVER ALERTS
          </button>

          {/* Right Sidebar Hazards & Alerts Panel Toggle */}
          <button 
            onClick={() => {
              setRightSidebarOpen(!rightSidebarOpen);
              if (setShowRoadClosures) setShowRoadClosures(true);
            }}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all flex items-center gap-1.5 cursor-pointer ${
              rightSidebarOpen 
                ? "bg-amber-950/80 border-amber-600/80 text-amber-300 shadow-md animate-pulse" 
                : "bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700 hover:text-white"
            }`}
            title="Toggle Road Closures Panel"
          >
            🚧 ROAD CLOSURES {alertsCount > 0 && <span className="bg-amber-500 text-slate-950 text-[9px] font-black px-1.5 py-0.2 rounded-full ml-1">{alertsCount}</span>}
          </button>
        </div>
    </div>
  );
}
