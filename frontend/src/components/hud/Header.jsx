import React from 'react';
import { STATIONS as STATIONS_LIST } from '../MapConstants';
import { AdminLock } from './AdminLock';

/**
 * The workstation header. One row at every width: on a phone the hall name, the mode
 * select (unless the padlock is open, when it carries the review entry) and MOBILE SETUP
 * (a QR page for pairing a phone, which a phone has no use for) give way, and ROAD
 * CLOSURES keeps its count and drops its word. Measured 2026-09-09: at 393 px the old
 * header wrapped to three lines and pushed the padlock off the right edge, so the admin
 * unlock could not be reached from a phone at all.
 */
export function Header({ 
  appMode, 
  setAppMode, 
  rightSidebarOpen,
  setRightSidebarOpen,
  setShowRoadClosures,
  alertsCount,
  gisOffline,
  admin
}) {
  const isExplore = appMode === "EXPLORE";

  const handleModeChange = (e) => {
    const selectedValue = e.target.value;
    setAppMode(selectedValue);
  };

  return (
    <div className="bg-slate-950 text-white px-2 py-2 lg:p-3 shadow-md z-[1100] flex justify-between items-center gap-2 border-b border-slate-800 h-16 relative select-none flex-shrink-0">
        {/* Left Side: Brand Logo */}
        <div className="flex items-center gap-4 min-w-0">
          <div className="flex items-center gap-3 min-w-0">
            <h1 className="text-lg font-bold tracking-wider flex items-center gap-1.5 select-none uppercase whitespace-nowrap">
              CFR <span className="text-emerald-500 font-extrabold">DISPATCH</span>
              <span className="hidden lg:inline text-slate-500 font-normal text-[10px] uppercase tracking-widest ml-1.5 border-l border-slate-800 pl-2 font-mono">
                {(() => {
                  const defaultHallId = import.meta.env.VITE_DEFAULT_HALL || "1";
                  const configStn = STATIONS_LIST.find(s => s.id === defaultHallId) || STATIONS_LIST[0];
                  const configStnName = configStn ? configStn.name.split(" Fire Hall")[0] : `HALL ${defaultHallId}`;
                  return `${configStnName} (Hall ${defaultHallId})`;
                })()}
              </span>
            </h1>
            
            {gisOffline && (
              <span
                className="bg-rose-500/10 text-rose-400 border border-rose-500/20 text-[9px] font-mono font-bold px-2 py-0.5 rounded flex items-center gap-1.5 select-none motion-safe:animate-pulse whitespace-nowrap"
                title="Coquitlam GIS offline"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                <span className="hidden sm:inline">COQUITLAM GIS OFFLINE</span>
                <span className="sm:hidden">GIS OFFLINE</span>
              </span>
            )}
          </div>
        </div>

        {/* Center: Mode Select Dropdown. Two entries, Explore and (unlocked) Admin; on a
            phone it is shown only while it has somewhere to go. */}
        <div className={`${admin?.unlocked ? 'flex' : 'hidden lg:flex'} items-center min-w-0`}>
          <div className="relative min-w-0">
            <select 
              value={isExplore ? "EXPLORE" : appMode} 
              onChange={handleModeChange}
              className="bg-slate-900 border border-slate-700 hover:border-slate-650 text-white rounded-lg pl-3 pr-8 py-1.5 touch:py-2.5 text-xs font-bold focus:outline-none focus:border-sky-500 cursor-pointer shadow-sm appearance-none min-w-0 max-w-[44vw] lg:max-w-none lg:min-w-[220px] truncate"
              style={{ 
                backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>")`, 
                backgroundPosition: 'right 8px center', 
                backgroundRepeat: 'no-repeat', 
                backgroundSize: '14px' 
              }}
            >
              <option value="EXPLORE">🧭 Notifications / Explore</option>
              {/* Admin controls show only while the padlock is unlocked (operator, 2026-09-08). */}
              {admin?.unlocked && <option value="ADMIN_DISPATCHES">🛡️ ADMIN: DISPATCH REVIEW</option>}
            </select>
          </div>
        </div>

        {/* Right Side: Alerts & Mobile Setup Triggers */}
        <div className="flex gap-2 lg:gap-3 items-center flex-shrink-0">
          <button
            onClick={() => setAppMode("DRIVER_SETUP")}
            className="hidden lg:flex px-3 py-1.5 touch:py-2.5 text-xs font-black rounded-lg border bg-amber-500/20 border-amber-500/40 text-amber-300 hover:bg-amber-500/30 hover:border-amber-500/60 transition-all items-center gap-1.5 cursor-pointer shadow-md"
            title="Open the QR pairing screen for phone push alerts"
          >
            📱 MOBILE SETUP
          </button>

          {/* Right Sidebar Hazards & Alerts Panel Toggle */}
          <button 
            onClick={() => {
              setRightSidebarOpen(!rightSidebarOpen);
              if (setShowRoadClosures) setShowRoadClosures(true);
            }}
            className={`px-3 py-1.5 touch:py-2.5 text-xs font-bold rounded-lg border transition-all flex items-center gap-1.5 cursor-pointer whitespace-nowrap ${
              rightSidebarOpen 
                ? "bg-amber-950/80 border-amber-600/80 text-amber-300 shadow-md motion-safe:animate-pulse" 
                : "bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700 hover:text-white"
            }`}
            title="Toggle Road Closures Panel"
            aria-label="Toggle road closures panel"
          >
            🚧 <span className="hidden lg:inline">ROAD CLOSURES</span> {alertsCount > 0 && <span className="bg-amber-500 text-slate-950 text-[9px] font-black px-1.5 py-0.2 rounded-full ml-1">{alertsCount}</span>}
          </button>

          {admin && <AdminLock admin={admin} />}
        </div>
    </div>
  );
}
