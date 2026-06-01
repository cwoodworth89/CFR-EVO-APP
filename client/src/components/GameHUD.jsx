import React from 'react';
import { UNIT_COLORS } from './MapConstants';

export function Header({ 
  gameMode, 
  score, 
  mapStyle, 
  setMapStyle, 
  startMode, 
  showLabels, 
  setShowLabels, 
  showHydrants, 
  setShowHydrants,
  showZones,
  setShowZones,
  showRoadClosures,
  setShowRoadClosures
}) {
  const [showLayersMenu, setShowLayersMenu] = React.useState(false);
  const isExplore = gameMode === "EXPLORE";

  return (
    <>
      <div className="bg-slate-950 text-white p-3 shadow-md z-20 flex justify-between items-center border-b border-slate-800 h-16 relative">
          {/* Rebranded App Logo */}
          <h1 className="text-lg font-bold tracking-wider flex items-center gap-1.5 select-none">
            CFR <span className="text-emerald-500 font-extrabold">EVO</span>
            <span className="text-slate-500 font-normal text-xs uppercase tracking-widest ml-1.5 border-l border-slate-800 pl-2">APP</span>
          </h1>

          {/* Center Mode Controls */}
          <div className="flex gap-4 items-center">
            {/* Segmented Mode Switcher */}
            <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-0.5 shadow-inner">
              <button 
                onClick={() => startMode("EXPLORE")} 
                className={`px-4 py-1.5 text-xs font-bold rounded-md transition-all ${
                  isExplore 
                    ? "bg-slate-800 text-white shadow-sm" 
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                🧭 EXPLORE
              </button>
              <button 
                onClick={() => {
                  if (isExplore) {
                    startMode("QUIZ_ZONES"); // Default quiz type
                  }
                }} 
                className={`px-4 py-1.5 text-xs font-bold rounded-md transition-all ${
                  !isExplore 
                    ? "bg-slate-800 text-white shadow-sm" 
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                🎓 TRAINING
              </button>
            </div>

            {/* Training Topic Dropdown Select Menu */}
            {!isExplore && (
              <div className="relative animate-in fade-in slide-in-from-left-2 duration-150">
                <select 
                  value={gameMode} 
                  onChange={(e) => startMode(e.target.value)}
                  className="bg-slate-900 border border-slate-700 hover:border-slate-600 text-white rounded-lg pl-3 pr-8 py-1.5 text-xs font-bold focus:outline-none focus:border-sky-500 cursor-pointer shadow-sm appearance-none"
                  style={{ 
                    backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>")`, 
                    backgroundPosition: 'right 8px center', 
                    backgroundRepeat: 'no-repeat', 
                    backgroundSize: '14px' 
                  }}
                >
                  <option value="QUIZ_ZONES">⚡ STATION ZONES</option>
                  <option value="QUIZ_INTERSECTIONS">📍 STREET INTERSECTIONS</option>
                  <option value="QUIZ_BLOCKS">🛣️ BLOCK RANGES</option>
                  <option value="QUIZ_ADDRESSES">🏠 PARCEL ADDRESSES</option>
                </select>
              </div>
            )}
          </div>

          <div className="flex gap-4 items-center">
            {/* Score HUD (Training only) */}
            {!isExplore && (
              <div className="font-mono text-xs text-slate-400 mr-2 border border-slate-800 px-3 py-1.5 rounded-lg bg-slate-900/40 select-none">
                SCORE: <span className="text-white font-bold text-sm">{score}</span>
              </div>
            )}

            {/* Unified Map Options Dropdown */}
            <div className="relative">
               <button 
                  onClick={() => setShowLayersMenu(!showLayersMenu)}
                  className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all flex items-center gap-1.5 select-none ${
                    showLayersMenu 
                      ? "bg-slate-800 text-white border-slate-600 shadow-md" 
                      : "bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700 hover:text-white"
                  }`}
               >
                  ⚙️ MAP OPTIONS
               </button>
               
               {showLayersMenu && (
                  <>
                    {/* Seamless Backdrop Click-out */}
                    <div className="fixed inset-0 z-[1050]" onClick={() => setShowLayersMenu(false)} />
                    
                    {/* Dropdown Options Card */}
                    <div className="absolute right-0 mt-2 w-52 bg-slate-900/98 backdrop-blur border border-slate-800 rounded-xl p-3.5 shadow-2xl z-[1100] flex flex-col gap-3.5 select-none animate-in fade-in slide-in-from-top-2 duration-150">
                       <div>
                         <div className="text-[9px] text-slate-500 font-extrabold uppercase tracking-wider mb-1.5 font-mono">Basemap Style</div>
                         <div className="flex bg-slate-950 rounded-lg p-0.5 border border-slate-850">
                           {['GREY', 'DARK'].map(style => (
                               <button 
                                 key={style} 
                                 onClick={() => { setMapStyle(style); setShowLayersMenu(false); }} 
                                 className={`flex-1 py-1 text-[10px] font-black rounded-md transition-all ${
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
                       
                       <div className="border-t border-slate-850 pt-2.5">
                         <div className="flex justify-between items-center">
                            <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider font-mono">Street Labels</span>
                            <button 
                               onClick={() => { setShowLabels(!showLabels); setShowLayersMenu(false); }}
                               className={`px-2.5 py-1 rounded-md text-[9px] font-black border transition-all ${
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
          </div>
      </div>

      {/* Secondary Explore Sub-Toolbar (Fades down when in Explore mode) */}
      {isExplore && (
        <div className="bg-slate-900/95 backdrop-blur border-b border-slate-850 py-2 px-4 flex justify-center items-center gap-3 z-10 shadow-inner select-none animate-in slide-in-from-top duration-200">
           <span className="text-[9px] font-mono text-slate-500 uppercase tracking-widest mr-2 font-bold">Explore Layers:</span>
           
           {/* ZONES pill */}
           <button 
              onClick={() => setShowZones(!showZones)}
              className={`px-3 py-1 rounded-full text-[10px] font-black border transition-all shadow-sm ${
                showZones 
                  ? "bg-sky-500/20 text-sky-400 border-sky-500/40 shadow-sky-500/5" 
                  : "bg-slate-950 text-slate-500 border-slate-850 hover:border-slate-700 hover:text-slate-400"
              }`}
           >
              ZONES
           </button>

           {/* HYDRANTS pill */}
           <button 
              onClick={() => setShowHydrants(!showHydrants)}
              className={`px-3 py-1 rounded-full text-[10px] font-black border transition-all shadow-sm ${
                showHydrants 
                  ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-emerald-500/5" 
                  : "bg-slate-950 text-slate-500 border-slate-850 hover:border-slate-700 hover:text-slate-400"
              }`}
           >
              HYDRANTS
           </button>

           {/* ROAD CLOSURES pill */}
           <button 
              onClick={() => setShowRoadClosures(!showRoadClosures)}
              className={`px-3 py-1 rounded-full text-[10px] font-black border transition-all shadow-sm ${
                showRoadClosures 
                  ? "bg-rose-500/20 text-rose-400 border-rose-500/40 shadow-rose-500/5" 
                  : "bg-slate-950 text-slate-500 border-slate-850 hover:border-slate-700 hover:text-slate-400"
              }`}
           >
              ROAD CLOSURES
           </button>
        </div>
      )}
    </>
  );
}

export function Sidebar({ gameMode, currentQuestion, feedback, distanceOff, clickedBlockData, onNext, onZoneGuess, map, roadClosures, showRoadClosures }) {
    if (!currentQuestion && !(gameMode === "EXPLORE" && showRoadClosures)) return null;

    return (
        <div className="absolute top-4 right-4 z-[1000] w-72 bg-slate-900/95 backdrop-blur border border-slate-700 shadow-2xl rounded-xl overflow-hidden flex flex-col pointer-events-auto">
            
            {/* HEADER */}
            <div className="bg-slate-800 p-4 border-b border-slate-700 text-center">
                {gameMode === "EXPLORE" && showRoadClosures && (
                  <>
                    <div className="text-slate-500 text-[10px] uppercase font-bold tracking-widest mb-1">REAL-TIME TRAFFIC</div>
                    <div className="text-lg text-rose-500 font-bold leading-tight uppercase font-sans tracking-wide">CFR EVO ALERTS</div>
                  </>
                )}
                {gameMode === "QUIZ_ZONES" && currentQuestion && (
                  <>
                    <h2 className="text-slate-500 text-[10px] uppercase font-bold">CFR EVO</h2>
                    <div className="text-3xl text-white font-bold">Zone {currentQuestion.zone_id}</div>
                  </>
                )}
                {gameMode === "QUIZ_INTERSECTIONS" && currentQuestion && (
                  <>
                    <div className="text-slate-500 text-[10px] uppercase font-bold">LOCATE</div>
                    <div className="text-xl text-white font-bold">{currentQuestion.name}</div>
                  </>
                )}
                {gameMode === "QUIZ_BLOCKS" && currentQuestion && (
                  <>
                    <div className="text-slate-500 text-[10px] uppercase font-bold">FIND THE BLOCK</div>
                    <div className="text-3xl text-amber-500 font-bold leading-tight">{currentQuestion.block}</div>
                    <div className="text-lg text-white font-bold">{currentQuestion.street}</div>
                  </>
                )}
                {gameMode === "QUIZ_ADDRESSES" && currentQuestion && (
                  <>
                    <div className="text-slate-500 text-[10px] uppercase font-bold tracking-widest mb-1">FIND ADDRESS</div>
                    <div className="text-xl text-white font-bold leading-tight">{currentQuestion.address}</div>
                  </>
                )}
            </div>

            {/* CONTENT AREA */}
            <div className="p-4">
                {/* ROAD CLOSURES PANEL */}
                {gameMode === "EXPLORE" && showRoadClosures && (
                    <div className="flex flex-col gap-2 max-h-[60vh] overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
                        <div className="text-slate-400 text-xs font-semibold mb-1 uppercase font-mono tracking-wider">Active Alerts ({roadClosures ? roadClosures.length : 0})</div>
                        {roadClosures && roadClosures.length > 0 ? (
                            roadClosures.map((closure) => (
                                <div 
                                  key={closure.id} 
                                  onClick={() => {
                                    if (map) {
                                      map.flyTo(closure.coordinates, 16, { animate: true });
                                    }
                                  }}
                                  className="bg-slate-850 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-left p-3 rounded-lg shadow-sm cursor-pointer transition-all flex flex-col gap-1.5 group"
                                >
                                     <div className="flex justify-between items-center gap-1.5">
                                         <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold tracking-wider ${
                                           closure.severity === 'MAJOR' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                                           closure.severity === 'MODERATE' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                                           'bg-slate-800/60 text-slate-300 border border-slate-700/30'
                                         }`}>{closure.severity}</span>
                                         <span className="text-[9px] text-slate-500 font-mono font-medium tracking-wide">{closure.source}</span>
                                     </div>
                                     <h4 className="font-bold text-xs text-amber-500 leading-snug group-hover:text-amber-400 transition-colors">{closure.headline}</h4>
                                     <p className="text-[10px] text-slate-300 font-medium font-mono leading-none">{closure.street}</p>
                                     <p className="text-[10px] text-slate-400 leading-relaxed mt-0.5">{closure.description}</p>
                                </div>
                            ))
                        ) : (
                            <div className="text-center py-8 text-slate-600 text-xs italic">
                               Loading real-time feeds...
                            </div>
                        )}
                    </div>
                )}

                {/* ZONE BUTTONS */}
                {gameMode === "QUIZ_ZONES" && (
                    <div className="flex flex-col gap-2">
                        {Object.keys(UNIT_COLORS).filter(u => u !== "UNKNOWN").map((unit) => (
                            <button 
                              key={unit} 
                              onClick={() => onZoneGuess(unit)} 
                              disabled={feedback !== null} 
                              className={`w-full py-3 px-4 rounded-lg font-bold text-left flex justify-between items-center transition-all border-l-4 ${
                                feedback === "WRONG" && unit === currentQuestion.unit_id 
                                  ? "bg-green-600 text-white border-green-300 shadow-inner" 
                                  : "bg-slate-800 text-slate-300 border-transparent hover:bg-slate-700 hover:text-white"
                              }`}
                            >
                                <span>{unit}</span>
                                <span 
                                  className="w-3 h-3 rounded-full shadow-sm" 
                                  style={{ backgroundColor: UNIT_COLORS[unit] }}
                                ></span>
                            </button>
                        ))}
                    </div>
                )}

                {/* FEEDBACK & NEXT BUTTON */}
                {feedback ? (
                    <div className="text-center animate-in fade-in">
                        <div className={`text-4xl font-bold mb-2 ${
                          feedback === "PERFECT" || feedback === "CORRECT" 
                            ? "text-green-400" 
                            : "text-slate-300"
                        }`}>
                            {feedback === "PERFECT" || feedback === "CORRECT" 
                              ? "PERFECT!" 
                              : <span className="text-2xl">OFF BY <span className="text-white">{distanceOff}m</span></span>
                            }
                        </div>
                        
                        {/* Show Picked Block if Wrong */}
                        {gameMode === "QUIZ_BLOCKS" && feedback === "WRONG" && clickedBlockData && (
                            <div className="text-red-400 font-bold text-sm mb-4">
                              Picked: {clickedBlockData.block} {clickedBlockData.street}
                            </div>
                        )}

                        <button 
                          onClick={onNext} 
                          className="bg-sky-600 hover:bg-sky-500 text-white font-bold py-3 px-6 rounded-lg w-full shadow-lg mt-4"
                        >
                          NEXT &rarr;
                        </button>
                    </div>
                ) : (
                    <div className="text-center text-slate-500 text-xs italic">
                        {gameMode === "QUIZ_INTERSECTIONS" && "Tap the intersection..."}
                        {gameMode === "QUIZ_BLOCKS" && "Click the road segment..."}
                        {gameMode === "QUIZ_ADDRESSES" && "Zoom in & find the house..."}
                    </div>
                )}

                {/* ZOOM BUTTON (Address Mode) */}
                {gameMode === "QUIZ_ADDRESSES" && !feedback && (
                    <button 
                      onClick={() => map.setView([currentQuestion.lat, currentQuestion.lng], 20, { animate: true })} 
                      className="mt-4 bg-slate-700 hover:bg-slate-600 text-xs text-white py-2 px-4 rounded w-full border border-slate-500"
                    >
                      🔍 ZOOM TO PARCEL
                    </button>
                )}
            </div>
        </div>
    );
}