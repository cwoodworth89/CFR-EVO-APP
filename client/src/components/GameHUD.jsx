import React from 'react';
import { UNIT_COLORS } from './MapConstants';

export function Header({ 
  gameMode, 
  startMode, 
  mapStyle, 
  setMapStyle, 
  showLabels, 
  setShowLabels,
  leftSidebarOpen,
  setLeftSidebarOpen,
  rightSidebarOpen,
  setRightSidebarOpen,
  alertsCount
}) {
  const [showLayersMenu, setShowLayersMenu] = React.useState(false);
  const isExplore = gameMode === "EXPLORE";

  return (
    <div className="bg-slate-950 text-white p-3 shadow-md z-20 flex justify-between items-center border-b border-slate-800 h-16 relative select-none">
        {/* Left Side: Brand Logo and Sidebar Toggles */}
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
            className={`p-2 rounded-lg border text-xs font-bold transition-all ${
              leftSidebarOpen 
                ? "bg-slate-800 border-slate-700 text-sky-400" 
                : "bg-slate-900 border-slate-800 text-slate-400 hover:text-white"
            }`}
            title="Toggle Left Control Panel"
          >
            📋 CONTROL PANEL
          </button>
          
          <h1 className="text-lg font-bold tracking-wider flex items-center gap-1.5 select-none">
            CFR <span className="text-emerald-500 font-extrabold">EVO</span>
            <span className="text-slate-500 font-normal text-[10px] uppercase tracking-widest ml-1.5 border-l border-slate-800 pl-2">APP</span>
          </h1>
        </div>

        {/* Center: Mode Select Dropdown */}
        <div className="flex items-center">
          <div className="relative">
            <select 
              value={isExplore ? "EXPLORE" : gameMode} 
              onChange={(e) => startMode(e.target.value)}
              className="bg-slate-900 border border-slate-700 hover:border-slate-650 text-white rounded-lg pl-3 pr-8 py-1.5 text-xs font-bold focus:outline-none focus:border-sky-500 cursor-pointer shadow-sm appearance-none min-w-[220px]"
              style={{ 
                backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>")`, 
                backgroundPosition: 'right 8px center', 
                backgroundRepeat: 'no-repeat', 
                backgroundSize: '14px' 
              }}
            >
              <option value="EXPLORE">🧭 EXPLORE / DRIVERS AID</option>
              <option value="QUIZ_ZONES">🎓 TRAINING: STATION ZONES</option>
              <option value="QUIZ_INTERSECTIONS">🎓 TRAINING: STREET INTERSECTIONS</option>
              <option value="QUIZ_BLOCKS">🎓 TRAINING: BLOCK RANGES</option>
              <option value="QUIZ_ADDRESSES">🎓 TRAINING: PARCEL ADDRESSES</option>
            </select>
          </div>
        </div>

        {/* Right Side: Options & Alerts Panel Trigger */}
        <div className="flex gap-3 items-center">
          {/* Map Options Button */}
          <div className="relative">
             <button 
                onClick={() => setShowLayersMenu(!showLayersMenu)}
                className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all flex items-center gap-1.5 ${
                  showLayersMenu 
                    ? "bg-slate-800 text-white border-slate-600 shadow-md" 
                    : "bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700 hover:text-white"
                }`}
             >
                ⚙️ MAP OPTIONS
             </button>
             
             {showLayersMenu && (
                <>
                  <div className="fixed inset-0 z-[1050]" onClick={() => setShowLayersMenu(false)} />
                  <div className="absolute right-0 mt-2 w-48 bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-2xl z-[1100] flex flex-col gap-3 animate-in fade-in slide-in-from-top-2 duration-150">
                     <div>
                       <div className="text-[8px] text-slate-500 font-extrabold uppercase tracking-wider mb-1 font-mono">Basemap Style</div>
                       <div className="flex bg-slate-950 rounded-lg p-0.5 border border-slate-855">
                         {['GREY', 'DARK'].map(style => (
                             <button 
                               key={style} 
                               onClick={() => { setMapStyle(style); setShowLayersMenu(false); }} 
                               className={`flex-1 py-1 text-[9px] font-black rounded transition-all ${
                                 mapStyle === style 
                                   ? "bg-slate-800 text-white shadow" 
                                   : "text-slate-500 hover:text-slate-300"
                               }`}
                             >
                               {style}
                             </button>
                         ))}
                       </div>
                     </div>
                     
                     <div className="border-t border-slate-850 pt-2">
                       <div className="flex justify-between items-center">
                          <span className="text-[9px] text-slate-400 font-extrabold uppercase tracking-wider font-mono">Street Labels</span>
                          <button 
                             onClick={() => { setShowLabels(!showLabels); setShowLayersMenu(false); }}
                             className={`px-2 py-0.5 rounded text-[8px] font-black border transition-all ${
                               showLabels 
                                 ? "bg-amber-500 text-black border-amber-600 shadow-sm" 
                                 : "bg-slate-950 text-slate-500 border-slate-850 hover:border-slate-700 hover:text-slate-400"
                             }`}
                          >
                             {showLabels ? "ON" : "OFF"}
                          </button>
                       </div>
                     </div>
                  </div>
                </>
             )}
          </div>

          {/* Right Sidebar Alerts Panel Toggle */}
          <button 
            onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all flex items-center gap-1.5 ${
              rightSidebarOpen 
                ? "bg-slate-800 border-slate-700 text-rose-400" 
                : "bg-slate-900 border-slate-800 text-slate-400 hover:text-white"
            }`}
            title="Toggle Alerts List"
          >
            🔔 ALERTS {alertsCount > 0 && <span className="bg-rose-500 text-white text-[9px] font-black px-1.5 py-0.2 rounded-full ml-1">{alertsCount}</span>}
          </button>
        </div>
    </div>
  );
}

export function LeftSidebar({ 
  leftSidebarOpen, 
  setLeftSidebarOpen, 
  gameMode, 
  // Explore layer toggles
  showZones, 
  setShowZones, 
  showHydrants, 
  setShowHydrants, 
  showRoadClosures, 
  setShowRoadClosures,
  // Road access filter toggles
  filterNoAccess,
  setFilterNoAccess,
  filterAccessOnly,
  setFilterAccessOnly,
  filterCaution,
  setFilterCaution,
  // Training HUD
  score,
  currentQuestion,
  feedback,
  distanceOff,
  clickedBlockData,
  onNext,
  onZoneGuess,
  map
}) {
  const isExplore = gameMode === "EXPLORE";

  return (
    <div className={`relative h-full transition-all duration-300 ease-in-out select-none ${leftSidebarOpen ? 'w-80' : 'w-0'}`}>
       {/* Sidebar Body Wrapper */}
       <div className={`absolute inset-y-0 left-0 w-80 h-full bg-slate-900 border-r border-slate-800 flex flex-col z-[1000] overflow-y-auto overflow-x-hidden ${!leftSidebarOpen && 'pointer-events-none'}`}>
          
          {/* Header Title */}
          <div className="bg-slate-950 p-4 border-b border-slate-800 text-center flex-shrink-0">
             {isExplore ? (
               <>
                 <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1">CFR EVO SYSTEM</div>
                 <div className="text-lg text-emerald-500 font-extrabold uppercase font-sans tracking-wide">MAP CONTROLS</div>
               </>
             ) : (
               <>
                 <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1">CFR EVO TRAINING</div>
                 <div className="text-lg text-sky-400 font-extrabold uppercase font-sans tracking-wide">ACTIVE SESSION</div>
               </>
             )}
          </div>

          {/* Controls / Information Area */}
          <div className="p-5 flex-grow flex flex-col gap-6 overflow-y-auto">
             {isExplore ? (
               <>
                 {/* 1. Time Filters */}
                 <div className="flex flex-col gap-2">
                    <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono border-b border-slate-850 pb-1.5">TIME FILTERS</h3>
                    <div className="flex flex-col gap-2.5 mt-1.5">
                       <label className="flex items-center gap-2.5 text-xs text-slate-350 cursor-pointer">
                          <input type="checkbox" checked readOnly className="rounded border-slate-800 bg-slate-950 text-emerald-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" />
                          <span>Now / Active Alerts</span>
                       </label>
                       <label className="flex items-center gap-2.5 text-xs text-slate-500 cursor-not-allowed">
                          <input type="checkbox" disabled className="rounded border-slate-900 bg-slate-950 text-slate-700 w-4 h-4" />
                          <span>Next 7 Days (Planned)</span>
                       </label>
                       <label className="flex items-center gap-2.5 text-xs text-slate-500 cursor-not-allowed">
                          <input type="checkbox" disabled className="rounded border-slate-900 bg-slate-950 text-slate-700 w-4 h-4" />
                          <span>Next 30 Days (Future)</span>
                       </label>
                    </div>
                 </div>

                 {/* 2. Map Overlays / Layers */}
                 <div className="flex flex-col gap-2">
                    <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono border-b border-slate-850 pb-1.5">MAP LAYERS</h3>
                    <div className="flex flex-col gap-2.5 mt-1.5">
                       <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                          <input 
                             type="checkbox" 
                             checked={showRoadClosures} 
                             onChange={(e) => setShowRoadClosures(e.target.checked)} 
                             className="rounded border-slate-800 bg-slate-950 text-rose-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                          />
                          <span className="flex items-center gap-1.5">🚧 Road Closures</span>
                       </label>
                       <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                          <input 
                             type="checkbox" 
                             checked={showHydrants} 
                             onChange={(e) => setShowHydrants(e.target.checked)} 
                             className="rounded border-slate-800 bg-slate-950 text-emerald-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                          />
                          <span className="flex items-center gap-1.5">💧 Fire Hydrants</span>
                       </label>
                       <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
                          <input 
                             type="checkbox" 
                             checked={showZones} 
                             onChange={(e) => setShowZones(e.target.checked)} 
                             className="rounded border-slate-800 bg-slate-950 text-sky-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                          />
                          <span className="flex items-center gap-1.5">📐 Station Boundaries</span>
                       </label>
                    </div>
                 </div>

                 {/* 3. Access Level Filter (Enabled only when Road Closures are toggled) */}
                 <div className={`flex flex-col gap-2 transition-all duration-300 ${!showRoadClosures && 'opacity-35 pointer-events-none'}`}>
                    <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono border-b border-slate-850 pb-1.5">ROAD EMERGENCY ACCESS</h3>
                    <div className="flex flex-col gap-2.5 mt-1.5">
                       <label className="flex items-center gap-2.5 text-xs text-slate-350 cursor-pointer">
                          <input 
                             type="checkbox" 
                             checked={filterNoAccess} 
                             onChange={(e) => setFilterNoAccess(e.target.checked)} 
                             className="rounded border-slate-850 bg-slate-950 text-red-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                          />
                          <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block"></span>No Emergency Access</span>
                       </label>
                       <label className="flex items-center gap-2.5 text-xs text-slate-350 cursor-pointer">
                          <input 
                             type="checkbox" 
                             checked={filterAccessOnly} 
                             onChange={(e) => setFilterAccessOnly(e.target.checked)} 
                             className="rounded border-slate-850 bg-slate-950 text-amber-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                          />
                          <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block"></span>Emergency Access Only</span>
                       </label>
                       <label className="flex items-center gap-2.5 text-xs text-slate-350 cursor-pointer">
                          <input 
                             type="checkbox" 
                             checked={filterCaution} 
                             onChange={(e) => setFilterCaution(e.target.checked)} 
                             className="rounded border-slate-850 bg-slate-950 text-yellow-500 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer" 
                          />
                          <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-yellow-500 inline-block"></span>Passable with Caution</span>
                       </label>
                    </div>
                 </div>

                 {/* 4. Legend Section */}
                 <div className="flex flex-col gap-2 mt-auto border-t border-slate-850 pt-4">
                    <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-wider font-mono mb-2">MAP LEGEND</h3>
                    <div className="flex flex-col gap-3 font-mono text-[9px] text-slate-400">
                       <div className="flex items-center gap-2.5">
                          <div className="w-6 border-b-2 border-dashed border-red-500"></div>
                          <span>No Emergency Access Road</span>
                       </div>
                       <div className="flex items-center gap-2.5">
                          <div className="w-6 border-b-2 border-dashed border-amber-500"></div>
                          <span>Emergency Access Only Road</span>
                       </div>
                       <div className="flex items-center gap-2.5">
                          <div className="w-6 border-b-2 border-dashed border-yellow-500"></div>
                          <span>Passable with Caution Road</span>
                       </div>
                       <div className="flex items-center gap-2.5">
                          <div className="w-4 h-4 rounded-full bg-slate-900 border border-slate-750 flex items-center justify-center text-[8px] font-bold text-sky-400">💧</div>
                          <span>City Fire Hydrant Overlay</span>
                       </div>
                       <div className="flex items-center gap-2.5">
                          <div className="w-4 h-4 rounded-full bg-white border-2 border-red-500 flex items-center justify-center text-[8px]">🚒</div>
                          <span>Coquitlam Fire Hall</span>
                       </div>
                    </div>
                 </div>
               </>
             ) : (
               <>
                 {/* Quiz Details Panel */}
                 <div className="flex flex-col gap-4 text-center">
                    {gameMode === "QUIZ_ZONES" && currentQuestion && (
                      <div className="bg-slate-950 p-4 border border-slate-850 rounded-xl">
                        <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest">Target Boundary</div>
                        <div className="text-3xl text-sky-400 font-extrabold mt-1">Zone {currentQuestion.zone_id}</div>
                      </div>
                    )}
                    {gameMode === "QUIZ_INTERSECTIONS" && currentQuestion && (
                      <div className="bg-slate-950 p-4 border border-slate-850 rounded-xl text-left">
                        <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1 text-center">Locate Intersection</div>
                        <div className="text-sm text-white font-black text-center mt-1 leading-snug">{currentQuestion.name}</div>
                      </div>
                    )}
                    {gameMode === "QUIZ_BLOCKS" && currentQuestion && (
                      <div className="bg-slate-950 p-4 border border-slate-850 rounded-xl">
                        <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest">Target Block Range</div>
                        <div className="text-3xl text-amber-500 font-black mt-1">{currentQuestion.block}</div>
                        <div className="text-sm text-white font-bold mt-1 font-mono">{currentQuestion.street}</div>
                      </div>
                    )}
                    {gameMode === "QUIZ_ADDRESSES" && currentQuestion && (
                      <div className="bg-slate-950 p-4 border border-slate-850 rounded-xl text-left">
                        <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1 text-center">Find Target Address</div>
                        <div className="text-base text-white font-black text-center mt-1 leading-snug">{currentQuestion.address}</div>
                      </div>
                    )}
                 </div>

                 {/* Active Option Inputs / Buttons */}
                 <div className="flex-grow flex flex-col justify-center gap-3">
                    {gameMode === "QUIZ_ZONES" && (
                        <div className="flex flex-col gap-2">
                            {Object.keys(UNIT_COLORS).filter(u => u !== "UNKNOWN").map((unit) => (
                                <button 
                                  key={unit} 
                                  onClick={() => onZoneGuess(unit)} 
                                  disabled={feedback !== null} 
                                  className={`w-full py-3 px-4 rounded-xl font-bold text-left flex justify-between items-center transition-all border-l-4 shadow-sm ${
                                    feedback === "WRONG" && unit === currentQuestion.unit_id 
                                      ? "bg-green-600 text-white border-green-300" 
                                      : "bg-slate-950 border-slate-850 text-slate-300 hover:bg-slate-800 hover:text-white"
                                  }`}
                                >
                                    <span>{unit} Response</span>
                                    <span 
                                      className="w-3 h-3 rounded-full" 
                                      style={{ backgroundColor: UNIT_COLORS[unit] }}
                                    ></span>
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Score Watermark */}
                    <div className="mt-4 text-center">
                       <span className="text-slate-500 text-[10px] font-mono uppercase tracking-wider">Session Score</span>
                       <div className="text-2xl font-black text-white font-mono mt-0.5">{score} pts</div>
                    </div>
                 </div>

                 {/* Response Feedback Details */}
                 {feedback ? (
                     <div className="text-center bg-slate-950 p-4 border border-slate-850 rounded-xl animate-in fade-in">
                         <div className={`text-3xl font-extrabold mb-1.5 ${
                           feedback === "PERFECT" || feedback === "CORRECT" 
                             ? "text-emerald-400" 
                             : "text-rose-400"
                         }`}>
                             {feedback === "PERFECT" || feedback === "CORRECT" ? "PERFECT!" : "WRONG"}
                         </div>
                         
                         {feedback !== "PERFECT" && feedback !== "CORRECT" && (
                            <div className="text-xs text-slate-400 font-mono mt-1">
                               Error Distance: <span className="text-white font-bold">{distanceOff}m</span>
                            </div>
                         )}

                         {gameMode === "QUIZ_BLOCKS" && feedback === "WRONG" && clickedBlockData && (
                             <div className="text-rose-400 font-semibold text-xs mt-1 border-t border-slate-900 pt-1.5">
                               Selected: {clickedBlockData.block} {clickedBlockData.street}
                             </div>
                         )}

                         <button 
                           onClick={onNext} 
                           className="bg-emerald-500 hover:bg-emerald-400 text-black font-extrabold py-3 px-6 rounded-xl w-full shadow-lg mt-4 transition-all"
                         >
                           NEXT &rarr;
                         </button>
                     </div>
                 ) : (
                     <div className="text-center text-slate-500 text-[10px] italic border-t border-slate-850/50 pt-4">
                         {gameMode === "QUIZ_INTERSECTIONS" && "Tap matching intersection point on the map..."}
                         {gameMode === "QUIZ_BLOCKS" && "Click correct highlighted road segment..."}
                         {gameMode === "QUIZ_ADDRESSES" && "Zoom in and tap correct parcel boundary..."}
                     </div>
                 )}

                 {/* ZOOM UTILITIES */}
                 {gameMode === "QUIZ_ADDRESSES" && !feedback && currentQuestion && (
                     <button 
                       onClick={() => map.setView([currentQuestion.lat, currentQuestion.lng], 20, { animate: true })} 
                       className="bg-slate-950 hover:bg-slate-850 text-[10px] text-white font-bold py-2.5 px-4 rounded-lg w-full border border-slate-800 flex items-center justify-center gap-1.5 transition-all mt-auto"
                     >
                       🔍 ZOOM TO PARCEL
                     </button>
                 )}
               </>
             )}
          </div>
       </div>

       {/* Floating Toggle Tab */}
       <button 
         onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
         className="absolute top-1/2 -translate-y-1/2 -right-6 z-[1010] bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white rounded-r-lg w-6 h-16 flex items-center justify-center shadow-2xl border border-l-0 border-slate-800 cursor-pointer select-none transition-all duration-300"
         title={leftSidebarOpen ? "Collapse Control Panel" : "Expand Control Panel"}
       >
         <span className="text-[10px] font-black">{leftSidebarOpen ? "◀" : "▶"}</span>
       </button>
    </div>
  );
}

export function RightSidebar({ 
  rightSidebarOpen, 
  setRightSidebarOpen, 
  gameMode, 
  roadClosures, 
  showRoadClosures, 
  filterNoAccess,
  filterAccessOnly,
  filterCaution,
  map 
}) {
  const isExplore = gameMode === "EXPLORE";
  if (!isExplore) return null; // Only render right sidebar alerts in Explore/Information Mode

  // Filter closures to match active filters
  const filteredClosures = roadClosures.filter(closure => {
    if (closure.emergencyAccess === "NO_ACCESS" && !filterNoAccess) return false;
    if (closure.emergencyAccess === "ACCESS_ONLY" && !filterAccessOnly) return false;
    if (closure.emergencyAccess === "CAUTION" && !filterCaution) return false;
    return true;
  });

  return (
    <div className={`relative h-full transition-all duration-300 ease-in-out select-none ${rightSidebarOpen ? 'w-80' : 'w-0'}`}>
       {/* Sidebar Body Wrapper */}
       <div className={`absolute inset-y-0 right-0 w-80 h-full bg-slate-900 border-l border-slate-800 flex flex-col z-[1000] overflow-y-auto overflow-x-hidden ${!rightSidebarOpen && 'pointer-events-none'}`}>
          
          {/* Header Title */}
          <div className="bg-slate-950 p-4 border-b border-slate-800 text-center flex-shrink-0">
             <div className="text-slate-500 text-[10px] uppercase font-mono tracking-widest mb-1">CFR EVO ALERTS</div>
             <div className="text-lg text-rose-500 font-extrabold uppercase font-sans tracking-wide">ACTIVE HAZARDS</div>
          </div>

          {/* Alerts Card List */}
          <div className="p-4 flex-grow overflow-y-auto">
             {showRoadClosures ? (
                 <div className="flex flex-col gap-2.5 max-h-[78vh] overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
                     <div className="text-slate-400 text-[10px] font-semibold mb-1 uppercase font-mono tracking-wider">Filtered Alerts ({filteredClosures.length})</div>
                     {filteredClosures.length > 0 ? (
                         filteredClosures.map((closure) => (
                             <div 
                               key={closure.id} 
                               onClick={() => {
                                 if (map) {
                                   map.flyTo(closure.coordinates, 16, { animate: true });
                                 }
                               }}
                               className="bg-slate-950 hover:bg-slate-850 border border-slate-850 hover:border-slate-750 text-left p-3.5 rounded-xl shadow-sm cursor-pointer transition-all flex flex-col gap-2 group relative overflow-hidden"
                             >
                                  {/* Access Badge Indicator */}
                                  <div className="flex justify-between items-center gap-1.5 flex-wrap">
                                      <span className={`px-1.5 py-0.5 rounded text-[8px] font-black tracking-wider ${
                                        closure.emergencyAccess === 'NO_ACCESS' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                                        closure.emergencyAccess === 'ACCESS_ONLY' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                                        'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                                      }`}>
                                        {closure.emergencyAccess === 'NO_ACCESS' ? 'NO EMERGENCY ACCESS' :
                                         closure.emergencyAccess === 'ACCESS_ONLY' ? 'EMERGENCY ACCESS ONLY' :
                                         'PASSABLE WITH CAUTION'}
                                      </span>
                                      <span className="text-[8px] text-slate-500 font-mono font-medium">{closure.source}</span>
                                  </div>
                                  
                                  <div>
                                     <h4 className="font-extrabold text-xs text-slate-200 leading-snug group-hover:text-white transition-colors">{closure.headline}</h4>
                                     <p className="text-[9px] text-slate-400 font-medium font-mono leading-none mt-1">{closure.street}</p>
                                  </div>
                                  <p className="text-[10px] text-slate-400 leading-relaxed border-t border-slate-900 pt-2">{closure.description}</p>
                             </div>
                         ))
                     ) : (
                         <div className="text-center py-12 text-slate-650 text-xs italic">
                            No matching alerts found.
                         </div>
                     )}
                 </div>
             ) : (
                 <div className="text-center py-16 text-slate-600 text-xs italic border border-dashed border-slate-850 rounded-xl p-4 mt-4">
                    Road Closures layer is disabled. Turn it on in the Control Panel to view active alerts.
                 </div>
             )}
          </div>
       </div>

       {/* Floating Toggle Tab */}
       <button 
         onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
         className="absolute top-1/2 -translate-y-1/2 -left-6 z-[1010] bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white rounded-l-lg w-6 h-16 flex items-center justify-center shadow-2xl border border-r-0 border-slate-800 cursor-pointer select-none transition-all duration-300"
         title={rightSidebarOpen ? "Collapse Alerts" : "Expand Alerts"}
       >
         <span className="text-[10px] font-black">{rightSidebarOpen ? "▶" : "◀"}</span>
       </button>
    </div>
  );
}